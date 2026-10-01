"""Restore reviewed historical hash links in authoritative official revisions."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.audit_phonetic_lineage_merges import canonical_json, load_inputs
from tools.content_sync import validate_repository
from tools.link_exact_official_transcripts import state


def plan_documents(
    documents: dict[str, dict[str, Any]], manifest: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Validate the complete reviewed plan before producing any file writes.

    Only explicitly approved inherited copies may change text. Destinations must
    already contain the unchanged official authority hash and official wording.
    Original file/hash memberships and all other revision metadata are retained.
    """
    if manifest.get("schemaVersion") != 1:
        raise ValueError("Unsupported backfill plan schema")
    excluded = set(manifest["unprovenHashesExcluded"]) | {
        row["sha256"] for row in manifest["excludedEntitySubstitutions"]
    }
    corrections = {}
    for row in manifest["corrections"]:
        digest = row["sha256"]
        if digest in corrections or digest in excluded:
            raise ValueError(f"Duplicate or excluded correction: {digest}")
        corrections[digest] = row
    occurrences: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for filename, document in documents.items():
        for revision in document["revisions"]:
            for digest in revision["sha256"]:
                occurrences[digest].append((filename, revision))

    additions: dict[tuple[str, str], set[str]] = defaultdict(set)
    targets: dict[str, str] = {}
    for group in manifest["groups"]:
        hashes = set(group["sha256"])
        if not hashes or hashes & excluded or not group["officialDestinations"]:
            raise ValueError("Empty, excluded, or destinationless backfill group")
        for digest in hashes:
            previous_target = targets.setdefault(digest, group["text"])
            if previous_target != group["text"]:
                raise ValueError(f"Conflicting group wording: {digest}")
            if not occurrences[digest]:
                raise ValueError(f"Missing reviewed recording: {digest}")
        for origin in group["officialDestinations"]:
            filename, digest = origin["filename"], origin["sha256"]
            if digest in excluded or origin["text"] != group["text"]:
                raise ValueError(f"Excluded or conflicting authority: {filename}")
            revisions = [rev for name, rev in occurrences[digest] if name == filename]
            if len(revisions) != 1 or revisions[0]["source"] != "official" or revisions[0]["text"] != group["text"]:
                raise ValueError(f"Official destination has drifted: {filename}: {digest}")
            # All existing hashes in a destination revision are also authoritative
            # members; preserve them and reject incompatible overlapping plans.
            for existing in revisions[0]["sha256"]:
                if existing in corrections and corrections[existing]["text"] != group["text"]:
                    raise ValueError(f"Conflicting destination member: {existing}")
            additions[filename, digest].update(hashes)

    if not corrections.keys() <= targets.keys():
        raise ValueError("Correction has no restored official link")
    for digest, text in targets.items():
        correction = corrections.get(digest)
        if correction and correction["text"] != text:
            raise ValueError(f"Correction disagrees with authority: {digest}")
        if correction:
            original_aliases = set(correction["filenames"])
            actual_aliases = {f for f, _ in occurrences[digest]}
            permitted_aliases = original_aliases | {
                filename for (filename, _authority), hashes in additions.items() if digest in hashes
            }
            if not original_aliases <= actual_aliases <= permitted_aliases:
                raise ValueError(f"Reviewed aliases have drifted: {digest}")
        allowed = {text, correction["previousText"]} if correction else {text}
        for filename, revision in occurrences[digest]:
            if revision["source"] != "official" or revision["text"] not in allowed:
                raise ValueError(f"Reviewed recording has drifted: {filename}: {digest}")

    changed = {}
    changed_occurrences = Counter()
    added_memberships = 0
    additions_by_file: dict[str, set[str]] = defaultdict(set)
    for (filename, _digest), hashes in additions.items():
        additions_by_file[filename].update(hashes)
    touched = set(additions_by_file)
    touched.update(filename for digest in corrections for filename, _ in occurrences[digest])
    for filename in sorted(touched):
        original = documents[filename]
        grouped: dict[str, dict[str, Any]] = {}
        for revision in original["revisions"]:
            extra = set()
            for digest in revision["sha256"]:
                extra.update(additions.get((filename, digest), set()))
            for digest in [*revision["sha256"], *sorted(extra - set(revision["sha256"]))]:
                updated_state = copy.deepcopy(state(revision))
                if digest in corrections:
                    updated_state["text"] = corrections[digest]["text"]
                key = json.dumps(updated_state, sort_keys=True)
                grouped.setdefault(key, {"sha256": [], **updated_state})["sha256"].append(digest)
        for revision in grouped.values():
            revision["sha256"] = sorted(set(revision["sha256"]))
        updated = {**copy.deepcopy(original), "revisions": list(grouped.values())}
        before = {digest: state(revision) for revision in original["revisions"] for digest in revision["sha256"]}
        counts = Counter(digest for revision in updated["revisions"] for digest in revision["sha256"])
        after = {digest: state(revision) for revision in updated["revisions"] for digest in revision["sha256"]}
        if any(count != 1 for count in counts.values()) or not before.keys() <= after.keys():
            raise ValueError(f"Invalid resulting hash membership: {filename}")
        if after.keys() - before.keys() != additions_by_file[filename] - before.keys():
            raise ValueError(f"Unexpected destination membership: {filename}")
        for digest, previous in before.items():
            expected = dict(previous)
            if digest in corrections:
                expected["text"] = corrections[digest]["text"]
            if after[digest] != expected:
                raise ValueError(f"Unrelated metadata or wording changed: {filename}: {digest}")
            if after[digest] != previous:
                changed_occurrences[corrections[digest]["kind"]] += 1
        # Keep the exact document on an idempotent rerun, including its ordering.
        if before == after:
            continue
        added_memberships += len(after.keys() - before.keys())
        changed[filename] = updated
    return changed, {
        "schemaVersion": 1,
        "baseCommit": manifest["baseCommit"],
        "statistics": {
            "reviewedGroups": len(manifest["groups"]),
            "approvedHistoricalCorrectionHashes": len(corrections),
            "approvedTypoHashes": sum(row["kind"] == "wording/spelling" for row in corrections.values()),
            "changedFiles": len(changed),
            "officialHashMembershipsAdded": added_memberships,
            "changedExistingOccurrencesByKind": dict(changed_occurrences),
            "entitySubstitutionHashesExcluded": len(manifest["excludedEntitySubstitutions"]),
            "unprovenHashesExcluded": len(manifest["unprovenHashesExcluded"]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.plan.read_text(encoding="utf-8"))
    documents, _correlations = load_inputs(args.repo, "deadlock")
    changed, report = plan_documents(documents, manifest)
    # Validate the full proposed dataset before writing any transcripts.
    proposed = {**documents, **changed}
    states: dict[str, dict[str, Any]] = {}
    for document in proposed.values():
        for revision in document["revisions"]:
            published_state = {"text": revision["text"], "official": revision["source"] == "official"}
            for digest in revision["sha256"]:
                if states.setdefault(digest, published_state) != published_state:
                    raise ValueError(f"Resulting recording aliases disagree: {digest}")
    if args.apply:
        for filename, document in changed.items():
            (args.repo / "transcripts" / f"{filename}.json").write_text(canonical_json(document), encoding="utf-8")
        validation = validate_repository(args.repo)
        if not validation.valid:
            raise ValueError(validation.errors)
        report["repositoryValidation"] = "passed"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(canonical_json(report), encoding="utf-8")
    print(canonical_json(report["statistics"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
