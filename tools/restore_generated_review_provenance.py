#!/usr/bin/env python3
"""Restore generated provenance for agent-reviewed novel transcript corrections."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from apply_reviewed_generated_duration_merges import (
        load_review,
        reconcile_audit_objections,
        reconcile_target_conflicts,
        selected_targets,
    )
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import revision_hashes
except ModuleNotFoundError:  # Imported as tools.restore_generated_review_provenance.
    from tools.apply_reviewed_generated_duration_merges import (
        load_review,
        reconcile_audit_objections,
        reconcile_target_conflicts,
        selected_targets,
    )
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import revision_hashes


def git_output(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, encoding="utf-8"
    )


def documents_at_ref(
    repo: Path, ref: str, relative_paths: list[str]
) -> dict[str, dict[str, Any]]:
    requests = "".join(f"{ref}:{path}\n" for path in relative_paths).encode()
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=requests,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    documents: dict[str, dict[str, Any]] = {}
    offset = 0
    for relative_path in relative_paths:
        line_end = result.stdout.index(b"\n", offset)
        header = result.stdout[offset:line_end].decode()
        offset = line_end + 1
        if header.endswith(" missing"):
            continue
        _, object_type, size_text = header.rsplit(" ", 2)
        if object_type != "blob":
            raise ValueError(f"{ref}:{relative_path} is a {object_type}, not a blob")
        size = int(size_text)
        blob = result.stdout[offset : offset + size]
        offset += size + 1
        documents[relative_path] = json.loads(blob)
    return documents


def hash_provenance(document: dict[str, Any]) -> dict[str, tuple[str, str | None]]:
    result: dict[str, tuple[str, str | None]] = {}
    for revision in document["revisions"]:
        provenance = (revision["source"], revision.get("model"))
        for digest in revision_hashes(revision):
            previous = result.setdefault(digest, provenance)
            if previous != provenance:
                raise ValueError(f"SHA-256 {digest} has conflicting provenance in one document")
    return result


def restore_document(
    document: dict[str, Any],
    base_document: dict[str, Any],
    correction_targets: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], Counter[str]]:
    updated = copy.deepcopy(document)
    base = hash_provenance(base_document)
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    statistics: Counter[str] = Counter()

    for revision in updated["revisions"]:
        retained: list[str] = []
        restored: dict[str | None, list[str]] = defaultdict(list)
        for digest in revision_hashes(revision):
            target = correction_targets.get(digest)
            if target is None or revision.get("text") != target["text"]:
                retained.append(digest)
                continue
            base_source, base_model = base.get(digest, ("", None))
            if revision.get("source") != "manual":
                retained.append(digest)
                statistics["alreadyNonManual"] += 1
            elif base_source != "generated":
                retained.append(digest)
                statistics["baseAuthoritativeOrMissing"] += 1
            else:
                restored[base_model].append(digest)
                changes.append(
                    {
                        "sha256": digest,
                        "text": target["text"],
                        "restoredSource": "generated",
                        "restoredModel": base_model,
                        "itemId": target["itemId"],
                    }
                )

        if retained:
            preserved = copy.deepcopy(revision)
            preserved["sha256"] = sorted(retained)
            output.append(preserved)
        for model, hashes in restored.items():
            replacement: dict[str, Any] = {
                "sha256": sorted(hashes),
                "text": revision["text"],
                "source": "generated",
            }
            if model:
                replacement["model"] = model
            output.append(replacement)

    updated["revisions"] = output
    before = Counter(
        digest for revision in document["revisions"] for digest in revision_hashes(revision)
    )
    after = Counter(
        digest for revision in updated["revisions"] for digest in revision_hashes(revision)
    )
    if before != after or any(count != 1 for count in after.values()):
        raise ValueError("Provenance restoration changed or duplicated recording hashes")
    return updated, changes, statistics


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--review-dir",
        type=Path,
        default=Path("migration-reports/generated-duration-review-pass-2"),
    )
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    review_dir = args.review_dir if args.review_dir.is_absolute() else repo / args.review_dir
    items, decisions = load_review(review_dir)
    decisions, _ = reconcile_audit_objections(decisions, review_dir)
    decisions, _ = reconcile_target_conflicts(decisions, review_dir)
    targets, _, _ = selected_targets(items, decisions)
    corrected_item_ids = {
        item_id for item_id, decision in decisions.items() if decision["action"] == "correct"
    }
    correction_targets = {
        digest: target
        for digest, target in targets.items()
        if target["itemId"] in corrected_item_ids
    }

    changed_paths = [
        path
        for path in git_output(
            repo, "diff", "--name-only", args.base_ref, "HEAD", "--", "transcripts"
        ).splitlines()
        if path.endswith(".json")
    ]
    base_documents = documents_at_ref(repo, args.base_ref, changed_paths)
    all_changes: list[dict[str, Any]] = []
    statistics: Counter[str] = Counter()
    changed_files = 0
    for relative_path in changed_paths:
        base_document = base_documents.get(relative_path)
        if base_document is None:
            statistics["pathsMissingAtBase"] += 1
            continue
        path = repo / relative_path
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        updated, changes, document_statistics = restore_document(
            document, base_document, correction_targets
        )
        statistics.update(document_statistics)
        if not changes:
            continue
        changed_files += 1
        for change in changes:
            change["path"] = relative_path
        all_changes.extend(changes)
        if args.apply:
            path.write_text(canonical_json(updated), encoding="utf-8")

    report = {
        "schemaVersion": 1,
        "applied": args.apply,
        "baseRef": args.base_ref,
        "statistics": {
            "correctedItems": len(corrected_item_ids),
            "correctionTargetHashes": len(correction_targets),
            "candidatePaths": len(changed_paths),
            "changedFiles": changed_files,
            "restoredHashOccurrences": len(all_changes),
            **dict(statistics),
        },
        "changes": all_changes,
    }
    if args.apply:
        (review_dir / "generated-provenance-restoration.json").write_text(
            canonical_json(report), encoding="utf-8"
        )
    print(canonical_json({"applied": args.apply, "statistics": report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
