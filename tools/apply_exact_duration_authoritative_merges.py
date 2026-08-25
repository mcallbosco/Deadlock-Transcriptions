#!/usr/bin/env python3
"""Merge generated hashes into exact-duration official or manual revisions.

The public manifests supply a filename, SHA-256 and duration for every audio
recording.  This applies only a deterministic subset of possible retranscode
matches: a generated hash must have an exactly equal manifest duration to one
and only one differently-texted authoritative (official or manual) revision in
the same transcript document.  It never merges two authoritative revisions.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from audit_duration_merge_candidates import ROOT_MANIFEST, load_manifest_audio, fetch_json, norm_filename
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import compact_revisions, revision_hashes
except ModuleNotFoundError:  # Imported as tools.apply_exact_duration_authoritative_merges.
    from tools.audit_duration_merge_candidates import ROOT_MANIFEST, load_manifest_audio, fetch_json, norm_filename
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import compact_revisions, revision_hashes


AUTHORITATIVE_SOURCES = {"official", "manual"}
MANUAL_CORRECTIONS = {
    "transcripts/atlas/ping/abrams_ping_warden_check_items_1.mp3.json": {
        "expectedTexts": {"Check out what Warden bought.", "Check out Wood Warden bought."},
        "text": "Check out what Warden bought.",
    },
    "transcripts/forge/ping/mcginnis_ping_wrecker_check_items.mp3.json": {
        "expectedTexts": {"Check out what Rekr bought.", "Check out what Record bought!"},
        "text": "Check out what Wrecker bought.",
    },
}


def hash_counts(document: dict[str, Any]) -> Counter[str]:
    return Counter(digest for revision in document["revisions"] for digest in revision_hashes(revision))


def exact_pairs(
    revisions: list[dict[str, Any]], durations: dict[str, set[int]]
) -> dict[str, set[int]]:
    """Map each eligible generated hash to its single authoritative revision index."""
    targets: dict[str, set[int]] = defaultdict(set)
    for source_index, source in enumerate(revisions):
        if source.get("source") != "generated":
            continue
        for target_index, target in enumerate(revisions):
            if target.get("source") not in AUTHORITATIVE_SOURCES:
                continue
            if source.get("text") == target.get("text"):
                continue
            for source_hash in revision_hashes(source):
                source_durations = durations.get(source_hash, set())
                if not source_durations:
                    continue
                for target_hash in revision_hashes(target):
                    if source_durations.intersection(durations.get(target_hash, set())):
                        targets[source_hash].add(target_index)
                        break
    return targets


def plan_authoritative_merges(
    document: dict[str, Any], relative_path: str, manifest_audio: dict[str, dict[str, set[int]]]
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    updated = copy.deepcopy(document)
    revisions = updated["revisions"]
    durations = manifest_audio.get(norm_filename(updated["filename"]), {})
    targets = exact_pairs(revisions, durations)
    selected = {digest: next(iter(indices)) for digest, indices in targets.items() if len(indices) == 1}
    ambiguous = sum(len(indices) > 1 for indices in targets.values())
    if not selected:
        return updated, [], ambiguous

    before = hash_counts(updated)
    moved_by_target: dict[int, list[str]] = defaultdict(list)
    for revision in revisions:
        retained = []
        for digest in revision_hashes(revision):
            target_index = selected.get(digest)
            if target_index is None:
                retained.append(digest)
            else:
                moved_by_target[target_index].append(digest)
        revision["sha256"] = retained
    for target_index, hashes in moved_by_target.items():
        revisions[target_index]["sha256"] = sorted(set(revision_hashes(revisions[target_index])).union(hashes))

    operations = [
        {
            "path": relative_path,
            "filename": updated["filename"],
            "targetSource": revisions[target_index]["source"],
            "targetText": revisions[target_index]["text"],
            "movedGeneratedHashes": sorted(hashes),
        }
        for target_index, hashes in sorted(moved_by_target.items())
    ]
    updated["revisions"] = compact_revisions(revision for revision in revisions if revision_hashes(revision))
    after = hash_counts(updated)
    if before != after or any(count != 1 for count in after.values()):
        raise ValueError(f"{relative_path}: merge changed or duplicated represented hashes")
    return updated, operations, ambiguous


def plan_manual_correction(document: dict[str, Any], relative_path: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    correction = MANUAL_CORRECTIONS.get(relative_path)
    if correction is None:
        return document, None
    updated = copy.deepcopy(document)
    matching = [
        revision for revision in updated["revisions"]
        if revision.get("source") == "manual" and revision.get("text") in correction["expectedTexts"]
    ]
    if {revision["text"] for revision in matching} != correction["expectedTexts"]:
        raise ValueError(f"{relative_path}: expected manual revisions were not found")
    before = hash_counts(updated)
    hashes = sorted({digest for revision in matching for digest in revision_hashes(revision)})
    updated["revisions"] = [revision for revision in updated["revisions"] if revision not in matching]
    updated["revisions"].append({"sha256": hashes, "text": correction["text"], "source": "manual"})
    updated["revisions"] = compact_revisions(updated["revisions"])
    after = hash_counts(updated)
    if before != after or any(count != 1 for count in after.values()):
        raise ValueError(f"{relative_path}: correction changed or duplicated represented hashes")
    return updated, {"path": relative_path, "text": correction["text"], "hashes": hashes}


def reconciliation_targets(report: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return the authoritative state selected for every touched hash."""
    targets: dict[str, dict[str, str]] = {}
    records = [
        {
            "text": item["targetText"],
            "source": item["targetSource"],
            "hashes": item["movedGeneratedHashes"],
        }
        for item in report.get("operations", [])
    ] + [
        {"text": item["text"], "source": "manual", "hashes": item["hashes"]}
        for item in report.get("manualCorrections", [])
    ]
    for record in records:
        for digest in record["hashes"]:
            target = {"text": record["text"], "source": record["source"]}
            previous = targets.setdefault(digest, target)
            if previous != target:
                raise ValueError(f"SHA-256 {digest} has conflicting selected authoritative states")
    return targets


def reconcile_document(
    document: dict[str, Any], relative_path: str, targets: dict[str, dict[str, str]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated = copy.deepcopy(document)
    before = hash_counts(updated)
    revisions: list[dict[str, Any]] = []
    reconciliations: list[dict[str, Any]] = []
    for revision in updated["revisions"]:
        retained: list[str] = []
        replacements: dict[tuple[str, str], list[str]] = defaultdict(list)
        for digest in revision_hashes(revision):
            target = targets.get(digest)
            if target is None or (
                revision.get("text") == target["text"] and revision.get("source") == target["source"]
            ):
                retained.append(digest)
                continue
            replacements[(target["text"], target["source"])].append(digest)
            reconciliations.append(
                {
                    "path": relative_path,
                    "sha256": digest,
                    "previousText": revision.get("text"),
                    "previousSource": revision.get("source"),
                    "authoritativeText": target["text"],
                    "authoritativeSource": target["source"],
                }
            )
        if retained:
            preserved = copy.deepcopy(revision)
            preserved["sha256"] = retained
            revisions.append(preserved)
        for (text, source), hashes in replacements.items():
            revisions.append({"sha256": hashes, "text": text, "source": source})
    updated["revisions"] = compact_revisions(revisions)
    after = hash_counts(updated)
    if before != after or any(count != 1 for count in after.values()):
        raise ValueError(f"{relative_path}: reconciliation changed or duplicated represented hashes")
    return updated, reconciliations


def reconcile_repo(repo: Path, report: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    targets = reconciliation_targets(report)
    reconciliations: list[dict[str, Any]] = []
    changed_files = 0
    for path in sorted((repo / "transcripts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        relative_path = path.relative_to(repo).as_posix()
        updated, document_reconciliations = reconcile_document(document, relative_path, targets)
        if document_reconciliations:
            changed_files += 1
            reconciliations.extend(document_reconciliations)
            if apply:
                path.write_text(canonical_json(updated), encoding="utf-8")
    return {
        "changedFiles": changed_files,
        "reconciledOccurrences": len(reconciliations),
        "reconciledHashes": len({item["sha256"] for item in reconciliations}),
        "reconciliations": reconciliations,
    }


def apply_repo(repo: Path, *, apply: bool, root_manifest_url: str) -> dict[str, Any]:
    root = fetch_json(root_manifest_url)
    manifest_audio, included_versions = load_manifest_audio(root)
    operations: list[dict[str, Any]] = []
    manual_corrections: list[dict[str, Any]] = []
    statistics: Counter[str] = Counter()
    for path in sorted((repo / "transcripts").rglob("*.json")):
        original = json.loads(path.read_text(encoding="utf-8-sig"))
        relative_path = path.relative_to(repo).as_posix()
        if original.get("schemaVersion") != 3:
            continue
        updated, correction = plan_manual_correction(original, relative_path)
        updated, document_operations, ambiguous = plan_authoritative_merges(updated, relative_path, manifest_audio)
        statistics["ambiguousGeneratedHashesSkipped"] += ambiguous
        operations.extend(document_operations)
        if correction:
            manual_corrections.append(correction)
        if correction or document_operations:
            statistics["changedFiles"] += 1
            if apply:
                path.write_text(canonical_json(updated), encoding="utf-8")
    statistics["authoritativeMergeOperations"] = len(operations)
    statistics["generatedHashesMerged"] = sum(len(item["movedGeneratedHashes"]) for item in operations)
    statistics["officialTargetOperations"] = sum(item["targetSource"] == "official" for item in operations)
    statistics["manualTargetOperations"] = sum(item["targetSource"] == "manual" for item in operations)
    report = {
        "schemaVersion": 1,
        "applied": apply,
        "rootManifestUrl": root_manifest_url,
        "excludedVersionIds": ["ognb-russian-voice-mod"],
        "includedVersionIds": included_versions,
        "selection": "generated hashes with an exact-duration, single authoritative target in the same filename",
        "statistics": dict(statistics),
        "manualCorrections": manual_corrections,
        "operations": operations,
    }
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--root-manifest-url", default=ROOT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    report_path = repo / "migration-reports" / "exact-duration-authoritative-merge.json"
    if args.reconcile:
        if not report_path.is_file():
            raise ValueError(f"No merge report to reconcile: {report_path}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["aliasReconciliation"] = reconcile_repo(repo, report, apply=args.apply)
    else:
        report = apply_repo(repo, apply=args.apply, root_manifest_url=args.root_manifest_url)
    if args.apply:
        report_path.write_text(canonical_json(report), encoding="utf-8")
    print(canonical_json({"applied": args.apply, "statistics": report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
