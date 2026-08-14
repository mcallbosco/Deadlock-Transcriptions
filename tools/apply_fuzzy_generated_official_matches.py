#!/usr/bin/env python3
"""Merge reviewed fuzzy generated/official groups while preserving exclusions."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from audit_fuzzy_transcript_matches import candidates_for_document, canonical_json
    from reconcile_fuzzy_official_aliases import reconcile_repo
    from transcript_schema import revision_hashes, transcript_match_key
except ModuleNotFoundError:  # Imported as tools.apply_fuzzy_generated_official_matches.
    from tools.audit_fuzzy_transcript_matches import candidates_for_document, canonical_json
    from tools.reconcile_fuzzy_official_aliases import reconcile_repo
    from tools.transcript_schema import revision_hashes, transcript_match_key


EXCLUDED_OFFICIAL_TERMS = {
    "archmother": "Archmother",
    "hiddenking": "Hidden King",
}


def excluded_official_terms(text: str) -> list[str]:
    key = transcript_match_key(text)
    return [label for term, label in EXCLUDED_OFFICIAL_TERMS.items() if term in key]


def _hashes(document: dict[str, Any]) -> Counter[str]:
    return Counter(
        digest
        for revision in document["revisions"]
        for digest in revision_hashes(revision)
    )


def _candidate_sides(
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    left = candidate["left"]
    right = candidate["right"]
    if left["source"] == "official" and right["source"] == "generated":
        return left, right
    if right["source"] == "official" and left["source"] == "generated":
        return right, left
    raise ValueError("candidate is not a generated/official pair")


def plan_document(
    document: dict[str, Any], relative_path: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the merged document, applied components, and excluded candidate pairs."""
    updated = copy.deepcopy(document)
    candidates, _statistics = candidates_for_document(updated, relative_path)
    selected = [
        candidate
        for candidate in candidates
        if candidate["sourcePair"] == ["generated", "official"]
    ]
    by_official: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    official_for_generated: dict[int, int] = {}
    exclusions: list[dict[str, Any]] = []

    for candidate in selected:
        official, generated = _candidate_sides(candidate)
        official_index = official["revisionIndex"]
        generated_index = generated["revisionIndex"]
        previous_official = official_for_generated.setdefault(generated_index, official_index)
        if previous_official != official_index:
            raise ValueError(
                f"{relative_path}: generated revision {generated_index} matches multiple official groups"
            )
        terms = excluded_official_terms(official["text"])
        if terms:
            exclusions.append(
                {
                    "path": relative_path,
                    "filename": candidate["filename"],
                    "confidence": candidate["confidence"],
                    "similarity": candidate["similarity"],
                    "matchedTerms": terms,
                    "official": official,
                    "generated": generated,
                }
            )
            continue
        by_official[official_index].append((candidate, generated))

    before_hashes = _hashes(updated)
    removed_indices: set[int] = set()
    operations: list[dict[str, Any]] = []
    revisions = updated["revisions"]
    for official_index, members in sorted(by_official.items()):
        official_revision = revisions[official_index]
        generated_indices = sorted(
            {generated["revisionIndex"] for _candidate, generated in members}
        )
        if official_revision.get("source") != "official":
            raise ValueError(f"{relative_path}: planned survivor is not official")
        merged_hashes = set(revision_hashes(official_revision))
        confidence_counts: Counter[str] = Counter()
        for candidate, generated in members:
            generated_revision = revisions[generated["revisionIndex"]]
            if generated_revision.get("source") != "generated":
                raise ValueError(f"{relative_path}: planned merge member is not generated")
            merged_hashes.update(revision_hashes(generated_revision))
            confidence_counts[candidate["confidence"]] += 1
        official_revision["sha256"] = sorted(merged_hashes)
        removed_indices.update(generated_indices)
        operations.append(
            {
                "path": relative_path,
                "filename": str(updated.get("filename") or ""),
                "officialRevisionIndex": official_index,
                "generatedRevisionIndices": generated_indices,
                "officialText": str(official_revision.get("text") or ""),
                "confidenceCounts": dict(confidence_counts),
                "resultingHashes": revision_hashes(official_revision),
            }
        )

    updated["revisions"] = [
        revision for index, revision in enumerate(revisions) if index not in removed_indices
    ]
    after_hashes = _hashes(updated)
    if before_hashes != after_hashes:
        raise ValueError(f"{relative_path}: merge changed the represented SHA-256 set")
    if any(count != 1 for count in after_hashes.values()):
        raise ValueError(f"{relative_path}: a SHA-256 appears in multiple resulting groups")
    return updated, operations, exclusions


def exclusion_markdown(report: dict[str, Any]) -> str:
    statistics = report["statistics"]
    lines = [
        "# Fuzzy generated/official exclusions",
        "",
        "These generated/official fuzzy candidates were deliberately not merged because",
        "the official text mentions **Hidden King** or **Archmother**.",
        "",
        "| Confidence | Excluded pairs |",
        "| --- | ---: |",
    ]
    for confidence in ("high", "medium", "low"):
        lines.append(
            f"| {confidence.title()} | {statistics['excludedByConfidence'].get(confidence, 0):,} |"
        )
    lines.extend(
        [
            "",
            f"Total: **{statistics['excludedCandidatePairs']:,} pairs** across "
            f"**{statistics['excludedFiles']:,} transcript files**.",
            "",
            "| Confidence | Similarity | Path | Terms | Official text | Generated text |",
            "| --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for exclusion in report["exclusions"]:
        def cell(value: object) -> str:
            return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")

        lines.append(
            "| {confidence} | {similarity:.2%} | `{path}` | {terms} | {official} | {generated} |".format(
                confidence=exclusion["confidence"].title(),
                similarity=exclusion["similarity"],
                path=cell(exclusion["path"]),
                terms=cell(", ".join(exclusion["matchedTerms"])),
                official=cell(exclusion["official"]["text"]),
                generated=cell(exclusion["generated"]["text"]),
            )
        )
    return "\n".join(lines) + "\n"


def apply_repo(repo: Path, *, apply: bool) -> dict[str, Any]:
    transcript_root = repo / "transcripts"
    statistics: Counter[str] = Counter()
    applied_by_confidence: Counter[str] = Counter()
    excluded_by_confidence: Counter[str] = Counter()
    operations: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []

    for path in sorted(transcript_root.rglob("*.json")):
        original_text = path.read_text(encoding="utf-8-sig")
        document = json.loads(original_text)
        relative_path = path.relative_to(repo).as_posix()
        updated, document_operations, document_exclusions = plan_document(
            document, relative_path
        )
        statistics["files"] += 1
        if document_operations:
            statistics["changedFiles"] += 1
        for operation in document_operations:
            statistics["officialGroupsRetained"] += 1
            count = len(operation["generatedRevisionIndices"])
            statistics["generatedGroupsMerged"] += count
            for confidence, confidence_count in operation["confidenceCounts"].items():
                applied_by_confidence[confidence] += confidence_count
        for exclusion in document_exclusions:
            excluded_by_confidence[exclusion["confidence"]] += 1
        operations.extend(document_operations)
        exclusions.extend(document_exclusions)
        if apply and document_operations:
            path.write_text(canonical_json(updated), encoding="utf-8")

    statistics["appliedCandidatePairs"] = sum(applied_by_confidence.values())
    statistics["excludedCandidatePairs"] = len(exclusions)
    statistics["excludedFiles"] = len({item["path"] for item in exclusions})
    report = {
        "schemaVersion": 1,
        "applied": apply,
        "selection": "all fuzzy generated/official candidates at or above 80% similarity",
        "sourcePriority": "official replaces generated",
        "excludedOfficialTerms": list(EXCLUDED_OFFICIAL_TERMS.values()),
        "statistics": {
            **dict(statistics),
            "appliedByConfidence": dict(applied_by_confidence),
            "excludedByConfidence": dict(excluded_by_confidence),
        },
        "operations": operations,
        "exclusions": exclusions,
    }
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    merge_report_path = repo / "migration-reports" / "fuzzy-generated-official-merge.json"
    previous_report = (
        json.loads(merge_report_path.read_text(encoding="utf-8"))
        if merge_report_path.is_file()
        else None
    )
    operations = []
    if isinstance(previous_report, dict) and isinstance(
        previous_report.get("operations"), list
    ):
        operations.extend(previous_report["operations"])
    alias_report_path = (
        repo / "migration-reports" / "fuzzy-official-alias-reconciliation.json"
    )
    previous_alias_report = (
        json.loads(alias_report_path.read_text(encoding="utf-8"))
        if alias_report_path.is_file()
        else None
    )
    reconciliations = []
    if isinstance(previous_alias_report, dict) and isinstance(
        previous_alias_report.get("reconciliations"), list
    ):
        reconciliations.extend(previous_alias_report["reconciliations"])

    exclusions: list[dict[str, Any]] = []
    iteration_summaries: list[dict[str, Any]] = []
    for iteration in range(1, 11):
        iteration_report = apply_repo(repo, apply=args.apply)
        new_operations = iteration_report["operations"]
        operations.extend(new_operations)
        exclusions = iteration_report["exclusions"]
        alias_iteration = reconcile_repo(repo, operations, apply=args.apply) if operations else {
            "schemaVersion": 1,
            "applied": args.apply,
            "statistics": {},
            "reconciliations": [],
        }
        reconciliations.extend(alias_iteration["reconciliations"])
        iteration_summaries.append(
            {
                "iteration": iteration,
                "mergedCandidatePairs": iteration_report["statistics"].get(
                    "appliedCandidatePairs", 0
                ),
                "reconciledAliasOccurrences": alias_iteration["statistics"].get(
                    "reconciledOccurrences", 0
                ),
            }
        )
        if not args.apply or (
            not new_operations and not alias_iteration["reconciliations"]
        ):
            break
    else:
        raise ValueError("fuzzy merge and alias reconciliation did not converge")

    applied_by_confidence: Counter[str] = Counter()
    for operation in operations:
        applied_by_confidence.update(operation.get("confidenceCounts", {}))
    excluded_by_confidence = Counter(
        exclusion["confidence"] for exclusion in exclusions
    )
    statistics = {
        "files": 98944,
        "changedFiles": len({operation["path"] for operation in operations}),
        "officialGroupsRetained": len(operations),
        "generatedGroupsMerged": sum(
            len(operation["generatedRevisionIndices"]) for operation in operations
        ),
        "appliedCandidatePairs": sum(applied_by_confidence.values()),
        "excludedCandidatePairs": len(exclusions),
        "excludedFiles": len({item["path"] for item in exclusions}),
        "appliedByConfidence": dict(applied_by_confidence),
        "excludedByConfidence": dict(excluded_by_confidence),
    }
    unique_reconciliations = {
        (item["path"], item["sha256"], item["officialText"]): item
        for item in reconciliations
    }
    reconciliations = [unique_reconciliations[key] for key in sorted(unique_reconciliations)]
    alias_statistics = {
        "files": 98944,
        "changedFiles": len({item["path"] for item in reconciliations}),
        "reconciledOccurrences": len(reconciliations),
        "targetHashes": len(
            {
                digest
                for operation in operations
                for digest in operation["resultingHashes"]
            }
        ),
        "reconciledHashes": len({item["sha256"] for item in reconciliations}),
    }
    alias_report = {
        "schemaVersion": 1,
        "applied": args.apply,
        "source": "fuzzy-generated-official merge operations",
        "statistics": alias_statistics,
        "reconciliations": reconciliations,
    }
    report = {
        "schemaVersion": 1,
        "applied": args.apply,
        "selection": "all fuzzy generated/official candidates at or above 80% similarity",
        "sourcePriority": "official replaces generated",
        "excludedOfficialTerms": list(EXCLUDED_OFFICIAL_TERMS.values()),
        "statistics": statistics,
        "iterations": iteration_summaries,
        "aliasReconciliation": alias_statistics,
        "operations": operations,
        "exclusions": exclusions,
    }
    if args.apply:
        report_root = repo / "migration-reports"
        merge_report_path.write_text(
            canonical_json(report), encoding="utf-8"
        )
        exclusion_report = {**report, "operations": []}
        (report_root / "fuzzy-generated-official-exclusions.json").write_text(
            canonical_json(exclusion_report), encoding="utf-8"
        )
        (report_root / "fuzzy-generated-official-exclusions.md").write_text(
            exclusion_markdown(report), encoding="utf-8"
        )
        alias_report_path.write_text(
            canonical_json(alias_report), encoding="utf-8"
        )
    print(
        canonical_json(
            {
                "applied": args.apply,
                "statistics": statistics,
                "aliasReconciliation": alias_statistics,
                "iterations": iteration_summaries,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
