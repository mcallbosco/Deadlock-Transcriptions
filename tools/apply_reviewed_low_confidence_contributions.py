#!/usr/bin/env python3
"""Apply explicitly reviewed low-confidence external contribution records."""

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
from audit_legacy_contributions import AuditError, git, valid_sha256
from transcript_schema import revision_group_identity, revisions_for_hash


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def author_is_excluded(author: dict[str, Any], approval: dict[str, Any]) -> bool:
    email = str(author.get("email", "")).casefold()
    identity = f"{author.get('name', '')} {email}".casefold()
    excluded_emails = {
        str(value).casefold() for value in approval.get("excludedAuthorEmails", [])
    }
    excluded_fragments = [
        str(value).casefold()
        for value in approval.get("excludedAuthorIdentityContains", [])
    ]
    return email in excluded_emails or any(
        fragment and fragment in identity for fragment in excluded_fragments
    )


def selected_records(
    report: dict[str, Any], decisions: dict[str, Any]
) -> list[dict[str, Any]]:
    approval = decisions.get("approval", {})
    required = {
        "confidence": "low",
        "status": "review_low_semantic_similarity",
        "requiresExternalEvent": True,
        "includeMixedUserExternalEpochs": True,
    }
    for key, expected in required.items():
        if approval.get(key) != expected:
            raise AuditError(f"The reviewed low-confidence selection changed: {key}")
    if not approval.get("excludedAuthorEmails"):
        raise AuditError("The decisions do not identify the reviewer's author email.")
    if "copilot" not in {
        str(value).casefold()
        for value in approval.get("excludedAuthorIdentityContains", [])
    }:
        raise AuditError("The decisions do not exclude Copilot-authored events.")

    records = []
    for record in report.get("records", []):
        if record.get("confidence") != approval["confidence"]:
            continue
        if record.get("status") != approval["status"]:
            continue
        events = record.get("events", [])
        if events and any(
            not author_is_excluded(event.get("author", {}), approval)
            for event in events
        ):
            records.append(record)
    if approval.get("candidateCount") != len(records):
        raise AuditError("The reviewed low-confidence candidate count no longer matches.")
    return records


def review_overrides(
    records: list[dict[str, Any]], decisions: dict[str, Any]
) -> dict[str, dict[str, str]]:
    candidate_paths = [str(record.get("legacyPath")) for record in records]
    if len(candidate_paths) != len(set(candidate_paths)):
        raise AuditError("Reviewed records do not have unique legacy paths.")
    overrides: dict[str, dict[str, str]] = {}
    for value in decisions.get("overrides", []):
        legacy_path = value.get("legacyPath")
        text = value.get("text")
        reason = value.get("reason")
        if not isinstance(legacy_path, str) or legacy_path not in candidate_paths:
            raise AuditError(f"Override does not identify an approved record: {legacy_path}")
        if legacy_path in overrides:
            raise AuditError(f"Duplicate override for {legacy_path}")
        if not isinstance(text, str) or not isinstance(reason, str) or not reason.strip():
            raise AuditError(f"Override is missing reviewed text or rationale: {legacy_path}")
        overrides[legacy_path] = {"text": text, "reason": reason}
    return overrides


def plan_changes(
    repo: Path, report: dict[str, Any], decisions: dict[str, Any]
) -> list[dict[str, Any]]:
    if report.get("mode") != "semantic-delta-audit-only":
        raise AuditError("The input is not a semantic-delta audit.")
    if decisions.get("schemaVersion") != 1:
        raise AuditError("Unsupported low-confidence review-decision schema.")
    policy = report.get("policy", {})
    required_policy = {
        "reportOnly": True,
        "officialRevisionsMutable": False,
        "noExactStateAcrossAnyManifestRequired": True,
        "dateSelectedSixHeroShaRequired": True,
        "currentHeadConflictCheckRequired": True,
        "semanticDeltaMayAutoApply": False,
        "fuzzyMatchingMayAutoApply": False,
    }
    for key, expected in required_policy.items():
        if policy.get(key) != expected:
            raise AuditError(f"The audit report has an unsafe or missing policy: {key}")
    if policy.get("eligibleTargetSources") != ["generated"]:
        raise AuditError("The audit report permits a non-generated target source.")

    records = selected_records(report, decisions)
    overrides = review_overrides(records, decisions)
    target_prefix = str(report["target"]["prefix"]).strip("/")
    protected_root = (repo / target_prefix).resolve()
    selected: set[tuple[str, str]] = set()
    selected_groups: set[tuple[str, tuple[str, ...]]] = set()
    documents: dict[Path, dict[str, Any]] = {}
    official_before: dict[Path, list[dict[str, Any]]] = {}
    changes: list[dict[str, Any]] = []

    for record in records:
        target = record["selectedTarget"]
        relative = Path(*str(target["path"]).split("/"))
        path = (repo / relative).resolve()
        try:
            path.relative_to(protected_root)
        except ValueError as exc:
            raise AuditError(f"Target is outside {protected_root}: {path}") from exc
        sha256 = target.get("sha256")
        if not valid_sha256(sha256):
            raise AuditError(f"Record has no valid version SHA-256: {target.get('path')}")
        identity = (str(target["path"]), sha256)
        if identity in selected:
            raise AuditError(f"Multiple records target the same revision: {identity}")
        selected.add(identity)

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
        revisions = revisions_for_hash(document, sha256)
        if len(revisions) != 1:
            raise AuditError(f"Expected one revision {identity}; found {len(revisions)}.")
        revision = revisions[0]
        group_identity = revision_group_identity(str(target["path"]), revision)
        if group_identity in selected_groups:
            raise AuditError(f"Multiple records target the same transcript group: {group_identity}")
        selected_groups.add(group_identity)
        if revision.get("source") == "official":
            raise AuditError(f"Refusing to modify official revision {identity}.")
        if revision.get("source") != "generated":
            raise AuditError(f"Revision is no longer generated: {identity}")
        if revision.get("text") != target.get("originalText"):
            raise AuditError(f"Revision text changed since the audit: {identity}")

        legacy_path = str(record["legacyPath"])
        override = overrides.get(legacy_path)
        reviewed_text = override["text"] if override else record.get("finalText")
        if not isinstance(reviewed_text, str):
            raise AuditError(f"Record has no final reviewed text: {record.get('epochId')}")
        before = copy.deepcopy(revision)
        revision["text"] = reviewed_text
        revision["source"] = "manual"
        revision.pop("model", None)
        changes.append(
            {
                "path": path,
                "relativePath": target["path"],
                "sha256": sha256,
                "epochId": record["epochId"],
                "legacyPath": legacy_path,
                "action": "apply_reviewed_low_confidence_and_mark_manual",
                "override": copy.deepcopy(override),
                "attributionEvents": copy.deepcopy(record["events"]),
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
        description="Apply reviewed low-confidence Six Hero external contributions."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path(
            "migration-reports/six-hero-semantic-delta-contribution-audit.json"
        ),
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path(
            "migration-reports/six-hero-low-confidence-review-decisions.json"
        ),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-reviewed-low-confidence", action="store_true")
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
            raise AuditError("The semantic-delta audit changed after review.")
        target_prefix = str(report.get("target", {}).get("prefix", "transcripts")).strip("/")
        require_clean_transcript_worktree(repo, target_prefix)
        changes = plan_changes(repo, report, decisions)
        if args.apply and not args.approve_reviewed_low_confidence:
            raise AuditError(
                "Pass --approve-reviewed-low-confidence with --apply after reviewing the pinned decisions."
            )
        if args.apply:
            apply_changes(changes)
        final_authors = Counter(
            (
                change["attributionEvents"][-1]["author"]["name"],
                change["attributionEvents"][-1]["author"]["email"],
            )
            for change in changes
        )
        print(
            f"{'Applied' if args.apply else 'Validated'} {len(changes)} "
            "reviewed low-confidence corrections."
        )
        print(
            json.dumps(
                {
                    "overrides": sum(bool(change["override"]) for change in changes),
                    "attributionEvents": sum(
                        len(change["attributionEvents"]) for change in changes
                    ),
                    "finalAuthors": len(final_authors),
                },
                indent=2,
            )
        )
        if not args.apply:
            print(
                "Dry run only; pass --apply --approve-reviewed-low-confidence "
                "to write transcript files."
            )
        return 0
    except (AuditError, KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
