#!/usr/bin/env python3
"""Propagate fuzzy-merge official states to every alias of the same audio hash."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import compact_revisions, revision_hashes
except ModuleNotFoundError:  # Imported as tools.reconcile_fuzzy_official_aliases.
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import compact_revisions, revision_hashes


def official_targets(
    operations: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build one canonical official state for every hash touched by a merge."""
    targets: dict[str, dict[str, Any]] = {}
    for operation in operations:
        path = str(operation.get("path") or "")
        text = str(operation.get("officialText") or "")
        hashes = operation.get("resultingHashes")
        if not path or not text or not isinstance(hashes, list):
            raise ValueError("merge operation is missing path, official text, or hashes")
        for digest in hashes:
            if not isinstance(digest, str):
                raise ValueError("merge operation contains an invalid hash")
            previous = targets.get(digest)
            if previous is not None and previous["text"] != text:
                raise ValueError(
                    f"SHA-256 {digest} has conflicting official merge targets"
                )
            target = targets.setdefault(
                digest, {"text": text, "source": "official", "sourcePaths": []}
            )
            if path not in target["sourcePaths"]:
                target["sourcePaths"].append(path)
    for target in targets.values():
        target["sourcePaths"].sort()
    return targets


def _hashes(document: dict[str, Any]) -> Counter[str]:
    return Counter(
        digest
        for revision in document["revisions"]
        for digest in revision_hashes(revision)
    )


def reconcile_document(
    document: dict[str, Any], relative_path: str, targets: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Split only the hashes whose alias state must become official."""
    updated = copy.deepcopy(document)
    before_hashes = _hashes(updated)
    output: list[dict[str, Any]] = []
    reconciliations: list[dict[str, Any]] = []

    for revision in updated["revisions"]:
        hashes = revision_hashes(revision)
        replacements: dict[str, list[str]] = {}
        untouched: list[str] = []
        for digest in hashes:
            target = targets.get(digest)
            if (
                target is None
                or relative_path in target["sourcePaths"]
                or (
                    revision.get("source") == "official"
                    and str(revision.get("text") or "") == target["text"]
                )
            ):
                untouched.append(digest)
                continue
            replacements.setdefault(target["text"], []).append(digest)
            reconciliations.append(
                {
                    "path": relative_path,
                    "sha256": digest,
                    "previousText": str(revision.get("text") or ""),
                    "previousSource": str(revision.get("source") or ""),
                    "officialText": target["text"],
                    "sourcePaths": target["sourcePaths"],
                }
            )

        if untouched:
            preserved = copy.deepcopy(revision)
            preserved["sha256"] = sorted(untouched)
            output.append(preserved)
        for text, replacement_hashes in sorted(replacements.items()):
            output.append(
                {
                    "sha256": sorted(replacement_hashes),
                    "text": text,
                    "source": "official",
                }
            )

    updated["revisions"] = compact_revisions(output)
    after_hashes = _hashes(updated)
    if before_hashes != after_hashes:
        raise ValueError(f"{relative_path}: alias reconciliation changed the SHA-256 set")
    if any(count != 1 for count in after_hashes.values()):
        raise ValueError(f"{relative_path}: a SHA-256 appears in multiple resulting groups")
    return updated, reconciliations


def reconcile_repo(
    repo: Path, operations: Iterable[dict[str, Any]], *, apply: bool
) -> dict[str, Any]:
    targets = official_targets(operations)
    statistics: Counter[str] = Counter()
    reconciliations: list[dict[str, Any]] = []
    for path in sorted((repo / "transcripts").rglob("*.json")):
        original_text = path.read_text(encoding="utf-8-sig")
        document = json.loads(original_text)
        relative_path = path.relative_to(repo).as_posix()
        updated, document_reconciliations = reconcile_document(
            document, relative_path, targets
        )
        statistics["files"] += 1
        if document_reconciliations:
            statistics["changedFiles"] += 1
            statistics["reconciledOccurrences"] += len(document_reconciliations)
            reconciliations.extend(document_reconciliations)
            if apply:
                path.write_text(canonical_json(updated), encoding="utf-8")
    statistics["targetHashes"] = len(targets)
    statistics["reconciledHashes"] = len(
        {item["sha256"] for item in reconciliations}
    )
    return {
        "schemaVersion": 1,
        "applied": apply,
        "source": "fuzzy-generated-official merge operations",
        "statistics": dict(statistics),
        "reconciliations": reconciliations,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--merge-report",
        type=Path,
        default=Path("migration-reports/fuzzy-generated-official-merge.json"),
    )
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    report_path = args.merge_report
    if not report_path.is_absolute():
        report_path = repo / report_path
    merge_report = json.loads(report_path.read_text(encoding="utf-8"))
    operations = merge_report.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError(f"Merge report has no operations: {report_path}")
    report = reconcile_repo(repo, operations, apply=args.apply)
    if args.apply:
        output_path = repo / "migration-reports" / "fuzzy-official-alias-reconciliation.json"
        output_path.write_text(canonical_json(report), encoding="utf-8")
    print(canonical_json({"applied": args.apply, "statistics": report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
