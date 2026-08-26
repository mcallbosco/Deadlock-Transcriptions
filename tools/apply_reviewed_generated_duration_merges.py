#!/usr/bin/env python3
"""Apply reviewed exact-duration generated/generated transcript decisions."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import compact_revisions, revision_hashes
except ModuleNotFoundError:  # Imported as tools.apply_reviewed_generated_duration_merges.
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import compact_revisions, revision_hashes


def load_review(review_dir: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    manifest = json.loads((review_dir / "manifest.json").read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    decisions: dict[str, dict[str, Any]] = {}
    for batch in manifest["batches"]:
        batch_number = int(batch["batch"])
        batch_items = json.loads(
            (review_dir / f"batch-{batch_number:02d}.json").read_text(encoding="utf-8")
        )["items"]
        decision_document = json.loads(
            (review_dir / f"decisions-{batch_number:02d}.json").read_text(encoding="utf-8")
        )
        if decision_document.get("batch") != batch_number:
            raise ValueError(f"Decision file has wrong batch number: {batch_number}")
        items.extend(batch_items)
        for decision in decision_document.get("decisions", []):
            item_id = decision.get("id")
            if not isinstance(item_id, str) or item_id in decisions:
                raise ValueError(f"Missing or duplicate decision ID in batch {batch_number}: {item_id}")
            decisions[item_id] = decision
    item_ids = {item["id"] for item in items}
    if len(item_ids) != len(items):
        raise ValueError("Review queue contains duplicate item IDs")
    missing = sorted(item_ids - decisions.keys())
    extra = sorted(decisions.keys() - item_ids)
    if missing or extra:
        raise ValueError(f"Decision coverage mismatch: {len(missing)} missing, {len(extra)} extra")
    return items, decisions


def selected_targets(
    items: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    targets: dict[str, dict[str, Any]] = {}
    reviewed: list[dict[str, Any]] = []
    statistics: Counter[str] = Counter()
    for item in items:
        decision = decisions[item["id"]]
        action = decision.get("action")
        confidence = decision.get("confidence")
        if confidence not in {"high", "medium", "low"}:
            raise ValueError(f"{item['id']}: invalid confidence {confidence}")
        statistics[f"{action}_{confidence}"] += 1
        if action == "review":
            reviewed.append(decision)
            continue
        if action != "choose":
            raise ValueError(f"{item['id']}: invalid action {action}")
        selected_index = decision.get("selectedRevisionIndex")
        selected_text = decision.get("selectedText")
        matching = [
            option
            for option in item["options"]
            if option["revisionIndex"] == selected_index and option["text"] == selected_text
        ]
        if len(matching) != 1:
            raise ValueError(f"{item['id']}: selected option does not exist exactly once")
        selected = matching[0]
        target = {
            "text": selected["text"],
            "source": "generated",
            "model": selected.get("model"),
            "itemId": item["id"],
        }
        for option in item["options"]:
            for digest in option["hashes"]:
                previous = targets.setdefault(digest, target)
                if (previous["text"], previous.get("model")) != (
                    target["text"],
                    target.get("model"),
                ):
                    raise ValueError(f"SHA-256 {digest} has conflicting reviewed targets")
    return targets, reviewed, statistics


def _hash_counts(document: dict[str, Any]) -> Counter[str]:
    return Counter(digest for revision in document["revisions"] for digest in revision_hashes(revision))


def apply_targets_to_document(
    document: dict[str, Any], relative_path: str, targets: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated = copy.deepcopy(document)
    before = _hash_counts(updated)
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for revision in updated["revisions"]:
        retained: list[str] = []
        replacements: dict[tuple[str, str | None], list[str]] = defaultdict(list)
        for digest in revision_hashes(revision):
            target = targets.get(digest)
            if target is None or (
                revision.get("source") == "generated"
                and revision.get("text") == target["text"]
                and revision.get("model") == target.get("model")
            ):
                retained.append(digest)
                continue
            replacements[(target["text"], target.get("model"))].append(digest)
            changes.append(
                {
                    "path": relative_path,
                    "sha256": digest,
                    "previousText": revision.get("text"),
                    "selectedText": target["text"],
                    "itemId": target["itemId"],
                }
            )
        if retained:
            preserved = copy.deepcopy(revision)
            preserved["sha256"] = sorted(retained)
            output.append(preserved)
        for (text, model), hashes in replacements.items():
            replacement: dict[str, Any] = {
                "sha256": sorted(hashes),
                "text": text,
                "source": "generated",
            }
            if model:
                replacement["model"] = model
            output.append(replacement)
    updated["revisions"] = compact_revisions(output)
    after = _hash_counts(updated)
    if before != after or any(count != 1 for count in after.values()):
        raise ValueError(f"{relative_path}: reviewed merge changed or duplicated hashes")
    return updated, changes


def apply_repo(
    repo: Path, targets: dict[str, dict[str, Any]], *, apply: bool
) -> tuple[list[dict[str, Any]], int]:
    changes: list[dict[str, Any]] = []
    changed_files = 0
    for path in sorted((repo / "transcripts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        relative_path = path.relative_to(repo).as_posix()
        updated, document_changes = apply_targets_to_document(document, relative_path, targets)
        if document_changes:
            changed_files += 1
            changes.extend(document_changes)
            if apply:
                path.write_text(canonical_json(updated), encoding="utf-8")
    return changes, changed_files


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--review-dir",
        type=Path,
        default=Path("migration-reports/generated-duration-review"),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    review_dir = args.review_dir if args.review_dir.is_absolute() else repo / args.review_dir
    items, decisions = load_review(review_dir)
    targets, reviewed, statistics = selected_targets(items, decisions)
    changes, changed_files = apply_repo(repo, targets, apply=args.apply)
    report = {
        "schemaVersion": 1,
        "applied": args.apply,
        "reviewItems": len(items),
        "statistics": {
            **dict(statistics),
            "selectedItems": sum(decision["action"] == "choose" for decision in decisions.values()),
            "heldForReviewItems": len(reviewed),
            "targetHashes": len(targets),
            "changedFiles": changed_files,
            "changedHashOccurrences": len(changes),
        },
        "heldForReview": reviewed,
        "changes": changes,
    }
    if args.apply:
        (review_dir / "apply-report.json").write_text(canonical_json(report), encoding="utf-8")
    print(canonical_json({"applied": args.apply, "statistics": report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
