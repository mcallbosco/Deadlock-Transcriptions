#!/usr/bin/env python3
"""One-time migration from scalar v2 hashes to grouped schema-v3 transcripts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from transcript_schema import (
    SHA256_RE,
    SOURCE_PRIORITY,
    TRANSCRIPT_SCHEMA_VERSION,
    compact_revisions,
    revision_hashes,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def normalized_revision(value: Any, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: revision must be an object")
    unexpected = set(value) - {"sha256", "text", "source", "model"}
    if unexpected:
        raise ValueError(f"{path}: unexpected revision fields: {sorted(unexpected)}")
    text = value.get("text")
    source = value.get("source")
    if not isinstance(text, str) or source not in SOURCE_PRIORITY:
        raise ValueError(f"{path}: revision has invalid text/source")
    raw_hashes = value.get("sha256")
    if isinstance(raw_hashes, str):
        hashes = [raw_hashes]
    elif raw_hashes is None:
        hashes = []
    elif isinstance(raw_hashes, list):
        hashes = raw_hashes
    else:
        raise ValueError(f"{path}: revision sha256 must be a string, null, or array")
    if any(not isinstance(digest, str) or not SHA256_RE.fullmatch(digest) for digest in hashes):
        raise ValueError(f"{path}: revision contains an invalid SHA-256")
    if len(hashes) != len(set(hashes)):
        raise ValueError(f"{path}: revision contains duplicate SHA-256 values")
    result: dict[str, Any] = {
        "sha256": sorted(hashes),
        "text": text,
        "source": source,
    }
    model = value.get("model")
    if model is not None:
        if not isinstance(model, str) or not model:
            raise ValueError(f"{path}: revision model must be a non-empty string")
        result["model"] = model
    return result


def migrate_document(value: Any, path: Path) -> tuple[dict[str, Any], Counter[tuple[str, str]]]:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: transcript must be an object")
    if value.get("schemaVersion") not in {2, TRANSCRIPT_SCHEMA_VERSION}:
        raise ValueError(f"{path}: unsupported transcript schema version")
    filename = value.get("filename")
    revisions = value.get("revisions")
    if not isinstance(filename, str) or not isinstance(revisions, list):
        raise ValueError(f"{path}: transcript has invalid filename/revisions")
    normalized = [normalized_revision(revision, path) for revision in revisions]
    compacted = compact_revisions(normalized)
    before_by_hash = {
        digest: str(revision["source"])
        for revision in normalized
        for digest in revision_hashes(revision)
    }
    after_by_hash = {
        digest: str(revision["source"])
        for revision in compacted
        for digest in revision_hashes(revision)
    }
    if len(before_by_hash) != sum(len(revision_hashes(revision)) for revision in normalized):
        raise ValueError(f"{path}: one SHA-256 appears in multiple input revisions")
    if set(before_by_hash) != set(after_by_hash):
        raise ValueError(f"{path}: migration changed the represented SHA-256 set")
    promotions = Counter(
        (before_by_hash[digest], after_by_hash[digest])
        for digest in before_by_hash
        if before_by_hash[digest] != after_by_hash[digest]
    )
    return {
        "schemaVersion": TRANSCRIPT_SCHEMA_VERSION,
        "filename": filename,
        "revisions": compacted,
    }, promotions


def migrate(repo: Path, *, apply: bool) -> dict[str, Any]:
    transcript_root = repo / "transcripts"
    files = sorted(transcript_root.rglob("*.json"))
    stats: Counter[str] = Counter()
    promotions: Counter[tuple[str, str]] = Counter()
    for path in files:
        original_text = path.read_text(encoding="utf-8-sig")
        original = json.loads(original_text)
        stats["files"] += 1
        stats["beforeRevisionGroups"] += len(original.get("revisions", []))
        migrated, document_promotions = migrate_document(original, path)
        stats["afterRevisionGroups"] += len(migrated["revisions"])
        stats["hashes"] += sum(len(revision["sha256"]) for revision in migrated["revisions"])
        promotions.update(document_promotions)
        serialized = canonical_json(migrated)
        if serialized != original_text:
            stats["changedFiles"] += 1
            if apply:
                path.write_text(serialized, encoding="utf-8")
    report = {
        "schemaVersion": 1,
        "targetTranscriptSchemaVersion": TRANSCRIPT_SCHEMA_VERSION,
        "applied": apply,
        "normalization": {
            "caseInsensitive": True,
            "ignoreUnicodePunctuation": True,
            "ignoreWhitespace": True,
        },
        "sourcePriority": ["official", "manual", "generated"],
        "statistics": dict(stats),
        "sourceTransitions": {
            f"{before}->{after}": count
            for (before, after), count in sorted(promotions.items())
        },
    }
    if apply:
        report_path = repo / "migration-reports" / "v3-transcript-migration.json"
        report_path.write_text(canonical_json(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(canonical_json(migrate(args.repo.resolve(), apply=args.apply)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
