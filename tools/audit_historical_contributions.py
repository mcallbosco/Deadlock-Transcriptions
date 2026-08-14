#!/usr/bin/env python3
"""Audit superseded and deleted legacy corrections against v3 audio revisions.

This is Stage 1B of the migration. It finds contiguous epochs of human,
text-only corrections that no longer represent the legacy branch's current
state, then requires a one-to-one exact-text relationship between an epoch and
a generated v3 audio-SHA group. It only writes reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from audit_legacy_contributions import (
    AuditError,
    CommitRecord,
    DEFAULT_OFFICIAL_IMPORT_COMMITS,
    ZERO_OBJECT,
    build_target_index,
    classify_commit,
    compare_legacy_documents,
    full_legacy_text,
    git,
    list_tree,
    normalize_text,
    parse_history,
    parse_json_blob,
    read_blobs,
    resolve_ref,
    safe_output_path,
    valid_sha256,
)


REPORT_SCHEMA_VERSION = 1


@dataclass
class CorrectionEvent:
    commit: CommitRecord
    legacy_path: str
    before_full_text: str
    after_full_text: str
    changed_segments: list[dict[str, Any]]


def collect_epochs(
    repo: Path,
    commits: list[CommitRecord],
    current_documents: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Collect correction epochs, using every non-eligible path change as a boundary."""

    eligible_objects = {
        object_id
        for commit in commits
        if commit.disposition == "eligible_human"
        for change in commit.changes
        if change.status == "M" and change.path.endswith(".json")
        for object_id in (change.old_object, change.new_object)
        if object_id != ZERO_OBJECT
    }
    blobs = read_blobs(repo, eligible_objects)
    path_changes: dict[str, list[CorrectionEvent | None]] = defaultdict(list)
    invalid_events = 0

    for commit in commits:
        for change in commit.changes:
            if not change.path.endswith(".json"):
                continue
            event: CorrectionEvent | None = None
            if commit.disposition == "eligible_human" and change.status == "M":
                try:
                    old_document = parse_json_blob(
                        blobs[change.old_object], f"{commit.commit}^:{change.path}"
                    )
                    new_document = parse_json_blob(
                        blobs[change.new_object], f"{commit.commit}:{change.path}"
                    )
                    segment_changes, text_only, before_full, after_full = (
                        compare_legacy_documents(
                            old_document,
                            new_document,
                            f"{commit.commit}:{change.path}",
                        )
                    )
                    if (
                        segment_changes
                        and text_only
                        and before_full is not None
                        and normalize_text(before_full) != normalize_text(after_full)
                    ):
                        event = CorrectionEvent(
                            commit=commit,
                            legacy_path=change.path,
                            before_full_text=before_full,
                            after_full_text=after_full,
                            changed_segments=[
                                {
                                    "index": value.index,
                                    "part": value.part,
                                    "before": value.before,
                                    "after": value.after,
                                }
                                for value in segment_changes
                            ],
                        )
                except (AuditError, KeyError):
                    invalid_events += 1
            path_changes[change.path].append(event)

    epochs: list[dict[str, Any]] = []
    for legacy_path in sorted(path_changes):
        groups: list[list[CorrectionEvent]] = []
        current_group: list[CorrectionEvent] = []
        for event in path_changes[legacy_path]:
            if event is None:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                continue
            if current_group and normalize_text(current_group[-1].after_full_text) != normalize_text(
                event.before_full_text
            ):
                groups.append(current_group)
                current_group = []
            current_group.append(event)
        if current_group:
            groups.append(current_group)

        current_text = None
        if legacy_path in current_documents:
            current_text = full_legacy_text(current_documents[legacy_path], legacy_path)
        historical_index = 0
        for group in groups:
            if current_text is not None and normalize_text(group[-1].after_full_text) == normalize_text(
                current_text
            ):
                continue
            epochs.append(
                {
                    "epochId": f"{legacy_path}#{historical_index}",
                    "status": "",
                    "legacyPath": legacy_path,
                    "legacyPathDeleted": legacy_path not in current_documents,
                    "initialText": group[0].before_full_text,
                    "finalText": group[-1].after_full_text,
                    "events": [
                        {
                            "legacyCommit": event.commit.commit,
                            "legacySubject": event.commit.subject,
                            "author": {
                                "name": event.commit.author_name,
                                "email": event.commit.author_email,
                                "date": event.commit.author_date,
                            },
                            "beforeFullText": event.before_full_text,
                            "afterFullText": event.after_full_text,
                            "changedSegments": event.changed_segments,
                        }
                        for event in group
                    ],
                    "targetDocumentCandidates": 0,
                    "targetMatches": [],
                }
            )
            historical_index += 1
    return epochs, invalid_events


def add_target_evidence(
    records: list[dict[str, Any]],
    target_index: dict[str, list[dict[str, Any]]],
) -> None:
    """Attach exact matches and classify only globally one-to-one generated anchors."""

    revision_epochs: dict[str, set[str]] = defaultdict(set)
    generated_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_sha_epochs: set[str] = set()

    for record in records:
        basename = PurePosixPath(record["legacyPath"]).name.casefold()
        documents = target_index.get(basename, [])
        record["targetDocumentCandidates"] = len(documents)
        states = [record["initialText"]] + [
            event["afterFullText"] for event in record["events"]
        ]
        for document in documents:
            for revision_index, revision in enumerate(document["revisions"]):
                positions = sorted(
                    {
                        index
                        for index, state in enumerate(states)
                        if normalize_text(state) == normalize_text(revision["text"])
                    }
                )
                if not positions:
                    continue
                hashes = revision.get("sha256")
                if not isinstance(hashes, list):
                    hashes = []
                sha256 = hashes[0] if hashes else None
                revision_id = f"{document['path']}@{','.join(hashes) or revision_index}"
                source = revision["source"]
                match = {
                    "revisionId": revision_id,
                    "path": document["path"],
                    "filename": document["filename"],
                    "sha256": sha256,
                    "groupSha256": hashes,
                    "source": source,
                    "statePositions": positions,
                    "proposedAction": "protected" if source == "official" else "review",
                }
                record["targetMatches"].append(match)
                if source == "generated":
                    if valid_sha256(sha256):
                        generated_edges[record["epochId"]].append(match)
                        revision_epochs[revision_id].add(record["epochId"])
                    else:
                        missing_sha_epochs.add(record["epochId"])

    for record in records:
        documents = record["targetDocumentCandidates"]
        matches = record["targetMatches"]
        generated = generated_edges[record["epochId"]]
        official = [value for value in matches if value["source"] == "official"]
        other_nonofficial = [
            value for value in matches if value["source"] not in {"official", "generated"}
        ]
        if documents == 0:
            record["status"] = "no_target"
        elif documents > 1:
            record["status"] = "ambiguous_path"
        elif not generated:
            if record["epochId"] in missing_sha_epochs:
                record["status"] = "review_missing_sha"
            elif official and not other_nonofficial:
                record["status"] = "protected_official"
            elif other_nonofficial:
                record["status"] = "review_non_generated_source"
            else:
                record["status"] = "no_exact_anchor"
        elif len(generated) > 1:
            record["status"] = "ambiguous_revision"
        else:
            selected = generated[0]
            if len(selected["statePositions"]) != 1:
                record["status"] = "ambiguous_state"
            elif len(revision_epochs[selected["revisionId"]]) != 1:
                record["status"] = "ambiguous_history"
            else:
                position = selected["statePositions"][0]
                if position < len(record["events"]):
                    record["status"] = "candidate_replay"
                    selected["proposedAction"] = "replay_and_mark_manual"
                    record["replayEvents"] = record["events"][position:]
                else:
                    record["status"] = "candidate_mark_manual"
                    selected["proposedAction"] = "mark_manual"
                    record["attributionEvent"] = record["events"][-1]
                record["selectedTarget"] = {
                    key: selected[key]
                    for key in ("path", "filename", "sha256", "source", "proposedAction")
                }
        record["officialRevisionsProtected"] = len(official)


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Historical legacy contribution audit",
        "",
        "> Audit only: this report did not modify transcripts or categories.",
        "",
        "## Pinned inputs",
        "",
        "| Input | Ref | Commit | Files |",
        "| --- | --- | --- | ---: |",
        f"| Legacy | `{report['legacy']['ref']}` | `{report['legacy']['commit']}` | {summary['currentLegacyFiles']:,} |",
        f"| Target | `{report['target']['ref']}` | `{report['target']['commit']}` | {summary['targetDocuments']:,} |",
        "",
        "## Historical coverage",
        "",
        f"- Paths ever present in non-merge legacy history: **{summary['everLegacyPaths']:,}**",
        f"- Paths deleted from the pinned legacy state: **{summary['deletedLegacyPaths']:,}**",
        f"- Historical human correction epochs: **{summary['historicalEpochs']:,}**",
        f"- Human correction commits represented: **{summary['historicalCorrectionEvents']:,}**",
        f"- Protected official revisions in the target: **{summary['officialRevisions']:,}**",
        "",
        "## Record classifications",
        "",
        "| Status | Epochs |",
        "| --- | ---: |",
    ]
    for status, count in sorted(
        summary["recordsByStatus"].items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"| `{status}` | {count:,} |")
    lines.extend(
        [
            "",
            "## Candidate attribution",
            "",
            "| Author | Email | Actions |",
            "| --- | --- | ---: |",
        ]
    )
    for author in summary["candidateAuthors"]:
        name = author["name"].replace("|", "\\|")
        email = author["email"].replace("|", "\\|")
        lines.append(f"| {name} | `{email}` | {author['actions']:,} |")
    if not summary["candidateAuthors"]:
        lines.append("| _None_ |  | 0 |")
    lines.extend(
        [
            "",
            "A candidate requires one transcript path, one generated SHA revision, one",
            "matching correction epoch, and one exact state within that epoch. Official",
            "revisions and non-generated sources are never proposed for mutation.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_historical(
    repo: Path,
    legacy_ref: str,
    target_ref: str,
    legacy_prefix: str,
    target_prefix: str,
    bulk_threshold: int,
    official_commits: set[str],
) -> dict[str, Any]:
    legacy_commit = resolve_ref(repo, legacy_ref)
    target_commit = resolve_ref(repo, target_ref)
    current_tree = {
        path: object_id
        for path, object_id in list_tree(repo, legacy_commit, legacy_prefix).items()
        if path.endswith(".json")
    }
    target_tree = {
        path: object_id
        for path, object_id in list_tree(repo, target_commit, target_prefix).items()
        if path.endswith(".json")
    }
    blobs = read_blobs(repo, [*current_tree.values(), *target_tree.values()])
    current_documents = {
        path: parse_json_blob(blobs[object_id], f"{legacy_commit}:{path}")
        for path, object_id in current_tree.items()
    }
    target_documents = {
        path: parse_json_blob(blobs[object_id], f"{target_commit}:{path}")
        for path, object_id in target_tree.items()
    }
    target_index, target_stats = build_target_index(target_documents, target_prefix)

    commits = parse_history(repo, legacy_commit, legacy_prefix)
    for commit in commits:
        commit.disposition = classify_commit(commit, official_commits, bulk_threshold)
    ever_paths = {
        change.path
        for commit in commits
        for change in commit.changes
        if change.path.endswith(".json")
    }
    records, invalid_events = collect_epochs(repo, commits, current_documents)
    add_target_evidence(records, target_index)
    records.sort(key=lambda value: (value["legacyPath"], value["epochId"]))

    statuses = Counter(record["status"] for record in records)
    candidate_authors: Counter[tuple[str, str]] = Counter()
    for record in records:
        if record["status"] == "candidate_replay":
            attribution = record["replayEvents"]
        elif record["status"] == "candidate_mark_manual":
            attribution = [record["attributionEvent"]]
        else:
            attribution = []
        for event in attribution:
            author = event["author"]
            candidate_authors[(author["name"], author["email"])] += 1

    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "mode": "historical-audit-only",
        "legacy": {"ref": legacy_ref, "commit": legacy_commit, "prefix": legacy_prefix},
        "target": {"ref": target_ref, "commit": target_commit, "prefix": target_prefix},
        "policy": {
            "bulkCommitFileThreshold": bulk_threshold,
            "officialImportCommits": sorted(official_commits),
            "officialRevisionsMutable": False,
            "eligibleTargetSources": ["generated"],
            "uniqueTranscriptPathRequired": True,
            "uniqueAudioRevisionRequired": True,
            "uniqueHistoryEpochRequired": True,
            "exactTextAnchorRequired": True,
            "fuzzyMatchingMayAutoApply": False,
        },
        "summary": {
            "legacyNonMergeCommits": len(commits),
            "everLegacyPaths": len(ever_paths),
            "currentLegacyFiles": len(current_tree),
            "deletedLegacyPaths": len(ever_paths - set(current_tree)),
            "targetDocuments": target_stats["documents"],
            "targetRevisions": target_stats["revisions"],
            "officialRevisions": target_stats["officialRevisions"],
            "historicalEpochs": len(records),
            "historicalCorrectionEvents": sum(len(record["events"]) for record in records),
            "candidateActionsOnDeletedPaths": sum(
                record["legacyPathDeleted"]
                and record["status"] in {"candidate_replay", "candidate_mark_manual"}
                for record in records
            ),
            "invalidHistoryEvents": invalid_events,
            "recordsByStatus": dict(sorted(statuses.items())),
            "candidateAuthors": [
                {"name": name, "email": email, "actions": count}
                for (name, email), count in sorted(
                    candidate_authors.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        },
        "records": records,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit superseded/deleted legacy corrections without modifying content."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--legacy-ref", default="main")
    parser.add_argument("--target-ref", default="HEAD")
    parser.add_argument("--legacy-prefix", default="data")
    parser.add_argument("--target-prefix", default="transcripts")
    parser.add_argument("--bulk-threshold", type=int, default=500)
    parser.add_argument("--official-commit", action="append", default=[])
    parser.add_argument(
        "--output-json", default="migration-reports/historical-contribution-audit.json"
    )
    parser.add_argument(
        "--output-markdown", default="migration-reports/historical-contribution-audit.md"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        report = audit_historical(
            repo=repo,
            legacy_ref=args.legacy_ref,
            target_ref=args.target_ref,
            legacy_prefix=args.legacy_prefix.strip("/"),
            target_prefix=args.target_prefix.strip("/"),
            bulk_threshold=args.bulk_threshold,
            official_commits=DEFAULT_OFFICIAL_IMPORT_COMMITS | set(args.official_commit),
        )
        protected: Iterable[str] = (args.legacy_prefix, args.target_prefix, "config")
        json_path = safe_output_path(repo, args.output_json, protected)
        markdown_path = safe_output_path(repo, args.output_markdown, protected)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"Wrote {json_path}")
        print(f"Wrote {markdown_path}")
        print(json.dumps(report["summary"]["recordsByStatus"], indent=2))
        return 0
    except (AuditError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
