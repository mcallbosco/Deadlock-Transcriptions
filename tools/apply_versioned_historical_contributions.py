#!/usr/bin/env python3
"""Apply audited historical corrections without staging or committing them."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from apply_current_contributions import read_json
from audit_legacy_contributions import AuditError, git, normalize_text, valid_sha256
from transcript_schema import revision_group_identity, revisions_for_hash


def require_clean_transcript_worktree(repo: Path, target_prefix: str) -> None:
    for label, arguments in (
        ("unstaged transcript tree", ("diff", "--quiet", "--", target_prefix)),
        ("staged transcript tree", ("diff", "--cached", "--quiet", "--", target_prefix)),
    ):
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments], capture_output=True, check=False
        )
        if result.returncode == 1:
            raise AuditError(f"The {label} differs; refusing to apply corrections.")
        if result.returncode:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise AuditError(f"Could not validate the {label}: {stderr}")


def attribution_events(record: dict[str, Any]) -> list[dict[str, Any]]:
    if record["status"] == "candidate_replay":
        return record["replayEvents"]
    if record["status"] == "candidate_mark_manual":
        return [record["attributionEvent"]]
    raise AuditError(f"Unsupported candidate status: {record.get('status')}")


def plan_changes(repo: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    if report.get("mode") != "versioned-historical-audit-only":
        raise AuditError("The input is not a versioned historical audit.")
    policy = report.get("policy", {})
    required = {
        "officialRevisionsMutable": False,
        "selectedReleaseRequired": True,
        "crossVersionReplayAllowed": False,
        "uniqueVersionHashRequired": True,
        "uniqueHistoryEpochRequired": True,
        "exactTextAnchorRequired": True,
        "fuzzyMatchingMayAutoApply": False,
    }
    for key, expected in required.items():
        if policy.get(key) is not expected:
            raise AuditError(f"The audit report has an unsafe or missing policy: {key}")
    if policy.get("eligibleTargetSources") != ["generated"]:
        raise AuditError("The audit report permits a non-generated target source.")

    target_prefix = str(report["target"]["prefix"]).strip("/")
    protected_root = (repo / target_prefix).resolve()
    candidates = [
        record
        for record in report.get("records", [])
        if record.get("status") in {"candidate_replay", "candidate_mark_manual"}
    ]
    selected: set[tuple[str, tuple[str, ...]]] = set()
    documents: dict[Path, dict[str, Any]] = {}
    official_before: dict[Path, list[dict[str, Any]]] = {}
    changes: list[dict[str, Any]] = []

    for record in candidates:
        target = record["selectedTarget"]
        relative = Path(*str(target["path"]).split("/"))
        path = (repo / relative).resolve()
        try:
            path.relative_to(protected_root)
        except ValueError as exc:
            raise AuditError(f"Target is outside {protected_root}: {path}") from exc
        sha256 = target.get("sha256")
        if not valid_sha256(sha256):
            raise AuditError(f"Candidate has no valid version SHA-256: {target.get('path')}")
        identity = (target["path"], sha256)
        document = documents.setdefault(path, read_json(path))
        official_before.setdefault(
            path,
            copy.deepcopy(
                [value for value in document.get("revisions", []) if value.get("source") == "official"]
            ),
        )
        revisions = revisions_for_hash(document, sha256)
        if len(revisions) != 1:
            raise AuditError(f"Expected one revision {identity}; found {len(revisions)}.")
        revision = revisions[0]
        group_identity = revision_group_identity(str(target["path"]), revision)
        if group_identity in selected:
            raise AuditError(f"Multiple candidates target the same transcript group: {group_identity}")
        selected.add(group_identity)
        if revision.get("source") == "official":
            raise AuditError(f"Refusing to modify official revision {identity}.")
        if revision.get("source") != "generated":
            raise AuditError(f"Revision is no longer generated: {identity}")
        if revision.get("text") != target.get("originalText"):
            raise AuditError(f"Revision text changed since the audit: {identity}")

        before = copy.deepcopy(revision)
        current_text = revision.get("text")
        events = attribution_events(record)
        if record["status"] == "candidate_replay":
            for event in events:
                if normalize_text(current_text) != normalize_text(event["beforeFullText"]):
                    raise AuditError(
                        f"Historical replay chain no longer matches {identity} at {event['legacyCommit']}."
                    )
                current_text = event["afterFullText"]
        else:
            current_text = record["finalText"]
            if normalize_text(revision.get("text")) != normalize_text(current_text):
                raise AuditError(f"Mark-manual text no longer matches for {identity}.")

        revision["text"] = current_text
        revision["source"] = "manual"
        revision.pop("model", None)
        changes.append(
            {
                "path": path,
                "relativePath": target["path"],
                "sha256": sha256,
                "epochId": record["epochId"],
                "action": target["proposedAction"],
                "attributionEvents": events,
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
        revisions = revisions_for_hash(document, change["sha256"])
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
    parser = argparse.ArgumentParser(
        description="Apply released-version historical correction candidates."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path(
            "migration-reports/six-hero-update-historical-contribution-audit.json"
        ),
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        audit_path = args.audit if args.audit.is_absolute() else repo / args.audit
        report = read_json(audit_path)
        target_prefix = str(report.get("target", {}).get("prefix", "transcripts")).strip("/")
        require_clean_transcript_worktree(repo, target_prefix)
        changes = plan_changes(repo, report)
        if args.apply:
            apply_changes(changes)
        actions = Counter(change["action"] for change in changes)
        events = [event for change in changes for event in change["attributionEvents"]]
        authors = Counter((event["author"]["name"], event["author"]["email"]) for event in events)
        print(f"{'Applied' if args.apply else 'Validated'} {len(changes)} historical corrections.")
        print(
            json.dumps(
                {
                    "actions": dict(sorted(actions.items())),
                    "attributionEvents": len(events),
                    "authors": len(authors),
                },
                indent=2,
            )
        )
        if not args.apply:
            print("Dry run only; pass --apply to write transcript files.")
        return 0
    except (AuditError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
