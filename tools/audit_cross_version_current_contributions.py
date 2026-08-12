#!/usr/bin/env python3
"""Search every version manifest for current corrections rejected on OGNB text."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from apply_current_contributions import read_json
from audit_cross_version_historical_contributions import (
    build_catalog,
    classify_records,
    load_documents,
    parse_root_manifest,
)
from audit_latest_version_contributions import fetch_manifest
from audit_legacy_contributions import (
    AuditError,
    build_target_index,
    git,
    resolve_ref,
    safe_output_path,
)


REPORT_SCHEMA_VERSION = 1


def as_epoch(record: dict[str, Any]) -> dict[str, Any]:
    event = {
        "legacyCommit": record["legacyCommit"],
        "legacySubject": record["legacySubject"],
        "author": record["author"],
        "beforeFullText": record["beforeFullText"],
        "afterFullText": record["currentFullText"],
        "changedSegments": record["changedSegments"],
    }
    return {
        "epochId": f"{record['legacyPath']}@{record['legacyCommit']}",
        "legacyPath": record["legacyPath"],
        "legacyPathDeleted": False,
        "initialText": record["beforeFullText"],
        "finalText": record["currentFullText"],
        "events": [event],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    candidates = [
        record
        for record in report["records"]
        if record["status"] == "candidate_cross_version_current_review"
    ]
    lines = [
        "# Cross-version current contribution audit",
        "",
        "> Review only: this report did not modify transcripts or categories.",
        "",
        "## Dataset and grain",
        "",
        f"- OGNB active-SHA text divergences: **{summary['activeShaDivergences']:,}**",
        f"- Published version manifests scanned: **{summary['versionManifests']:,}**",
        "- Candidate grain: one correction, one transcript path, one older audio SHA, and one exact text state.",
        "",
        "## Findings",
        "",
        "| Status | Corrections | Share |",
        "| --- | ---: | ---: |",
    ]
    for status, count in sorted(
        summary["recordsByStatus"].items(), key=lambda item: (-item[1], item[0])
    ):
        share = count / summary["activeShaDivergences"] if summary["activeShaDivergences"] else 0
        lines.append(f"| `{status}` | {count:,} | {share:.1%} |")
    lines.extend(
        [
            "",
            "## Unique older-SHA review candidates",
            "",
            "| Legacy path | Author/date | Before | After | SHA | Matching versions | Action |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in candidates:
        event = record["attributionEvents"][0]
        target = record["selectedTarget"]
        versions = ", ".join(value["versionId"] for value in target["manifestVersions"])
        values = [
            record["legacyPath"],
            f"{event['author']['name']} ({event['author']['date']})",
            event["beforeFullText"],
            event["afterFullText"],
        ]
        values = [value.replace("|", "\\|").replace("\n", " ") for value in values]
        lines.append(
            f"| `{values[0]}` | {values[1]} | {values[2]} | {values[3]} | "
            f"`{target['sha256'][:12]}` | `{versions}` | `{target['proposedAction']}` |"
        )
    if not candidates:
        lines.append("| _None_ |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The correction date selected OGNB's active SHA for the first pass, but the",
            "legacy repository did not store an audio hash. Every divergence here has an",
            "exact state on at least one older SHA. Unique generated matches are suitable",
            "for explicit review; multiple-SHA matches remain ambiguous. No semantic text",
            "transfer is needed for this set.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search all manifests for current corrections divergent on OGNB."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--latest-audit",
        type=Path,
        default=Path("migration-reports/latest-version-current-contribution-audit.json"),
    )
    parser.add_argument(
        "--release-map",
        type=Path,
        default=Path("config/deadlock/version-releases.json"),
    )
    parser.add_argument(
        "--output-json",
        default="migration-reports/cross-version-current-contribution-audit.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="migration-reports/cross-version-current-contribution-audit.md",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        latest_path = args.latest_audit if args.latest_audit.is_absolute() else repo / args.latest_audit
        release_map_path = args.release_map if args.release_map.is_absolute() else repo / args.release_map
        latest = read_json(latest_path)
        if latest.get("mode") != "latest-version-audit-only":
            raise AuditError("The input is not a latest-version contribution audit.")
        divergent = [
            record
            for record in latest.get("records", [])
            if record.get("status") == "review_latest_text_diverged"
        ]
        epochs = [as_epoch(record) for record in divergent]
        assignments = {
            epoch["epochId"]: [
                {"versionId": "ognb", "status": "review_latest_text_diverged"}
            ]
            for epoch in epochs
        }
        target_paths = {record["selectedTarget"]["path"] for record in divergent}
        target_commit = resolve_ref(repo, latest["target"]["commit"])
        target_documents = load_documents(repo, target_commit, target_paths)
        target_index, target_stats = build_target_index(
            target_documents, latest["target"]["prefix"]
        )
        current_commit = resolve_ref(repo, "HEAD")
        current_documents = load_documents(repo, current_commit, target_paths)
        relevant_filenames = {record["filename"] for record in divergent}

        release_map = read_json(release_map_path)
        root_url = release_map.get("rootManifestUrl")
        if not isinstance(root_url, str) or not root_url.startswith("https://"):
            raise AuditError("The release map has no valid rootManifestUrl.")
        root_content, root_headers = fetch_manifest(root_url)
        root_summary, versions = parse_root_manifest(root_content)
        catalog, manifest_reports = build_catalog(versions, relevant_filenames)
        records = classify_records(
            epochs, assignments, target_index, current_documents, catalog
        )
        for record in records:
            if record["status"] == "candidate_historical_version_review":
                record["status"] = "candidate_cross_version_current_review"
                record["temporalRisk"] = "legacy_current_file_not_ognb_active_recording"
        statuses = Counter(record["status"] for record in records)
        candidates = [
            record
            for record in records
            if record["status"] == "candidate_cross_version_current_review"
        ]
        candidate_events = [record["attributionEvents"][0] for record in candidates]
        authors = Counter(
            (event["author"]["name"], event["author"]["email"])
            for event in candidate_events
        )
        report = {
            "schemaVersion": REPORT_SCHEMA_VERSION,
            "mode": "cross-version-current-audit-only",
            "latestAudit": {
                "path": latest_path.relative_to(repo).as_posix(),
                "contentSha256": hashlib.sha256(latest_path.read_bytes()).hexdigest(),
            },
            "target": {**latest["target"], "observedHeadCommit": current_commit},
            "releaseMap": {
                "path": release_map_path.relative_to(repo).as_posix(),
                "contentSha256": hashlib.sha256(release_map_path.read_bytes()).hexdigest(),
            },
            "rootManifest": {
                "url": root_url,
                "contentSha256": hashlib.sha256(root_content).hexdigest(),
                **root_headers,
                **root_summary,
            },
            "versionManifests": manifest_reports,
            "policy": {
                "reportOnly": True,
                "officialRevisionsMutable": False,
                "eligibleTargetSources": ["generated"],
                "allRootManifestVersionsScanned": True,
                "uniqueTranscriptPathRequired": True,
                "uniqueAudioRevisionRequired": True,
                "exactTextAnchorRequired": True,
                "currentHeadConflictCheckRequired": True,
                "temporalMismatchMayAutoApply": False,
                "fuzzyMatchingMayAutoApply": False,
            },
            "summary": {
                "activeShaDivergences": len(divergent),
                "versionManifests": len(manifest_reports),
                "targetDocuments": target_stats["documents"],
                "reviewCandidates": len(candidates),
                "ambiguousCorrections": statuses["ambiguous_exact_revision"],
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
        protected: Iterable[str] = (latest["target"]["prefix"], "data", "config")
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
    except (AuditError, KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
