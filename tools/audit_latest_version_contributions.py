#!/usr/bin/env python3
"""Resolve current legacy corrections to one version manifest's active audio hashes.

The version manifest supplies the filename-to-audio-SHA relationship missing
from the legacy transcript format. A correction is eligible only when the
active revision already contains either the exact pre-correction text or the
exact corrected text. Divergent re-recordings remain review-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from audit_legacy_contributions import (
    AuditError,
    git,
    normalize_text,
    parse_json_blob,
    read_blobs,
    resolve_ref,
    safe_output_path,
    valid_sha256,
)
from apply_current_contributions import read_json
from transcript_schema import revisions_for_hash


REPORT_SCHEMA_VERSION = 1
AUDIO_KEY = re.compile(r"sha256/[0-9a-f]{2}/([0-9a-f]{64})\.mp3")


def fetch_manifest(url: str) -> tuple[bytes, dict[str, str | None]]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(), {
                "etag": response.headers.get("ETag"),
                "lastModified": response.headers.get("Last-Modified"),
                "contentType": response.headers.get("Content-Type"),
            }
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AuditError(f"Could not fetch version manifest {url}: {exc}") from exc


def manifest_entries(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def visit(current: Any) -> None:
        if isinstance(current, dict):
            if isinstance(current.get("filename"), str) and isinstance(
                current.get("audioKey"), str
            ):
                result.append(current)
            for child in current.values():
                visit(child)
        elif isinstance(current, list):
            for child in current:
                visit(child)

    visit(value)
    return result


def build_manifest_index(
    content: bytes,
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, int]]:
    try:
        value = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"Version manifest is not valid JSON: {exc}") from exc
    by_filename: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    entries = manifest_entries(value)
    invalid_audio_keys = 0
    for entry in entries:
        match = AUDIO_KEY.fullmatch(entry["audioKey"])
        if not match:
            invalid_audio_keys += 1
            continue
        evidence = {
            key: entry[key]
            for key in (
                "filename",
                "audioKey",
                "date",
                "transcription",
                "officialtranscription",
                "duration",
                "versionStatus",
            )
            if key in entry
        }
        values = by_filename[entry["filename"].casefold()][match.group(1)]
        if evidence not in values:
            values.append(evidence)
    return by_filename, {
        "entries": len(entries),
        "uniqueFilenames": len(by_filename),
        "conflictingFilenames": sum(len(values) > 1 for values in by_filename.values()),
        "invalidAudioKeys": invalid_audio_keys,
    }


def is_anchored_human_correction(record: dict[str, Any]) -> bool:
    if record.get("status") == "candidate_manual":
        return True
    return (
        record.get("status") == "ambiguous_revision"
        and record.get("commitDisposition") == "eligible_human"
        and record.get("changeKind") == "modified_file"
        and record.get("textOnly") is True
    )


def classify_records(
    current_report: dict[str, Any],
    target_documents: dict[str, dict[str, Any]],
    manifest_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    selected_revisions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for original in current_report.get("records", []):
        if not is_anchored_human_correction(original):
            continue
        paths = sorted({value["path"] for value in original.get("targetMatches", [])})
        filenames = sorted({value["filename"] for value in original.get("targetMatches", [])})
        record: dict[str, Any] = {
            "status": "",
            "priorAuditStatus": original["status"],
            "legacyPath": original["legacyPath"],
            "legacyCommit": original["legacyCommit"],
            "legacySubject": original["legacySubject"],
            "author": original["author"],
            "beforeFullText": original["beforeFullText"],
            "currentFullText": original["currentFullText"],
            "changedSegments": original["changedSegments"],
        }
        if len(paths) != 1 or len(filenames) != 1:
            record["status"] = "ambiguous_target_document"
            records.append(record)
            continue
        path = paths[0]
        filename = filenames[0]
        record["targetPath"] = path
        record["filename"] = filename
        manifest_hashes = manifest_index.get(filename.casefold(), {})
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
        document = target_documents.get(path)
        if document is None:
            record["status"] = "target_document_missing"
            records.append(record)
            continue
        revisions = revisions_for_hash(document, sha256)
        if len(revisions) != 1:
            record["status"] = (
                "latest_revision_missing" if not revisions else "duplicate_latest_revision"
            )
            record["latestSha256"] = sha256
            records.append(record)
            continue
        revision = revisions[0]
        target = {
            "path": path,
            "filename": filename,
            "sha256": sha256,
            "source": revision["source"],
            "originalText": revision["text"],
            "proposedAction": "protected" if revision["source"] == "official" else "review",
        }
        record["selectedTarget"] = target
        if revision["source"] == "official":
            record["status"] = "protected_latest_official"
            records.append(record)
            continue
        desired = normalize_text(original["currentFullText"])
        before = normalize_text(original.get("beforeFullText"))
        actual = normalize_text(revision["text"])
        if actual == desired:
            record["status"] = "candidate_latest_manual"
            target["match"] = "current"
            target["proposedAction"] = "mark_manual"
        elif original.get("beforeFullText") is not None and actual == before:
            record["status"] = "candidate_latest_manual"
            target["match"] = "before"
            target["proposedAction"] = "replace_text_and_mark_manual"
        else:
            record["status"] = "review_latest_text_diverged"
            target["match"] = "neither"
        identity = (path, sha256)
        if record["status"] == "candidate_latest_manual":
            selected_revisions[identity].append(record)
        records.append(record)
    for values in selected_revisions.values():
        if len(values) > 1:
            for record in values:
                record["status"] = "ambiguous_history"
                record["selectedTarget"]["proposedAction"] = "review"
    records.sort(key=lambda value: (value["legacyCommit"], value["legacyPath"]))
    return records


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Latest-version current contribution audit",
        "",
        "> Audit only: this report did not modify transcripts or categories.",
        "",
        "## Inputs",
        "",
        f"- Current-contribution report: `{report['currentAudit']['path']}`",
        f"- Pinned target commit: `{report['target']['commit']}`",
        f"- Version manifest: {report['manifest']['url']}",
        f"- Manifest SHA-256: `{report['manifest']['contentSha256']}`",
        f"- Manifest ETag: `{report['manifest'].get('etag')}`",
        "",
        "## Latest-hash classifications",
        "",
        "| Status | Corrections |",
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
            f"- Latest revisions already containing corrected text: **{summary['markManualActions']:,}**",
            f"- Latest revisions containing exact pre-correction text: **{summary['replaceTextActions']:,}**",
            f"- Candidate latest revisions: **{summary['candidateLatestCorrections']:,}**",
            "",
            "A latest revision is eligible only when its text exactly matches the legacy",
            "pre-correction or corrected state. Divergent re-recordings, absent filenames,",
            "conflicts, and official revisions remain review-only.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_latest_version(
    repo: Path,
    current_audit_path: Path,
    manifest_url: str,
    manifest_content: bytes,
    manifest_headers: dict[str, str | None],
) -> dict[str, Any]:
    current_report = read_json(current_audit_path)
    if current_report.get("mode") != "audit-only":
        raise AuditError("The input is not a current-contribution audit report.")
    target_commit = resolve_ref(repo, current_report["target"]["commit"])
    manifest_index, manifest_stats = build_manifest_index(manifest_content)
    eligible = [
        value for value in current_report.get("records", []) if is_anchored_human_correction(value)
    ]
    paths = {
        match["path"]
        for record in eligible
        for match in record.get("targetMatches", [])
    }
    object_ids: dict[str, str] = {}
    for path in sorted(paths):
        object_id = str(git(repo, "rev-parse", f"{target_commit}:{path}")).strip()
        object_ids[path] = object_id
    blobs = read_blobs(repo, object_ids.values())
    target_documents = {
        path: parse_json_blob(blobs[object_id], f"{target_commit}:{path}")
        for path, object_id in object_ids.items()
    }
    records = classify_records(current_report, target_documents, manifest_index)
    statuses = Counter(record["status"] for record in records)
    candidates = [value for value in records if value["status"] == "candidate_latest_manual"]
    authors: Counter[tuple[str, str]] = Counter(
        (value["author"]["name"], value["author"]["email"]) for value in candidates
    )
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "mode": "latest-version-audit-only",
        "currentAudit": {
            "path": current_audit_path.relative_to(repo).as_posix(),
            "targetCommit": current_report["target"]["commit"],
        },
        "target": current_report["target"],
        "manifest": {
            "url": manifest_url,
            "contentSha256": hashlib.sha256(manifest_content).hexdigest(),
            **manifest_headers,
            **manifest_stats,
        },
        "policy": {
            "officialRevisionsMutable": False,
            "latestManifestHashRequired": True,
            "exactLegacyStateMatchRequired": True,
            "divergentLatestTextMayAutoApply": False,
            "fuzzyMatchingMayAutoApply": False,
        },
        "summary": {
            "anchoredHumanCorrections": len(records),
            "candidateLatestCorrections": len(candidates),
            "markManualActions": sum(
                value["selectedTarget"]["proposedAction"] == "mark_manual"
                for value in candidates
            ),
            "replaceTextActions": sum(
                value["selectedTarget"]["proposedAction"]
                == "replace_text_and_mark_manual"
                for value in candidates
            ),
            "recordsByStatus": dict(sorted(statuses.items())),
            "candidateAuthors": [
                {"name": name, "email": email, "records": count}
                for (name, email), count in sorted(
                    authors.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        },
        "records": records,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit current corrections against a version's active audio hashes."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--current-audit",
        type=Path,
        default=Path("migration-reports/manual-contribution-audit.json"),
    )
    parser.add_argument("--manifest-url", required=True)
    parser.add_argument(
        "--output-json",
        default="migration-reports/latest-version-current-contribution-audit.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="migration-reports/latest-version-current-contribution-audit.md",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        current_path = args.current_audit if args.current_audit.is_absolute() else repo / args.current_audit
        content, headers = fetch_manifest(args.manifest_url)
        report = audit_latest_version(repo, current_path, args.manifest_url, content, headers)
        protected: Iterable[str] = (
            report["target"]["prefix"],
            report.get("legacy", {}).get("prefix", "data"),
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
