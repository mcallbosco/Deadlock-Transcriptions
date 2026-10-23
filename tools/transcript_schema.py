"""Schema-v3 transcript helpers shared by validation, audits, and migrations."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable


TRANSCRIPT_SCHEMA_VERSION = 3
TAG_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_BLANK_SOURCES = {"skippedeffort", "skippednonspeech"}
SOURCE_PRIORITY = {
    "skippedeffort": 0,
    "skippednonspeech": 0,
    "generated": 1,
    "manual": 2,
    "official": 3,
}


def revision_tags(revision: dict[str, Any]) -> tuple[str, ...]:
    """Validate editorial metadata independently of text/source precedence."""
    tags = revision.get("tags", [])
    if not isinstance(tags, list) or any(
        not isinstance(tag, str) or not TAG_ID_RE.fullmatch(tag) for tag in tags
    ):
        raise ValueError("revision tags must be an array of lowercase slug IDs")
    if len(tags) != len(set(tags)):
        raise ValueError("revision tags must not contain duplicate IDs")
    return tuple(sorted(tags))


def matching_revision_tags(revisions: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    sets = {revision_tags(revision) for revision in revisions}
    if len(sets) > 1:
        raise ValueError("Conflicting content tags: resolve the tag sets in the transcript repository before merging groups")
    return next(iter(sets), ())


def transcript_match_key(text: str) -> str:
    """Ignore case, Unicode punctuation, and all whitespace for grouping."""
    return "".join(
        character
        for character in text.casefold()
        if not character.isspace()
        and not unicodedata.category(character).startswith("P")
    )


def transcript_group_key(revision: dict[str, Any]) -> tuple[str, str]:
    text = str(revision.get("text") or "")
    source = str(revision.get("source") or "")
    if not text.strip() and source in TERMINAL_BLANK_SOURCES:
        return "terminal-blank", source
    return "text", transcript_match_key(text)


def revision_hashes(revision: dict[str, Any]) -> list[str]:
    value = revision.get("sha256")
    if not isinstance(value, list):
        raise ValueError("revision sha256 must be an array")
    return value


def revision_contains_hash(revision: dict[str, Any], sha256: str) -> bool:
    hashes = revision.get("sha256")
    return isinstance(hashes, list) and sha256 in hashes


def revisions_for_hash(document: dict[str, Any], sha256: str) -> list[dict[str, Any]]:
    revisions = document.get("revisions")
    if not isinstance(revisions, list):
        return []
    return [
        revision
        for revision in revisions
        if isinstance(revision, dict) and revision_contains_hash(revision, sha256)
    ]


def revision_group_identity(path: str, revision: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return path, tuple(revision_hashes(revision))


def preserve_revision_tags(
    original: Iterable[dict[str, Any]], revisions: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Carry tags through writers that reconstruct text/source revisions.

    Hashes added to an existing group inherit its metadata. Combining existing
    recordings with different assignments requires an explicit tag edit first.
    """
    by_sha: dict[str, tuple[str, ...]] = {}
    explicit: set[str] = set()
    for revision in original:
        tags = revision_tags(revision)
        for sha in revision_hashes(revision):
            if sha in by_sha and by_sha[sha] != tags:
                raise ValueError(f"Conflicting content tags for recording {sha}")
            by_sha[sha] = tags
            if "tags" in revision:
                explicit.add(sha)
    result = []
    for revision in revisions:
        hashes = revision_hashes(revision)
        sets = {by_sha[sha] for sha in hashes if sha in by_sha}
        if len(sets) > 1:
            raise ValueError("Conflicting content tags: resolve the tag sets in the transcript repository before merging groups")
        updated = dict(revision)
        if sets:
            tags = next(iter(sets))
            if tags or any(sha in explicit for sha in hashes):
                updated["tags"] = list(tags)
            else:
                updated.pop("tags", None)
        result.append(updated)
    return result


def compact_revisions(
    revisions: Iterable[dict[str, Any]], *, original_revisions: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if original_revisions is not None:
        revisions = preserve_revision_tags(original_revisions, revisions)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    order: list[tuple[str, str]] = []
    for revision in revisions:
        key = transcript_group_key(revision)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(revision)

    compacted: list[dict[str, Any]] = []
    for key in order:
        members = grouped[key]
        tags = matching_revision_tags(members)
        chosen_source = max(
            (str(member.get("source") or "") for member in members),
            key=lambda source: SOURCE_PRIORITY.get(source, -1),
        )
        candidates = [member for member in members if member.get("source") == chosen_source]
        counts = Counter(str(member.get("text") or "") for member in candidates)
        chosen_text = max(counts, key=lambda text: counts[text])
        hashes = sorted(
            {
                digest
                for member in members
                for digest in revision_hashes(member)
            }
        )
        result: dict[str, Any] = {
            "sha256": hashes,
            "text": chosen_text,
            "source": chosen_source,
        }
        if chosen_source in {"generated", "skippednonspeech"}:
            models = {
                member["model"]
                for member in candidates
                if isinstance(member.get("model"), str) and member["model"]
            }
            if len(models) == 1:
                result["model"] = next(iter(models))
        if tags or any("tags" in member for member in members):
            result["tags"] = list(tags)
        compacted.append(result)
    return compacted
