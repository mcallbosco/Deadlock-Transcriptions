#!/usr/bin/env python3
"""Apply explicitly approved transcript corrections from an OGNB review CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_COLUMNS = {
    "sha256",
    "current_transcript",
    "recommended_transcript",
    "decision",
    "needs_manual_review",
    "apply_recommended",
}


class ReviewError(ValueError):
    """Raised when the review cannot be applied without ambiguity."""


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def read_review(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ReviewError(f"Review CSV is missing columns: {sorted(missing)}")
        rows = list(reader)

    review: dict[str, dict[str, str]] = {}
    for number, row in enumerate(rows, 2):
        digest = row["sha256"]
        if not SHA256.fullmatch(digest):
            raise ReviewError(f"Row {number} has an invalid SHA-256: {digest!r}")
        if digest in review:
            raise ReviewError(f"Row {number} repeats SHA-256 {digest}")
        if row["apply_recommended"] not in {"true", "false"}:
            raise ReviewError(f"Row {number} has an invalid apply_recommended value")
        if row["needs_manual_review"] not in {"true", "false"}:
            raise ReviewError(f"Row {number} has an invalid needs_manual_review value")
        if row["apply_recommended"] == "true" and (
            row["needs_manual_review"] != "false" or row["decision"] == "manual_review"
        ):
            raise ReviewError(f"Row {number} selects an unresolved manual-review item")
        review[digest] = row
    return review


def plan_changes(
    transcripts: Path, review: dict[str, dict[str, str]]
) -> tuple[dict[Path, dict[str, Any]], dict[str, int]]:
    found: Counter[str] = Counter()
    changes: dict[Path, dict[str, Any]] = {}
    selected_groups: dict[tuple[Path, int], list[dict[str, str]]] = defaultdict(list)

    for path in sorted(transcripts.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for index, revision in enumerate(document.get("revisions", [])):
            matching = [review[digest] for digest in revision.get("sha256", []) if digest in review]
            for row in matching:
                found[row["sha256"]] += 1
                if revision.get("text") != row["current_transcript"]:
                    raise ReviewError(
                        f"{path}: {row['sha256']} no longer matches current_transcript"
                    )
                if row["apply_recommended"] == "true":
                    selected_groups[(path, index)].append(row)

    missing = sorted(set(review) - set(found))
    if missing:
        raise ReviewError(f"Review SHA-256 values not found in transcripts: {missing[:5]}")

    for (path, index), rows in selected_groups.items():
        recommendations = {row["recommended_transcript"] for row in rows}
        if len(recommendations) != 1:
            raise ReviewError(f"{path}: grouped hashes have conflicting recommendations")
        document = changes.setdefault(
            path, json.loads(path.read_text(encoding="utf-8"))
        )
        revision = document["revisions"][index]
        if revision.get("source") == "official":
            raise ReviewError(f"{path}: refusing to modify an official revision")
        if revision.get("source") != "generated":
            raise ReviewError(
                f"{path}: selected revision source is {revision.get('source')!r}, not generated"
            )
        revision["text"] = recommendations.pop()

    return changes, {
        "reviewRows": len(review),
        "approvedHashes": sum(
            row["apply_recommended"] == "true" for row in review.values()
        ),
        "unresolvedManualReviewHashes": sum(
            row["needs_manual_review"] == "true" for row in review.values()
        ),
        "duplicateFilenameAliases": sum(count - 1 for count in found.values()),
        "changedFiles": len(changes),
    }


def apply_review(
    transcripts: Path, review_path: Path, *, apply: bool
) -> dict[str, int]:
    review = read_review(review_path)
    changes, statistics = plan_changes(transcripts, review)
    if apply:
        for path, document in changes.items():
            path.write_text(canonical_json(document), encoding="utf-8")
    return statistics


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-reviewed-corrections", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.approve_reviewed_corrections:
        parser.error("--apply requires --approve-reviewed-corrections")
    try:
        repo = args.repo.resolve()
        statistics = apply_review(
            repo / "transcripts", args.review_csv.resolve(), apply=args.apply
        )
        print(json.dumps(statistics, indent=2))
        if not args.apply:
            print(
                "Dry run only; pass --apply --approve-reviewed-corrections to write files."
            )
        return 0
    except (OSError, json.JSONDecodeError, ReviewError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
