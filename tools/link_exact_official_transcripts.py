"""Link exact manual/generated equivalents into their official revision hashes."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.audit_phonetic_lineage_merges import build_lineages, canonical_json, load_inputs
from tools.content_sync import validate_repository
from tools.transcript_schema import transcript_match_key


def state(revision: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in revision.items() if key != "sha256"}


def plan_documents(
    documents: dict[str, dict[str, Any]], lineages: dict[str, list[str]]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Preserve original memberships and extend only existing official groups."""
    candidates: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    occurrences: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for filename, document in documents.items():
        for index, revision in enumerate(document["revisions"]):
            for digest in revision["sha256"]:
                occurrences[digest].append((filename, index))

    for filenames in lineages.values():
        officials: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for filename in filenames:
            for index, revision in enumerate(documents[filename]["revisions"]):
                if revision["source"] == "official" and revision["text"].strip():
                    officials[transcript_match_key(revision["text"])].append((filename, index))
        for filename in filenames:
            for index, revision in enumerate(documents[filename]["revisions"]):
                if revision["source"] not in {"manual", "generated"} or not revision["text"].strip():
                    continue
                origins = officials.get(transcript_match_key(revision["text"]), [])
                if not origins:
                    continue
                texts = {documents[name]["revisions"][i]["text"] for name, i in origins}
                if len(texts) != 1:
                    ambiguous.append({"filename": filename, "revisionIndex": index, "officialTexts": sorted(texts)})
                    continue
                candidates.append({
                    "filename": filename,
                    "revisionIndex": index,
                    "sha256": list(revision["sha256"]),
                    "previous": state(revision),
                    "officialText": next(iter(texts)),
                    "officialOrigins": origins,
                })

    proposed: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        for digest in candidate["sha256"]:
            proposed[digest].add(candidate["officialText"])
    blocked: set[str] = set()
    for digest, texts in proposed.items():
        if len(texts) != 1:
            blocked.add(digest)
            continue
        text = next(iter(texts))
        for filename, index in occurrences[digest]:
            revision = documents[filename]["revisions"][index]
            if revision["source"] == "official":
                if state(revision) != {"text": text, "source": "official"}:
                    blocked.add(digest)
            elif revision["source"] not in {"manual", "generated"} or transcript_match_key(revision["text"]) != transcript_match_key(text):
                blocked.add(digest)

    targets = {
        digest: {"text": next(iter(texts)), "source": "official"}
        for digest, texts in proposed.items() if digest not in blocked
    }
    additions: dict[tuple[str, int], set[str]] = defaultdict(set)
    operations = []
    for candidate in candidates:
        selected = sorted(set(candidate["sha256"]) & targets.keys())
        if not selected:
            continue
        for origin in candidate["officialOrigins"]:
            additions[tuple(origin)].update(selected)
        operations.append({**candidate, "sha256": selected})

    changed = {}
    added_memberships = 0
    changed_occurrences: Counter[str] = Counter()
    added_by_file: dict[str, set[str]] = defaultdict(set)
    for (filename, _index), digests in additions.items():
        added_by_file[filename].update(digests)
    for filename, original in documents.items():
        touched = any(
            (filename, index) in additions
            or revision["source"] in {"manual", "generated"} and any(digest in targets for digest in revision["sha256"])
            for index, revision in enumerate(original["revisions"])
        )
        if not touched:
            continue
        revisions = []
        for index, revision in enumerate(original["revisions"]):
            if revision["source"] == "official":
                updated = copy.deepcopy(revision)
                extra = additions.get((filename, index), set())
                added_memberships += len(extra - set(revision["sha256"]))
                updated["sha256"] = sorted(set(revision["sha256"]) | extra)
                revisions.append(updated)
                continue
            by_state: dict[str, dict[str, Any]] = {}
            for digest in revision["sha256"]:
                target = targets.get(digest, state(revision))
                key = json.dumps(target, sort_keys=True)
                by_state.setdefault(key, {"sha256": [], **copy.deepcopy(target)})["sha256"].append(digest)
                if target != state(revision):
                    changed_occurrences[revision["source"]] += 1
            revisions.extend(by_state.values())
        # Coalesce equal states locally, retaining official state and every hash.
        grouped: dict[str, dict[str, Any]] = {}
        for revision in revisions:
            key = json.dumps(state(revision), sort_keys=True)
            if key not in grouped:
                grouped[key] = copy.deepcopy(revision)
            else:
                grouped[key]["sha256"] = sorted(set(grouped[key]["sha256"]) | set(revision["sha256"]))
        updated = {**copy.deepcopy(original), "revisions": list(grouped.values())}
        before = {digest: state(revision) for revision in original["revisions"] for digest in revision["sha256"]}
        counts = Counter(digest for revision in updated["revisions"] for digest in revision["sha256"])
        after = {digest: state(revision) for revision in updated["revisions"] for digest in revision["sha256"]}
        if any(count != 1 for count in counts.values()) or not before.keys() <= after.keys():
            raise ValueError(f"Invalid hash membership after linking {filename}")
        expected_added = added_by_file.get(filename, set())
        if after.keys() - before.keys() != expected_added - before.keys():
            raise ValueError(f"Unexpected hash additions in {filename}")
        for digest, previous in before.items():
            expected = targets.get(digest, previous) if previous["source"] in {"manual", "generated"} else previous
            if after[digest] != expected:
                raise ValueError(f"Changed unrelated or official state in {filename}: {digest}")
        if updated != original:
            changed[filename] = updated
    return changed, {
        "schemaVersion": 1,
        "policy": "Exact case/punctuation/spacing equivalents within confirmed filename lineages; persist older hashes in existing official revisions and original files.",
        "statistics": {
            "transcriptFilesScanned": len(documents),
            "changedFiles": len(changed),
            "editableGroupsLinked": len(operations),
            "linkedRecordingHashes": len(targets),
            "officialHashMembershipsAdded": added_memberships,
            "changedExistingOccurrencesBySource": dict(changed_occurrences),
            "ambiguousGroupsSkipped": len(ambiguous),
            "conflictingHashesSkipped": len(blocked),
        },
        "ambiguous": ambiguous,
        "blockedHashes": sorted(blocked),
        "operations": operations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    documents, correlations = load_inputs(args.repo, "deadlock")
    changed, report = plan_documents(documents, build_lineages(documents, correlations))
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
