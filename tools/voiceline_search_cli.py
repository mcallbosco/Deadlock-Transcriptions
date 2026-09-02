"""Generate and measure the prototype VLViewer site-wide search index."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from .content_sync import validate_repository
from .voiceline_search import SearchCatalog, build_search_index


DEFAULT_MANIFEST_URL = "https://cdn.vlviewer.com/deadlock/manifest.json"


def _read_json_url(url: str, cache_path: Path | None = None) -> dict[str, Any]:
    body: bytes
    if cache_path is not None and cache_path.is_file():
        body = cache_path.read_bytes()
    else:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Deadlock-Transcriptions search-index prototype"},
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read()
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(body)
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object at {url}")
    return value


def _catalogs(
    repo: Path,
    game: str,
    manifest_url: str,
    cache_dir: Path | None,
) -> list[SearchCatalog]:
    config_path = repo / "config" / game / "voice-line-history.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    configured_ids = config.get("officialVersions")
    if not isinstance(configured_ids, list):
        raise ValueError(f"{config_path} has no officialVersions array")
    # Always refresh the small mutable manifest. Catalog caches are partitioned
    # by contentRevision, so updated versions cannot silently reuse stale JSON.
    manifest = _read_json_url(manifest_url)
    entries = {
        entry.get("id"): entry
        for entry in manifest.get("versions", [])
        if isinstance(entry, dict) and entry.get("kind") != "custom"
    }
    result: list[SearchCatalog] = []
    for version_id in configured_ids:
        entry = entries.get(version_id)
        if entry is None:
            print(f"Skipping configured but unpublished version {version_id!r}.", file=sys.stderr)
            continue
        voice_line_url = entry.get("voiceLineUrl")
        conversation_url = entry.get("conversationUrl")
        if not isinstance(voice_line_url, str) or not isinstance(conversation_url, str):
            raise ValueError(f"Official version {version_id!r} has incomplete catalog URLs")
        try:
            content_revision = int(entry.get("contentRevision", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Official version {version_id!r} has an invalid contentRevision"
            ) from exc
        version_cache = (
            cache_dir / "versions" / version_id / str(content_revision)
            if cache_dir is not None
            else None
        )
        print(f"Loading {version_id}...", file=sys.stderr)
        result.append(
            SearchCatalog(
                id=version_id,
                label=str(entry.get("label") or version_id),
                voice_lines=_read_json_url(
                    voice_line_url,
                    version_cache / "voicelines.json" if version_cache is not None else None,
                ),
                conversations=_read_json_url(
                    conversation_url,
                    version_cache / "conversations.json" if version_cache is not None else None,
                ),
                content_revision=content_revision,
            )
        )
    return result


def _manual_correlations(repo: Path, game: str) -> list[list[str]]:
    path = repo / "config" / game / "voice-line-history-correlations.json"
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    correlations = value.get("correlations") if isinstance(value, dict) else None
    if not isinstance(correlations, list):
        raise ValueError(f"{path} has no correlations array")
    return correlations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--game", default="deadlock")
    parser.add_argument("--manifest-url", default=DEFAULT_MANIFEST_URL)
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/search-index"))
    parser.add_argument("--output", type=Path, default=Path(".cache/search-index/voiceline-search.json"))
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    cache_dir = args.cache_dir.resolve() if args.cache_dir else None
    output = args.output.resolve()
    validation = validate_repository(repo, args.game)
    if not validation.valid:
        for error in validation.errors:
            print(error, file=sys.stderr)
        raise ValueError("Transcript repository validation failed.")
    transcript_states = {
        sha: occurrences[0].state.published
        for sha, occurrences in validation.by_sha.items()
        if occurrences
    }
    build = build_search_index(
        _catalogs(repo, args.game, args.manifest_url, cache_dir),
        args.game,
        transcript_states,
        _manual_correlations(repo, args.game),
    )
    body = json.dumps(
        build.value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    compressed = gzip.compress(body, compresslevel=9, mtime=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(body)
    gzip_path = output.with_suffix(output.suffix + ".gz")
    gzip_path.write_bytes(compressed)
    summary = {
        "versions": len(build.value["versions"]),
        "lineages": build.lineages,
        "states": build.states,
        "variants": build.variants,
        "destinations": build.destinations,
        "strings": build.strings,
        "jsonBytes": len(body),
        "gzipBytes": len(compressed),
        "gzipRatio": round(len(compressed) / len(body), 4),
        "output": str(output),
        "gzipOutput": str(gzip_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
