#!/usr/bin/env python3
"""Find distinct transcript revisions that may be re-encodes of one recording.

The public VLViewer manifests include filename, audio SHA-256, duration and
subtitle.  This audit combines their conversation and voice-line trees across
published versions, then looks only at local schema-v3 transcript documents
that retain different subtitles in separate revisions.  A document is a merge
candidate when hashes belonging to different subtitle revisions have the same
manifest filename and a duration delta inside a requested threshold.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator


ROOT_MANIFEST = "https://cdn.vlviewer.com/deadlock/manifest.json"
AUDIO_KEY = re.compile(r"sha256/[0-9a-f]{2}/([0-9a-f]{64})\.mp3$", re.I)


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "Deadlock-Transcriptions audit"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def entries(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("filename"), str) and isinstance(value.get("audioKey"), str):
            yield value
        for child in value.values():
            yield from entries(child)
    elif isinstance(value, list):
        for child in value:
            yield from entries(child)


def norm_filename(value: str) -> str:
    return value.replace("\\", "/").casefold()


def load_manifest_audio(root: dict[str, Any]) -> tuple[dict[str, dict[str, set[int]]], list[str]]:
    """Return filename -> hash -> observed duration milliseconds."""
    by_filename: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    included: list[str] = []
    for version in root["versions"]:
        # The Russian Voice Mod is a fan-made embedded-transcript version.
        if version.get("id") == "ognb-russian-voice-mod":
            continue
        included.append(version["id"])
        for url_field in ("voiceLineUrl", "conversationUrl"):
            for entry in entries(fetch_json(version[url_field])):
                match = AUDIO_KEY.fullmatch(entry["audioKey"])
                duration = entry.get("duration")
                if not match or not isinstance(duration, (int, float)):
                    continue
                by_filename[norm_filename(entry["filename"])][match.group(1).lower()].add(
                    round(float(duration) * 1000)
                )
    return by_filename, included


def transcript_candidates(
    transcript_root: Path, manifest_audio: dict[str, dict[str, set[int]]]
) -> tuple[dict[int, list[dict[str, Any]]], dict[str, int]]:
    candidates: dict[int, list[dict[str, Any]]] = {0: [], 50: [], 100: []}
    stats = defaultdict(int)
    for path in sorted(transcript_root.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("schemaVersion") != 3 or not isinstance(document.get("filename"), str):
            continue
        revisions = document.get("revisions")
        if not isinstance(revisions, list):
            continue
        texts = {item.get("text") for item in revisions if isinstance(item, dict) and isinstance(item.get("text"), str)}
        if len(texts) < 2:
            continue
        stats["differentSubtitleDocuments"] += 1
        available = manifest_audio.get(norm_filename(document["filename"]), {})
        groups: list[tuple[str, str, list[str]]] = []
        for revision in revisions:
            if not isinstance(revision, dict) or not isinstance(revision.get("text"), str):
                continue
            hashes = [sha.lower() for sha in revision.get("sha256", []) if isinstance(sha, str) and sha.lower() in available]
            if hashes:
                groups.append((revision["text"], revision.get("source", "unknown"), hashes))
        if len(groups) < 2:
            continue
        stats["differentSubtitleDocumentsWithManifestHashes"] += 1
        deltas: list[tuple[int, str, str, str, str]] = []
        for index, (left_text, left_source, left_hashes) in enumerate(groups):
            for right_text, right_source, right_hashes in groups[index + 1 :]:
                if left_text == right_text:
                    continue
                for left_hash in left_hashes:
                    for right_hash in right_hashes:
                        for left_ms in available[left_hash]:
                            for right_ms in available[right_hash]:
                                deltas.append(
                                    (abs(left_ms - right_ms), left_hash, right_hash, left_source, right_source)
                                )
        if not deltas:
            continue
        minimum, left_hash, right_hash, _, _ = min(deltas)
        exact_pairs = [value for value in deltas if value[0] == 0]
        exact_generated_to_authoritative = [
            value
            for value in exact_pairs
            if (value[3] in {"official", "manual"}) != (value[4] in {"official", "manual"})
        ]
        record = {
            "path": path.as_posix(),
            "filename": document["filename"],
            "minimumDurationDeltaMs": minimum,
            "hashPair": [left_hash, right_hash],
            "hasExactOfficialMergeTarget": any(
                "official" in (value[3], value[4]) for value in exact_generated_to_authoritative
            ),
            "hasExactManualMergeTarget": any(
                "manual" in (value[3], value[4]) for value in exact_generated_to_authoritative
            ),
        }
        for threshold in candidates:
            if minimum <= threshold:
                candidates[threshold].append(record)
    return candidates, dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-manifest-url", default=ROOT_MANIFEST)
    parser.add_argument("--transcript-root", type=Path, default=Path("transcripts"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = fetch_json(args.root_manifest_url)
    manifest_audio, versions = load_manifest_audio(root)
    candidates, stats = transcript_candidates(args.transcript_root, manifest_audio)
    report = {
        "rootManifestUrl": args.root_manifest_url,
        "excludedVersionIds": ["ognb-russian-voice-mod"],
        "includedVersionIds": versions,
        "thresholdsMs": {str(threshold): len(records) for threshold, records in candidates.items()},
        "bucketsMs": {
            "exact": len(candidates[0]),
            "1To50": len(candidates[50]) - len(candidates[0]),
            "51To100": len(candidates[100]) - len(candidates[50]),
        },
        "exactCandidateAuthoritativeTargets": {
            "official": sum(record["hasExactOfficialMergeTarget"] for record in candidates[0]),
            "manual": sum(record["hasExactManualMergeTarget"] for record in candidates[0]),
            "officialOrManual": sum(
                record["hasExactOfficialMergeTarget"] or record["hasExactManualMergeTarget"]
                for record in candidates[0]
            ),
        },
        "stats": stats,
        "candidates": {str(threshold): records for threshold, records in candidates.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["thresholdsMs"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
