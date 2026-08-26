#!/usr/bin/env python3
"""Prepare and run a deduplicated GPT transcription pass for duration conflicts."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

try:
    from audit_duration_merge_candidates import AUDIO_KEY, ROOT_MANIFEST, entries, fetch_json, norm_filename
    from audit_fuzzy_transcript_matches import canonical_json
    from build_exact_duration_generated_review_queue import build_items
    from transcript_schema import transcript_match_key
except ModuleNotFoundError:  # Imported as tools.gpt_transcribe_duration_review.
    from tools.audit_duration_merge_candidates import (
        AUDIO_KEY,
        ROOT_MANIFEST,
        entries,
        fetch_json,
        norm_filename,
    )
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.build_exact_duration_generated_review_queue import build_items
    from tools.transcript_schema import transcript_match_key


DEFAULT_OUTPUT_DIR = Path("migration-reports/generated-duration-gpt-transcribe")
DEFAULT_VOCABULARY = Path("config/deadlock/transcription-vocabulary.json")
DEFAULT_MODEL = "gpt-transcribe"
MODEL_USD_PER_MINUTE = {"gpt-transcribe": 0.0045}
PROMPT_PREFIX = (
    "Transcribe this Deadlock voice line in English exactly. Preserve all spoken words. "
    "Do not add commentary or quotation marks. The following JSON contains authoritative "
    "Deadlock spellings, terminology, and transcription guidelines. Follow it when applicable: "
)


def build_transcription_prompt(vocabulary_path: Path) -> str:
    payload = json.loads(vocabulary_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Transcription vocabulary must be a non-empty JSON object")
    for category, values in payload.items():
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Transcription vocabulary has an empty category")
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ValueError(f"Vocabulary category {category!r} must contain non-empty strings")
    return PROMPT_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def load_cdn_audio_index(
    root: dict[str, Any],
) -> tuple[dict[str, dict[str, set[int]]], dict[str, dict[str, Any]], list[str]]:
    """Load durations and the newest published CDN location for every audio hash."""
    by_filename: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    locations: dict[str, dict[str, Any]] = {}
    included_versions: list[str] = []
    shared_audio_base = root["sharedAudioBaseUrl"]
    for version_index, version in enumerate(root["versions"]):
        if version.get("id") == "ognb-russian-voice-mod":
            continue
        included_versions.append(version["id"])
        for url_field in ("voiceLineUrl", "conversationUrl"):
            for entry in entries(fetch_json(version[url_field])):
                match = AUDIO_KEY.fullmatch(entry["audioKey"])
                duration = entry.get("duration")
                if not match or not isinstance(duration, (int, float)):
                    continue
                digest = match.group(1).lower()
                duration_ms = round(float(duration) * 1000)
                by_filename[norm_filename(entry["filename"])][digest].add(duration_ms)
                locations.setdefault(
                    digest,
                    {
                        "sha256": digest,
                        "audioKey": entry["audioKey"],
                        "audioUrl": urljoin(shared_audio_base, entry["audioKey"]),
                        "filename": entry["filename"],
                        "durationMs": duration_ms,
                        "versionId": version["id"],
                        "versionIndex": version_index,
                    },
                )
    return by_filename, locations, included_versions


def group_review_items(
    items: list[dict[str, Any]], locations: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    union_find = UnionFind()
    item_hashes: dict[str, list[str]] = {}
    for item in items:
        hashes = sorted({digest for option in item["options"] for digest in option["hashes"]})
        if not hashes:
            raise ValueError(f"Review item has no hashes: {item['id']}")
        item_hashes[item["id"]] = hashes
        for digest in hashes[1:]:
            union_find.union(hashes[0], digest)
        union_find.find(hashes[0])

    items_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hashes_by_root: dict[str, set[str]] = defaultdict(set)
    for item in items:
        root = union_find.find(item_hashes[item["id"]][0])
        items_by_root[root].append(item)
        hashes_by_root[root].update(item_hashes[item["id"]])

    groups: list[dict[str, Any]] = []
    for root, grouped_items in items_by_root.items():
        hashes = sorted(hashes_by_root[root])
        candidates = [locations[digest] for digest in hashes if digest in locations]
        if not candidates:
            raise ValueError(f"No CDN audio exists for review hashes: {hashes[:3]}")
        representative = min(candidates, key=lambda value: (value["versionIndex"], value["sha256"]))
        recording_id = hashlib.sha256("\n".join(hashes).encode()).hexdigest()
        groups.append(
            {
                "recordingId": recording_id,
                "hashes": hashes,
                "representative": {
                    key: value for key, value in representative.items() if key != "versionIndex"
                },
                "observedDurationMs": sorted(
                    {int(item["durationMs"]) for item in grouped_items}
                ),
                "items": sorted(grouped_items, key=lambda item: item["id"]),
            }
        )
    return sorted(groups, key=lambda group: group["recordingId"])


def prepare_queue(repo: Path, root_manifest_url: str, vocabulary_path: Path) -> dict[str, Any]:
    root = fetch_json(root_manifest_url)
    manifest_audio, locations, included_versions = load_cdn_audio_index(root)
    items = build_items(repo / "transcripts", manifest_audio)
    groups = group_review_items(items, locations)
    total_duration_ms = sum(group["representative"]["durationMs"] for group in groups)
    model_rate = MODEL_USD_PER_MINUTE[DEFAULT_MODEL]
    return {
        "schemaVersion": 1,
        "rootManifestUrl": root_manifest_url,
        "rootManifestUpdatedAt": root.get("updatedAt"),
        "excludedVersionIds": ["ognb-russian-voice-mod"],
        "includedVersionIds": included_versions,
        "model": DEFAULT_MODEL,
        "prompt": build_transcription_prompt(vocabulary_path),
        "promptSource": {
            "implementation": "DLSoundProjectUtilities HistoricalContent build_transcription_prompt",
            "vocabulary": vocabulary_path.relative_to(repo).as_posix(),
        },
        "statistics": {
            "reviewItems": len(items),
            "uniqueRecordingHashes": len({digest for group in groups for digest in group["hashes"]}),
            "recordingGroups": len(groups),
            "totalDurationMs": total_duration_ms,
            "totalDurationMinutes": round(total_duration_ms / 60_000, 3),
            "estimatedModelCostUsd": round(total_duration_ms / 60_000 * model_rate, 4),
        },
        "recordings": groups,
    }


def read_completed_results(path: Path) -> set[str]:
    completed: set[str] = set()
    if not path.exists():
        return completed
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        result = json.loads(line)
        if result.get("status") == "success":
            recording_id = result.get("recordingId")
            if not isinstance(recording_id, str) or recording_id in completed:
                raise ValueError(f"Invalid or duplicate completed result on line {line_number}")
            completed.add(recording_id)
    return completed


def download_verified_audio(recording: dict[str, Any], attempts: int = 4) -> bytes:
    representative = recording["representative"]
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                representative["audioUrl"], headers={"User-Agent": "Deadlock-Transcriptions GPT review"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                audio = response.read()
            actual = hashlib.sha256(audio).hexdigest()
            if actual != representative["sha256"]:
                raise ValueError(
                    f"CDN hash mismatch for {representative['audioUrl']}: {actual}"
                )
            return audio
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"Audio download failed: {last_error}")


def option_comparisons(recording: dict[str, Any], transcription: str) -> list[dict[str, Any]]:
    normalized = transcript_match_key(transcription)
    comparisons: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in recording["items"]:
        for option in item["options"]:
            text = option["text"]
            if text in seen:
                continue
            seen.add(text)
            option_normalized = transcript_match_key(text)
            comparisons.append(
                {
                    "text": text,
                    "normalizedExactMatch": option_normalized == normalized,
                    "similarity": round(SequenceMatcher(None, normalized, option_normalized).ratio(), 6),
                }
            )
    return sorted(
        comparisons,
        key=lambda comparison: (
            not comparison["normalizedExactMatch"],
            -comparison["similarity"],
            comparison["text"],
        ),
    )


def transcribe_recording(
    client: Any, recording: dict[str, Any], *, model: str, prompt: str
) -> dict[str, Any]:
    started = time.time()
    try:
        audio = download_verified_audio(recording)
        representative = recording["representative"]
        response = client.audio.transcriptions.create(
            model=model,
            file=(f"{representative['sha256']}.mp3", audio, "audio/mpeg"),
            response_format="json",
            language="en",
            prompt=prompt,
        )
        transcription = (
            response.get("text", "") if isinstance(response, dict) else response.text
        ).strip()
        return {
            "recordingId": recording["recordingId"],
            "status": "success",
            "model": model,
            "representativeSha256": representative["sha256"],
            "transcription": transcription,
            "optionComparisons": option_comparisons(recording, transcription),
            "elapsedSeconds": round(time.time() - started, 3),
        }
    except Exception as exc:
        return {
            "recordingId": recording["recordingId"],
            "status": "error",
            "model": model,
            "error": str(exc),
            "elapsedSeconds": round(time.time() - started, 3),
        }


def execute_queue(
    queue: dict[str, Any], results_path: Path, *, max_workers: int, max_requests: int | None
) -> dict[str, int]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY in the environment before using the run command")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install requirements-transcription.txt before using the run command") from exc

    completed = read_completed_results(results_path)
    pending = [
        recording for recording in queue["recordings"] if recording["recordingId"] not in completed
    ]
    if max_requests is not None:
        pending = pending[:max_requests]
    results_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=api_key, max_retries=3)
    successes = 0
    errors = 0
    with results_path.open("a", encoding="utf-8", newline="\n") as output:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    transcribe_recording,
                    client,
                    recording,
                    model=queue["model"],
                    prompt=queue["prompt"],
                ): recording
                for recording in pending
            }
            for index, future in enumerate(as_completed(futures), 1):
                result = future.result()
                output.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
                output.flush()
                os.fsync(output.fileno())
                successes += result["status"] == "success"
                errors += result["status"] == "error"
                print(
                    f"[{index}/{len(futures)}] {result['status']} {result['recordingId'][:12]}",
                    flush=True,
                )
    return {"scheduled": len(pending), "successes": successes, "errors": errors}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--root-manifest-url", default=ROOT_MANIFEST)
    prepare.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY)
    prepare.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR / "queue.json")

    run = subparsers.add_parser("run")
    run.add_argument("--queue", type=Path, default=DEFAULT_OUTPUT_DIR / "queue.json")
    run.add_argument("--results", type=Path, default=DEFAULT_OUTPUT_DIR / "results.jsonl")
    run.add_argument("--max-workers", type=int, default=8)
    run.add_argument("--max-requests", type=int)
    run.add_argument("--confirm-paid-requests", action="store_true")

    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.command == "prepare":
        vocabulary = args.vocabulary if args.vocabulary.is_absolute() else repo / args.vocabulary
        output = args.output if args.output.is_absolute() else repo / args.output
        queue = prepare_queue(repo, args.root_manifest_url, vocabulary)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(canonical_json(queue), encoding="utf-8")
        print(canonical_json({"output": str(output), "statistics": queue["statistics"]}), end="")
        return 0

    if not args.confirm_paid_requests:
        parser.error("run requires --confirm-paid-requests because it submits billable API calls")
    if args.max_workers < 1:
        parser.error("--max-workers must be positive")
    if args.max_requests is not None and args.max_requests < 1:
        parser.error("--max-requests must be positive")
    queue_path = args.queue if args.queue.is_absolute() else repo / args.queue
    results_path = args.results if args.results.is_absolute() else repo / args.results
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    print(canonical_json(execute_queue(
        queue,
        results_path,
        max_workers=args.max_workers,
        max_requests=args.max_requests,
    )), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
