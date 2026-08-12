#!/usr/bin/env python3
"""Resolve historical corrections against the manifest active at the time.

Release dates are curated separately from the CDN manifest because manifest
publication timestamps describe CDN ingestion, not the original game release.
This command is audit-only and never edits transcript or configuration files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from apply_current_contributions import read_json
from audit_latest_version_contributions import build_manifest_index, fetch_manifest
from audit_legacy_contributions import (
    AuditError,
    build_target_index,
    git,
    list_tree,
    normalize_text,
    parse_json_blob,
    read_blobs,
    resolve_ref,
    safe_output_path,
)


REPORT_SCHEMA_VERSION = 1


def parse_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise AuditError(f"{label} must be an ISO date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AuditError(f"{label} is not a valid ISO date: {value}") from exc


def select_release(
    release_map: dict[str, Any], version_id: str
) -> dict[str, Any]:
    if release_map.get("schemaVersion") != 1:
        raise AuditError("Unsupported version release-map schema.")
    if release_map.get("dateBasis") != "git-author-offset-calendar-date":
        raise AuditError("The release map has no supported dateBasis.")
    matches = [
        value
        for value in release_map.get("versions", [])
        if isinstance(value, dict) and value.get("id") == version_id
    ]
    if len(matches) != 1:
        raise AuditError(f"Expected one release-map entry for {version_id}; found {len(matches)}.")
    release = dict(matches[0])
    release["activeFrom"] = parse_date(release.get("activeFrom"), "activeFrom")
    release["activeUntilExclusive"] = parse_date(
        release.get("activeUntilExclusive"), "activeUntilExclusive"
    )
    if release["activeUntilExclusive"] <= release["activeFrom"]:
        raise AuditError("activeUntilExclusive must be after activeFrom.")
    for field in ("releaseEvidenceUrl", "supersededEvidenceUrl"):
        if not isinstance(release.get(field), str) or not release[field].startswith("https://"):
            raise AuditError(f"The release-map entry has no valid {field}.")
    return release


def resolve_version_manifest(
    root_content: bytes, version_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        root = json.loads(root_content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"Root manifest is not valid JSON: {exc}") from exc
    matches = [
        value
        for value in root.get("versions", [])
        if isinstance(value, dict) and value.get("id") == version_id
    ]
    if len(matches) != 1:
        raise AuditError(f"Expected one root-manifest version {version_id}; found {len(matches)}.")
    version = matches[0]
    voice_line_url = version.get("voiceLineUrl")
    if not isinstance(voice_line_url, str) or not voice_line_url.startswith("https://"):
        raise AuditError(f"Version {version_id} has no valid voiceLineUrl.")
    root_summary = {
        key: root.get(key)
        for key in ("schemaVersion", "game", "latestVersion", "updatedAt")
    }
    return version, root_summary


def event_local_date(event: dict[str, Any]) -> date:
    value = event.get("author", {}).get("date")
    if not isinstance(value, str):
        raise AuditError("Historical correction event has no author date.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditError(f"Invalid historical author date: {value}") from exc
    if parsed.tzinfo is None:
        raise AuditError(f"Historical author date has no timezone: {value}")
    return parsed.date()


def classify_records(
    historical_report: dict[str, Any],
    target_index: dict[str, list[dict[str, Any]]],
    manifest_index: dict[str, dict[str, list[dict[str, Any]]]],
    release: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    selected_revisions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    active_from = release["activeFrom"]
    active_until = release["activeUntilExclusive"]

    for original in historical_report.get("records", []):
        record = {
            key: original[key]
            for key in (
                "epochId",
                "legacyPath",
                "legacyPathDeleted",
                "initialText",
                "finalText",
                "events",
            )
        }
        dates = [event_local_date(event) for event in record["events"]]
        in_release = [active_from <= value < active_until for value in dates]
        record["eventLocalDates"] = [value.isoformat() for value in dates]
        record["versionId"] = release["id"]
        if any(value in {active_from, active_until} for value in dates):
            record["status"] = "release_boundary_date_review"
            records.append(record)
            continue
        if not any(in_release):
            record["status"] = "outside_selected_version"
            records.append(record)
            continue
        if not all(in_release):
            record["status"] = "crosses_version_boundary"
            records.append(record)
            continue

        basename = PurePosixPath(record["legacyPath"]).name.casefold()
        documents = target_index.get(basename, [])
        record["targetDocumentCandidates"] = len(documents)
        if len(documents) != 1:
            record["status"] = "no_target" if not documents else "ambiguous_path"
            records.append(record)
            continue
        document = documents[0]
        record["targetPath"] = document["path"]
        record["filename"] = document["filename"]
        manifest_hashes = manifest_index.get(document["filename"].casefold(), {})
        if not manifest_hashes:
            record["status"] = "not_in_version_manifest"
            records.append(record)
            continue
        if len(manifest_hashes) != 1:
            record["status"] = "manifest_hash_conflict"
            record["manifestHashes"] = sorted(manifest_hashes)
            records.append(record)
            continue
        sha256 = next(iter(manifest_hashes))
        record["manifestEvidence"] = manifest_hashes[sha256]
        revisions = [
            value for value in document.get("revisions", []) if value.get("sha256") == sha256
        ]
        if len(revisions) != 1:
            record["status"] = (
                "version_revision_missing" if not revisions else "duplicate_version_revision"
            )
            record["versionSha256"] = sha256
            records.append(record)
            continue
        revision = revisions[0]
        target = {
            "path": document["path"],
            "filename": document["filename"],
            "sha256": sha256,
            "source": revision.get("source"),
            "originalText": revision.get("text"),
            "proposedAction": "protected" if revision.get("source") == "official" else "review",
        }
        record["selectedTarget"] = target
        if revision.get("source") == "official":
            record["status"] = "protected_official"
            records.append(record)
            continue
        if revision.get("source") != "generated":
            record["status"] = "review_non_generated_source"
            records.append(record)
            continue

        states = [record["initialText"]] + [
            event["afterFullText"] for event in record["events"]
        ]
        positions = [
            index
            for index, state in enumerate(states)
            if normalize_text(state) == normalize_text(revision.get("text"))
        ]
        record["matchingStatePositions"] = positions
        if not positions:
            record["status"] = "review_version_text_diverged"
        elif len(positions) > 1:
            record["status"] = "ambiguous_state"
        elif positions[0] < len(record["events"]):
            record["status"] = "candidate_replay"
            target["proposedAction"] = "replay_and_mark_manual"
            record["replayEvents"] = record["events"][positions[0] :]
        else:
            record["status"] = "candidate_mark_manual"
            target["proposedAction"] = "mark_manual"
            record["attributionEvent"] = record["events"][-1]

        if record["status"] in {"candidate_replay", "candidate_mark_manual"}:
            selected_revisions[(document["path"], sha256)].append(record)
        records.append(record)

    for conflicts in selected_revisions.values():
        if len(conflicts) > 1:
            for record in conflicts:
                record["status"] = "ambiguous_history"
                record["selectedTarget"]["proposedAction"] = "review"
                record.pop("replayEvents", None)
                record.pop("attributionEvent", None)
    records.sort(key=lambda value: (value["legacyPath"], value["epochId"]))
    return records


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    release = report["release"]
    lines = [
        f"# {release['label']} historical contribution audit",
        "",
        "> Audit only: this report did not modify transcripts or categories.",
        "",
        "## Selected release",
        "",
        f"- Version: `{release['id']}`",
        f"- Active dates: `{release['activeFrom']}` through `{release['activeUntilExclusive']}` (exclusive)",
        f"- Date basis: `{release['dateBasis']}`",
        f"- Root manifest: {report['rootManifest']['url']}",
        f"- Voice-line manifest: {report['versionManifest']['url']}",
        f"- Release evidence: {release['releaseEvidenceUrl']}",
        f"- Superseding-release evidence: {release['supersededEvidenceUrl']}",
        "",
        "## Classifications",
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
            "## Candidate actions",
            "",
            f"- Replay corrected text and mark manual: **{summary['replayCandidates']:,}**",
            f"- Mark an already-correct revision manual: **{summary['markManualCandidates']:,}**",
            f"- Correction events represented: **{summary['candidateCorrectionEvents']:,}**",
            "",
            "Candidates require an in-window correction date, one transcript path, the",
            "version manifest's unique audio SHA, a generated target revision, and one",
            "exact historical text state. Official revisions remain protected.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_versioned_historical(
    repo: Path,
    historical_path: Path,
    release_map_path: Path,
    version_id: str,
    root_content: bytes,
    root_headers: dict[str, str | None],
    version_content: bytes,
    version_headers: dict[str, str | None],
    version_entry: dict[str, Any],
    root_summary: dict[str, Any],
) -> dict[str, Any]:
    historical = read_json(historical_path)
    if historical.get("mode") != "historical-audit-only":
        raise AuditError("The input is not a historical-contribution audit.")
    release_map = read_json(release_map_path)
    release = select_release(release_map, version_id)
    target_commit = resolve_ref(repo, historical["target"]["commit"])
    target_prefix = historical["target"]["prefix"]
    tree = {
        path: object_id
        for path, object_id in list_tree(repo, target_commit, target_prefix).items()
        if path.endswith(".json")
    }
    blobs = read_blobs(repo, tree.values())
    documents = {
        path: parse_json_blob(blobs[object_id], f"{target_commit}:{path}")
        for path, object_id in tree.items()
    }
    target_index, target_stats = build_target_index(documents, target_prefix)
    manifest_index, manifest_stats = build_manifest_index(version_content)
    records = classify_records(historical, target_index, manifest_index, release)
    statuses = Counter(record["status"] for record in records)
    candidates = [
        record
        for record in records
        if record["status"] in {"candidate_replay", "candidate_mark_manual"}
    ]
    candidate_events = [
        event
        for record in candidates
        for event in (
            record.get("replayEvents", [])
            if record["status"] == "candidate_replay"
            else [record["attributionEvent"]]
        )
    ]
    authors = Counter(
        (event["author"]["name"], event["author"]["email"])
        for event in candidate_events
    )
    release_report = {
        **{
            key: value
            for key, value in release.items()
            if key not in {"activeFrom", "activeUntilExclusive"}
        },
        "activeFrom": release["activeFrom"].isoformat(),
        "activeUntilExclusive": release["activeUntilExclusive"].isoformat(),
        "dateBasis": release_map["dateBasis"],
    }
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "mode": "versioned-historical-audit-only",
        "historicalAudit": {
            "path": historical_path.relative_to(repo).as_posix(),
            "legacyCommit": historical["legacy"]["commit"],
            "targetCommit": historical["target"]["commit"],
        },
        "legacy": historical["legacy"],
        "target": historical["target"],
        "releaseMap": {
            "path": release_map_path.relative_to(repo).as_posix(),
            "contentSha256": hashlib.sha256(release_map_path.read_bytes()).hexdigest(),
        },
        "release": release_report,
        "rootManifest": {
            "url": release_map["rootManifestUrl"],
            "contentSha256": hashlib.sha256(root_content).hexdigest(),
            **root_headers,
            **root_summary,
        },
        "versionManifest": {
            "url": version_entry["voiceLineUrl"],
            "contentSha256": hashlib.sha256(version_content).hexdigest(),
            **version_headers,
            **manifest_stats,
        },
        "policy": {
            "officialRevisionsMutable": False,
            "eligibleTargetSources": ["generated"],
            "selectedReleaseRequired": True,
            "crossVersionReplayAllowed": False,
            "uniqueTranscriptPathRequired": True,
            "uniqueVersionHashRequired": True,
            "uniqueHistoryEpochRequired": True,
            "exactTextAnchorRequired": True,
            "fuzzyMatchingMayAutoApply": False,
        },
        "summary": {
            "historicalEpochs": len(records),
            "epochsInSelectedVersion": sum(
                record["status"] != "outside_selected_version" for record in records
            ),
            "targetDocuments": target_stats["documents"],
            "candidateRevisions": len(candidates),
            "replayCandidates": statuses["candidate_replay"],
            "markManualCandidates": statuses["candidate_mark_manual"],
            "candidateCorrectionEvents": len(candidate_events),
            "candidateActionsOnDeletedPaths": sum(
                record["legacyPathDeleted"] for record in candidates
            ),
            "recordsByStatus": dict(sorted(statuses.items())),
            "candidateAuthors": [
                {"name": name, "email": email, "actions": count}
                for (name, email), count in sorted(
                    authors.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        },
        "records": records,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit historical corrections against a released-version manifest."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--historical-audit",
        type=Path,
        default=Path("migration-reports/historical-contribution-audit.json"),
    )
    parser.add_argument(
        "--release-map",
        type=Path,
        default=Path("config/deadlock/version-releases.json"),
    )
    parser.add_argument("--version-id", default="six-hero-update")
    parser.add_argument(
        "--output-json",
        default="migration-reports/six-hero-update-historical-contribution-audit.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="migration-reports/six-hero-update-historical-contribution-audit.md",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        historical_path = (
            args.historical_audit
            if args.historical_audit.is_absolute()
            else repo / args.historical_audit
        )
        release_map_path = (
            args.release_map if args.release_map.is_absolute() else repo / args.release_map
        )
        release_map = read_json(release_map_path)
        root_url = release_map.get("rootManifestUrl")
        if not isinstance(root_url, str) or not root_url.startswith("https://"):
            raise AuditError("The release map has no valid rootManifestUrl.")
        root_content, root_headers = fetch_manifest(root_url)
        version_entry, root_summary = resolve_version_manifest(root_content, args.version_id)
        version_content, version_headers = fetch_manifest(version_entry["voiceLineUrl"])
        report = audit_versioned_historical(
            repo,
            historical_path,
            release_map_path,
            args.version_id,
            root_content,
            root_headers,
            version_content,
            version_headers,
            version_entry,
            root_summary,
        )
        protected: Iterable[str] = (
            report["target"]["prefix"],
            report["legacy"]["prefix"],
            "config",
        )
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
    except (AuditError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
