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
HISTORY_CONFIG_SCHEMA_VERSION = 1
HISTORY_CORRELATIONS_SCHEMA_VERSION = 1
HISTORY_INDEX_SCHEMA_VERSION = 1
HISTORY_SCHEMA_VERSION = 2
TRANSCRIPT_LINEAGE_SCHEMA_VERSION = 1
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
    transcript_lineages: dict[str, dict[str, Any]]
    presence: dict[str, Any]
    transcript_differences: dict[str, Any]
    history_lines: int
    events: int
    lineages: int
    branched_lineages: int
    aliased_lineages: int
    transcript_difference_lines: int
    max_aliases_per_lineage: int
    max_variants_per_period: int
    transcript_lineage_lines: int
    transcript_lineages_count: int


@dataclass(frozen=True)
class _Occurrence:
    version_index: int
    version_id: str
    audio_key: str
    audio_sha256: str
    transcription: str
    official: bool
    voiceline_id: str | None
    filename: str


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
            filename=filename,
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


def _variant(occurrences: list[_Occurrence]) -> dict[str, Any]:
    """Build one recording variant active under one or more aliases."""
    first = min(occurrences, key=lambda item: (item.filename, item.audio_key))
    result: dict[str, Any] = {
        "filenames": sorted({item.filename for item in occurrences}),
        "audioKey": first.audio_key,
        "transcription": first.transcription,
    }
    if first.official:
        result["officialtranscription"] = True
    voiceline_ids = sorted(
        {item.voiceline_id for item in occurrences if item.voiceline_id is not None}
    )
    if voiceline_ids:
        result["voicelineIds"] = voiceline_ids
    return result


def _periods(
    occurrences: list[_Occurrence],
) -> tuple[list[dict[str, Any]], bool]:
    """Collapse consecutive versions only when their complete active state matches."""
    by_version: dict[int, list[_Occurrence]] = {}
    for occurrence in occurrences:
        by_version.setdefault(occurrence.version_index, []).append(occurrence)

    version_states: list[tuple[int, str, list[dict[str, Any]]]] = []
    branched = False
    for version_index in sorted(by_version):
        by_sha: dict[str, list[_Occurrence]] = {}
        for occurrence in by_version[version_index]:
            by_sha.setdefault(occurrence.audio_sha256, []).append(occurrence)
        variants = [
            _variant(by_sha[audio_sha])
            for audio_sha in sorted(by_sha)
        ]
        branched = branched or len(variants) > 1
        version_states.append(
            (version_index, by_version[version_index][0].version_id, variants)
        )

    periods: list[dict[str, Any]] = []
    first_index, first_version, first_variants = version_states[0]
    previous_index = first_index
    through_version = first_version
    for version_index, version_id, variants in version_states[1:]:
        if version_index == previous_index + 1 and variants == first_variants:
            previous_index = version_index
            through_version = version_id
            continue
        periods.append(
            {
                "fromVersion": first_version,
                "throughVersion": through_version,
                "variants": first_variants,
            }
        )
        first_index = version_index
        first_version = version_id
        first_variants = variants
        previous_index = version_index
        through_version = version_id
    periods.append(
        {
            "fromVersion": first_version,
            "throughVersion": through_version,
            "variants": first_variants,
        }
    )
    return periods, branched


class _FilenameComponents:
    def __init__(self, filenames: Iterable[str]) -> None:
        self.parent = {filename: filename for filename in filenames}

    def find(self, filename: str) -> str:
        parent = self.parent[filename]
        if parent != filename:
            self.parent[filename] = self.find(parent)
        return self.parent[filename]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        # The root is not externally meaningful, but choosing it deterministically
        # makes complete regenerations easier to reason about.
        if left_root < right_root:
            self.parent[right_root] = left_root
        else:
            self.parent[left_root] = right_root


def build_filename_lineages(
    filenames_by_sha: Mapping[str, Iterable[str]],
    manual_correlations: Iterable[Iterable[str]] = (),
) -> dict[str, str]:
    """Return the deterministic transitive recording lineage for each filename.

    Shared audio creates the automatic edges. Reviewed manual groups add edges
    for renamed files whose recordings changed, including simultaneous variants.
    """
    filenames = sorted(
        {
            normalize_filename(filename)
            for values in filenames_by_sha.values()
            for filename in values
            if normalize_filename(filename)
        }
    )
    components = _FilenameComponents(filenames)
    for values in filenames_by_sha.values():
        ordered = sorted(
            {
                normalize_filename(filename)
                for filename in values
                if normalize_filename(filename)
            }
        )
        for filename in ordered[1:]:
            components.union(ordered[0], filename)
    known_filenames = set(filenames)
    for index, values in enumerate(manual_correlations):
        if isinstance(values, (str, bytes)):
            raise VoiceLineHistoryError(
                f"Manual correlation group {index} must be an array of filenames."
            )
        raw_values = list(values)
        if any(not isinstance(value, str) for value in raw_values):
            raise VoiceLineHistoryError(
                f"Manual correlation group {index} must contain only filenames."
            )
        ordered = sorted({normalize_filename(value) for value in raw_values})
        if len(ordered) < 2:
            raise VoiceLineHistoryError(
                f"Manual correlation group {index} must contain at least two unique filenames."
            )
        unknown = sorted(set(ordered) - known_filenames)
        if unknown:
            raise VoiceLineHistoryError(
                f"Manual correlation group {index} references filenames absent from all "
                f"official catalogs: {', '.join(unknown)}"
            )
        for filename in ordered[1:]:
            components.union(ordered[0], filename)
    return {filename: components.find(filename) for filename in filenames}


def build_history(
    catalogs: Iterable[OfficialCatalog],
    transcript_states: Mapping[str, tuple[str, bool]],
    manual_correlations: Iterable[Iterable[str]] = (),
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

    filenames_by_sha: dict[str, set[str]] = {}
    for filename, occurrences in occurrences_by_filename.items():
        for occurrence in occurrences:
            filenames_by_sha.setdefault(occurrence.audio_sha256, set()).add(filename)
    components = build_filename_lineages(filenames_by_sha, manual_correlations)

    occurrences_by_component: dict[str, list[_Occurrence]] = {}
    aliases_by_component: dict[str, list[str]] = {}
    for filename, occurrences in occurrences_by_filename.items():
        component = components[filename]
        occurrences_by_component.setdefault(component, []).extend(occurrences)
        aliases_by_component.setdefault(component, []).append(filename)

    # Transcript editing needs every official filename component, including
    # components that exist in only one version and are therefore intentionally
    # omitted from the rendered history timeline below.
    transcript_lineage_lines_by_shard: dict[str, dict[str, Any]] = {}
    for component in sorted(occurrences_by_component):
        occurrences = occurrences_by_component[component]
        aliases = sorted(aliases_by_component[component])
        earliest_version = min(item.version_index for item in occurrences)
        canonical_filename = min(
            item.filename for item in occurrences if item.version_index == earliest_version
        )
        lineage_id = sha256_bytes(
            f"voice-line-lineage-v2\0{canonical_filename}".encode("utf-8")
        )
        membership_sha256 = sha256_bytes(canonical_json(aliases))
        line = {
            "lineageId": lineage_id,
            "membershipSha256": membership_sha256,
            "canonicalFilename": canonical_filename,
            "aliases": aliases,
        }
        for filename in aliases:
            bucket = history_shard(filename)
            transcript_lineage_lines_by_shard.setdefault(bucket, {})[filename] = line

    transcript_lineages = {
        bucket: {
            "schemaVersion": TRANSCRIPT_LINEAGE_SCHEMA_VERSION,
            "bucket": bucket,
            "lines": lines,
        }
        for bucket, lines in sorted(transcript_lineage_lines_by_shard.items())
    }

    lines_by_shard: dict[str, dict[str, Any]] = {}
    multiple_event_filenames: list[str] = []
    transcript_difference_filenames: list[str] = []
    event_count = 0
    lineage_count = 0
    branched_lineage_count = 0
    aliased_lineage_count = 0
    transcript_difference_lines = 0
    max_aliases_per_lineage = 0
    max_variants_per_period = 0
    for component in sorted(occurrences_by_component):
        occurrences = occurrences_by_component[component]
        version_indices = {item.version_index for item in occurrences}
        if len(version_indices) < 2:
            continue
        aliases = sorted(aliases_by_component[component])
        earliest_version = min(version_indices)
        canonical_filename = min(
            item.filename for item in occurrences if item.version_index == earliest_version
        )
        lineage_id = sha256_bytes(
            f"voice-line-lineage-v2\0{canonical_filename}".encode("utf-8")
        )
        periods, branched = _periods(occurrences)
        has_transcript_differences = len(
            {item.transcription for item in occurrences}
        ) > 1
        line = {
            "lineageId": lineage_id,
            "canonicalFilename": canonical_filename,
            "aliases": aliases,
            "versionCount": len(version_indices),
            "hasHistory": True,
            "hasTranscriptDifferences": has_transcript_differences,
            "periods": periods,
        }
        event_count += len(periods)
        lineage_count += 1
        branched_lineage_count += int(branched)
        aliased_lineage_count += int(len(aliases) > 1)
        transcript_difference_lines += len(aliases) * int(has_transcript_differences)
        max_aliases_per_lineage = max(max_aliases_per_lineage, len(aliases))
        max_variants_per_period = max(
            max_variants_per_period,
            *(len(period["variants"]) for period in periods),
        )
        for filename in aliases:
            bucket = history_shard(filename)
            lines_by_shard.setdefault(bucket, {})[filename] = line

    shards = {
        bucket: {
            "schemaVersion": HISTORY_SCHEMA_VERSION,
            "bucket": bucket,
            "lines": lines,
        }
        for bucket, lines in sorted(lines_by_shard.items())
    }
    presence_filenames = sorted(
        filename
        for shard in shards.values()
        for filename, line in shard["lines"].items()
        if len(line["periods"]) > 1
    )
    transcript_difference_filenames = sorted(
        filename
        for shard in shards.values()
        for filename, line in shard["lines"].items()
        if line["hasTranscriptDifferences"]
    )
    presence = {
        "schemaVersion": HISTORY_INDEX_SCHEMA_VERSION,
        "identity": "normalized-filename",
        "criterion": MULTIPLE_EVENTS_CRITERION,
        "lineCount": len(presence_filenames),
        "filenames": presence_filenames,
    }
    transcript_differences = {
        "schemaVersion": HISTORY_INDEX_SCHEMA_VERSION,
        "identity": "normalized-filename",
        "criterion": TRANSCRIPT_DIFFERENCES_CRITERION,
        "lineCount": len(transcript_difference_filenames),
        "filenames": transcript_difference_filenames,
    }
    assert len(transcript_difference_filenames) == transcript_difference_lines
    return HistoryBuild(
        catalog_fingerprint=fingerprint,
        versions=versions,
        shards=shards,
        transcript_lineages=transcript_lineages,
        presence=presence,
        transcript_differences=transcript_differences,
        history_lines=sum(len(value["lines"]) for value in shards.values()),
        events=event_count,
        lineages=lineage_count,
        branched_lineages=branched_lineage_count,
        aliased_lineages=aliased_lineage_count,
        transcript_difference_lines=transcript_difference_lines,
        max_aliases_per_lineage=max_aliases_per_lineage,
        max_variants_per_period=max_variants_per_period,
        transcript_lineage_lines=sum(
            len(value["lines"]) for value in transcript_lineages.values()
        ),
        transcript_lineages_count=len(occurrences_by_component),
    )


__all__ = [
    "HISTORY_SCHEMA_VERSION",
    "HISTORY_CONFIG_SCHEMA_VERSION",
    "HISTORY_CORRELATIONS_SCHEMA_VERSION",
    "HISTORY_INDEX_SCHEMA_VERSION",
    "MULTIPLE_EVENTS_CRITERION",
    "TRANSCRIPT_DIFFERENCES_CRITERION",
    "TRANSCRIPT_LINEAGE_SCHEMA_VERSION",
    "HistoryBuild",
    "OfficialCatalog",
    "SHARD_COUNT",
    "VoiceLineHistoryError",
    "build_filename_lineages",
    "build_history",
    "canonical_json",
    "history_shard",
    "normalize_filename",
    "sha256_bytes",
]
