#!/usr/bin/env python3
"""Apply latest-version correction candidates without staging or committing them."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from audit_legacy_contributions import AuditError, git, valid_sha256
from apply_current_contributions import read_json, require_clean_transcripts


def plan_changes(repo: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    if report.get("mode") != "latest-version-audit-only":
        raise AuditError("The input is not a latest-version contribution audit.")
    policy = report.get("policy", {})
    if policy.get("officialRevisionsMutable") is not False:
        raise AuditError("The report does not explicitly protect official revisions.")
    if policy.get("latestManifestHashRequired") is not True:
        raise AuditError("The report does not require a version-manifest hash.")
    if policy.get("divergentLatestTextMayAutoApply") is not False:
        raise AuditError("The report permits divergent latest text; refusing to apply it.")

    target_prefix = str(report["target"]["prefix"]).strip("/")
    candidates = [
        value for value in report.get("records", []) if value.get("status") == "candidate_latest_manual"
    ]
    selected: set[tuple[str, str]] = set()
    documents: dict[Path, dict[str, Any]] = {}
    official_before: dict[Path, list[dict[str, Any]]] = {}
    changes: list[dict[str, Any]] = []

    for record in candidates:
        target = record["selectedTarget"]
        path = (repo / Path(*target["path"].split("/"))).resolve()
        protected_root = (repo / target_prefix).resolve()
        try:
            path.relative_to(protected_root)
        except ValueError as exc:
            raise AuditError(f"Target is outside {protected_root}: {path}") from exc
        sha256 = target.get("sha256")
        if not valid_sha256(sha256):
            raise AuditError(f"Candidate has no valid latest SHA-256: {target.get('path')}")
        identity = (target["path"], sha256)
        if identity in selected:
            raise AuditError(f"Multiple corrections target the same latest revision: {identity}")
        selected.add(identity)

        document = documents.setdefault(path, read_json(path))
        official_before.setdefault(
            path,
            copy.deepcopy(
                [value for value in document.get("revisions", []) if value.get("source") == "official"]
            ),
        )
        revisions = [
            value for value in document.get("revisions", []) if value.get("sha256") == sha256
        ]
        if len(revisions) != 1:
            raise AuditError(f"Expected one latest revision {identity}; found {len(revisions)}.")
        revision = revisions[0]
        if revision.get("source") == "official":
            raise AuditError(f"Refusing to modify official revision {identity}.")
        if revision.get("source") != target.get("source") or revision.get("text") != target.get(
            "originalText"
        ):
            raise AuditError(f"Latest revision changed since the audit: {identity}")
        action = target.get("proposedAction")
        if action not in {"mark_manual", "replace_text_and_mark_manual"}:
            raise AuditError(f"Unsupported latest-version action for {identity}: {action}")
        before = copy.deepcopy(revision)
        revision["text"] = record["currentFullText"]
        revision["source"] = "manual"
        revision.pop("model", None)
        changes.append(
            {
                "path": path,
                "relativePath": target["path"],
                "sha256": sha256,
                "legacyCommit": record["legacyCommit"],
                "author": record["author"],
                "action": action,
                "before": before,
                "after": copy.deepcopy(revision),
            }
        )

    for path, document in documents.items():
        official_after = [
            value for value in document.get("revisions", []) if value.get("source") == "official"
        ]
        if official_after != official_before[path]:
            raise AuditError(f"Official revision changed in memory: {path}")
    return changes


def apply_changes(changes: list[dict[str, Any]]) -> None:
    documents: dict[Path, dict[str, Any]] = {}
    for change in changes:
        path = change["path"]
        document = documents.setdefault(path, read_json(path))
        revisions = [
            value
            for value in document.get("revisions", [])
            if value.get("sha256") == change["sha256"]
        ]
        if len(revisions) != 1 or revisions[0].get("source") == "official":
            raise AuditError(
                f"Target changed between planning and writing: {change['relativePath']}@{change['sha256']}"
            )
        revisions[0].clear()
        revisions[0].update(change["after"])
    for path in sorted(documents):
        path.write_text(
            json.dumps(documents[path], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply latest-version correction candidates.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("migration-reports/latest-version-current-contribution-audit.json"),
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        path = args.audit if args.audit.is_absolute() else repo / args.audit
        report = read_json(path)
        prefix = str(report.get("target", {}).get("prefix", "transcripts")).strip("/")
        require_clean_transcripts(repo, str(report["target"]["commit"]), prefix)
        changes = plan_changes(repo, report)
        if args.apply:
            apply_changes(changes)
        actions = Counter(value["action"] for value in changes)
        authors = Counter((value["author"]["name"], value["author"]["email"]) for value in changes)
        print(f"{'Applied' if args.apply else 'Validated'} {len(changes)} latest-version corrections.")
        print(json.dumps({"actions": dict(sorted(actions.items())), "authors": len(authors)}, indent=2))
        if not args.apply:
            print("Dry run only; pass --apply to write transcript files.")
        return 0
    except (AuditError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
