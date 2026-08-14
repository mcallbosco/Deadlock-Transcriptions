"""Schema-v3 transcript helpers shared by validation, audits, and migrations."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable


TRANSCRIPT_SCHEMA_VERSION = 3
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_BLANK_SOURCES = {"skippedeffort", "skippednonspeech"}
SOURCE_PRIORITY = {
    "skippedeffort": 0,
    "skippednonspeech": 0,
    "generated": 1,
    "manual": 2,
    "official": 3,
}


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


def compact_revisions(revisions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
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
        compacted.append(result)
    return compacted
