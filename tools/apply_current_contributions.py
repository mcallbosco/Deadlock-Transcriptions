#!/usr/bin/env python3
"""Apply uniquely matched Stage 1 current corrections for human review.

The command validates the complete operation before writing. It only accepts
`candidate_manual` records from the pinned audit, targets non-official revisions
by both mirrored path and audio SHA-256, and never runs Git staging or commit
commands.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from audit_legacy_contributions import AuditError, git, normalize_text, valid_sha256
from transcript_schema import revision_group_identity, revisions_for_hash


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"Could not read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"Expected a JSON object in {path}.")
    return value


def require_clean_transcripts(repo: Path, pinned_target: str, target_prefix: str) -> None:
    checks = [
        ("pinned target", ["git", "-C", str(repo), "diff", "--quiet", pinned_target, "HEAD", "--", target_prefix]),
        ("unstaged transcript tree", ["git", "-C", str(repo), "diff", "--quiet", "--", target_prefix]),
        ("staged transcript tree", ["git", "-C", str(repo), "diff", "--cached", "--quiet", "--", target_prefix]),
    ]
    for label, command in checks:
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode == 1:
            raise AuditError(f"The {label} differs; refusing to apply corrections.")
        if result.returncode:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise AuditError(f"Could not validate the {label}: {stderr}")


def candidate_action(record: dict[str, Any]) -> dict[str, Any]:
    matches = [
        value
        for value in record.get("targetMatches", [])
        if value.get("source") != "official"
        and value.get("proposedAction") in {"mark_manual", "replace_text_and_mark_manual"}
    ]
    if len(matches) != 1:
        raise AuditError(
            f"Candidate {record.get('legacyPath')} has {len(matches)} mutable revision matches; expected one."
        )
    return matches[0]


def plan_changes(repo: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    if report.get("mode") != "audit-only":
        raise AuditError("The input is not a current-contribution audit report.")
    policy = report.get("policy", {})
    if policy.get("officialRevisionsMutable") is not False:
        raise AuditError("The audit report does not explicitly protect official revisions.")
    if policy.get("uniqueNonOfficialRevisionRequired") is not True:
        raise AuditError("The audit report predates the unique-revision safety rule.")

    target_prefix = str(report["target"]["prefix"]).strip("/")
    candidates = [record for record in report.get("records", []) if record.get("status") == "candidate_manual"]
    selected_ids: set[tuple[str, tuple[str, ...]]] = set()
    documents: dict[Path, dict[str, Any]] = {}
    original_official: dict[Path, list[dict[str, Any]]] = {}
    changes: list[dict[str, Any]] = []

    for record in candidates:
        match = candidate_action(record)
        relative = Path(*str(match["path"]).split("/"))
        path = (repo / relative).resolve()
        protected_root = (repo / target_prefix).resolve()
        try:
            path.relative_to(protected_root)
        except ValueError as exc:
            raise AuditError(f"Target is outside {protected_root}: {path}") from exc
        document = documents.setdefault(path, read_json(path))
        original_official.setdefault(
            path,
            copy.deepcopy(
                [value for value in document.get("revisions", []) if value.get("source") == "official"]
            ),
        )
        revisions = document.get("revisions")
        if not isinstance(revisions, list):
            raise AuditError(f"Target has no revisions array: {path}")
        sha256 = match.get("sha256")
        if not valid_sha256(sha256):
            raise AuditError(f"Candidate has no addressable audio SHA-256: {match.get('path')}")
        identity = (str(match["path"]), str(sha256))
        found = revisions_for_hash(document, sha256)
        if len(found) != 1:
            raise AuditError(f"Expected one revision with SHA-256 {sha256} in {path}; found {len(found)}.")
        revision = found[0]
        group_identity = revision_group_identity(str(match["path"]), revision)
        if group_identity in selected_ids:
            raise AuditError(f"Multiple candidates target the same transcript group: {group_identity}")
        selected_ids.add(group_identity)
        if revision.get("source") == "official":
            raise AuditError(f"Refusing to modify official revision {identity}.")

        action = match["proposedAction"]
        expected = record["currentFullText"] if action == "mark_manual" else record["beforeFullText"]
        if normalize_text(revision.get("text")) != normalize_text(expected):
            raise AuditError(f"Pinned text no longer matches for {identity}.")
        before = copy.deepcopy(revision)
        revision["text"] = record["currentFullText"]
        revision["source"] = "manual"
        revision.pop("model", None)
        changes.append(
            {
                "path": path,
                "relativePath": match["path"],
                "sha256": sha256,
                "legacyCommit": record["legacyCommit"],
                "author": record["author"],
                "action": action,
                "before": before,
                "after": copy.deepcopy(revision),
            }
        )

    for path, document in documents.items():
        after_official = [
            value for value in document.get("revisions", []) if value.get("source") == "official"
        ]
        if after_official != original_official[path]:
            raise AuditError(f"Official revision changed in memory: {path}")
    return changes


def apply_changes(changes: list[dict[str, Any]]) -> None:
    documents: dict[Path, dict[str, Any]] = {}
    for change in changes:
        path = change["path"]
        if path not in documents:
            documents[path] = read_json(path)
        revisions = documents[path]["revisions"]
        found = revisions_for_hash(documents[path], change["sha256"])
        if len(found) != 1 or found[0].get("source") == "official":
            raise AuditError(f"Target changed between planning and writing: {path}@{change['sha256']}")
        found[0].clear()
        found[0].update(change["after"])
    for path in sorted(documents):
        path.write_text(
            json.dumps(documents[path], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply uniquely matched current corrections.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audit", type=Path, default=Path("migration-reports/manual-contribution-audit.json")
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write transcript changes. Without this flag, validate and print a dry run.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        audit_path = args.audit if args.audit.is_absolute() else repo / args.audit
        report = read_json(audit_path)
        target_prefix = str(report.get("target", {}).get("prefix", "transcripts")).strip("/")
        require_clean_transcripts(repo, str(report["target"]["commit"]), target_prefix)
        changes = plan_changes(repo, report)
        if args.apply:
            apply_changes(changes)
        actions = Counter(value["action"] for value in changes)
        authors = Counter((value["author"]["name"], value["author"]["email"]) for value in changes)
        print(f"{'Applied' if args.apply else 'Validated'} {len(changes)} current corrections.")
        print(json.dumps({"actions": dict(sorted(actions.items())), "authors": len(authors)}, indent=2))
        if not args.apply:
            print("Dry run only; pass --apply to write transcript files.")
        return 0
    except (AuditError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
