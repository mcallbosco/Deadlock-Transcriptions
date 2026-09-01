#!/usr/bin/env python3
"""Plan and publish Git-authored transcript/config corrections to VLViewer R2.

Phase 1 deliberately updates only transcript text/official status plus category
and character-name JSON. Structural generator inputs are reported as blocking
until the canonical recording-inventory compiler is available.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Iterator

from .transcript_schema import TRANSCRIPT_SCHEMA_VERSION
from .voiceline_history import (
    HISTORY_SCHEMA_VERSION,
    MULTIPLE_EVENTS_CRITERION,
    SHARD_COUNT,
    TRANSCRIPT_DIFFERENCES_CRITERION,
    OfficialCatalog,
    VoiceLineHistoryError,
    build_history,
)

MUTABLE_JSON_CACHE_CONTROL = "public, max-age=0, must-revalidate"
IMMUTABLE_JSON_CACHE_CONTROL = "public, max-age=31536000, immutable"
TRANSCRIPT_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
AUDIO_KEY_RE = re.compile(
    r"(?:^|/)sha256/[0-9a-f]{2}/(?P<sha>[0-9a-f]{64})\.mp3$"
)
VERSION_CONFIG_RE = re.compile(
    r"^config/(?P<game>[a-z0-9-]+)/versions/(?P<version>[a-z0-9][a-z0-9._-]*)/"
    r"(?P<name>categories|character-names)\.json$"
)
VERSION_GENERATOR_CONFIG_RE = re.compile(
    r"^config/(?P<game>[a-z0-9-]+)/versions/(?P<version>[a-z0-9][a-z0-9._-]*)/"
    r"audio-filename-overrides\.json$"
)
SUPPORTED_SOURCES = {
    "generated",
    "official",
    "manual",
    "skippedeffort",
    "skippednonspeech",
}
GENERATOR_INPUTS = {
    "character-mappings.json",
    "topic-aliases.json",
    "voiceline-groups.json",
    "conversation-overrides.json",
}
VALIDATE_ONLY_CONFIG = {
    "transcription-vocabulary.json",
    "version-releases.json",
    "voice-line-history.json",
    "source-lock.json",
}
PHASE_ORDER = {
    "content": 10,
    "history-content": 15,
    "metadata": 20,
    "history-manifest": 25,
    "manifest": 30,
}


class ContentSyncError(RuntimeError):
    """Raised for a safe, user-facing content-sync failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_copy(value: Any) -> Any:
    return copy.deepcopy(value)


@dataclass(frozen=True)
class TranscriptState:
    text: str
    source: str

    @property
    def official(self) -> bool:
        return self.source == "official"

    @property
    def published(self) -> tuple[str, bool]:
        return self.text, self.official

    def to_json(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "officialtranscription": self.official,
        }


@dataclass(frozen=True)
class TranscriptOccurrence:
    state: TranscriptState
    path: str
    filename: str


@dataclass
class ConfigValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _validate_categories_manifest(value: Any, report: ConfigValidation) -> None:
    if not isinstance(value, dict):
        report.errors.append("categories.json must contain a JSON object")
        return
    if value.get("schemaVersion") != 1:
        report.errors.append("categories.json schemaVersion must be 1")
    default_category = value.get("defaultCategory")
    categories = value.get("categories")
    if not isinstance(default_category, str) or not default_category.strip():
        report.errors.append("categories.json must contain a non-empty defaultCategory")
    if not isinstance(categories, list):
        report.errors.append("categories.json must contain a categories array")
        return

    names: set[str] = set()
    assigned: set[str] = set()
    default_visible = False
    for index, category in enumerate(categories):
        if not isinstance(category, dict):
            report.errors.append(f"categories.json categories[{index}] must be an object")
            continue
        name = category.get("name")
        characters = category.get("characters")
        if not isinstance(name, str) or not name.strip():
            report.errors.append(f"categories.json categories[{index}] needs a non-empty name")
            continue
        normalized_name = name.strip().casefold()
        if normalized_name in names:
            report.errors.append(f"categories.json contains duplicate category name: {name}")
        names.add(normalized_name)
        if (
            isinstance(default_category, str)
            and normalized_name == default_category.strip().casefold()
            and category.get("hidden") is not True
        ):
            default_visible = True
        if not isinstance(characters, list) or any(
            not isinstance(character, str) or not character.strip() for character in characters
        ):
            report.errors.append(
                f"categories.json category {name!r} must contain a characters string array"
            )
            continue
        for character in characters:
            normalized_character = character.strip().casefold()
            if normalized_character in assigned:
                report.errors.append(
                    f"categories.json assigns character more than once: {character}"
                )
            assigned.add(normalized_character)
    if isinstance(default_category, str) and default_category.strip() and not default_visible:
        report.errors.append(
            "categories.json defaultCategory must name a visible category in categories"
        )


def _validate_character_names_manifest(
    value: Any,
    report: ConfigValidation,
    expected_game: str | None = None,
) -> None:
    if not isinstance(value, dict):
        report.errors.append("character-names.json must contain a JSON object")
        return
    if value.get("schemaVersion") != 1:
        report.errors.append("character-names.json schemaVersion must be 1")
    game = value.get("game")
    if not isinstance(game, str) or not game.strip():
        report.errors.append("character-names.json must contain a non-empty game")
    elif expected_game and game.strip().casefold() != expected_game.casefold():
        report.errors.append(
            f"character-names.json game must be {expected_game!r}, received {game!r}"
        )
    names = value.get("names")
    if not isinstance(names, dict) or not names:
        report.errors.append("character-names.json must contain a non-empty names object")
        return
    seen: set[str] = set()
    for key, display_name in names.items():
        if not isinstance(key, str) or not key.strip():
            report.errors.append("character-names.json contains an empty character key")
            continue
        normalized = " ".join(key.strip().casefold().split())
        if normalized in seen:
            report.errors.append(f"character-names.json contains a duplicate key: {key}")
        seen.add(normalized)
        if not isinstance(display_name, str) or not display_name.strip():
            report.errors.append(
                f"character-names.json display name for {key!r} must be a non-empty string"
            )


@dataclass
class RepositoryValidation:
    repo: Path
    transcript_files: int = 0
    revisions: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    by_sha: dict[str, list[TranscriptOccurrence]] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_json(self) -> dict[str, Any]:
        ambiguous: list[dict[str, Any]] = []
        for sha, occurrences in sorted(self.by_sha.items()):
            states: dict[tuple[str, bool], list[TranscriptOccurrence]] = {}
            for occurrence in occurrences:
                states.setdefault(occurrence.state.published, []).append(occurrence)
            if len(states) < 2:
                continue
            ambiguous.append(
                {
                    "sha256": sha,
                    "states": [
                        {
                            "text": published[0],
                            "officialtranscription": published[1],
                            "sources": sorted({item.state.source for item in items}),
                            "occurrences": len(items),
                            "examplePaths": [item.path for item in items[:10]],
                        }
                        for published, items in states.items()
                    ],
                }
            )
        return {
            "valid": self.valid,
            "repository": str(self.repo),
            "transcriptFiles": self.transcript_files,
            "revisions": self.revisions,
            "recordingHashes": len(self.by_sha),
            "ambiguousRecordingHashes": len(ambiguous),
            "ambiguousRecordings": ambiguous,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class StoredJson:
    key: str
    value: dict[str, Any] | None
    body: bytes | None
    etag: str | None

    @property
    def exists(self) -> bool:
        return self.value is not None


@dataclass
class PlannedWrite:
    key: str
    value: dict[str, Any]
    expected_etag: str | None
    phase: str
    reason: str
    public: bool = True
    cache_control: str = MUTABLE_JSON_CACHE_CONTROL
    previous_value: dict[str, Any] | None = field(default=None, repr=False)

    def to_json(self) -> dict[str, Any]:
        body = canonical_json(self.value)
        return {
            "key": self.key,
            "phase": self.phase,
            "reason": self.reason,
            "operation": "replace" if self.expected_etag else "create",
            "expectedEtag": self.expected_etag,
            "beforeSha256": (
                sha256_bytes(canonical_json(self.previous_value))
                if self.previous_value is not None
                else None
            ),
            "bytes": len(body),
            "sha256": sha256_bytes(body),
            "public": self.public,
            "cacheControl": self.cache_control,
        }


@dataclass
class SyncPlan:
    repository: str
    base_commit: str | None
    target_commit: str
    game: str
    baseline: bool
    created_at: str
    validation: RepositoryValidation
    changed_paths: list[str] = field(default_factory=list)
    unsupported_paths: list[str] = field(default_factory=list)
    ignored_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    record_changes: list[dict[str, Any]] = field(default_factory=list)
    config_changes: list[dict[str, Any]] = field(default_factory=list)
    unmatched_hashes: list[str] = field(default_factory=list)
    noop_records: int = 0
    matched_records: int = 0
    affected_versions: list[str] = field(default_factory=list)
    version_revisions: list[dict[str, Any]] = field(default_factory=list)
    history: dict[str, Any] | None = None
    object_reads: int = 0
    writes: list[PlannedWrite] = field(default_factory=list, repr=False)

    @property
    def deployable(self) -> bool:
        return (
            self.validation.valid
            and not self.errors
            and not self.unsupported_paths
            and not any(item.get("status") == "conflict" for item in self.record_changes)
            and not any(item.get("status") == "conflict" for item in self.config_changes)
        )

    @property
    def conflict_count(self) -> int:
        return sum(
            item.get("status") == "conflict"
            for item in [*self.record_changes, *self.config_changes]
        )

    def sorted_writes(self) -> list[PlannedWrite]:
        return sorted(
            self.writes,
            key=lambda item: (PHASE_ORDER[item.phase], item.key),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "mode": "baseline" if self.baseline else "incremental",
            "deployable": self.deployable,
            "repository": self.repository,
            "game": self.game,
            "baseCommit": self.base_commit,
            "targetCommit": self.target_commit,
            "createdAt": self.created_at,
            "validation": self.validation.to_json(),
            "changedPaths": self.changed_paths,
            "unsupportedPaths": self.unsupported_paths,
            "ignoredPaths": self.ignored_paths,
            "errors": self.errors,
            "warnings": [*self.validation.warnings, *self.warnings],
            "summary": {
                "matchedRecords": self.matched_records,
                "recordUpdates": sum(
                    item.get("status") in {"update", "approved_update", "baseline_update"}
                    for item in self.record_changes
                ),
                "approvedConflictUpdates": sum(
                    item.get("status") == "approved_update"
                    for item in self.record_changes
                ),
                "recordNoops": self.noop_records,
                "conflicts": self.conflict_count,
                "unmatchedHashes": len(self.unmatched_hashes),
                "affectedVersions": len(self.affected_versions),
                "objectsRead": self.object_reads,
                "writes": len(self.writes),
                "writeBytes": sum(len(canonical_json(item.value)) for item in self.writes),
            },
            "affectedVersions": self.affected_versions,
            "versionRevisions": self.version_revisions,
            "history": self.history,
            "recordChanges": self.record_changes,
            "configChanges": self.config_changes,
            "unmatchedHashes": self.unmatched_hashes,
            "writes": [item.to_json() for item in self.sorted_writes()],
        }

    def to_markdown(self) -> str:
        state = "Deployable" if self.deployable else "Blocked"
        data = self.to_json()
        summary = data["summary"]
        lines = [
            f"# VLViewer content sync: {state}",
            "",
            f"- Mode: **{data['mode']}**",
            f"- Base commit: `{self.base_commit or 'none'}`",
            f"- Target commit: `{self.target_commit}`",
            f"- Changed paths: **{len(self.changed_paths):,}**",
            f"- Matched published records: **{summary['matchedRecords']:,}**",
            f"- Record updates: **{summary['recordUpdates']:,}**",
            f"- Approved conflict overwrites: **{summary['approvedConflictUpdates']:,}**",
            f"- Record no-ops: **{summary['recordNoops']:,}**",
            f"- Conflicts: **{summary['conflicts']:,}**",
            f"- Affected versions: **{summary['affectedVersions']:,}**",
            f"- Public/R2 objects read: **{summary['objectsRead']:,}**",
            f"- Planned conditional writes: **{summary['writes']:,}**",
            "",
        ]
        if self.unsupported_paths:
            lines.extend(["## Regeneration required", ""])
            lines.extend(f"- `{path}`" for path in self.unsupported_paths)
            lines.append("")
        combined_errors = [*self.validation.errors, *self.errors]
        if combined_errors:
            lines.extend(["## Errors", ""])
            lines.extend(f"- {item}" for item in combined_errors[:100])
            lines.append("")
        conflicts = [
            item
            for item in [*self.record_changes, *self.config_changes]
            if item.get("status") == "conflict"
        ]
        if conflicts:
            lines.extend(["## Conflicts", ""])
            for item in conflicts[:100]:
                location = item.get("jsonPath") or item.get("sourcePath") or item.get("key")
                lines.append(f"- `{location}`: {item.get('reason', 'unexpected CDN state')}")
            lines.append("")
        updates = [
            item
            for item in self.record_changes
            if item.get("status") in {"update", "approved_update", "baseline_update"}
        ]
        if updates:
            lines.extend(["## Transcript updates", ""])
            lines.append("| Version | Object | SHA-256 | Current text | Desired text |")
            lines.append("| --- | --- | --- | --- | --- |")
            for item in updates[:200]:
                current = str((item.get("current") or {}).get("text", "")).replace("|", "\\|")
                desired = str((item.get("desired") or {}).get("text", "")).replace("|", "\\|")
                lines.append(
                    f"| {item['version']} | `{item['key']}` | `{item['sha256'][:12]}…` "
                    f"| {current} | {desired} |"
                )
            lines.append("")
        if self.config_changes:
            lines.extend(["## Direct configuration", ""])
            lines.extend(
                f"- `{item['sourcePath']}` → `{item['key']}`: **{item['status']}**"
                for item in self.config_changes
            )
            lines.append("")
        if self.history:
            lines.extend(
                [
                    "## Voice-line history",
                    "",
                    f"- Official versions represented: **{self.history['versions']:,}**",
                    f"- Lines with history: **{self.history['lines']:,}**",
                    f"- History events: **{self.history['events']:,}**",
                    f"- Lines with multiple events: **{self.history['presenceLines']:,}**",
                    "- Lines with transcript differences: "
                    f"**{self.history['transcriptDifferenceLines']:,}**",
                    f"- Changed immutable shards: **{self.history['changedShards']:,}**",
                    "- Multiple-events index changed: "
                    f"**{str(self.history['presenceChanged']).lower()}**",
                    "- Transcript-differences index changed: "
                    f"**{str(self.history['transcriptDifferencesChanged']).lower()}**",
                    f"- History manifest changed: **{str(self.history['manifestChanged']).lower()}**",
                    "",
                ]
            )
        if self.unmatched_hashes:
            lines.extend(["## Changed recording hashes with no published match", ""])
            lines.extend(f"- `{item}`" for item in self.unmatched_hashes[:200])
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


class PublicJsonStore:
    """Read JSON through the public content Worker."""

    def __init__(
        self,
        base_url: str = "https://cdn.vlviewer.com",
        *,
        read_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.read_attempts = max(1, read_attempts)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)

    def url(self, key: str) -> str:
        encoded = "/".join(urllib.parse.quote(part) for part in key.split("/"))
        return f"{self.base_url}/{encoded}"

    def get_json(self, key: str) -> StoredJson:
        request = urllib.request.Request(
            self.url(key),
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "User-Agent": "VLViewer-Content-Sync/1.0",
            },
        )
        for attempt in range(1, self.read_attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read()
                    etag = response.headers.get("ETag")
                    if response.headers.get("Content-Encoding", "").casefold() == "gzip":
                        body = gzip.decompress(body)
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return StoredJson(key, None, None, None)
                if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == self.read_attempts:
                    raise ContentSyncError(
                        f"Could not read {self.url(key)}: HTTP {exc.code}"
                    ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == self.read_attempts:
                    raise ContentSyncError(f"Could not read {self.url(key)}: {exc}") from exc
            time.sleep(self.retry_delay_seconds * attempt)
        try:
            value = json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContentSyncError(f"Public JSON is invalid at {self.url(key)}: {exc}") from exc
        if not isinstance(value, dict):
            raise ContentSyncError(f"Public JSON must be an object: {self.url(key)}")
        return StoredJson(key, value, body, etag)


class R2JsonStore:
    """Read and conditionally write JSON through R2's S3-compatible API."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str,
        client: Any | None = None,
    ) -> None:
        self.bucket = bucket.strip()
        self.endpoint_url = endpoint_url.strip().rstrip("/")
        if not self.bucket or not self.endpoint_url:
            raise ContentSyncError("R2 bucket and endpoint URL are required.")
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
        secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
        if not access_key or not secret_key:
            raise ContentSyncError(
                "Set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY before deploying."
            )
        try:
            import boto3  # type: ignore
            from botocore.config import Config  # type: ignore
        except ImportError as exc:
            raise ContentSyncError("R2 deployment requires boto3.") from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(retries={"max_attempts": 4, "mode": "standard"}),
        )
        return self._client

    @staticmethod
    def _status(exc: Exception) -> int | None:
        response = getattr(exc, "response", {})
        return response.get("ResponseMetadata", {}).get("HTTPStatusCode")

    @classmethod
    def _missing(cls, exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        code = str(response.get("Error", {}).get("Code", ""))
        return cls._status(exc) == 404 or code in {"NoSuchKey", "NotFound", "404"}

    def get_json(self, key: str) -> StoredJson:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            if self._missing(exc):
                return StoredJson(key, None, None, None)
            raise ContentSyncError(f"Could not read r2://{self.bucket}/{key}: {exc}") from exc
        body = response["Body"].read()
        try:
            value = json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContentSyncError(f"R2 JSON is invalid at {key}: {exc}") from exc
        if not isinstance(value, dict):
            raise ContentSyncError(f"R2 JSON must be an object: {key}")
        return StoredJson(key, value, body, response.get("ETag"))

    def put_json(self, write: PlannedWrite) -> None:
        body = canonical_json(write.value)
        request: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": write.key,
            "Body": body,
            "ContentType": "application/json; charset=utf-8",
            "CacheControl": write.cache_control,
            "Metadata": {"sha256": sha256_bytes(body)},
        }
        if write.expected_etag:
            request["IfMatch"] = write.expected_etag
        else:
            request["IfNoneMatch"] = "*"
        try:
            self.client.put_object(**request)
        except Exception as exc:
            if self._status(exc) == 412:
                if (
                    write.expected_etag is None
                    and write.cache_control == IMMUTABLE_JSON_CACHE_CONTROL
                    and self.get_json(write.key).value == write.value
                ):
                    return
                raise ContentSyncError(
                    f"R2 precondition failed for {write.key}; another writer changed it."
                ) from exc
            raise ContentSyncError(f"Could not write r2://{self.bucket}/{write.key}: {exc}") from exc


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ContentSyncError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout.decode("utf-8", errors="surrogateescape")


def resolve_commit(repo: Path, value: str) -> str:
    return run_git(repo, "rev-parse", f"{value}^{{commit}}").strip()


def require_checked_out_target(repo: Path, target: str) -> str:
    target_commit = resolve_commit(repo, target)
    head = resolve_commit(repo, "HEAD")
    if target_commit != head:
        raise ContentSyncError(
            f"Target {target_commit} is not checked out (HEAD is {head})."
        )
    return target_commit


def require_ancestor(repo: Path, base: str, target: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", base, target],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 1:
        raise ContentSyncError(
            f"Base commit {base} is not an ancestor of target {target}. "
            "Use a reviewed baseline/reconciliation instead of comparing unrelated histories."
        )
    if result.returncode:
        raise ContentSyncError(
            "Could not validate the Git deployment range: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )


def require_clean_content_worktree(repo: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "transcripts",
            "config",
            "schema.json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ContentSyncError(
            "Could not check the content worktree: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    changed = result.stdout.decode("utf-8", errors="replace").strip()
    if changed:
        preview = "\n".join(changed.splitlines()[:20])
        raise ContentSyncError(
            "Transcript/config planning requires a clean committed content tree. "
            "Commit or remove these changes first:\n" + preview
        )


def changed_paths(repo: Path, base: str, target: str) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "diff",
            "--name-only",
            "-z",
            base,
            target,
            "--",
            "transcripts",
            "config",
            "schema.json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ContentSyncError(
            "Could not calculate the Git change range: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    return sorted(
        item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    )


def read_git_json(repo: Path, ref: str, path: str) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        return None
    try:
        value = json.loads(result.stdout.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContentSyncError(f"Invalid JSON at {ref}:{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContentSyncError(f"JSON must be an object at {ref}:{path}")
    return value


def read_worktree_json(repo: Path, path: str) -> dict[str, Any] | None:
    local = repo / Path(*PurePosixPath(path).parts)
    if not local.is_file():
        return None
    try:
        value = json.loads(local.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContentSyncError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContentSyncError(f"JSON must be an object: {path}")
    return value


def _transcript_files(root: Path) -> Iterator[Path]:
    for directory, names, files in os.walk(root):
        names.sort()
        for name in sorted(files):
            if name.lower().endswith(".json"):
                yield Path(directory) / name


def _document_states(
    document: dict[str, Any] | None,
    context: str,
    *,
    allow_legacy_v2: bool = False,
) -> dict[str, TranscriptState]:
    if document is None:
        return {}
    schema_version = document.get("schemaVersion")
    if schema_version != TRANSCRIPT_SCHEMA_VERSION and not (
        allow_legacy_v2 and schema_version == 2
    ):
        raise ContentSyncError(
            f"Transcript schemaVersion must be {TRANSCRIPT_SCHEMA_VERSION}: {context}"
        )
    revisions = document.get("revisions")
    if not isinstance(revisions, list):
        raise ContentSyncError(f"Transcript has no revisions array: {context}")
    result: dict[str, TranscriptState] = {}
    for index, revision in enumerate(revisions):
        if not isinstance(revision, dict):
            raise ContentSyncError(f"{context} revisions[{index}] must be an object")
        missing = {"sha256", "text", "source"} - set(revision)
        if missing:
            raise ContentSyncError(
                f"{context} revisions[{index}] is missing {', '.join(sorted(missing))}"
            )
        unexpected = set(revision) - {"sha256", "text", "source", "model"}
        if unexpected:
            raise ContentSyncError(
                f"{context} revisions[{index}] has unexpected fields: "
                + ", ".join(sorted(unexpected))
            )
        text = revision.get("text")
        source = revision.get("source")
        model = revision.get("model")
        if not isinstance(text, str) or source not in SUPPORTED_SOURCES:
            raise ContentSyncError(f"{context} revisions[{index}] has invalid text/source")
        if model is not None and (not isinstance(model, str) or not model):
            raise ContentSyncError(f"{context} revisions[{index}] has invalid model")
        hashes = revision.get("sha256")
        if schema_version == 2:
            if isinstance(hashes, str):
                hashes = [hashes]
            elif hashes is None:
                hashes = []
        if not isinstance(hashes, list):
            raise ContentSyncError(f"{context} revisions[{index}] SHA-256 must be an array")
        for sha in hashes:
            if not isinstance(sha, str) or not TRANSCRIPT_SHA_RE.fullmatch(sha):
                raise ContentSyncError(f"{context} revisions[{index}] has invalid SHA-256")
            if sha in result:
                raise ContentSyncError(f"{context} contains duplicate revision SHA-256 {sha}")
            result[sha] = TranscriptState(text=text, source=source)
    return result


def hash_preservation_errors(
    repo: Path,
    base: str,
    validation: RepositoryValidation,
    paths: Iterable[str],
) -> list[str]:
    """Reject removal of the final target occurrence of any recording hash."""
    removed_from: dict[str, list[str]] = {}
    errors: list[str] = []
    for path in paths:
        if not path.startswith("transcripts/") or not path.endswith(".json"):
            continue
        try:
            old_states = _document_states(
                read_git_json(repo, base, path),
                f"{base}:{path}",
                allow_legacy_v2=True,
            )
            new_states = _document_states(read_worktree_json(repo, path), path)
        except ContentSyncError as exc:
            errors.append(str(exc))
            continue
        for sha in sorted(set(old_states) - set(new_states)):
            removed_from.setdefault(sha, []).append(path)

    for sha, source_paths in sorted(removed_from.items()):
        if sha in validation.by_sha:
            continue
        examples = ", ".join(source_paths[:4])
        errors.append(
            f"Recording SHA-256 {sha} was removed from the transcript tree ({examples}). "
            "Recording hashes may be moved between files or revisions, but must not be deleted."
        )
    return errors


def _string_array_mapping_errors(value: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    aliases_seen: dict[str, str] = {}
    for canonical, aliases in value.items():
        if not isinstance(canonical, str) or not canonical.strip():
            errors.append(f"{label} keys must be non-empty strings")
            continue
        if not isinstance(aliases, list) or any(
            not isinstance(alias, str) or not alias.strip() for alias in aliases
        ):
            errors.append(f"{label}.{canonical} must be an array of non-empty strings")
            continue
        for alias in [canonical, *aliases]:
            normalized = alias.strip().casefold()
            previous = aliases_seen.get(normalized)
            if previous and previous != canonical:
                errors.append(
                    f"{label} alias {alias!r} belongs to both {previous!r} and {canonical!r}"
                )
            aliases_seen[normalized] = canonical
    return errors


def _safe_mp3_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not value.startswith("/")
        and all(part not in {"", ".", ".."} and ":" not in part for part in path.parts)
        and path.suffix.casefold() == ".mp3"
    )


def _audio_override_errors(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schemaVersion") != 1 or not isinstance(value.get("overrides"), dict):
        return ["must have schemaVersion 1 and an overrides object"]
    if set(value) - {"schemaVersion", "overrides"}:
        errors.append("contains unexpected top-level fields")
    seen: set[str] = set()
    for source, rule in value["overrides"].items():
        if not _safe_mp3_path(source) or not isinstance(rule, dict):
            errors.append(f"override {source!r} must map a safe relative MP3 path to an object")
            continue
        normalized = source.casefold()
        if normalized in seen:
            errors.append(f"duplicate case-insensitive override path: {source!r}")
        seen.add(normalized)
        parse_as = rule.get("parseAs")
        ignore = rule.get("ignore") is True
        if ignore == isinstance(parse_as, str):
            errors.append(f"override {source!r} must specify exactly one of parseAs or ignore: true")
        elif parse_as is not None and not _safe_mp3_path(parse_as):
            errors.append(f"override {source!r} has an unsafe parseAs MP3 path")
        if set(rule) - {"parseAs", "ignore"}:
            errors.append(f"override {source!r} contains unexpected fields")
    return errors


def _voiceline_group_errors(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def string_list(candidate: Any, field_name: str) -> list[str]:
        if not isinstance(candidate, list) or any(
            not isinstance(item, str) or not item for item in candidate
        ):
            errors.append(f"{field_name} must be an array of non-empty strings")
            return []
        return candidate

    def match_block(candidate: Any, field_name: str) -> dict[str, list[str]]:
        if not isinstance(candidate, dict):
            errors.append(f"{field_name} must be an object")
            candidate = {}
        return {
            "topics": string_list(candidate.get("topics", []), f"{field_name}.topics"),
            "prefixes": string_list(candidate.get("prefixes", []), f"{field_name}.prefixes"),
            "excludePrefixes": string_list(
                candidate.get("excludePrefixes", []), f"{field_name}.excludePrefixes"
            ),
        }

    if value.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    unmatched = value.get("unmatched")
    if not isinstance(unmatched, dict):
        errors.append("unmatched must be an object")
    else:
        if unmatched.get("voice") != "keep-topic-at-root":
            errors.append("unmatched.voice must be keep-topic-at-root")
        if unmatched.get("ping") != "keep-topic-at-pings-root":
            errors.append("unmatched.ping must be keep-topic-at-pings-root")
    if not isinstance(value.get("pingRoot"), str) or not value["pingRoot"]:
        errors.append("pingRoot must be a non-empty string")
    string_list(value.get("rootTopicOrder", []), "rootTopicOrder")

    groups = value.get("groups")
    if not isinstance(groups, list):
        return [*errors, "groups must be an array"]
    group_ids: set[str] = set()
    group_labels: set[tuple[str, str]] = set()
    subgroup_ids: dict[str, set[str]] = {}
    exact_assignments: dict[tuple[str, str], str] = {}
    prefix_assignments: dict[tuple[str, str], str] = {}

    def assign(
        values: Iterable[str],
        scope: str,
        target: str,
        assignments: dict[tuple[str, str], str],
        kind: str,
    ) -> None:
        for item in values:
            key = (scope, item.strip().replace(" ", "_").casefold())
            previous = assignments.get(key)
            if previous:
                errors.append(f"{kind} {item!r} is assigned to both {previous!r} and {target!r}")
            assignments[key] = target

    for index, group in enumerate(groups):
        field_name = f"groups[{index}]"
        if not isinstance(group, dict):
            errors.append(f"{field_name} must be an object")
            continue
        group_id = group.get("id")
        label = group.get("label")
        scope = group.get("scope")
        if not isinstance(group_id, str) or not group_id:
            errors.append(f"{field_name}.id must be a non-empty string")
            group_id = f"invalid-{index}"
        elif group_id in group_ids:
            errors.append(f"duplicate group ID: {group_id}")
        group_ids.add(group_id)
        if not isinstance(label, str) or not label:
            errors.append(f"{field_name}.label must be a non-empty string")
            label = group_id
        if scope not in {"voice", "ping"}:
            errors.append(f"{field_name}.scope must be voice or ping")
            scope = "voice"
        if (scope, label.casefold()) in group_labels:
            errors.append(f"duplicate {scope} group label: {label}")
        group_labels.add((scope, label.casefold()))
        if group.get("sortSection") not in {"root", "groups"}:
            errors.append(f"{field_name}.sortSection must be root or groups")

        match = match_block(group.get("match"), f"{field_name}.match")
        assign(match["topics"], scope, label, exact_assignments, "topic")
        assign(match["prefixes"], scope, label, prefix_assignments, "prefix")
        subgroups = group.get("subgroups")
        if not isinstance(subgroups, list):
            errors.append(f"{field_name}.subgroups must be an array")
            continue
        subgroup_ids[group_id] = set()
        for sub_index, subgroup in enumerate(subgroups):
            sub_field = f"{field_name}.subgroups[{sub_index}]"
            if not isinstance(subgroup, dict):
                errors.append(f"{sub_field} must be an object")
                continue
            sub_id = subgroup.get("id")
            sub_label = subgroup.get("label")
            if not isinstance(sub_id, str) or not sub_id:
                errors.append(f"{sub_field}.id must be a non-empty string")
                sub_id = f"invalid-{sub_index}"
            elif sub_id in subgroup_ids[group_id]:
                errors.append(f"duplicate subgroup ID {sub_id!r} in group {group_id!r}")
            subgroup_ids[group_id].add(sub_id)
            if not isinstance(sub_label, str) or not sub_label:
                errors.append(f"{sub_field}.label must be a non-empty string")
                sub_label = sub_id
            sub_match = match_block(subgroup.get("match"), f"{sub_field}.match")
            target = f"{label}/{sub_label}"
            assign(sub_match["topics"], scope, target, exact_assignments, "topic")
            assign(sub_match["prefixes"], scope, target, prefix_assignments, "prefix")

    overrides = value.get("overrides")
    if not isinstance(overrides, list):
        errors.append("overrides must be an array")
    else:
        for index, override in enumerate(overrides):
            field_name = f"overrides[{index}]"
            if not isinstance(override, dict):
                errors.append(f"{field_name} must be an object")
                continue
            if not isinstance(override.get("filename"), str) or not override["filename"]:
                errors.append(f"{field_name}.filename must be a non-empty string")
            if override.get("scope") not in {"voice", "ping"}:
                errors.append(f"{field_name}.scope must be voice or ping")
            target_group = override.get("group")
            if target_group not in group_ids:
                errors.append(f"{field_name}.group refers to unknown group {target_group!r}")
            target_subgroup = override.get("subgroup")
            if target_subgroup is not None and target_subgroup not in subgroup_ids.get(
                str(target_group), set()
            ):
                errors.append(
                    f"{field_name}.subgroup refers to unknown subgroup {target_subgroup!r}"
                )
    return errors


def _config_errors(path: Path, value: dict[str, Any], game: str) -> list[str]:
    name = path.name
    if name in {"categories.json", "character-names.json"}:
        return []
    if name == "character-mappings.json":
        return _string_array_mapping_errors(value, "character-mappings")
    if name == "topic-aliases.json":
        return _string_array_mapping_errors(value, "topic-aliases")
    if name == "voiceline-groups.json":
        return _voiceline_group_errors(value)
    if name == "conversation-overrides.json":
        items = value.get("complete_conversations")
        if set(value) != {"complete_conversations"} or not isinstance(items, list) or any(
            not isinstance(item, str) or not item for item in items
        ):
            return ["must contain only a complete_conversations array of non-empty strings"]
        return []
    if name == "transcription-vocabulary.json":
        return [
            "every vocabulary section must be an array of non-empty strings"
        ] if any(
            not isinstance(section, str)
            or not section
            or not isinstance(items, list)
            or any(not isinstance(item, str) or not item for item in items)
            for section, items in value.items()
        ) else []
    if name == "version-releases.json":
        errors: list[str] = []
        if value.get("schemaVersion") != 1 or value.get("game") != game:
            errors.append(f"must have schemaVersion 1 and game {game!r}")
        versions = value.get("versions")
        if not isinstance(versions, list):
            return [*errors, "versions must be an array"]
        ids: set[str] = set()
        for index, version in enumerate(versions):
            if not isinstance(version, dict):
                errors.append(f"versions[{index}] must be an object")
                continue
            version_id = version.get("id")
            if not isinstance(version_id, str) or not version_id:
                errors.append(f"versions[{index}].id must be a non-empty string")
            elif version_id in ids:
                errors.append(f"duplicate version release ID {version_id!r}")
            else:
                ids.add(version_id)
            for field_name in ("label", "activeFrom", "releaseEvidenceUrl"):
                if not isinstance(version.get(field_name), str) or not version[field_name]:
                    errors.append(f"versions[{index}].{field_name} must be a non-empty string")
            until = version.get("activeUntilExclusive")
            if until is not None and (not isinstance(until, str) or not until):
                errors.append(f"versions[{index}].activeUntilExclusive must be a string or null")
        return errors
    if name == "voice-line-history.json":
        errors: list[str] = []
        if set(value) != {"schemaVersion", "game", "shardCount", "officialVersions"}:
            errors.append(
                "must contain exactly schemaVersion, game, shardCount, and officialVersions"
            )
        if value.get("schemaVersion") != HISTORY_SCHEMA_VERSION or value.get("game") != game:
            errors.append(
                f"must have schemaVersion {HISTORY_SCHEMA_VERSION} and game {game!r}"
            )
        if value.get("shardCount") != SHARD_COUNT:
            errors.append(f"shardCount must be {SHARD_COUNT}")
        versions = value.get("officialVersions")
        if not isinstance(versions, list) or not versions:
            errors.append("officialVersions must be a non-empty array")
        elif any(not isinstance(version, str) or not version for version in versions):
            errors.append("officialVersions must contain only non-empty strings")
        elif len(versions) != len(set(versions)):
            errors.append("officialVersions must not contain duplicate IDs")
        return errors
    if name == "audio-filename-overrides.json":
        return _audio_override_errors(value)
    if name == "source-lock.json":
        return []
    return ["is not a recognized content configuration file"]


def validate_repository(repo: Path, game: str = "deadlock") -> RepositoryValidation:
    repo = Path(repo).expanduser().resolve()
    report = RepositoryValidation(repo=repo)
    transcripts = repo / "transcripts"
    if not transcripts.is_dir():
        report.errors.append(f"Transcript directory does not exist: {transcripts}")
        return report

    for path in _transcript_files(transcripts):
        relative = path.relative_to(repo).as_posix()
        report.transcript_files += 1
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            report.errors.append(f"Invalid JSON in {relative}: {exc}")
            continue
        if not isinstance(document, dict):
            report.errors.append(f"{relative} must contain a JSON object")
            continue
        unexpected = set(document) - {"schemaVersion", "filename", "revisions"}
        if unexpected:
            report.errors.append(
                f"{relative} has unexpected fields: {', '.join(sorted(unexpected))}"
            )
        if document.get("schemaVersion") != TRANSCRIPT_SCHEMA_VERSION:
            report.errors.append(
                f"{relative} schemaVersion must be {TRANSCRIPT_SCHEMA_VERSION}"
            )
        filename = document.get("filename")
        expected = relative[len("transcripts/") : -len(".json")]
        if not isinstance(filename, str) or not filename:
            report.errors.append(f"{relative} must contain a non-empty filename")
            filename = ""
        elif filename.replace("\\", "/") != expected:
            report.errors.append(
                f"{relative} filename must be {expected!r}, received {filename!r}"
            )
        try:
            states = _document_states(document, relative)
        except ContentSyncError as exc:
            report.errors.append(str(exc))
            continue
        report.revisions += len(document.get("revisions", []))
        for sha, state in states.items():
            report.by_sha.setdefault(sha, []).append(
                TranscriptOccurrence(state=state, path=relative, filename=filename)
            )

    config_root = repo / "config" / game
    if not config_root.is_dir():
        report.errors.append(f"Configuration directory does not exist: {config_root}")
        return report
    for path in sorted(config_root.rglob("*.json")):
        relative = path.relative_to(repo).as_posix()
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            report.errors.append(f"Invalid JSON in {relative}: {exc}")
            continue
        if not isinstance(value, dict):
            report.errors.append(f"{relative} must contain a JSON object")
            continue
        validation = ConfigValidation()
        if path.name == "categories.json":
            _validate_categories_manifest(value, validation)
        elif path.name == "character-names.json":
            _validate_character_names_manifest(value, validation, game)
        validation.errors.extend(_config_errors(path, value, game))
        for error in validation.errors:
            report.errors.append(f"{relative}: {error}")
        for warning in validation.warnings:
            report.warnings.append(f"{relative}: {warning}")

    ambiguous = [
        (sha, values)
        for sha, values in report.by_sha.items()
        if len({item.state.published for item in values}) > 1
    ]
    if ambiguous:
        report.errors.append(
            f"{len(ambiguous):,} recording SHA-256 values have conflicting repository states. "
            "Reconcile every duplicate hash before planning or deployment."
        )
    return report


def classify_config_path(path: str, game: str) -> tuple[str, str | None, str | None]:
    normalized = path.replace("\\", "/")
    root = f"config/{game}/"
    if not normalized.startswith(root):
        return "unknown", None, None
    rest = normalized[len(root) :]
    if rest in {"categories.json", "character-names.json"}:
        return "direct", None, rest[:-len(".json")]
    version_match = VERSION_CONFIG_RE.fullmatch(normalized)
    if version_match and version_match.group("game") == game:
        return "direct", version_match.group("version"), version_match.group("name")
    if rest in GENERATOR_INPUTS or VERSION_GENERATOR_CONFIG_RE.fullmatch(normalized):
        return "generator", None, None
    if rest in VALIDATE_ONLY_CONFIG:
        return "validate_only", None, None
    return "unknown", None, None


def config_object_key(path: str, game: str) -> tuple[str, str | None, str]:
    classification, version, name = classify_config_path(path, game)
    if classification != "direct" or not name:
        raise ContentSyncError(f"Not a direct configuration path: {path}")
    filename = f"{name}.json"
    if version:
        return f"{game}/versions/{version}/{filename}", version, name
    return f"{game}/{filename}", None, name


def key_from_url(url: str, expected_base_url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    expected = urllib.parse.urlparse(expected_base_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != expected.netloc:
        raise ContentSyncError(f"Manifest URL is outside {expected_base_url}: {url}")
    key = urllib.parse.unquote(parsed.path).lstrip("/")
    if not key or "\\" in key or ".." in PurePosixPath(key).parts:
        raise ContentSyncError(f"Manifest contains an unsafe object URL: {url}")
    return key


def walk_audio_records(value: Any, path: str = "$") -> Iterator[tuple[dict[str, Any], str, str]]:
    if isinstance(value, dict):
        audio_key = value.get("audioKey")
        if isinstance(audio_key, str):
            match = AUDIO_KEY_RE.search(audio_key.casefold())
            if match:
                yield value, path, match.group("sha")
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from walk_audio_records(child, f"{path}/{escaped}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_audio_records(child, f"{path}/{index}")


def published_state(record: dict[str, Any]) -> tuple[Any, bool]:
    return record.get("transcription"), record.get("officialtranscription") is True


def state_json(state: tuple[Any, bool] | TranscriptState | None) -> dict[str, Any] | None:
    if state is None:
        return None
    if isinstance(state, TranscriptState):
        return state.to_json()
    return {"text": state[0], "officialtranscription": state[1]}


@dataclass(frozen=True)
class ConflictApproval:
    version: str
    key: str
    json_path: str
    sha256: str
    current_text: Any
    current_official: bool
    desired_text: Any
    desired_official: bool

    @classmethod
    def from_json(cls, value: Any, index: int) -> "ConflictApproval":
        if not isinstance(value, dict):
            raise ContentSyncError(f"Conflict approval {index} must be an object.")
        required = {"version", "key", "jsonPath", "sha256", "current", "desired"}
        if set(value) != required:
            raise ContentSyncError(
                f"Conflict approval {index} must contain exactly: {', '.join(sorted(required))}."
            )
        current = value["current"]
        desired = value["desired"]
        for label, state in (("current", current), ("desired", desired)):
            if not isinstance(state, dict) or set(state) != {
                "text",
                "officialtranscription",
            }:
                raise ContentSyncError(
                    f"Conflict approval {index} {label} must contain exactly text and officialtranscription."
                )
            if not isinstance(state["officialtranscription"], bool):
                raise ContentSyncError(
                    f"Conflict approval {index} {label}.officialtranscription must be boolean."
                )
        strings = (value["version"], value["key"], value["jsonPath"], value["sha256"])
        if not all(isinstance(item, str) and item for item in strings):
            raise ContentSyncError(f"Conflict approval {index} has an invalid identity field.")
        if not TRANSCRIPT_SHA_RE.fullmatch(value["sha256"]):
            raise ContentSyncError(f"Conflict approval {index} has an invalid SHA-256.")
        return cls(
            version=value["version"],
            key=value["key"],
            json_path=value["jsonPath"],
            sha256=value["sha256"],
            current_text=current["text"],
            current_official=current["officialtranscription"],
            desired_text=desired["text"],
            desired_official=desired["officialtranscription"],
        )


def load_conflict_approvals(path: Path | None) -> frozenset[ConflictApproval]:
    if path is None:
        return frozenset()
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContentSyncError(f"Could not read conflict approvals from {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise ContentSyncError("Conflict approvals must use schemaVersion 1.")
    raw = value.get("approvals")
    if not isinstance(raw, list):
        raise ContentSyncError("Conflict approvals must contain an approvals array.")
    approvals = [ConflictApproval.from_json(item, index) for index, item in enumerate(raw)]
    if len(set(approvals)) != len(approvals):
        raise ContentSyncError("Conflict approvals contain duplicate entries.")
    return frozenset(approvals)


class ContentSyncPlanner:
    def __init__(
        self,
        repo: Path,
        store: PublicJsonStore | R2JsonStore,
        game: str = "deadlock",
        cdn_base_url: str = "https://cdn.vlviewer.com",
        conflict_approvals: Iterable[ConflictApproval] = (),
    ) -> None:
        self.repo = Path(repo).expanduser().resolve()
        self.store = store
        self.game = game
        self.cdn_base_url = cdn_base_url.rstrip("/")
        self.conflict_approvals = frozenset(conflict_approvals)
        self.loaded: dict[str, StoredJson] = {}
        self.uncached_reads = 0

    def load(self, key: str) -> StoredJson:
        if key not in self.loaded:
            self.loaded[key] = self.store.get_json(key)
        return self.loaded[key]

    def add_write(
        self,
        plan: SyncPlan,
        key: str,
        value: dict[str, Any],
        phase: str,
        reason: str,
        public: bool = True,
    ) -> None:
        current = self.load(key)
        if current.value == value:
            return
        existing = next((item for item in plan.writes if item.key == key), None)
        if existing:
            existing.value = value
            existing.phase = phase
            existing.reason = reason
            return
        plan.writes.append(
            PlannedWrite(
                key=key,
                value=value,
                expected_etag=current.etag,
                phase=phase,
                reason=reason,
                public=public,
                previous_value=json_copy(current.value),
            )
        )

    def add_immutable_write(
        self,
        plan: SyncPlan,
        key: str,
        value: dict[str, Any],
        reason: str,
    ) -> bool:
        plan.writes.append(
            PlannedWrite(
                key=key,
                value=value,
                expected_etag=None,
                phase="history-content",
                reason=reason,
                cache_control=IMMUTABLE_JSON_CACHE_CONTROL,
            )
        )
        return True

    def finish(self, plan: SyncPlan) -> SyncPlan:
        plan.object_reads = len(self.loaded) + self.uncached_reads
        return plan

    def _revision_changes(
        self,
        validation: RepositoryValidation,
        paths: Iterable[str],
        base: str | None,
        baseline: bool,
        plan: SyncPlan,
    ) -> dict[str, tuple[tuple[TranscriptState, ...], TranscriptState]]:
        paths = list(paths)
        if baseline:
            selected = set(validation.by_sha)
            old_by_sha: dict[str, list[TranscriptState]] = {}
        else:
            selected: set[str] = set()
            old_by_sha = {}
            for error in hash_preservation_errors(
                self.repo, base or "", validation, paths
            ):
                if error not in plan.errors:
                    plan.errors.append(error)
            for path in paths:
                if not path.startswith("transcripts/") or not path.endswith(".json"):
                    continue
                old_document = read_git_json(self.repo, base or "", path) if base else None
                new_document = read_worktree_json(self.repo, path)
                try:
                    old_states = _document_states(
                        old_document,
                        f"{base}:{path}",
                        allow_legacy_v2=True,
                    )
                    new_states = _document_states(new_document, path)
                except ContentSyncError as exc:
                    if str(exc) not in plan.errors:
                        plan.errors.append(str(exc))
                    continue
                for sha in sorted(set(old_states) | set(new_states)):
                    old = old_states.get(sha)
                    new = new_states.get(sha)
                    if old is not None:
                        old_by_sha.setdefault(sha, []).append(old)
                    if new is None:
                        continue
                    if old is None or old.published != new.published:
                        selected.add(sha)

        changes: dict[str, tuple[tuple[TranscriptState, ...], TranscriptState]] = {}
        for sha in sorted(selected):
            candidates = validation.by_sha.get(sha, [])
            desired_states = {item.state.published for item in candidates}
            if not candidates:
                plan.warnings.append(f"Changed SHA-256 {sha} is no longer present in the target tree.")
                continue
            if len(desired_states) != 1:
                examples = ", ".join(item.path for item in candidates[:4])
                plan.errors.append(
                    f"Recording SHA-256 {sha} has conflicting target transcript states: {examples}"
                )
                continue
            desired = candidates[0].state
            old_candidates = old_by_sha.get(sha, [])
            # A duplicated hash may have conflicting states in the base tree. A
            # target that converges those aliases is safe to plan as long as the
            # live CDN record matches any observed base state (or already matches
            # the unique desired state). Preserve every candidate for that check.
            old_by_published = {
                item.published: item for item in old_candidates
            }
            expected_old = tuple(
                old_by_published[published]
                for published in sorted(old_by_published)
            )
            changes[sha] = expected_old, desired
        return changes

    def _direct_config_paths(self, paths: Iterable[str], baseline: bool) -> list[str]:
        if baseline:
            root = self.repo / "config" / self.game
            return sorted(
                path.relative_to(self.repo).as_posix()
                for path in root.rglob("*.json")
                if classify_config_path(path.relative_to(self.repo).as_posix(), self.game)[0]
                == "direct"
            )
        return sorted(
            path
            for path in paths
            if classify_config_path(path, self.game)[0] == "direct"
        )

    def _plan_voice_line_history(
        self,
        plan: SyncPlan,
        manifest: dict[str, Any],
        version_entries: dict[str, dict[str, Any]],
        validation: RepositoryValidation,
        target_commit: str,
    ) -> None:
        config_path = self.repo / "config" / self.game / "voice-line-history.json"
        if not config_path.is_file():
            return
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            plan.errors.append(f"Could not read {config_path}: {exc}")
            return
        configured_ids = config.get("officialVersions") if isinstance(config, dict) else None
        if not isinstance(configured_ids, list):
            plan.errors.append("Voice-line history has no configured officialVersions array.")
            return

        published_official_ids = {
            version_id
            for version_id, entry in version_entries.items()
            if entry.get("kind") != "custom"
        }
        unconfigured = sorted(published_official_ids - set(configured_ids))
        if unconfigured:
            plan.errors.append(
                "Published official versions are missing from voice-line-history.json: "
                + ", ".join(unconfigured)
            )
            return
        unavailable = [version_id for version_id in configured_ids if version_id not in version_entries]
        if unavailable:
            plan.warnings.append(
                "Configured history versions are not published yet and were skipped: "
                + ", ".join(unavailable)
            )

        transcript_states = {
            sha: occurrences[0].state.published
            for sha, occurrences in validation.by_sha.items()
            if occurrences
        }
        catalog_specs: list[tuple[str, dict[str, Any], str, str, int]] = []
        for version_id in configured_ids:
            entry = version_entries.get(version_id)
            if entry is None:
                continue
            if entry.get("kind") == "custom":
                plan.errors.append(
                    f"Configured voice-line history version {version_id!r} is custom."
                )
                continue
            url = entry.get("voiceLineUrl")
            if not isinstance(url, str) or not url:
                plan.errors.append(f"Version {version_id} has no voiceLineUrl for history.")
                continue
            conversation_url = entry.get("conversationUrl")
            if not isinstance(conversation_url, str) or not conversation_url:
                plan.errors.append(f"Version {version_id} has no conversationUrl for history.")
                continue
            voice_line_key = key_from_url(url, self.cdn_base_url)
            conversation_key = key_from_url(conversation_url, self.cdn_base_url)
            try:
                content_revision = int(entry.get("contentRevision", 0))
            except (TypeError, ValueError):
                plan.errors.append(f"Version {version_id} has invalid contentRevision for history.")
                continue
            catalog_specs.append(
                (version_id, entry, voice_line_key, conversation_key, content_revision)
            )
        if plan.errors:
            return

        def catalog_inputs() -> Iterator[OfficialCatalog]:
            for (
                version_id,
                entry,
                voice_line_key,
                conversation_key,
                content_revision,
            ) in catalog_specs:
                values: dict[str, dict[str, Any]] = {}
                for input_name, key in (
                    ("voice-line", voice_line_key),
                    ("conversation", conversation_key),
                ):
                    write = next((item for item in plan.writes if item.key == key), None)
                    if write is not None:
                        value = write.value
                    else:
                        stored = self.store.get_json(key)
                        self.uncached_reads += 1
                        value = stored.value
                    if value is None:
                        raise VoiceLineHistoryError(
                            f"Published {input_name} history input does not exist: {key}"
                        )
                    values[input_name] = value
                yield OfficialCatalog(
                    id=version_id,
                    label=str(entry.get("label") or version_id),
                    content_revision=content_revision,
                    value=values["voice-line"],
                    sha256=sha256_bytes(canonical_json(values["voice-line"])),
                    conversation_value=values["conversation"],
                    conversation_sha256=sha256_bytes(
                        canonical_json(values["conversation"])
                    ),
                )

        try:
            history = build_history(catalog_inputs(), transcript_states)
        except (ContentSyncError, VoiceLineHistoryError) as exc:
            plan.errors.append(str(exc))
            return

        history_manifest_key = f"{self.game}/history/voicelines/manifest.json"
        current = self.load(history_manifest_key)
        referenced_shard_hashes: set[str] = set()
        if current.value is not None and isinstance(current.value.get("shards"), dict):
            for shard in current.value["shards"].values():
                if isinstance(shard, dict) and isinstance(shard.get("sha256"), str):
                    referenced_shard_hashes.add(shard["sha256"])

        shard_manifest: dict[str, dict[str, Any]] = {}
        changed_shards = 0
        for bucket, value in history.shards.items():
            body = canonical_json(value)
            digest = sha256_bytes(body)
            key = f"{self.game}/history/voicelines/shards/{digest}.json"
            if digest not in referenced_shard_hashes and self.add_immutable_write(
                plan,
                key,
                value,
                f"Publish immutable voice-line history shard {bucket}",
            ):
                changed_shards += 1
            shard_manifest[bucket] = {
                "url": f"{self.cdn_base_url}/{key}",
                "sha256": digest,
                "bytes": len(body),
                "lineCount": len(value["lines"]),
            }

        def plan_index(
            manifest_key: str,
            directory: str,
            value: dict[str, Any],
            criterion: str,
            reason: str,
        ) -> tuple[dict[str, Any], bool]:
            body = canonical_json(value)
            digest = sha256_bytes(body)
            key = f"{self.game}/history/voicelines/{directory}/{digest}.json"
            current_digest = None
            if current.value is not None:
                reference = current.value.get(manifest_key)
                if isinstance(reference, dict) and isinstance(
                    reference.get("sha256"), str
                ):
                    current_digest = reference["sha256"]
            changed = digest != current_digest
            if changed:
                self.add_immutable_write(plan, key, value, reason)
            return (
                {
                    "url": f"{self.cdn_base_url}/{key}",
                    "sha256": digest,
                    "bytes": len(body),
                    "lineCount": value["lineCount"],
                    "criterion": criterion,
                },
                changed,
            )

        presence_reference, presence_changed = plan_index(
            "presence",
            "presence",
            history.presence,
            MULTIPLE_EVENTS_CRITERION,
            "Publish immutable multiple-event voice-line history index",
        )
        (
            transcript_differences_reference,
            transcript_differences_changed,
        ) = plan_index(
            "transcriptDifferences",
            "transcript-differences",
            history.transcript_differences,
            TRANSCRIPT_DIFFERENCES_CRITERION,
            "Publish immutable transcript-difference voice-line history index",
        )

        desired_core: dict[str, Any] = {
            "schemaVersion": HISTORY_SCHEMA_VERSION,
            "game": self.game,
            "identity": "normalized-filename",
            "shardAlgorithm": "sha256-first-byte",
            "shardCount": SHARD_COUNT,
            "sourceTranscriptCommit": target_commit,
            "catalogFingerprint": history.catalog_fingerprint,
            "versions": history.versions,
            "historyLines": history.history_lines,
            "eventCount": history.events,
            "shards": shard_manifest,
            "presence": presence_reference,
            "transcriptDifferences": transcript_differences_reference,
        }
        current_core = None
        if current.value is not None:
            current_core = {
                key: value
                for key, value in current.value.items()
                if key not in {"contentRevision", "updatedAt"}
            }
        manifest_changed = current_core != desired_core
        if manifest_changed:
            current_revision = 0
            if current.value is not None:
                try:
                    current_revision = int(current.value.get("contentRevision", 0))
                except (TypeError, ValueError):
                    plan.errors.append("Published voice-line history has invalid contentRevision.")
                    return
            desired_manifest = {
                **desired_core,
                "contentRevision": current_revision + 1,
                "updatedAt": plan.created_at,
            }
            self.add_write(
                plan,
                history_manifest_key,
                desired_manifest,
                "history-manifest",
                "Publish voice-line history manifest after immutable shards",
            )

        manifest["voiceLineHistoryManifestUrl"] = (
            f"{self.cdn_base_url}/{history_manifest_key}"
        )
        plan.history = {
            "versions": len(history.versions),
            "lines": history.history_lines,
            "events": history.events,
            "presenceLines": history.presence["lineCount"],
            "transcriptDifferenceLines": history.transcript_differences["lineCount"],
            "changedShards": changed_shards,
            "presenceChanged": presence_changed,
            "transcriptDifferencesChanged": transcript_differences_changed,
            "manifestChanged": manifest_changed,
            "catalogFingerprint": history.catalog_fingerprint,
        }

    def build(
        self,
        target: str = "HEAD",
        base: str | None = None,
        baseline: bool = False,
        repository_name: str = "mcallbosco/Deadlock-Transcriptions",
    ) -> SyncPlan:
        target_commit = require_checked_out_target(self.repo, target)
        require_clean_content_worktree(self.repo)
        base_commit = resolve_commit(self.repo, base) if base else None
        if not baseline and not base_commit:
            raise ContentSyncError("Incremental planning requires a base commit.")
        if base_commit:
            require_ancestor(self.repo, base_commit, target_commit)
        paths = (
            changed_paths(self.repo, base_commit or "", target_commit)
            if base_commit
            else []
        )
        validation = validate_repository(self.repo, self.game)
        plan = SyncPlan(
            repository=repository_name,
            base_commit=base_commit,
            target_commit=target_commit,
            game=self.game,
            baseline=baseline,
            created_at=utc_now(),
            validation=validation,
            changed_paths=paths,
        )
        if not validation.valid:
            return self.finish(plan)

        for path in paths:
            if path.startswith(f"config/{self.game}/"):
                classification, _version, _name = classify_config_path(path, self.game)
                if classification in {"generator", "unknown"}:
                    plan.unsupported_paths.append(path)
                elif classification == "validate_only":
                    plan.ignored_paths.append(path)
        plan.unsupported_paths = sorted(set(plan.unsupported_paths))
        plan.ignored_paths = sorted(set(plan.ignored_paths))

        revision_changes = self._revision_changes(
            validation, paths, base_commit, baseline, plan
        )
        if plan.errors:
            return self.finish(plan)

        manifest_key = f"{self.game}/manifest.json"
        manifest_stored = self.load(manifest_key)
        if not manifest_stored.exists:
            plan.errors.append(f"Published game manifest does not exist: {manifest_key}")
            return self.finish(plan)
        manifest = json_copy(manifest_stored.value)
        assert isinstance(manifest, dict)
        versions = manifest.get("versions")
        if not isinstance(versions, list):
            plan.errors.append("Published game manifest has no versions array.")
            return self.finish(plan)
        version_entries: dict[str, dict[str, Any]] = {}
        for item in versions:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                plan.errors.append("Published manifest contains an invalid version entry.")
                continue
            version_entries[item["id"]] = item
        if plan.errors:
            return self.finish(plan)

        logical_version_keys: dict[str, set[str]] = {}
        matched_hashes: set[str] = set()

        if revision_changes:
            for version_id, entry in version_entries.items():
                for field in ("voiceLineUrl", "conversationUrl"):
                    url = entry.get(field)
                    if not isinstance(url, str) or not url:
                        plan.errors.append(f"Version {version_id} has no {field}.")
                        continue
                    key = key_from_url(url, self.cdn_base_url)
                    stored = self.load(key)
                    if not stored.exists:
                        plan.errors.append(f"Published object does not exist: {key}")
                        continue
                    desired_object = json_copy(stored.value)
                    object_updates = 0
                    object_matches = 0
                    for record, json_path, sha in walk_audio_records(desired_object):
                        selected = revision_changes.get(sha)
                        if selected is None:
                            continue
                        expected_old, desired = selected
                        old = expected_old[0] if len(expected_old) == 1 else None
                        current = published_state(record)
                        matched_hashes.add(sha)
                        plan.matched_records += 1
                        object_matches += 1
                        desired_published = desired.published
                        status: str
                        reason = ""
                        if current == desired_published:
                            status = "noop"
                            plan.noop_records += 1
                        elif baseline:
                            status = "baseline_update"
                            object_updates += 1
                        elif any(current == candidate.published for candidate in expected_old):
                            status = "update"
                            object_updates += 1
                        else:
                            approval = ConflictApproval(
                                version=version_id,
                                key=key,
                                json_path=json_path,
                                sha256=sha,
                                current_text=current[0],
                                current_official=current[1],
                                desired_text=desired_published[0],
                                desired_official=desired_published[1],
                            )
                            if approval in self.conflict_approvals:
                                status = "approved_update"
                                reason = "Exact CDN conflict state explicitly approved for overwrite"
                                object_updates += 1
                            else:
                                status = "conflict"
                                reason = "CDN record matches neither the expected base nor desired target state"
                        if status != "noop" or not baseline:
                            plan.record_changes.append(
                                {
                                    "status": status,
                                    "reason": reason,
                                    "version": version_id,
                                    "key": key,
                                    "jsonPath": json_path,
                                    "sha256": sha,
                                    "sourcePaths": sorted(
                                        {
                                            occurrence.path
                                            for occurrence in validation.by_sha.get(sha, [])
                                        }
                                    ),
                                    "current": state_json(current),
                                    "expectedOld": state_json(old),
                                    "expectedOldStates": [
                                        state_json(candidate) for candidate in expected_old
                                    ],
                                    "desired": state_json(desired),
                                }
                            )
                        if status in {"update", "approved_update", "baseline_update"}:
                            record["transcription"] = desired.text
                            if desired.official:
                                record["officialtranscription"] = True
                            else:
                                record.pop("officialtranscription", None)
                    logical = object_updates > 0 or (object_matches > 0 and not baseline)
                    if logical:
                        logical_version_keys.setdefault(version_id, set()).add(key)
                    if object_updates:
                        self.add_write(
                            plan,
                            key,
                            desired_object,
                            "content",
                            f"Apply transcript revisions for {version_id}",
                        )

        plan.unmatched_hashes = sorted(set(revision_changes) - matched_hashes)

        for source_path in self._direct_config_paths(paths, baseline):
            desired = read_worktree_json(self.repo, source_path)
            old = read_git_json(self.repo, base_commit, source_path) if base_commit else None
            key, version_id, name = config_object_key(source_path, self.game)
            if desired is None:
                plan.warnings.append(
                    f"Removed {source_path}; CDN deletion is out of scope."
                )
                continue
            if version_id and version_id not in version_entries:
                plan.config_changes.append(
                    {
                        "status": "conflict",
                        "reason": "Version overlay targets a version absent from the public manifest",
                        "sourcePath": source_path,
                        "key": key,
                        "version": version_id,
                    }
                )
                continue
            current = self.load(key)
            source_changed = old != desired
            if current.value == desired:
                status = "noop" if baseline or source_changed else "source_noop"
            elif baseline:
                status = "baseline_update" if current.exists else "create"
            elif old is not None and current.value == old:
                status = "update"
            elif old is None and not current.exists:
                status = "create"
            else:
                status = "conflict"
            reason = ""
            if status == "conflict":
                reason = "CDN config matches neither the expected base nor desired target state"
            plan.config_changes.append(
                {
                    "status": status,
                    "reason": reason,
                    "sourcePath": source_path,
                    "key": key,
                    "version": version_id,
                }
            )
            logical = status in {"update", "create", "baseline_update"} or (
                status == "noop" and not baseline and source_changed
            )
            if logical and version_id:
                logical_version_keys.setdefault(version_id, set()).add(key)
            if status in {"update", "create", "baseline_update"}:
                self.add_write(
                    plan,
                    key,
                    desired,
                    "content",
                    f"Publish direct configuration from {source_path}",
                )
            if logical and version_id:
                entry = version_entries[version_id]
                base_url = f"{self.cdn_base_url}/{self.game}/versions/{version_id}"
                if name == "categories":
                    entry["categoriesUrl"] = f"{base_url}/categories.json"
                else:
                    entry["characterNamesUrl"] = f"{base_url}/character-names.json"
            elif logical and not version_id:
                if name == "categories":
                    manifest["defaultCategoriesUrl"] = f"{self.cdn_base_url}/{key}"
                else:
                    manifest["characterNamesUrl"] = f"{self.cdn_base_url}/{key}"

        if plan.conflict_count or plan.errors:
            plan.affected_versions = sorted(logical_version_keys)
            return self.finish(plan)

        timestamp = plan.created_at
        for version_id in sorted(logical_version_keys):
            entry = version_entries[version_id]
            prefix = f"{self.game}/versions/{version_id}"
            inventory_key = f"{prefix}/publish-inventory.json"
            release_key = f"{prefix}/release.json"
            inventory_stored = self.load(inventory_key)
            release_stored = self.load(release_key)
            if not inventory_stored.exists or not release_stored.exists:
                plan.errors.append(
                    f"Version {version_id} is missing release or inventory metadata."
                )
                continue
            inventory = json_copy(inventory_stored.value)
            release = json_copy(release_stored.value)
            assert isinstance(inventory, dict) and isinstance(release, dict)

            target_revisions: set[int] = set()
            target_timestamps: list[str] = []
            for metadata in (inventory, release):
                if metadata.get("sourceCommit") == target_commit or metadata.get(
                    "deploymentId"
                ) == target_commit:
                    try:
                        target_revisions.add(int(metadata.get("contentRevision", 0)))
                    except (TypeError, ValueError):
                        plan.errors.append(
                            f"Version {version_id} has invalid target deployment metadata."
                        )
                    for field in ("generatedAt", "updatedAt"):
                        value = metadata.get(field)
                        if isinstance(value, str) and value:
                            target_timestamps.append(value)
            if len(target_revisions) > 1:
                plan.errors.append(
                    f"Version {version_id} records target commit at conflicting revisions."
                )
                continue
            if target_revisions:
                revision = next(iter(target_revisions))
                deployment_timestamp = target_timestamps[0] if target_timestamps else timestamp
                generated_at = deployment_timestamp
                updated_at = deployment_timestamp
            else:
                try:
                    revisions = {
                        int(entry.get("contentRevision", 0)),
                        int(inventory.get("contentRevision", 0)),
                        int(release.get("contentRevision", 0)),
                    }
                except (TypeError, ValueError):
                    plan.errors.append(f"Version {version_id} has invalid contentRevision.")
                    continue
                if len(revisions) != 1:
                    plan.errors.append(
                        f"Version {version_id} manifest, inventory, and release revisions disagree."
                    )
                    continue
                revision = next(iter(revisions)) + 1
                generated_at = timestamp
                updated_at = timestamp

            files = inventory.get("files")
            if not isinstance(files, dict):
                plan.errors.append(f"Version {version_id} inventory has no files object.")
                continue
            for key in sorted(logical_version_keys[version_id]):
                relative = PurePosixPath(key).relative_to(prefix).as_posix()
                write = next((item for item in plan.writes if item.key == key), None)
                if write:
                    body = canonical_json(write.value)
                else:
                    stored = self.load(key)
                    if stored.body is None:
                        plan.errors.append(f"Cannot inventory missing desired object: {key}")
                        continue
                    body = stored.body
                files[relative] = {
                    "size": len(body),
                    "sha256": sha256_bytes(body),
                    "contentType": "application/json; charset=utf-8",
                    "mutable": True,
                }
            inventory.update(
                {
                    "contentRevision": revision,
                    "generatedAt": generated_at,
                    "sourceCommit": target_commit,
                    "deploymentId": target_commit,
                }
            )
            entry["contentRevision"] = revision
            entry["updatedAt"] = updated_at
            plan.version_revisions.append(
                {
                    "version": version_id,
                    "current": int(release_stored.value.get("contentRevision", 0)),
                    "proposed": revision,
                    "deploymentId": target_commit,
                }
            )
            release.update(entry)
            release.update(
                {
                    "contentRevision": revision,
                    "updatedAt": updated_at,
                    "fileCount": len(files),
                    "totalBytes": sum(
                        int(item.get("size", 0))
                        for item in files.values()
                        if isinstance(item, dict)
                    ),
                    "sourceCommit": target_commit,
                    "deploymentId": target_commit,
                }
            )
            self.add_write(
                plan,
                inventory_key,
                inventory,
                "metadata",
                f"Advance {version_id} inventory to revision {revision}",
            )
            self.add_write(
                plan,
                release_key,
                release,
                "metadata",
                f"Advance {version_id} release to revision {revision}",
            )

        plan.affected_versions = sorted(logical_version_keys)
        if plan.errors:
            return self.finish(plan)

        self._plan_voice_line_history(
            plan,
            manifest,
            version_entries,
            validation,
            target_commit,
        )
        if plan.errors:
            return self.finish(plan)

        public_changes = any(
            item.public
            and item.phase not in {"manifest", "history-content", "history-manifest"}
            for item in plan.writes
        )
        if public_changes:
            manifest["updatedAt"] = timestamp
        if manifest != manifest_stored.value:
            self.add_write(
                plan,
                manifest_key,
                manifest,
                "manifest",
                "Publish the game manifest after all version content and metadata",
            )
        return self.finish(plan)


def purge_urls(urls: Iterable[str], zone_id: str, token: str) -> None:
    unique = sorted(set(urls))
    if not unique or not zone_id or not token:
        return
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"
    for index in range(0, len(unique), 30):
        body = json.dumps({"files": unique[index : index + 30]}).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            method="POST",
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ContentSyncError(f"Cloudflare cache purge failed: {exc}") from exc
        if not result.get("success"):
            raise ContentSyncError(f"Cloudflare rejected the cache purge: {result}")


def verify_public_writes(
    writes: Iterable[PlannedWrite],
    public_store: PublicJsonStore,
    attempts: int = 5,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    pending = [item for item in writes if item.public]
    last_errors: dict[str, str] = {}
    for attempt in range(attempts):
        failures: list[PlannedWrite] = []
        for write in pending:
            try:
                observed = public_store.get_json(write.key)
            except ContentSyncError as exc:
                failures.append(write)
                last_errors[write.key] = str(exc)
                continue
            if observed.value != write.value:
                failures.append(write)
                last_errors[write.key] = "public JSON does not match the planned value"
            else:
                last_errors.pop(write.key, None)
        if not failures:
            return
        pending = failures
        if attempt + 1 < attempts:
            sleep_fn(min(2**attempt, 8))
            continue
        keys = [item.key for item in failures]
        details = "; ".join(
            f"{key}: {last_errors[key]}" for key in keys[:5] if key in last_errors
        )
        raise ContentSyncError(
            "Public CDN verification failed for: "
            + ", ".join(keys[:20])
            + (f". Last errors: {details}" if details else "")
        )


def deploy_plan(
    plan: SyncPlan,
    store: R2JsonStore,
    public_store: PublicJsonStore,
    cursor: StoredJson,
    cursor_key: str,
    zone_id: str = "",
    purge_token: str = "",
    result_path: Path | None = None,
) -> dict[str, Any]:
    if not plan.deployable:
        raise ContentSyncError("The content-sync plan is blocked and cannot be deployed.")
    writes = plan.sorted_writes()
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "running",
        "targetCommit": plan.target_commit,
        "plannedWrites": len(writes),
        "completedWrites": [],
        "affectedVersions": plan.affected_versions,
        "cursorWritten": False,
        "verifiedUrls": 0,
    }

    def save_result() -> None:
        if not result_path:
            return
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    save_result()
    try:
        for write in writes:
            store.put_json(write)
            result["completedWrites"].append(write.key)
            save_result()
        public_urls = [public_store.url(item.key) for item in writes if item.public]
        result["purgeAttempted"] = bool(public_urls and zone_id and purge_token)
        if zone_id and purge_token:
            purge_urls(public_urls, zone_id, purge_token)
        verify_public_writes(writes, public_store)
        result["verifiedUrls"] = len(public_urls)
        save_result()

        if cursor.value and cursor.value.get("lastSuccessfulCommit") == plan.target_commit:
            cursor_written = False
        else:
            cursor_payload = {
                "schemaVersion": 1,
                "repository": plan.repository,
                "lastSuccessfulCommit": plan.target_commit,
                "deploymentId": plan.target_commit,
                "completedAt": utc_now(),
            }
            store.put_json(
                PlannedWrite(
                    key=cursor_key,
                    value=cursor_payload,
                    expected_etag=cursor.etag,
                    phase="manifest",
                    reason="Advance the private successful-deployment cursor",
                    public=False,
                )
            )
            cursor_written = True
        result.update(
            {
                "status": "succeeded",
                "cursorWritten": cursor_written,
                "completedAt": utc_now(),
            }
        )
        save_result()
        return result
    except Exception as exc:
        result.update({"status": "failed", "error": str(exc), "failedAt": utc_now()})
        save_result()
        raise


def write_reports(plan: SyncPlan, json_path: Path | None, markdown_path: Path | None) -> None:
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(plan.to_json(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if markdown_path:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(plan.to_markdown(), encoding="utf-8")


def write_backups(plan: SyncPlan, backup_dir: Path | None) -> None:
    if not backup_dir:
        return
    backup_dir = Path(backup_dir)
    for write in plan.sorted_writes():
        if not write.public or write.previous_value is None:
            continue
        path = backup_dir.joinpath(*PurePosixPath(write.key).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json(write.previous_value))


__all__ = [
    "ContentSyncError",
    "ConflictApproval",
    "ContentSyncPlanner",
    "PublicJsonStore",
    "R2JsonStore",
    "require_clean_content_worktree",
    "require_ancestor",
    "RepositoryValidation",
    "StoredJson",
    "SyncPlan",
    "TranscriptState",
    "deploy_plan",
    "load_conflict_approvals",
    "resolve_commit",
    "validate_repository",
    "write_reports",
    "write_backups",
]
