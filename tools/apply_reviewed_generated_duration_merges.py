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


def reconcile_audit_objections(
    decisions: dict[str, dict[str, Any]], review_dir: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    reconciled = copy.deepcopy(decisions)
    objections: list[dict[str, Any]] = []
    seen: dict[str, tuple[str, str | None]] = {}
    for path in sorted(review_dir.glob("audit-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        entries = payload.get("objections", []) if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            raise ValueError(f"{path}: expected an objection array")
        for entry in entries:
            item_id = entry.get("id")
            if not isinstance(item_id, str):
                raise ValueError(f"{path}: missing objection ID {item_id}")
            signature = (str(entry.get("recommendedAction")), entry.get("replacementText"))
            previous_signature = seen.setdefault(item_id, signature)
            if previous_signature != signature:
                raise ValueError(f"{path}: conflicting duplicate objection ID {item_id}")
            if previous_signature == signature and any(
                objection["id"] == item_id for objection in objections
            ):
                objections.append({**entry, "auditFile": path.name})
                continue
            decision = reconciled.get(item_id)
            if decision is None or decision.get("action") not in {"choose", "correct"}:
                raise ValueError(f"{path}: objection does not target a selected item: {item_id}")
            action = entry.get("recommendedAction")
            if action == "reject":
                decision.update(
                    {
                        "action": "review",
                        "selectedRevisionIndex": None,
                        "selectedText": None,
                        "confidence": "low",
                        "rationale": f"Cross-audit rejected selection: {entry.get('reason', '')}",
                    }
                )
            elif action == "replace":
                replacement = entry.get("replacementText")
                if not isinstance(replacement, str) or not replacement.strip():
                    raise ValueError(f"{path}: replacement text is missing for {item_id}")
                decision.update(
                    {
                        "action": "correct",
                        "selectedRevisionIndex": None,
                        "selectedText": replacement,
                        "confidence": "high",
                        "rationale": f"Cross-audit replacement: {entry.get('reason', '')}",
                    }
                )
            else:
                raise ValueError(f"{path}: invalid objection action {action}")
            objections.append({**entry, "auditFile": path.name})
    return reconciled, objections


def reconcile_target_conflicts(
    decisions: dict[str, dict[str, Any]], review_dir: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    path = review_dir / "target-conflict-resolutions.json"
    if not path.exists():
        return decisions, []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    groups = payload.get("groups", [])
    if not isinstance(groups, list):
        raise ValueError(f"{path}: expected a conflict-resolution group array")
    reconciled = copy.deepcopy(decisions)
    seen_items: set[str] = set()
    for group in groups:
        item_ids = group.get("itemIds")
        if not isinstance(item_ids, list) or not item_ids:
            raise ValueError(f"{path}: conflict group has no item IDs")
        if any(not isinstance(item_id, str) or item_id in seen_items for item_id in item_ids):
            raise ValueError(f"{path}: duplicate or invalid conflict item ID")
        seen_items.update(item_ids)
        action = group.get("action")
        for item_id in item_ids:
            decision = reconciled.get(item_id)
            if decision is None or decision.get("action") not in {"choose", "correct"}:
                raise ValueError(f"{path}: conflict resolution targets unselected item {item_id}")
            if action == "reject":
                decision.update(
                    {
                        "action": "review",
                        "selectedRevisionIndex": None,
                        "selectedText": None,
                        "confidence": "low",
                        "rationale": f"Shared-hash conflict rejected: {group.get('reason', '')}",
                    }
                )
            elif action == "resolve":
                text = group.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"{path}: resolved conflict has no text")
                decision.update(
                    {
                        "action": "correct",
                        "selectedRevisionIndex": None,
                        "selectedText": text,
                        "confidence": "high",
                        "rationale": f"Shared-hash conflict resolved: {group.get('reason', '')}",
                    }
                )
            else:
                raise ValueError(f"{path}: invalid conflict action {action}")
    return reconciled, groups


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
        if action == "correct":
            if decision.get("selectedRevisionIndex") is not None:
                raise ValueError(f"{item['id']}: corrected text must not select a revision")
            selected_text = decision.get("selectedText")
            if not isinstance(selected_text, str) or not selected_text.strip():
                raise ValueError(f"{item['id']}: corrected text is missing")
            for option in item["options"]:
                target = {
                    "text": selected_text,
                    "source": "generated",
                    "model": option.get("model"),
                    "itemId": item["id"],
                }
                for digest in option["hashes"]:
                    previous = targets.setdefault(digest, target)
                    if (previous["text"], previous["source"], previous.get("model")) != (
                        target["text"],
                        target["source"],
                        target.get("model"),
                    ):
                        raise ValueError(f"SHA-256 {digest} has conflicting reviewed targets")
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
                if (previous["text"], previous["source"], previous.get("model")) != (
                    target["text"],
                    target["source"],
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
        replacements: dict[tuple[str, str, str | None], list[str]] = defaultdict(list)
        for digest in revision_hashes(revision):
            target = targets.get(digest)
            if target is None or (
                revision.get("source") == target["source"]
                and revision.get("text") == target["text"]
                and revision.get("model") == target.get("model")
            ):
                retained.append(digest)
                continue
            replacements[(target["text"], target["source"], target.get("model"))].append(digest)
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
        for (text, source, model), hashes in replacements.items():
            replacement: dict[str, Any] = {
                "sha256": sorted(hashes),
                "text": text,
                "source": source,
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
    decisions, audit_objections = reconcile_audit_objections(decisions, review_dir)
    decisions, conflict_resolutions = reconcile_target_conflicts(decisions, review_dir)
    targets, reviewed, statistics = selected_targets(items, decisions)
    changes, changed_files = apply_repo(repo, targets, apply=args.apply)
    report = {
        "schemaVersion": 1,
        "applied": args.apply,
        "reviewItems": len(items),
        "statistics": {
            **dict(statistics),
            "selectedItems": sum(
                decision["action"] in {"choose", "correct"} for decision in decisions.values()
            ),
            "chosenItems": sum(decision["action"] == "choose" for decision in decisions.values()),
            "correctedItems": sum(
                decision["action"] == "correct" for decision in decisions.values()
            ),
            "heldForReviewItems": len(reviewed),
            "targetHashes": len(targets),
            "changedFiles": changed_files,
            "changedHashOccurrences": len(changes),
        },
        "heldForReview": reviewed,
        "auditObjections": audit_objections,
        "targetConflictResolutions": conflict_resolutions,
        "changes": changes,
    }
    if args.apply:
        (review_dir / "apply-report.json").write_text(canonical_json(report), encoding="utf-8")
    print(canonical_json({"applied": args.apply, "statistics": report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
