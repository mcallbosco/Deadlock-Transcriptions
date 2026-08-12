#!/usr/bin/env python3
"""Apply reviewed current corrections to their exact older audio revisions."""

from __future__ import annotations

import argparse
import copy
import hashlib
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_changes(
    repo: Path, report: dict[str, Any], decisions: dict[str, Any]
) -> list[dict[str, Any]]:
    if report.get("mode") != "cross-version-current-audit-only":
        raise AuditError("The input is not a cross-version current audit.")
    if decisions.get("schemaVersion") != 1:
        raise AuditError("Unsupported cross-version current decision schema.")
    approval = decisions.get("approval", {})
    if approval.get("status") != "candidate_cross_version_current_review":
        raise AuditError("The decisions approve an unsupported record status.")
    if approval.get("temporalMismatchAcknowledged") is not True:
        raise AuditError("The cross-version temporal mismatch was not acknowledged.")
    if decisions.get("overrides") != []:
        raise AuditError("This exact-state review does not permit text overrides.")

    policy = report.get("policy", {})
    required = {
        "reportOnly": True,
        "officialRevisionsMutable": False,
        "allRootManifestVersionsScanned": True,
        "uniqueTranscriptPathRequired": True,
        "uniqueAudioRevisionRequired": True,
        "exactTextAnchorRequired": True,
        "currentHeadConflictCheckRequired": True,
        "temporalMismatchMayAutoApply": False,
        "fuzzyMatchingMayAutoApply": False,
    }
    for key, expected in required.items():
        if policy.get(key) != expected:
            raise AuditError(f"The audit report has an unsafe or missing policy: {key}")
    if policy.get("eligibleTargetSources") != ["generated"]:
        raise AuditError("The audit report permits a non-generated target source.")

    candidates = [
        record
        for record in report.get("records", [])
        if record.get("status") == approval["status"]
    ]
    if approval.get("candidateCount") != len(candidates):
        raise AuditError("The reviewed candidate count no longer matches the audit.")
    target_prefix = str(report["target"]["prefix"]).strip("/")
    protected_root = (repo / target_prefix).resolve()
    selected: set[tuple[str, str]] = set()
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
        identity = (str(target["path"]), sha256)
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
                [
                    revision
                    for revision in document.get("revisions", [])
                    if revision.get("source") == "official"
                ]
            ),
        )
        revisions = [
            revision
            for revision in document.get("revisions", [])
            if revision.get("sha256") == sha256
        ]
        if len(revisions) != 1:
            raise AuditError(f"Expected one current revision {identity}; found {len(revisions)}.")
        revision = revisions[0]
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
                "legacyPath": record["legacyPath"],
                "action": action,
                "attributionEvents": copy.deepcopy(events),
                "before": before,
                "after": copy.deepcopy(revision),
            }
        )

    for path, document in documents.items():
        official_after = [
            revision
            for revision in document.get("revisions", [])
            if revision.get("source") == "official"
        ]
        if official_after != official_before[path]:
            raise AuditError(f"Official revision changed in memory: {path}")
    return changes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply reviewed current corrections to exact older audio revisions."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("migration-reports/cross-version-current-contribution-audit.json"),
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path("migration-reports/cross-version-current-review-decisions.json"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-reviewed-temporal-mismatch", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        audit_path = args.audit if args.audit.is_absolute() else repo / args.audit
        decisions_path = args.decisions if args.decisions.is_absolute() else repo / args.decisions
        report = read_json(audit_path)
        decisions = read_json(decisions_path)
        if decisions.get("audit") != audit_path.relative_to(repo).as_posix():
            raise AuditError("The decisions file identifies a different audit path.")
        if decisions.get("auditSha256") != file_sha256(audit_path):
            raise AuditError("The cross-version current audit changed after review.")
        target_prefix = str(report.get("target", {}).get("prefix", "transcripts")).strip("/")
        require_clean_transcript_worktree(repo, target_prefix)
        changes = plan_changes(repo, report, decisions)
        if args.apply and not args.approve_reviewed_temporal_mismatch:
            raise AuditError(
                "Pass --approve-reviewed-temporal-mismatch with --apply after reviewing the pinned decisions."
            )
        if args.apply:
            apply_changes(changes)
        actions = Counter(change["action"] for change in changes)
        final_authors = Counter(
            (
                change["attributionEvents"][-1]["author"]["name"],
                change["attributionEvents"][-1]["author"]["email"],
            )
            for change in changes
        )
        print(
            f"{'Applied' if args.apply else 'Validated'} {len(changes)} "
            "reviewed cross-version current corrections."
        )
        print(
            json.dumps(
                {
                    "actions": dict(sorted(actions.items())),
                    "finalAuthors": len(final_authors),
                },
                indent=2,
            )
        )
        if not args.apply:
            print(
                "Dry run only; pass --apply --approve-reviewed-temporal-mismatch "
                "to write transcript files."
            )
        return 0
    except (AuditError, KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
