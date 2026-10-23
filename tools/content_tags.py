"""Validate transcript-owned content tags and build deterministic CDN projections."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .transcript_schema import TAG_ID_RE, revision_tags
from .voiceline_history import build_filename_lineages

AUDIO_KEY_RE = re.compile(r"(?:^|/)sha256/[0-9a-f]{2}/([0-9a-f]{64})\.mp3$")


def validate_definitions(value: dict[str, Any], game: str) -> list[dict[str, str]]:
    if set(value) != {"schemaVersion", "game", "tags"} or value.get("schemaVersion") != 1 or value.get("game") != game:
        raise ValueError(f"content-tags must contain schemaVersion 1, game {game!r}, and tags")
    definitions = value["tags"]
    if not isinstance(definitions, list):
        raise ValueError("content-tags tags must be an array")
    seen = set()
    for tag in definitions:
        if not isinstance(tag, dict) or set(tag) - {"id", "label", "description"}:
            raise ValueError("content-tags definitions require id, label, and optional description")
        tag_id = tag.get("id")
        if not isinstance(tag_id, str) or not TAG_ID_RE.fullmatch(tag_id) or tag_id in seen:
            raise ValueError(f"Invalid or duplicate content tag ID: {tag_id!r}")
        seen.add(tag_id)
        if not isinstance(tag.get("label"), str) or not tag["label"].strip():
            raise ValueError(f"Content tag {tag_id!r} requires a non-empty label")
        if "description" in tag and (not isinstance(tag["description"], str) or not tag["description"].strip()):
            raise ValueError(f"Content tag {tag_id!r} has an invalid description")
    return definitions


def logical_tag_groups(documents: Mapping[str, dict[str, Any]], correlations: list[list[str]]) -> list[list[tuple[str, int]]]:
    """Use correction-editor lineage/exact-text boundaries, never global text matches."""
    filenames_by_sha: dict[str, set[str]] = {}
    for filename, document in documents.items():
        for revision in document["revisions"]:
            for sha in revision["sha256"]:
                filenames_by_sha.setdefault(sha, set()).add(filename)
    lineages = build_filename_lineages(filenames_by_sha, correlations)
    groups: dict[tuple[Any, ...], list[tuple[str, int]]] = {}
    for filename, document in documents.items():
        for index, revision in enumerate(document["revisions"]):
            text = revision["text"].strip()
            if not text and revision["source"] != "skippednonspeech":
                key = (filename, index)
            elif not text and revision["source"] == "skippednonspeech":
                key = (lineages.get(filename, filename), "non-speech")
            else:
                key = (lineages.get(filename, filename), "text", text)
            groups.setdefault(key, []).append((filename, index))
    return list(groups.values())


def assignment_errors(documents: Mapping[str, dict[str, Any]], definitions: list[dict[str, str]], correlations: list[list[str]]) -> list[str]:
    allowed = {tag["id"] for tag in definitions}
    errors = []
    by_sha: dict[str, tuple[tuple[str, ...], str]] = {}
    tagged = False
    for filename, document in documents.items():
        for index, revision in enumerate(document["revisions"]):
            location = f"transcripts/{filename}.json revisions[{index}]"
            tags = revision_tags(revision)
            tagged |= bool(tags)
            if unknown := set(tags) - allowed:
                errors.append(f"{location}: undefined content tags {', '.join(sorted(unknown))}")
            for sha in revision["sha256"]:
                previous = by_sha.setdefault(sha, (tags, location))
                if previous[0] != tags:
                    errors.append(f"Conflicting content tags for {sha}: {previous[1]} and {location}")
    if tagged:
        for group in logical_tag_groups(documents, correlations):
            if len({revision_tags(documents[name]["revisions"][index]) for name, index in group}) > 1:
                locations = ', '.join(f"transcripts/{name}.json revisions[{index}]" for name, index in group)
                errors.append(f"Conflicting content tags in logical group: {locations}; use tools.set_content_tags to update all aliases")
    return errors


def build_artifacts(game: str, definitions: list[dict[str, str]], by_sha: Mapping[str, tuple[str, ...]], cdn_base_url: str) -> list[tuple[str, dict[str, Any]]]:
    artifacts = []
    catalogue_tags = []

    def address(prefix: str, value: dict[str, Any]) -> tuple[str, bytes, str]:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        return f"{game}/tags/content/{prefix}/{digest}.json", body, digest

    for definition in sorted(definitions, key=lambda tag: tag["id"]):
        tag_id = definition["id"]
        hashes = sorted(sha for sha, tags in by_sha.items() if tag_id in tags)
        value = {"schemaVersion": 1, "game": game, "identity": "audio-sha256", "tagId": tag_id, "hashes": hashes}
        key, body, digest = address("memberships", value)
        artifacts.append((key, value))
        entry = {"id": tag_id, "label": definition["label"]}
        if "description" in definition:
            entry["description"] = definition["description"]
        entry["membership"] = {"url": f"{cdn_base_url}/{key}", "bytes": len(body), "sha256": digest, "recordingCount": len(hashes)}
        catalogue_tags.append(entry)
    catalogue = {"schemaVersion": 1, "game": game, "identity": "audio-sha256", "tags": catalogue_tags}
    key, _, _ = address("catalog", catalogue)
    artifacts.append((key, catalogue))
    return artifacts


def project_conversation_tags(value: dict[str, Any], by_sha: Mapping[str, tuple[str, ...]]) -> int:
    """Materialize tags on lines/variations and exact unions on their containers."""
    changed = 0

    def assign(item: dict[str, Any], tags: set[str]) -> None:
        nonlocal changed
        result = sorted(tags)
        if item.get("contentTags") != result:
            item["contentTags"] = result
            changed += 1

    def line_tags(item: Any) -> set[str]:
        if isinstance(item, list):
            return set().union(*(line_tags(child) for child in item))
        if not isinstance(item, dict):
            return set()
        tags = set()
        for key, child in list(item.items()):
            if key != "contentTags" and isinstance(child, (dict, list)):
                tags.update(line_tags(child))
        audio = item.get("audioKey")
        match = AUDIO_KEY_RE.search(audio.casefold()) if isinstance(audio, str) else None
        if match:
            tags.update(by_sha.get(match[1], ()))
        # Nested metadata objects are not recording/variation objects.
        if "audioKey" in item or "filename" in item or "variations" in item:
            assign(item, tags)
        return tags

    def walk(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            if isinstance(item.get("lines"), list):
                tags = set()
                for line in item["lines"]:
                    line_result = line_tags(line)
                    tags.update(line_result)
                    if isinstance(line, dict):
                        assign(line, line_result)
                assign(item, tags)
            else:
                for child in list(item.values()):
                    walk(child)

    walk(value)
    return changed
