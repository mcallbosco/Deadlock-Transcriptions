#!/usr/bin/env python3
"""Search every published version manifest for unresolved historical anchors.

This is a diagnostic-only pass. A correction submitted while one version was
active may refer to an older recording, so exact matches found in other version
snapshots are presented for review and are never made automatically eligible.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
from collections import Counter, defaultdict
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
    valid_sha256,
)


REPORT_SCHEMA_VERSION = 1
CANDIDATE_STATUSES = {"candidate_replay", "candidate_mark_manual"}
OUTSIDE_STATUSES = {"outside_selected_version"}


def parse_root_manifest(content: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        root = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"Root manifest is not valid JSON: {exc}") from exc
    versions = root.get("versions")
    if not isinstance(versions, list) or not versions:
        raise AuditError("Root manifest has no versions.")
    ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for order, value in enumerate(versions):
        if not isinstance(value, dict):
            raise AuditError("Root manifest contains a non-object version.")
        version_id = value.get("id")
        url = value.get("voiceLineUrl")
        if not isinstance(version_id, str) or not version_id or version_id in ids:
            raise AuditError(f"Root manifest has an invalid or duplicate version ID: {version_id}")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise AuditError(f"Version {version_id} has no valid voiceLineUrl.")
        ids.add(version_id)
        normalized.append(
            {
                "id": version_id,
                "label": value.get("label", version_id),
                "order": order,
                "voiceLineUrl": url,
                "publishedAt": value.get("publishedAt"),
                "updatedAt": value.get("updatedAt"),
                "contentRevision": value.get("contentRevision"),
            }
        )
    summary = {
        key: root.get(key)
        for key in ("schemaVersion", "game", "latestVersion", "updatedAt")
    }
    summary["versions"] = len(normalized)
    return summary, normalized


def unresolved_records(
    historical: dict[str, Any], scoped_reports: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, str]]], set[str]]:
    historical_by_id = {record["epochId"]: record for record in historical.get("records", [])}
    assignments: dict[str, list[dict[str, str]]] = defaultdict(list)
    resolved: set[str] = set()
    for report in scoped_reports:
        if report.get("mode") != "versioned-historical-audit-only":
            raise AuditError("A scope input is not a versioned historical audit.")
        version_id = report.get("release", {}).get("id")
        if not isinstance(version_id, str):
            raise AuditError("A scope audit has no release ID.")
        for record in report.get("records", []):
            status = record.get("status")
            if status in OUTSIDE_STATUSES:
                continue
            epoch_id = record.get("epochId")
            if epoch_id not in historical_by_id:
                raise AuditError(f"Scope audit references unknown epoch: {epoch_id}")
            assignments[epoch_id].append({"versionId": version_id, "status": status})
            if status in CANDIDATE_STATUSES or status == "protected_official":
                resolved.add(epoch_id)
    unresolved = [
        record
        for record in historical.get("records", [])
        if record["epochId"] not in resolved
    ]
    return unresolved, assignments, resolved


def build_catalog(
    versions: list[dict[str, Any]], relevant_filenames: set[str]
) -> tuple[
    dict[str, dict[str, list[dict[str, Any]]]],
    list[dict[str, Any]],
]:
    catalog: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    manifest_reports: list[dict[str, Any]] = []
    for index, version in enumerate(versions, 1):
        print(f"Fetching manifest {index}/{len(versions)}: {version['id']}", flush=True)
        content, headers = fetch_manifest(version["voiceLineUrl"])
        manifest_index, stats = build_manifest_index(content)
        matched_filenames = 0
        matched_hashes = 0
        for filename in relevant_filenames:
            hashes = manifest_index.get(filename.casefold(), {})
            if hashes:
                matched_filenames += 1
            for sha256, evidence in hashes.items():
                matched_hashes += 1
                catalog[filename.casefold()][sha256].append(
                    {
                        "versionId": version["id"],
                        "versionLabel": version["label"],
                        "versionOrder": version["order"],
                        "manifestEvidence": evidence,
                    }
                )
        manifest_reports.append(
            {
                **version,
                "contentSha256": hashlib.sha256(content).hexdigest(),
                **headers,
                **stats,
                "relevantFilenamesPresent": matched_filenames,
                "relevantHashes": matched_hashes,
            }
        )
        del content, manifest_index
        gc.collect()
    return catalog, manifest_reports


def desired_state(record: dict[str, Any], position: int) -> tuple[str, list[dict[str, Any]]]:
    if position < len(record["events"]):
        events = record["events"][position:]
        return events[-1]["afterFullText"], events
    return record["finalText"], [record["events"][-1]]


def classify_records(
    records: list[dict[str, Any]],
    assignments: dict[str, list[dict[str, str]]],
    target_index: dict[str, list[dict[str, Any]]],
    current_documents: dict[str, dict[str, Any]],
    catalog: dict[str, dict[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    selected_revisions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for original in records:
        result = {
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
        result["assignedReleaseResults"] = assignments.get(original["epochId"], [])
        documents = target_index.get(PurePosixPath(original["legacyPath"]).name.casefold(), [])
        result["targetDocumentCandidates"] = len(documents)
        if len(documents) != 1:
            result["status"] = "no_target" if not documents else "ambiguous_path"
            results.append(result)
            continue
        document = documents[0]
        result["targetPath"] = document["path"]
        result["filename"] = document["filename"]
        hashes = catalog.get(document["filename"].casefold(), {})
        result["manifestHashes"] = len(hashes)
        if not hashes:
            result["status"] = "not_in_any_manifest"
            results.append(result)
            continue

        states = [original["initialText"]] + [
            event["afterFullText"] for event in original["events"]
        ]
        exact_matches: list[dict[str, Any]] = []
        missing_revisions: list[str] = []
        for sha256, occurrences in hashes.items():
            revisions = [
                revision
                for revision in document.get("revisions", [])
                if revision.get("sha256") == sha256
            ]
            if not revisions:
                missing_revisions.append(sha256)
                continue
            if len(revisions) > 1:
                exact_matches.append(
                    {
                        "sha256": sha256,
                        "source": "duplicate",
                        "statePositions": [],
                        "manifestVersions": occurrences,
                    }
                )
                continue
            revision = revisions[0]
            positions = [
                index
                for index, state in enumerate(states)
                if normalize_text(state) == normalize_text(revision.get("text"))
            ]
            if positions:
                exact_matches.append(
                    {
                        "path": document["path"],
                        "filename": document["filename"],
                        "sha256": sha256,
                        "source": revision.get("source"),
                        "originalText": revision.get("text"),
                        "statePositions": positions,
                        "manifestVersions": occurrences,
                        "proposedAction": (
                            "protected" if revision.get("source") == "official" else "review"
                        ),
                    }
                )
        result["targetRevisionsMissingForManifestHashes"] = missing_revisions
        result["exactMatches"] = exact_matches
        generated = [match for match in exact_matches if match["source"] == "generated"]
        official = [match for match in exact_matches if match["source"] == "official"]
        other = [
            match
            for match in exact_matches
            if match["source"] not in {"generated", "official"}
        ]
        if not generated:
            if official and not other:
                result["status"] = "protected_official_match"
            elif other:
                result["status"] = "review_non_generated_or_duplicate_match"
            elif missing_revisions and len(missing_revisions) == len(hashes):
                result["status"] = "manifest_revisions_missing_from_target"
            else:
                result["status"] = "no_exact_state_across_manifests"
            results.append(result)
            continue
        if len(generated) != 1:
            result["status"] = "ambiguous_exact_revision"
            results.append(result)
            continue
        selected = generated[0]
        if len(selected["statePositions"]) != 1:
            result["status"] = "ambiguous_state"
            results.append(result)
            continue
        position = selected["statePositions"][0]
        desired, events = desired_state(original, position)
        current_document = current_documents.get(document["path"])
        if current_document is None:
            result["status"] = "current_target_missing"
            results.append(result)
            continue
        current = [
            revision
            for revision in current_document.get("revisions", [])
            if revision.get("sha256") == selected["sha256"]
        ]
        if len(current) != 1:
            result["status"] = "current_revision_missing_or_duplicate"
            results.append(result)
            continue
        current_revision = current[0]
        result["selectedTarget"] = selected
        result["desiredText"] = desired
        result["attributionEvents"] = events
        result["temporalRisk"] = "recording_not_active_in_assigned_release"
        assigned_ids = {
            value["versionId"] for value in result["assignedReleaseResults"]
        }
        matching_ids = {
            value["versionId"] for value in selected["manifestVersions"]
        }
        if assigned_ids & matching_ids:
            result["status"] = "inconsistent_with_assigned_release_audit"
        elif current_revision.get("source") == "official":
            result["status"] = "protected_current_official"
        elif current_revision.get("source") == "manual":
            result["status"] = (
                "already_satisfied_current_head"
                if normalize_text(current_revision.get("text")) == normalize_text(desired)
                else "conflict_current_manual"
            )
        elif current_revision.get("source") != "generated":
            result["status"] = "review_current_non_generated_source"
        elif current_revision.get("text") != selected["originalText"]:
            result["status"] = "current_revision_changed"
        else:
            result["status"] = "candidate_historical_version_review"
            selected["proposedAction"] = (
                "replay_and_mark_manual" if position < len(original["events"]) else "mark_manual"
            )
            selected_revisions[(document["path"], selected["sha256"])].append(result)
        results.append(result)

    for conflicts in selected_revisions.values():
        if len(conflicts) > 1:
            for result in conflicts:
                result["status"] = "ambiguous_history"
                result["selectedTarget"]["proposedAction"] = "review"
    results.sort(key=lambda value: (value["legacyPath"], value["epochId"]))
    return results


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    candidates = [
        record
        for record in report["records"]
        if record["status"] == "candidate_historical_version_review"
    ]
    lines = [
        "# Cross-version historical contribution audit",
        "",
        "> Review only: this report did not modify transcripts or categories.",
        "",
        "## Dataset and grain",
        "",
        f"- Published version manifests scanned: **{summary['versionManifests']:,}**",
        f"- Historical epochs entering this diagnostic: **{summary['unresolvedEpochs']:,}**",
        f"- Previously resolved or officially protected epochs excluded: **{summary['excludedResolvedEpochs']:,}**",
        "- Candidate grain: one epoch, one transcript path, one audio SHA, and one exact text state.",
        "",
        "## Checks performed",
        "",
        "- Filename coverage across every version listed by the live root manifest.",
        "- Exact normalized text-state matching against SHA-addressed target revisions.",
        "- Path, SHA, state-position, and history uniqueness.",
        "- Official-source protection and current-HEAD conflict detection.",
        "- Temporal consistency with the release active when the correction was committed.",
        "",
        "## Findings",
        "",
        "| Status | Epochs | Share |",
        "| --- | ---: | ---: |",
    ]
    for status, count in sorted(
        summary["recordsByStatus"].items(), key=lambda item: (-item[1], item[0])
    ):
        share = count / summary["unresolvedEpochs"] if summary["unresolvedEpochs"] else 0
        lines.append(f"| `{status}` | {count:,} | {share:.1%} |")
    lines.extend(
        [
            "",
            "## Newly recoverable review candidates",
            "",
            "| Legacy path | Author/date | Before | After | SHA | Matching versions | Action |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in candidates:
        event = record["attributionEvents"][-1]
        versions = ", ".join(
            value["versionId"] for value in record["selectedTarget"]["manifestVersions"]
        )
        path = record["legacyPath"].replace("|", "\\|")
        author = (
            f"{event['author']['name']} ({event['author']['date']})"
            .replace("|", "\\|")
            .replace("\n", " ")
        )
        before = event["beforeFullText"].replace("|", "\\|").replace("\n", " ")
        after = event["afterFullText"].replace("|", "\\|").replace("\n", " ")
        sha = record["selectedTarget"]["sha256"][:12]
        lines.append(
            f"| `{path}` | {author} | {before} | {after} | `{sha}` | `{versions}` | `{record['selectedTarget']['proposedAction']}` |"
        )
    if not candidates:
        lines.append("| _None_ |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Risk and recommendation",
            "",
            f"Manifest integrity checks found **{summary['manifestConflictingFilenames']:,}** conflicting filename mappings and **{summary['manifestInvalidAudioKeys']:,}** invalid audio keys.",
            "",
            "These candidates have strong structural evidence but a temporal mismatch:",
            "their recording SHA appears only in snapshots other than the version active",
            "when the correction was committed. Review the audio/text intent before any",
            "application. Official, ambiguous, missing, and current-manual conflicts must",
            "not be applied automatically. Candidate confidence is high for identity and",
            "text lineage but medium overall until the correction's semantic intent is",
            "confirmed.",
            "",
        ]
    )
    return "\n".join(lines)


def load_documents(
    repo: Path, commit: str, paths: Iterable[str]
) -> dict[str, dict[str, Any]]:
    object_ids = {
        path: str(git(repo, "rev-parse", f"{commit}:{path}")).strip()
        for path in sorted(set(paths))
    }
    blobs = read_blobs(repo, object_ids.values())
    return {
        path: parse_json_blob(blobs[object_id], f"{commit}:{path}")
        for path, object_id in object_ids.items()
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search all version manifests for unresolved historical corrections."
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
    parser.add_argument("--scope-audit", type=Path, action="append")
    parser.add_argument(
        "--output-json",
        default="migration-reports/cross-version-historical-contribution-audit.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="migration-reports/cross-version-historical-contribution-audit.md",
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
        scope_paths = args.scope_audit or [
            Path("migration-reports/six-hero-update-historical-contribution-audit.json"),
            Path("migration-reports/ognb-historical-contribution-audit.json"),
        ]
        scope_paths = [path if path.is_absolute() else repo / path for path in scope_paths]
        historical = read_json(historical_path)
        if historical.get("mode") != "historical-audit-only":
            raise AuditError("The input is not a historical contribution audit.")
        scoped_reports = [read_json(path) for path in scope_paths]
        unresolved, assignments, resolved = unresolved_records(historical, scoped_reports)

        target_commit = resolve_ref(repo, historical["target"]["commit"])
        target_prefix = historical["target"]["prefix"]
        tree = {
            path: object_id
            for path, object_id in list_tree(repo, target_commit, target_prefix).items()
            if path.endswith(".json")
        }
        blobs = read_blobs(repo, tree.values())
        target_documents = {
            path: parse_json_blob(blobs[object_id], f"{target_commit}:{path}")
            for path, object_id in tree.items()
        }
        target_index, target_stats = build_target_index(target_documents, target_prefix)
        relevant_paths = {
            document["path"]
            for record in unresolved
            for document in target_index.get(
                PurePosixPath(record["legacyPath"]).name.casefold(), []
            )
        }
        relevant_filenames = {
            target_documents[path]["filename"] for path in relevant_paths
        }

        release_map = read_json(release_map_path)
        root_url = release_map.get("rootManifestUrl")
        if not isinstance(root_url, str) or not root_url.startswith("https://"):
            raise AuditError("The release map has no valid rootManifestUrl.")
        root_content, root_headers = fetch_manifest(root_url)
        root_summary, versions = parse_root_manifest(root_content)
        catalog, manifest_reports = build_catalog(versions, relevant_filenames)

        current_commit = resolve_ref(repo, "HEAD")
        current_documents = load_documents(repo, current_commit, relevant_paths)
        records = classify_records(
            unresolved, assignments, target_index, current_documents, catalog
        )
        statuses = Counter(record["status"] for record in records)
        candidates = [
            record
            for record in records
            if record["status"] == "candidate_historical_version_review"
        ]
        candidate_events = [
            event for record in candidates for event in record["attributionEvents"]
        ]
        candidate_authors = Counter(
            (event["author"]["name"], event["author"]["email"])
            for event in candidate_events
        )
        report = {
            "schemaVersion": REPORT_SCHEMA_VERSION,
            "mode": "cross-version-historical-audit-only",
            "historicalAudit": {
                "path": historical_path.relative_to(repo).as_posix(),
                "contentSha256": hashlib.sha256(historical_path.read_bytes()).hexdigest(),
            },
            "scopeAudits": [
                {
                    "path": path.relative_to(repo).as_posix(),
                    "versionId": scope["release"]["id"],
                    "contentSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path, scope in zip(scope_paths, scoped_reports)
            ],
            "target": {
                **historical["target"],
                "observedHeadCommit": current_commit,
            },
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
                "uniqueHistoryEpochRequired": True,
                "exactTextAnchorRequired": True,
                "currentHeadConflictCheckRequired": True,
                "temporalMismatchMayAutoApply": False,
                "fuzzyMatchingMayAutoApply": False,
            },
            "summary": {
                "historicalEpochs": len(historical.get("records", [])),
                "unresolvedEpochs": len(unresolved),
                "excludedResolvedEpochs": len(resolved),
                "versionManifests": len(manifest_reports),
                "relevantTranscriptPaths": len(relevant_paths),
                "reviewCandidates": len(candidates),
                "candidateCorrectionEvents": len(candidate_events),
                "reviewCandidateRate": (
                    len(candidates) / len(unresolved) if unresolved else 0
                ),
                "manifestConflictingFilenames": sum(
                    value["conflictingFilenames"] for value in manifest_reports
                ),
                "manifestInvalidAudioKeys": sum(
                    value["invalidAudioKeys"] for value in manifest_reports
                ),
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
        protected: Iterable[str] = (
            historical["target"]["prefix"],
            historical["legacy"]["prefix"],
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
    except (AuditError, KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
