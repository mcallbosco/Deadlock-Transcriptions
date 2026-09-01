"""Build deterministic, sharded voice-line history from official catalogs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable, Iterator, Mapping


AUDIO_KEY_RE = re.compile(
    r"(?:^|/)sha256/[0-9a-f]{2}/(?P<sha>[0-9a-f]{64})\.mp3$"
)
HISTORY_SCHEMA_VERSION = 1
SHARD_COUNT = 256
MULTIPLE_EVENTS_CRITERION = "multiple-events"
TRANSCRIPT_DIFFERENCES_CRITERION = "transcription-text-differences"


class VoiceLineHistoryError(ValueError):
    """Raised when official catalogs cannot produce unambiguous history."""


@dataclass(frozen=True)
class OfficialCatalog:
    id: str
    label: str
    content_revision: int
    value: dict[str, Any]
    sha256: str
    conversation_value: dict[str, Any] | None = None
    conversation_sha256: str | None = None


@dataclass(frozen=True)
class HistoryBuild:
    catalog_fingerprint: str
    versions: list[dict[str, Any]]
    shards: dict[str, dict[str, Any]]
    presence: dict[str, Any]
    transcript_differences: dict[str, Any]
    history_lines: int
    events: int


@dataclass(frozen=True)
class _Occurrence:
    version_index: int
    version_id: str
    audio_key: str
    audio_sha256: str
    transcription: str
    official: bool
    voiceline_id: str | None


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_filename(value: str) -> str:
    return PurePosixPath(value.strip().replace("\\", "/")).as_posix().casefold()


def history_shard(filename: str) -> str:
    digest = hashlib.sha256(normalize_filename(filename).encode("utf-8")).digest()
    return f"{digest[0]:02x}"


def _walk_records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        filename = value.get("filename")
        audio_key = value.get("audioKey")
        if isinstance(filename, str) and isinstance(audio_key, str):
            match = AUDIO_KEY_RE.search(audio_key.casefold())
            if match:
                yield value
        for child in value.values():
            yield from _walk_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_records(child)


def _catalog_index(
    catalog: OfficialCatalog,
    version_index: int,
    transcript_states: Mapping[str, tuple[str, bool]],
) -> dict[str, _Occurrence]:
    result: dict[str, _Occurrence] = {}
    catalog_values = [catalog.value]
    if catalog.conversation_value is not None:
        catalog_values.append(catalog.conversation_value)
    for record in _walk_records(catalog_values):
        filename = normalize_filename(record["filename"])
        if not filename:
            continue
        audio_key = str(record["audioKey"])
        match = AUDIO_KEY_RE.search(audio_key.casefold())
        assert match is not None
        audio_sha = match.group("sha")
        transcript = transcript_states.get(audio_sha)
        if transcript is None:
            raise VoiceLineHistoryError(
                f"Official version {catalog.id!r} uses recording {audio_sha} at "
                f"{filename!r}, but the transcript repository has no state for that SHA-256."
            )
        voiceline_id = record.get("voiceline_id")
        occurrence = _Occurrence(
            version_index=version_index,
            version_id=catalog.id,
            audio_key=audio_key,
            audio_sha256=audio_sha,
            transcription=transcript[0],
            official=transcript[1],
            voiceline_id=voiceline_id if isinstance(voiceline_id, str) and voiceline_id else None,
        )
        previous = result.get(filename)
        if previous is not None and previous.audio_sha256 != occurrence.audio_sha256:
            raise VoiceLineHistoryError(
                f"Official version {catalog.id!r} contains different recordings at "
                f"normalized filename {filename!r}."
            )
        if previous is None:
            result[filename] = occurrence
    return result


def _event(first: _Occurrence, last: _Occurrence) -> dict[str, Any]:
    result: dict[str, Any] = {
        "fromVersion": first.version_id,
        "throughVersion": last.version_id,
        "audioKey": first.audio_key,
        "transcription": first.transcription,
    }
    if first.official:
        result["officialtranscription"] = True
    if first.voiceline_id:
        result["voicelineId"] = first.voiceline_id
    return result


def _events(occurrences: list[_Occurrence]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    first = occurrences[0]
    last = first
    for occurrence in occurrences[1:]:
        consecutive = occurrence.version_index == last.version_index + 1
        same_recording = occurrence.audio_sha256 == last.audio_sha256
        if consecutive and same_recording:
            last = occurrence
            continue
        events.append(_event(first, last))
        first = occurrence
        last = occurrence
    events.append(_event(first, last))
    return events


def build_history(
    catalogs: Iterable[OfficialCatalog],
    transcript_states: Mapping[str, tuple[str, bool]],
) -> HistoryBuild:
    versions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    occurrences_by_filename: dict[str, list[_Occurrence]] = {}
    for version_index, catalog in enumerate(catalogs):
        if catalog.id in seen_ids:
            raise VoiceLineHistoryError(
                f"Voice-line history contains duplicate official version ID {catalog.id!r}."
            )
        seen_ids.add(catalog.id)
        version = {
            "id": catalog.id,
            "label": catalog.label,
            "contentRevision": catalog.content_revision,
            "voiceLineSha256": catalog.sha256,
        }
        if catalog.conversation_sha256 is not None:
            version["conversationSha256"] = catalog.conversation_sha256
        versions.append(version)
        for filename, occurrence in _catalog_index(
            catalog, version_index, transcript_states
        ).items():
            occurrences_by_filename.setdefault(filename, []).append(occurrence)
    if not versions:
        raise VoiceLineHistoryError("Voice-line history requires at least one official catalog.")
    fingerprint = sha256_bytes(canonical_json({"versions": versions}))

    lines_by_shard: dict[str, dict[str, Any]] = {}
    multiple_event_filenames: list[str] = []
    transcript_difference_filenames: list[str] = []
    event_count = 0
    for filename in sorted(occurrences_by_filename):
        occurrences = occurrences_by_filename[filename]
        if len(occurrences) < 2:
            continue
        events = _events(occurrences)
        event_count += len(events)
        if len(events) > 1:
            multiple_event_filenames.append(filename)
        if len({event["transcription"] for event in events}) > 1:
            transcript_difference_filenames.append(filename)
        bucket = history_shard(filename)
        lines_by_shard.setdefault(bucket, {})[filename] = {
            "versionCount": len(occurrences),
            "events": events,
        }

    shards = {
        bucket: {
            "schemaVersion": HISTORY_SCHEMA_VERSION,
            "bucket": bucket,
            "lines": lines,
        }
        for bucket, lines in sorted(lines_by_shard.items())
    }
    presence = {
        "schemaVersion": HISTORY_SCHEMA_VERSION,
        "identity": "normalized-filename",
        "criterion": MULTIPLE_EVENTS_CRITERION,
        "lineCount": len(multiple_event_filenames),
        "filenames": multiple_event_filenames,
    }
    transcript_differences = {
        "schemaVersion": HISTORY_SCHEMA_VERSION,
        "identity": "normalized-filename",
        "criterion": TRANSCRIPT_DIFFERENCES_CRITERION,
        "lineCount": len(transcript_difference_filenames),
        "filenames": transcript_difference_filenames,
    }
    return HistoryBuild(
        catalog_fingerprint=fingerprint,
        versions=versions,
        shards=shards,
        presence=presence,
        transcript_differences=transcript_differences,
        history_lines=sum(len(value["lines"]) for value in shards.values()),
        events=event_count,
    )


__all__ = [
    "HISTORY_SCHEMA_VERSION",
    "MULTIPLE_EVENTS_CRITERION",
    "TRANSCRIPT_DIFFERENCES_CRITERION",
    "HistoryBuild",
    "OfficialCatalog",
    "SHARD_COUNT",
    "VoiceLineHistoryError",
    "build_history",
    "canonical_json",
    "history_shard",
    "normalize_filename",
    "sha256_bytes",
]
