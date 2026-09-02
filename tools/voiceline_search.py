"""Build a compact, version-aware site-wide voice-line search index."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from itertools import chain
from typing import Any, Iterable, Iterator, Mapping

from .voiceline_history import build_filename_lineages, normalize_filename


AUDIO_KEY_RE = re.compile(
    r"(?:^|/)sha256/[0-9a-f]{2}/(?P<sha>[0-9a-f]{64})\.mp3$"
)
SEARCH_INDEX_SCHEMA_VERSION = 1
NORMAL_DESTINATION = 0
CONVERSATION_DESTINATION = 1


class VoiceLineSearchError(ValueError):
    """Raised when official catalogs cannot produce an unambiguous index."""


@dataclass(frozen=True)
class SearchCatalog:
    id: str
    label: str
    voice_lines: dict[str, Any]
    conversations: dict[str, Any]
    content_revision: int = 0


@dataclass(frozen=True)
class SearchIndexBuild:
    value: dict[str, Any]
    lineages: int
    states: int
    variants: int
    destinations: int
    strings: int


@dataclass(frozen=True)
class _Occurrence:
    version_index: int
    filename: str
    audio_key: str
    audio_sha256: str
    transcription: str
    official: bool
    duration: float | None
    destinations: tuple[tuple[Any, ...], ...]


class _StringTable:
    def __init__(self) -> None:
        self.values: list[str] = []
        self.indexes: dict[str, int] = {}

    def add(self, value: str) -> int:
        existing = self.indexes.get(value)
        if existing is not None:
            return existing
        index = len(self.values)
        self.values.append(value)
        self.indexes[value] = index
        return index


def _audio_sha(audio_key: str) -> str:
    match = AUDIO_KEY_RE.search(audio_key.casefold())
    if match is None:
        raise VoiceLineSearchError(f"Invalid content-addressed audio key: {audio_key!r}")
    return match.group("sha")


def _record_fields(record: dict[str, Any]) -> tuple[str, str, str, bool, float | None]:
    filename_value = record.get("filename")
    audio_key_value = record.get("audioKey")
    transcription_value = record.get("transcription")
    if not isinstance(filename_value, str) or not filename_value.strip():
        raise VoiceLineSearchError("A searchable voice-line record has no filename.")
    if not isinstance(audio_key_value, str) or not audio_key_value.strip():
        raise VoiceLineSearchError(f"Voice line {filename_value!r} has no audioKey.")
    if not isinstance(transcription_value, str):
        raise VoiceLineSearchError(f"Voice line {filename_value!r} has no transcription.")
    duration_value = record.get("duration")
    duration = (
        float(duration_value)
        if isinstance(duration_value, (int, float)) and not isinstance(duration_value, bool)
        else None
    )
    return (
        normalize_filename(filename_value),
        audio_key_value,
        transcription_value,
        record.get("officialtranscription") is True,
        duration,
    )


def _walk_voice_line_records(
    value: Any,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[dict[str, Any], tuple[str, ...]]]:
    if isinstance(value, dict):
        if all(key in value for key in ("filename", "audioKey", "transcription")):
            yield value, path
            return
        for key in sorted(value):
            yield from _walk_voice_line_records(value[key], (*path, str(key)))
    elif isinstance(value, list):
        for child in value:
            yield from _walk_voice_line_records(child, path)


def _normal_occurrences(catalog: SearchCatalog, version_index: int) -> Iterator[_Occurrence]:
    for record, path in _walk_voice_line_records(catalog.voice_lines):
        filename, audio_key, transcription, official, duration = _record_fields(record)
        if not filename:
            continue
        character = path[0] if path else ""
        hierarchy = path[1:] if len(path) > 1 else ()
        voiceline_id = record.get("voiceline_id")
        destination = (
            NORMAL_DESTINATION,
            filename,
            character,
            hierarchy,
            voiceline_id if isinstance(voiceline_id, str) else "",
        )
        yield _Occurrence(
            version_index,
            filename,
            audio_key,
            _audio_sha(audio_key),
            transcription,
            official,
            duration,
            (destination,),
        )


def _conversation_occurrences(
    catalog: SearchCatalog,
    version_index: int,
) -> Iterator[_Occurrence]:
    conversations = catalog.conversations.get("conversations")
    if not isinstance(conversations, list):
        raise VoiceLineSearchError(
            f"Conversation catalog {catalog.id!r} has no conversations array."
        )
    ordered = sorted(
        (item for item in conversations if isinstance(item, dict)),
        key=lambda item: str(item.get("conversation_id", "")),
    )
    for conversation in ordered:
        conversation_id = conversation.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id:
            raise VoiceLineSearchError(
                f"Conversation catalog {catalog.id!r} contains an entry without an ID."
            )
        speakers_value = conversation.get("speakers")
        speakers = tuple(
            str(value) for value in speakers_value
        ) if isinstance(speakers_value, list) else ()
        lines = conversation.get("lines")
        if not isinstance(lines, list):
            continue
        for line in lines:
            if not isinstance(line, dict):
                continue
            filename, audio_key, transcription, official, duration = _record_fields(line)
            speaker = line.get("speaker")
            part = line.get("part")
            variation = line.get("variation")
            destination = (
                CONVERSATION_DESTINATION,
                filename,
                conversation_id,
                speaker if isinstance(speaker, str) else "",
                speakers,
                int(part) if isinstance(part, int) and not isinstance(part, bool) else 0,
                int(variation)
                if isinstance(variation, int) and not isinstance(variation, bool)
                else 0,
            )
            yield _Occurrence(
                version_index,
                filename,
                audio_key,
                _audio_sha(audio_key),
                transcription,
                official,
                duration,
                (destination,),
            )


def _catalog_occurrences(
    catalog: SearchCatalog,
    version_index: int,
    transcript_states: Mapping[str, tuple[str, bool]],
) -> list[_Occurrence]:
    merged: dict[str, _Occurrence] = {}
    for occurrence in chain(
        _normal_occurrences(catalog, version_index),
        _conversation_occurrences(catalog, version_index),
    ):
        transcript_state = transcript_states.get(occurrence.audio_sha256)
        if transcript_state is None:
            raise VoiceLineSearchError(
                f"Official version {catalog.id!r} uses recording "
                f"{occurrence.audio_sha256} at {occurrence.filename!r}, but the transcript "
                "repository has no state for that SHA-256."
            )
        occurrence = _Occurrence(
            version_index=occurrence.version_index,
            filename=occurrence.filename,
            audio_key=occurrence.audio_key,
            audio_sha256=occurrence.audio_sha256,
            transcription=transcript_state[0],
            official=transcript_state[1],
            duration=occurrence.duration,
            destinations=occurrence.destinations,
        )
        previous = merged.get(occurrence.filename)
        if previous is None:
            merged[occurrence.filename] = occurrence
            continue
        if (
            previous.audio_sha256 != occurrence.audio_sha256
            or previous.transcription != occurrence.transcription
        ):
            raise VoiceLineSearchError(
                f"Official version {catalog.id!r} has conflicting searchable states for "
                f"{occurrence.filename!r}."
            )
        merged[occurrence.filename] = _Occurrence(
            version_index=version_index,
            filename=previous.filename,
            audio_key=previous.audio_key,
            audio_sha256=previous.audio_sha256,
            transcription=previous.transcription,
            official=previous.official or occurrence.official,
            duration=previous.duration if previous.duration is not None else occurrence.duration,
            destinations=tuple(sorted(set(previous.destinations + occurrence.destinations))),
        )
    return [merged[filename] for filename in sorted(merged)]


def _encode_destination(destination: tuple[Any, ...], strings: _StringTable) -> list[Any]:
    if destination[0] == NORMAL_DESTINATION:
        _, filename, character, hierarchy, voiceline_id = destination
        return [
            NORMAL_DESTINATION,
            strings.add(filename),
            strings.add(character),
            [strings.add(value) for value in hierarchy],
            strings.add(voiceline_id) if voiceline_id else -1,
        ]
    _, filename, conversation_id, speaker, speakers, part, variation = destination
    return [
        CONVERSATION_DESTINATION,
        strings.add(filename),
        strings.add(conversation_id),
        strings.add(speaker) if speaker else -1,
        [strings.add(value) for value in speakers],
        part,
        variation,
    ]


def _encode_variant(occurrences: list[_Occurrence], strings: _StringTable) -> list[Any]:
    first = min(occurrences, key=lambda item: (item.filename, item.audio_key))
    destinations = sorted(
        {destination for item in occurrences for destination in item.destinations}
    )
    duration = first.duration
    return [
        strings.add(first.transcription),
        strings.add(
            base64.urlsafe_b64encode(bytes.fromhex(first.audio_sha256))
            .rstrip(b"=")
            .decode("ascii")
        ),
        [_encode_destination(value, strings) for value in destinations],
        1 if any(item.official for item in occurrences) else 0,
        round(duration, 3) if duration is not None else None,
    ]


def _searchable_variant_signature(variants: list[list[Any]]) -> list[list[Any]]:
    """Exclude playback-only fields when deciding whether search state changed."""
    return [[variant[0], variant[2], variant[3]] for variant in variants]


def _compact_strings(records: list[list[Any]], strings: _StringTable) -> list[str]:
    """Remove strings interned by version states that were later collapsed."""
    referenced: set[int] = set()
    for record in records:
        referenced.add(record[0])
        referenced.update(record[1])
        for state in record[2]:
            for variant in state[2]:
                referenced.update((variant[0], variant[1]))
                for destination in variant[2]:
                    if destination[0] == NORMAL_DESTINATION:
                        referenced.update((destination[1], destination[2]))
                        referenced.update(destination[3])
                        if destination[4] >= 0:
                            referenced.add(destination[4])
                    else:
                        referenced.update((destination[1], destination[2]))
                        if destination[3] >= 0:
                            referenced.add(destination[3])
                        referenced.update(destination[4])

    ordered = sorted(referenced)
    remap = {old: new for new, old in enumerate(ordered)}
    for record in records:
        record[0] = remap[record[0]]
        record[1] = [remap[value] for value in record[1]]
        for state in record[2]:
            for variant in state[2]:
                variant[0] = remap[variant[0]]
                variant[1] = remap[variant[1]]
                for destination in variant[2]:
                    destination[1] = remap[destination[1]]
                    destination[2] = remap[destination[2]]
                    if destination[0] == NORMAL_DESTINATION:
                        destination[3] = [remap[value] for value in destination[3]]
                        if destination[4] >= 0:
                            destination[4] = remap[destination[4]]
                    else:
                        if destination[3] >= 0:
                            destination[3] = remap[destination[3]]
                        destination[4] = [remap[value] for value in destination[4]]
    return [strings.values[index] for index in ordered]


def build_search_index(
    catalogs: Iterable[SearchCatalog],
    game: str,
    transcript_states: Mapping[str, tuple[str, bool]],
    manual_correlations: Iterable[Iterable[str]] = (),
) -> SearchIndexBuild:
    """Build the complete index in oldest-to-newest catalog order."""
    catalog_list = list(catalogs)
    if not catalog_list:
        raise VoiceLineSearchError("Search index requires at least one official catalog.")
    ids = [catalog.id for catalog in catalog_list]
    if len(ids) != len(set(ids)):
        raise VoiceLineSearchError("Search index contains duplicate version IDs.")

    by_filename: dict[str, list[_Occurrence]] = {}
    filenames_by_sha: dict[str, set[str]] = {}
    for version_index, catalog in enumerate(catalog_list):
        for occurrence in _catalog_occurrences(
            catalog,
            version_index,
            transcript_states,
        ):
            by_filename.setdefault(occurrence.filename, []).append(occurrence)
            filenames_by_sha.setdefault(occurrence.audio_sha256, set()).add(
                occurrence.filename
            )

    correlation_groups = [list(group) for group in manual_correlations]
    lineage_for_filename = build_filename_lineages(
        filenames_by_sha,
        correlation_groups,
    )
    by_lineage: dict[str, list[_Occurrence]] = {}
    aliases_by_lineage: dict[str, set[str]] = {}
    for filename, filename_occurrences in by_filename.items():
        lineage = lineage_for_filename[filename]
        by_lineage.setdefault(lineage, []).extend(filename_occurrences)
        aliases_by_lineage.setdefault(lineage, set()).add(filename)

    strings = _StringTable()
    records: list[list[Any]] = []
    state_count = 0
    variant_count = 0
    destination_count = 0
    for lineage in sorted(by_lineage):
        lineage_occurrences = by_lineage[lineage]
        by_version: dict[int, list[_Occurrence]] = {}
        for occurrence in lineage_occurrences:
            by_version.setdefault(occurrence.version_index, []).append(occurrence)

        encoded_states: list[list[Any]] = []
        for version_index in sorted(by_version):
            by_audio: dict[str, list[_Occurrence]] = {}
            for occurrence in by_version[version_index]:
                by_audio.setdefault(occurrence.audio_sha256, []).append(occurrence)
            variants = [
                _encode_variant(by_audio[audio_sha], strings)
                for audio_sha in sorted(by_audio)
            ]
            if (
                encoded_states
                and version_index == encoded_states[-1][1] + 1
                and _searchable_variant_signature(variants)
                == _searchable_variant_signature(encoded_states[-1][2])
            ):
                encoded_states[-1][1] = version_index
                # Search applicability is unchanged, but playback should use the
                # newest recording and duration within the represented period.
                encoded_states[-1][2] = variants
            else:
                encoded_states.append([version_index, version_index, variants])
                state_count += 1

        variant_count += sum(len(state[2]) for state in encoded_states)
        destination_count += sum(
            len(variant[2])
            for state in encoded_states
            for variant in state[2]
        )

        aliases = sorted(aliases_by_lineage[lineage])
        earliest_version = min(item.version_index for item in lineage_occurrences)
        canonical = min(
            item.filename
            for item in lineage_occurrences
            if item.version_index == earliest_version
        )
        records.append(
            [
                strings.add(canonical),
                [strings.add(alias) for alias in aliases],
                encoded_states,
            ]
        )

    compacted_strings = _compact_strings(records, strings)
    value = {
        "schemaVersion": SEARCH_INDEX_SCHEMA_VERSION,
        "game": game,
        "identity": "transitive-audio-sha256-lineage",
        "lineageSources": [
            "audio-sha256",
            *(["manual-correlations"] if correlation_groups else []),
        ],
        "versionOrder": "oldest-to-newest",
        "versions": [
            {
                "id": catalog.id,
                "label": catalog.label,
                "contentRevision": catalog.content_revision,
            }
            for catalog in catalog_list
        ],
        "destinationTypes": {"normal": NORMAL_DESTINATION, "conversation": CONVERSATION_DESTINATION},
        "layout": {
            "record": ["canonicalFilename", "aliases", "states"],
            "state": ["fromVersionIndex", "throughVersionIndex", "variants"],
            "variant": ["transcription", "audioSha256Base64Url", "destinations", "official", "duration"],
            "normalDestination": ["type", "filename", "character", "hierarchy", "voicelineId"],
            "conversationDestination": ["type", "filename", "conversationId", "speaker", "speakers", "part", "variation"],
            "stringReferences": "All string-valued record fields are indexes into strings; -1 means absent.",
        },
        "strings": compacted_strings,
        "records": records,
    }
    return SearchIndexBuild(
        value=value,
        lineages=len(records),
        states=state_count,
        variants=variant_count,
        destinations=destination_count,
        strings=len(compacted_strings),
    )


__all__ = [
    "CONVERSATION_DESTINATION",
    "NORMAL_DESTINATION",
    "SEARCH_INDEX_SCHEMA_VERSION",
    "SearchCatalog",
    "SearchIndexBuild",
    "VoiceLineSearchError",
    "build_search_index",
]
