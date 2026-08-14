#!/usr/bin/env python3
"""Audit surviving legacy transcript corrections against the v3 transcript tree.

This command is intentionally read-only with respect to transcript and category
content. It reads both layouts from Git objects, identifies surviving text-only
changes in the legacy history, and writes JSON/Markdown reports describing what
a later migration may safely apply.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from transcript_schema import TRANSCRIPT_SCHEMA_VERSION


REPORT_SCHEMA_VERSION = 1
ZERO_OBJECT = "0" * 40
DEFAULT_OFFICIAL_IMPORT_COMMITS = {
    "0322fc64ca2e514fed976dec77f6540934624361",
    "ed2b3e4c473a5a65fe188247b3eb09326f34a54c",
    "26eee84004096a5f0573ffa3e35a0705b70ebaf1",
}
OFFICIAL_IMPORT_SUBJECT = re.compile(r"\b(?:off?icial|offical)\b.*\b(?:transcript|subtitle)s?\b", re.I)
MECHANICAL_SUBJECT = re.compile(
    r"\b(?:all[ -]?caps|common mistake|format(?:ting)? update|mass fix|bulk fix)\b",
    re.I,
)
RAW_CHANGE = re.compile(
    r"^:\d+ \d+ ([0-9a-f]{40}) ([0-9a-f]{40}) ([A-Z])\t(.+)$"
)


class AuditError(RuntimeError):
    """Raised when the audit cannot safely interpret its Git inputs."""


@dataclass
class RawChange:
    old_object: str
    new_object: str
    status: str
    path: str


@dataclass
class CommitRecord:
    commit: str
    parents: list[str]
    author_name: str
    author_email: str
    author_date: str
    subject: str
    changes: list[RawChange] = field(default_factory=list)
    disposition: str = ""


@dataclass
class SegmentChange:
    index: int
    part: Any
    before: str | None
    after: str


@dataclass
class ContributionEvent:
    commit: CommitRecord
    legacy_path: str
    change_kind: str
    text_only: bool
    before_full_text: str | None
    after_full_text: str
    current_full_text: str
    segment: SegmentChange


def git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    command = ["git", "-C", str(repo), *args]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise AuditError(f"Git command failed ({' '.join(command)}): {stderr}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", errors="replace")


def resolve_ref(repo: Path, ref: str) -> str:
    return str(git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")).strip()


def list_tree(repo: Path, ref: str, prefix: str) -> dict[str, str]:
    raw = bytes(git(repo, "ls-tree", "-r", "-z", ref, "--", prefix, binary=True))
    entries: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        if object_type != "blob":
            continue
        path = encoded_path.decode("utf-8", errors="strict")
        entries[path] = object_id
    return entries


def read_blobs(repo: Path, object_ids: Iterable[str]) -> dict[str, bytes]:
    ordered = sorted({value for value in object_ids if value and value != ZERO_OBJECT})
    if not ordered:
        return {}
    request = ("\n".join(ordered) + "\n").encode("ascii")
    process = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=request,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise AuditError(process.stderr.decode("utf-8", errors="replace").strip())
    output = process.stdout
    cursor = 0
    result: dict[str, bytes] = {}
    for requested in ordered:
        line_end = output.find(b"\n", cursor)
        if line_end < 0:
            raise AuditError("Unexpected end of git cat-file output.")
        header = output[cursor:line_end].decode("ascii", errors="replace")
        cursor = line_end + 1
        if header.endswith(" missing"):
            raise AuditError(f"Git object is missing: {requested}")
        fields = header.split()
        if len(fields) != 3 or fields[1] != "blob":
            raise AuditError(f"Expected a blob for {requested}, got: {header}")
        size = int(fields[2])
        result[requested] = output[cursor : cursor + size]
        cursor += size
        if output[cursor : cursor + 1] != b"\n":
            raise AuditError(f"Malformed git cat-file delimiter after {requested}.")
        cursor += 1
    return result


def parse_json_blob(blob: bytes, origin: str) -> dict[str, Any]:
    try:
        value = json.loads(blob.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"Invalid JSON in {origin}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"Expected a JSON object in {origin}.")
    return value


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def legacy_segments(document: dict[str, Any], origin: str) -> list[dict[str, Any]]:
    values = document.get("segments")
    if not isinstance(values, list):
        raise AuditError(f"Legacy transcript has no segments array: {origin}")
    result: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            raise AuditError(f"Legacy segment {index} has no text string: {origin}")
        result.append(value)
    return result


def full_legacy_text(document: dict[str, Any], origin: str) -> str:
    return " ".join(
        segment["text"].strip()
        for segment in legacy_segments(document, origin)
        if segment["text"].strip()
    )


def without_legacy_text(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    segments = result.get("segments")
    if isinstance(segments, list):
        for segment in segments:
            if isinstance(segment, dict):
                segment.pop("text", None)
    return result


def compare_legacy_documents(
    old: dict[str, Any] | None,
    new: dict[str, Any],
    origin: str,
) -> tuple[list[SegmentChange], bool, str | None, str]:
    new_segments = legacy_segments(new, origin)
    new_full = full_legacy_text(new, origin)
    if old is None:
        return (
            [
                SegmentChange(index, segment.get("part"), None, segment["text"])
                for index, segment in enumerate(new_segments)
            ],
            False,
            None,
            new_full,
        )

    old_segments = legacy_segments(old, origin)
    changes: list[SegmentChange] = []
    for index, new_segment in enumerate(new_segments):
        before = old_segments[index].get("text") if index < len(old_segments) else None
        after = new_segment["text"]
        if before != after:
            changes.append(SegmentChange(index, new_segment.get("part"), before, after))
    text_only = without_legacy_text(old) == without_legacy_text(new)
    return changes, text_only, full_legacy_text(old, origin), new_full


def parse_history(repo: Path, ref: str, legacy_prefix: str) -> list[CommitRecord]:
    marker = "@@AUDIT@@"
    format_value = marker + "%H%x1f%P%x1f%an%x1f%ae%x1f%aI%x1f%s"
    output = str(
        git(
            repo,
            "log",
            "--reverse",
            "--topo-order",
            "--no-merges",
            "--raw",
            "--no-abbrev",
            "--no-renames",
            f"--format={format_value}",
            ref,
            "--",
            legacy_prefix,
        )
    )
    commits: list[CommitRecord] = []
    current: CommitRecord | None = None
    for line in output.splitlines():
        if line.startswith(marker):
            fields = line[len(marker) :].split("\x1f", 5)
            if len(fields) != 6:
                raise AuditError(f"Malformed Git history marker: {line}")
            current = CommitRecord(
                commit=fields[0],
                parents=fields[1].split() if fields[1] else [],
                author_name=fields[2],
                author_email=fields[3],
                author_date=fields[4],
                subject=fields[5],
            )
            commits.append(current)
            continue
        if not line.startswith(":"):
            continue
        if current is None:
            raise AuditError("Git emitted a raw change before its commit metadata.")
        match = RAW_CHANGE.match(line)
        if not match:
            raise AuditError(f"Could not parse Git raw change: {line}")
        current.changes.append(
            RawChange(
                old_object=match.group(1),
                new_object=match.group(2),
                status=match.group(3),
                path=match.group(4),
            )
        )
    return commits


def is_bot_author(commit: CommitRecord) -> bool:
    identity = f"{commit.author_name} {commit.author_email}".casefold()
    return "[bot]" in identity or "copilot" in identity


def classify_commit(
    commit: CommitRecord,
    official_commits: set[str],
    bulk_threshold: int,
) -> str:
    file_count = len(commit.changes)
    if commit.commit in official_commits or (
        file_count >= 100 and OFFICIAL_IMPORT_SUBJECT.search(commit.subject)
    ):
        return "excluded_official_import"
    if file_count > bulk_threshold:
        return "excluded_bulk"
    if is_bot_author(commit):
        return "review_bot_authored"
    if MECHANICAL_SUBJECT.search(commit.subject):
        return "review_mechanical"
    return "eligible_human"


def current_segment(document: dict[str, Any], index: int, origin: str) -> dict[str, Any] | None:
    segments = legacy_segments(document, origin)
    return segments[index] if index < len(segments) else None


def build_target_index(
    target_documents: dict[str, dict[str, Any]],
    target_prefix: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    by_basename: dict[str, list[dict[str, Any]]] = defaultdict(list)
    revisions = 0
    official_revisions = 0
    manual_revisions = 0
    invalid_paths = 0
    for path, document in target_documents.items():
        filename = document.get("filename")
        values = document.get("revisions")
        if (
            document.get("schemaVersion") != TRANSCRIPT_SCHEMA_VERSION
            or not isinstance(filename, str)
            or not isinstance(values, list)
        ):
            raise AuditError(f"Unsupported target transcript structure: {path}")
        expected = f"{target_prefix.rstrip('/')}/{filename}.json"
        if path.casefold() != expected.casefold():
            invalid_paths += 1
        normalized_revisions: list[dict[str, Any]] = []
        for index, revision in enumerate(values):
            if not isinstance(revision, dict):
                raise AuditError(f"Target revision {index} is not an object: {path}")
            if not isinstance(revision.get("text"), str) or not isinstance(revision.get("source"), str):
                raise AuditError(f"Target revision {index} has an invalid text/source: {path}")
            hashes = revision.get("sha256")
            if not isinstance(hashes, list) or any(not valid_sha256(value) for value in hashes):
                raise AuditError(f"Target revision {index} has invalid SHA-256 values: {path}")
            normalized_revisions.append(revision)
            revisions += 1
            official_revisions += revision.get("source") == "official"
            manual_revisions += revision.get("source") == "manual"
        by_basename[PurePosixPath(path).name.casefold()].append(
            {"path": path, "filename": filename, "revisions": normalized_revisions}
        )
    return by_basename, {
        "documents": len(target_documents),
        "revisions": revisions,
        "officialRevisions": official_revisions,
        "manualRevisions": manual_revisions,
        "invalidMirroredPaths": invalid_paths,
        "ambiguousBasenameGroups": sum(len(values) > 1 for values in by_basename.values()),
    }


def target_matches(record: dict[str, Any], target_index: dict[str, list[dict[str, Any]]]) -> None:
    basename = PurePosixPath(record["legacyPath"]).name.casefold()
    documents = target_index.get(basename, [])
    record["targetDocumentCandidates"] = len(documents)
    if not documents:
        record["status"] = "no_target"
        record["targetMatches"] = []
        return

    before = normalize_text(record.get("beforeFullText"))
    desired = normalize_text(record["currentFullText"])
    matches: list[dict[str, Any]] = []
    for document in documents:
        for revision in document["revisions"]:
            target_text = normalize_text(revision.get("text"))
            match_kind = ""
            if target_text == desired:
                match_kind = "current"
            elif record.get("beforeFullText") is not None and target_text == before:
                match_kind = "before"
            if not match_kind:
                continue
            source = revision.get("source")
            action = "protected"
            if source == "manual" and match_kind == "current":
                action = "none"
            elif source != "official":
                action = "mark_manual" if match_kind == "current" else "replace_text_and_mark_manual"
            matches.append(
                {
                    "path": document["path"],
                    "filename": document["filename"],
                    "sha256": (
                        revision["sha256"][0]
                        if isinstance(revision.get("sha256"), list) and revision["sha256"]
                        else None
                    ),
                    "groupSha256": (
                        revision["sha256"]
                        if isinstance(revision.get("sha256"), list)
                        else []
                    ),
                    "source": source,
                    "match": match_kind,
                    "proposedAction": action,
                }
            )
    record["targetMatches"] = matches

    matched_paths = {value["path"] for value in matches}
    nonofficial = [value for value in matches if value["source"] != "official"]
    official = [value for value in matches if value["source"] == "official"]
    if len(matched_paths) > 1:
        record["status"] = "ambiguous_path"
    elif nonofficial:
        if len(nonofficial) > 1:
            record["status"] = "ambiguous_revision"
        elif not valid_sha256(nonofficial[0].get("sha256")):
            record["status"] = "review_missing_sha"
        elif all(value["source"] == "manual" and value["match"] == "current" for value in nonofficial):
            record["status"] = "already_manual"
        else:
            record["status"] = "candidate_manual"
        record["officialRevisionsProtected"] = len(official)
    elif official:
        if all(value["match"] == "current" for value in official):
            record["status"] = "official_already_matches"
        else:
            record["status"] = "blocked_official"
    elif len(documents) == 1 and all(
        revision.get("source") == "official" for revision in documents[0]["revisions"]
    ):
        record["status"] = "blocked_official"
    else:
        record["status"] = "no_exact_revision_match"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    statuses = summary["recordsByStatus"]
    authors = summary["candidateAuthors"]
    lines = [
        "# Legacy manual-contribution audit",
        "",
        "> Audit only: this report did not modify transcripts or categories.",
        "",
        "## Pinned inputs",
        "",
        "| Input | Ref | Commit | Files |",
        "| --- | --- | --- | ---: |",
        f"| Legacy | `{report['legacy']['ref']}` | `{report['legacy']['commit']}` | {summary['legacyFiles']:,} |",
        f"| Target | `{report['target']['ref']}` | `{report['target']['commit']}` | {summary['targetDocuments']:,} |",
        "",
        "## Safety checks",
        "",
        f"- Protected official revisions: **{summary['officialRevisions']:,}**",
        f"- Existing manual revisions: **{summary['existingManualRevisions']:,}**",
        f"- Invalid target mirrored paths: **{summary['invalidTargetMirroredPaths']:,}**",
        f"- Ambiguous target basename groups: **{summary['ambiguousTargetBasenameGroups']:,}**",
        "- No content mutation code is present in this audit command.",
        "",
        "## Record classifications",
        "",
        "| Status | Records |",
        "| --- | ---: |",
    ]
    for status, count in sorted(statuses.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{status}` | {count:,} |")
    lines.extend(
        [
            "",
            "## High-confidence candidate authors",
            "",
            "| Author | Email | Records |",
            "| --- | --- | ---: |",
        ]
    )
    for author in authors:
        safe_name = author["name"].replace("|", "\\|")
        safe_email = author["email"].replace("|", "\\|")
        lines.append(f"| {safe_name} | `{safe_email}` | {author['records']:,} |")
    if not authors:
        lines.append("| _None_ |  | 0 |")
    lines.extend(
        [
            "",
            "## Commit exclusions and review queues",
            "",
            "| Disposition | Commits | Data-file changes |",
            "| --- | ---: | ---: |",
        ]
    )
    for disposition, values in sorted(report["commitSummary"].items()):
        lines.append(
            f"| `{disposition}` | {values['commits']:,} | {values['dataFileChanges']:,} |"
        )
    lines.extend(
        [
            "",
            "The JSON report contains the original author metadata, legacy before/after text,",
            "target revision hashes, and the reason for every surviving contribution decision.",
            "Only `candidate_manual` records with exactly one non-official SHA revision are",
            "eligible for automatic replay in stage 2.",
            "",
        ]
    )
    return "\n".join(lines)


def audit(
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
    legacy_tree = {
        path: object_id
        for path, object_id in list_tree(repo, legacy_commit, legacy_prefix).items()
        if path.endswith(".json")
    }
    target_tree = {
        path: object_id
        for path, object_id in list_tree(repo, target_commit, target_prefix).items()
        if path.endswith(".json")
    }
    tree_blobs = read_blobs(repo, [*legacy_tree.values(), *target_tree.values()])
    current_legacy = {
        path: parse_json_blob(tree_blobs[object_id], f"{legacy_commit}:{path}")
        for path, object_id in legacy_tree.items()
    }
    target_documents = {
        path: parse_json_blob(tree_blobs[object_id], f"{target_commit}:{path}")
        for path, object_id in target_tree.items()
    }
    target_index, target_stats = build_target_index(target_documents, target_prefix)

    commits = parse_history(repo, legacy_commit, legacy_prefix)
    for commit in commits:
        commit.disposition = classify_commit(commit, official_commits, bulk_threshold)
    inspectable = [
        commit
        for commit in commits
        if commit.disposition not in {"excluded_official_import", "excluded_bulk"}
    ]
    history_objects = {
        object_id
        for commit in inspectable
        for change in commit.changes
        for object_id in (change.old_object, change.new_object)
        if object_id != ZERO_OBJECT and change.status in {"A", "M"}
    }
    history_blobs = read_blobs(repo, history_objects)

    selected: dict[tuple[str, int], ContributionEvent] = {}
    superseded_events = 0
    invalid_history_events = 0
    structural_events = 0
    addition_events = 0
    for commit in inspectable:
        for change in commit.changes:
            if change.status not in {"A", "M"} or not change.path.endswith(".json"):
                continue
            try:
                new_document = parse_json_blob(
                    history_blobs[change.new_object], f"{commit.commit}:{change.path}"
                )
                old_document = (
                    parse_json_blob(
                        history_blobs[change.old_object],
                        f"{commit.commit}^:{change.path}",
                    )
                    if change.old_object != ZERO_OBJECT
                    else None
                )
                segment_changes, text_only, before_full, after_full = compare_legacy_documents(
                    old_document, new_document, f"{commit.commit}:{change.path}"
                )
            except AuditError:
                invalid_history_events += 1
                continue
            if not segment_changes:
                continue
            if old_document is None:
                addition_events += len(segment_changes)
            elif not text_only:
                structural_events += len(segment_changes)
            current_document = current_legacy.get(change.path)
            if current_document is None:
                superseded_events += len(segment_changes)
                continue
            current_full = full_legacy_text(current_document, f"{legacy_commit}:{change.path}")
            for segment_change in segment_changes:
                current_value = current_segment(
                    current_document, segment_change.index, f"{legacy_commit}:{change.path}"
                )
                if current_value is None or current_value.get("text") != segment_change.after:
                    superseded_events += 1
                    continue
                selected[(change.path, segment_change.index)] = ContributionEvent(
                    commit=commit,
                    legacy_path=change.path,
                    change_kind="added_file" if old_document is None else "modified_file",
                    text_only=text_only,
                    before_full_text=before_full,
                    after_full_text=after_full,
                    current_full_text=current_full,
                    segment=segment_change,
                )

    grouped: dict[tuple[str, str], list[ContributionEvent]] = defaultdict(list)
    commits_by_legacy_path: dict[str, set[str]] = defaultdict(set)
    for event in selected.values():
        grouped[(event.commit.commit, event.legacy_path)].append(event)
        commits_by_legacy_path[event.legacy_path].add(event.commit.commit)

    records: list[dict[str, Any]] = []
    for (_commit_id, legacy_path), events in grouped.items():
        events.sort(key=lambda value: value.segment.index)
        event = events[0]
        record: dict[str, Any] = {
            "status": "",
            "legacyPath": legacy_path,
            "legacyCommit": event.commit.commit,
            "legacySubject": event.commit.subject,
            "author": {
                "name": event.commit.author_name,
                "email": event.commit.author_email,
                "date": event.commit.author_date,
            },
            "commitDisposition": event.commit.disposition,
            "changeKind": event.change_kind,
            "textOnly": event.text_only,
            "beforeFullText": event.before_full_text,
            "afterFullText": event.after_full_text,
            "currentFullText": event.current_full_text,
            "changedSegments": [
                {
                    "index": value.segment.index,
                    "part": value.segment.part,
                    "before": value.segment.before,
                    "after": value.segment.after,
                }
                for value in events
            ],
        }
        target_matches(record, target_index)
        if len(commits_by_legacy_path[legacy_path]) > 1:
            record["status"] = "review_multiple_contributions"
        elif event.change_kind == "added_file":
            record["status"] = "review_added_file"
        elif not event.text_only:
            record["status"] = "review_structural_change"
        elif event.commit.disposition != "eligible_human" and record["status"] == "candidate_manual":
            record["status"] = event.commit.disposition
        records.append(record)
    records.sort(key=lambda value: (value["legacyCommit"], value["legacyPath"]))

    status_counts = Counter(record["status"] for record in records)
    candidate_authors: Counter[tuple[str, str]] = Counter()
    for record in records:
        if record["status"] == "candidate_manual":
            candidate_authors[(record["author"]["name"], record["author"]["email"])] += 1

    commit_summary: dict[str, dict[str, int]] = {}
    for disposition, values in sorted(
        ((key, [commit for commit in commits if commit.disposition == key]) for key in {c.disposition for c in commits}),
        key=lambda item: item[0],
    ):
        commit_summary[disposition] = {
            "commits": len(values),
            "dataFileChanges": sum(len(commit.changes) for commit in values),
        }

    excluded_commits = [
        {
            "commit": commit.commit,
            "subject": commit.subject,
            "author": {
                "name": commit.author_name,
                "email": commit.author_email,
                "date": commit.author_date,
            },
            "disposition": commit.disposition,
            "dataFileChanges": len(commit.changes),
        }
        for commit in commits
        if commit.disposition in {"excluded_official_import", "excluded_bulk"}
    ]
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "mode": "audit-only",
        "legacy": {"ref": legacy_ref, "commit": legacy_commit, "prefix": legacy_prefix},
        "target": {"ref": target_ref, "commit": target_commit, "prefix": target_prefix},
        "policy": {
            "bulkCommitFileThreshold": bulk_threshold,
            "officialImportCommits": sorted(official_commits),
            "officialRevisionsMutable": False,
            "uniqueNonOfficialRevisionRequired": True,
            "fuzzyMatchingMayAutoApply": False,
            "botAuthoredChangesMayAutoApply": False,
        },
        "summary": {
            "legacyFiles": len(legacy_tree),
            "targetDocuments": target_stats["documents"],
            "targetRevisions": target_stats["revisions"],
            "officialRevisions": target_stats["officialRevisions"],
            "existingManualRevisions": target_stats["manualRevisions"],
            "invalidTargetMirroredPaths": target_stats["invalidMirroredPaths"],
            "ambiguousTargetBasenameGroups": target_stats["ambiguousBasenameGroups"],
            "legacyCommits": len(commits),
            "survivingContributionRecords": len(records),
            "supersededTextEvents": superseded_events,
            "structuralTextEvents": structural_events,
            "addedFileTextEvents": addition_events,
            "invalidHistoryEvents": invalid_history_events,
            "recordsByStatus": dict(sorted(status_counts.items())),
            "candidateAuthors": [
                {"name": name, "email": email, "records": count}
                for (name, email), count in sorted(
                    candidate_authors.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        },
        "commitSummary": commit_summary,
        "excludedCommits": excluded_commits,
        "records": records,
    }


def safe_output_path(repo: Path, value: str, protected_prefixes: Iterable[str]) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo / path
    resolved = path.resolve()
    for prefix in protected_prefixes:
        protected = (repo / prefix).resolve()
        try:
            resolved.relative_to(protected)
        except ValueError:
            continue
        raise AuditError(f"Audit reports may not be written below {protected}.")
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit surviving legacy transcript contributions without modifying content."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--legacy-ref", default="main")
    parser.add_argument("--target-ref", default="HEAD")
    parser.add_argument("--legacy-prefix", default="data")
    parser.add_argument("--target-prefix", default="transcripts")
    parser.add_argument("--bulk-threshold", type=int, default=500)
    parser.add_argument(
        "--official-commit",
        action="append",
        default=[],
        help="Additional legacy commit to classify as an official import.",
    )
    parser.add_argument(
        "--output-json", default="migration-reports/manual-contribution-audit.json"
    )
    parser.add_argument(
        "--output-markdown", default="migration-reports/manual-contribution-audit.md"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        official_commits = DEFAULT_OFFICIAL_IMPORT_COMMITS | set(args.official_commit)
        report = audit(
            repo=repo,
            legacy_ref=args.legacy_ref,
            target_ref=args.target_ref,
            legacy_prefix=args.legacy_prefix.strip("/"),
            target_prefix=args.target_prefix.strip("/"),
            bulk_threshold=args.bulk_threshold,
            official_commits=official_commits,
        )
        json_path = safe_output_path(
            repo, args.output_json, (args.legacy_prefix, args.target_prefix, "config")
        )
        markdown_path = safe_output_path(
            repo, args.output_markdown, (args.legacy_prefix, args.target_prefix, "config")
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
