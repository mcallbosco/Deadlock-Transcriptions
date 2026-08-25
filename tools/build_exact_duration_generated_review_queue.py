#!/usr/bin/env python3
"""Build review batches for exact-duration generated/generated transcript conflicts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

try:
    from audit_duration_merge_candidates import (
        ROOT_MANIFEST,
        fetch_json,
        load_manifest_audio,
        norm_filename,
    )
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import revision_hashes
except ModuleNotFoundError:  # Imported as tools.build_exact_duration_generated_review_queue.
    from tools.audit_duration_merge_candidates import (
        ROOT_MANIFEST,
        fetch_json,
        load_manifest_audio,
        norm_filename,
    )
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import revision_hashes


def build_items(
    transcript_root: Path, manifest_audio: dict[str, dict[str, set[int]]]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(transcript_root.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        if document.get("schemaVersion") != 3 or not isinstance(document.get("filename"), str):
            continue
        durations = manifest_audio.get(norm_filename(document["filename"]), {})
        by_duration: dict[int, list[dict[str, Any]]] = {}
        for revision_index, revision in enumerate(document["revisions"]):
            if revision.get("source") != "generated":
                continue
            hashes_by_duration: dict[int, list[str]] = {}
            for digest in revision_hashes(revision):
                for duration_ms in durations.get(digest, set()):
                    hashes_by_duration.setdefault(duration_ms, []).append(digest)
            for duration_ms, hashes in hashes_by_duration.items():
                by_duration.setdefault(duration_ms, []).append(
                    {
                        "revisionIndex": revision_index,
                        "text": revision.get("text", ""),
                        "model": revision.get("model"),
                        "hashes": sorted(hashes),
                    }
                )
        relative_path = path.relative_to(transcript_root.parent).as_posix()
        for duration_ms, options in sorted(by_duration.items()):
            distinct_texts = {option["text"] for option in options}
            if len(distinct_texts) < 2:
                continue
            items.append(
                {
                    "id": f"{relative_path}#{duration_ms}",
                    "path": relative_path,
                    "filename": document["filename"],
                    "durationMs": duration_ms,
                    "options": options,
                }
            )
    return items


def write_batches(items: list[dict[str, Any]], output_dir: Path, batches: int) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_size = math.ceil(len(items) / batches) if items else 0
    summaries: list[dict[str, Any]] = []
    for index in range(batches):
        start = index * batch_size
        selected = items[start : start + batch_size]
        path = output_dir / f"batch-{index + 1:02d}.json"
        path.write_text(canonical_json({"schemaVersion": 1, "items": selected}), encoding="utf-8")
        summaries.append({"batch": index + 1, "path": path.name, "items": len(selected)})
    return summaries


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--root-manifest-url", default=ROOT_MANIFEST)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("migration-reports/generated-duration-review"),
    )
    parser.add_argument("--batches", type=int, default=12)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else repo / args.output_dir
    root = fetch_json(args.root_manifest_url)
    manifest_audio, versions = load_manifest_audio(root)
    items = build_items(repo / "transcripts", manifest_audio)
    summaries = write_batches(items, output_dir, args.batches)
    manifest = {
        "schemaVersion": 1,
        "rootManifestUrl": args.root_manifest_url,
        "excludedVersionIds": ["ognb-russian-voice-mod"],
        "includedVersionIds": versions,
        "items": len(items),
        "batches": summaries,
    }
    (output_dir / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    print(canonical_json(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
