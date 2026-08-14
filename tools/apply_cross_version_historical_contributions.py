#!/usr/bin/env python3
"""Apply explicitly approved cross-version historical review candidates."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from apply_current_contributions import read_json
from apply_versioned_historical_contributions import (
    apply_changes,
    require_clean_transcript_worktree,
)
from audit_legacy_contributions import AuditError, git, normalize_text, valid_sha256
from transcript_schema import revision_group_identity, revisions_for_hash


def plan_changes(repo: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    if report.get("mode") != "cross-version-historical-audit-only":
        raise AuditError("The input is not a cross-version historical audit.")
    policy = report.get("policy", {})
    required = {
        "reportOnly": True,
        "officialRevisionsMutable": False,
        "allRootManifestVersionsScanned": True,
        "uniqueTranscriptPathRequired": True,
        "uniqueAudioRevisionRequired": True,
        "uniqueHistoryEpochRequired": True,
        "exactTextAnchorRequired": True,
        "currentHeadConflictCheckRequired": True,
        "temporalMismatchMayAutoApply": False,
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
        if record.get("status") == "candidate_historical_version_review"
    ]
    selected: set[tuple[str, str]] = set()
    selected_groups: set[tuple[str, tuple[str, ...]]] = set()
    documents: dict[Path, dict[str, Any]] = {}
    official_before: dict[Path, list[dict[str, Any]]] = {}
    changes: list[dict[str, Any]] = []

    for record in candidates:
        target = record["selectedTarget"]
        path = (repo / Path(*str(target["path"]).split("/"))).resolve()
        try:
            path.relative_to(protected_root)
        except ValueError as exc:
            raise AuditError(f"Target is outside {protected_root}: {path}") from exc
        sha256 = target.get("sha256")
        if not valid_sha256(sha256):
            raise AuditError(f"Candidate has no valid SHA-256: {target.get('path')}")
        identity = (target["path"], sha256)
        if identity in selected:
            raise AuditError(f"Multiple candidates target the same revision: {identity}")
        selected.add(identity)
        if len(record.get("exactMatches", [])) != 1:
            raise AuditError(f"Candidate no longer has one exact cross-version match: {identity}")
        if target.get("source") != "generated" or len(target.get("statePositions", [])) != 1:
            raise AuditError(f"Candidate has unsafe target evidence: {identity}")
        assigned = {value["versionId"] for value in record["assignedReleaseResults"]}
        matched = {value["versionId"] for value in target["manifestVersions"]}
        if assigned & matched:
            raise AuditError(f"Candidate is not a temporal mismatch: {identity}")

        document = documents.setdefault(path, read_json(path))
        official_before.setdefault(
            path,
            copy.deepcopy(
                [value for value in document.get("revisions", []) if value.get("source") == "official"]
            ),
        )
        revisions = revisions_for_hash(document, sha256)
        if len(revisions) != 1:
            raise AuditError(f"Expected one current revision {identity}; found {len(revisions)}.")
        revision = revisions[0]
        group_identity = revision_group_identity(str(target["path"]), revision)
        if group_identity in selected_groups:
            raise AuditError(f"Multiple candidates target the same transcript group: {group_identity}")
        selected_groups.add(group_identity)
        if revision.get("source") == "official":
            raise AuditError(f"Refusing to modify official revision {identity}.")
        if revision.get("source") != "generated" or revision.get("text") != target.get(
            "originalText"
        ):
            raise AuditError(f"Current revision changed since the audit: {identity}")

        before = copy.deepcopy(revision)
        current_text = revision.get("text")
        events = record["attributionEvents"]
        action = target.get("proposedAction")
        if action == "replay_and_mark_manual":
            for event in events:
                if normalize_text(current_text) != normalize_text(event["beforeFullText"]):
                    raise AuditError(
                        f"Replay chain no longer matches {identity} at {event['legacyCommit']}."
                    )
                current_text = event["afterFullText"]
        elif action == "mark_manual":
            current_text = record["desiredText"]
            if normalize_text(revision.get("text")) != normalize_text(current_text):
                raise AuditError(f"Mark-manual text no longer matches for {identity}.")
        else:
            raise AuditError(f"Unsupported cross-version action for {identity}: {action}")

        revision["text"] = current_text
        revision["source"] = "manual"
        revision.pop("model", None)
        changes.append(
            {
                "path": path,
                "relativePath": target["path"],
                "sha256": sha256,
                "epochId": record["epochId"],
                "action": action,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply explicitly approved cross-version historical corrections."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("migration-reports/cross-version-historical-contribution-audit.json"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--approve-temporal-mismatch",
        action="store_true",
        help="Required with --apply to acknowledge that matching SHAs are from older versions.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.apply and not args.approve_temporal_mismatch:
            raise AuditError("--apply requires --approve-temporal-mismatch.")
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
        print(f"{'Applied' if args.apply else 'Validated'} {len(changes)} cross-version corrections.")
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
            print("Dry run only; pass both approval flags to write transcript files.")
        return 0
    except (AuditError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
