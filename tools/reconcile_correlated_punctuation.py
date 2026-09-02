#!/usr/bin/env python3
"""Reconcile punctuation-equivalent transcripts across reviewed filename lineages."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator

try:
    from tools.transcript_schema import (
        SOURCE_PRIORITY,
        revision_hashes,
        transcript_match_key,
    )
except ModuleNotFoundError:
    from transcript_schema import SOURCE_PRIORITY, revision_hashes, transcript_match_key

try:
    from tools.voiceline_history import build_filename_lineages, normalize_filename
except ModuleNotFoundError:
    from voiceline_history import build_filename_lineages, normalize_filename


AUDIO_KEY_RE = re.compile(
    r"(?:^|/)sha256/[0-9a-f]{2}/(?P<sha>[0-9a-f]{64})\.mp3$", re.IGNORECASE
)


class ReconciliationError(ValueError):
    """Raised when a punctuation reconciliation cannot be applied safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _walk_audio_records(value: Any) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        filename = value.get("filename")
        audio_key = value.get("audioKey")
        if isinstance(filename, str) and isinstance(audio_key, str):
            match = AUDIO_KEY_RE.search(audio_key)
            if match:
                yield normalize_filename(filename), match.group("sha").lower()
        for child in value.values():
            yield from _walk_audio_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_audio_records(child)


def load_official_catalog(
    repo: Path, catalog_root: Path, game: str
) -> tuple[set[str], dict[str, set[str]]]:
    history_path = repo / "config" / game / "voice-line-history.json"
    history = json.loads(history_path.read_text(encoding="utf-8"))
    result: set[str] = set()
    filenames_by_sha: dict[str, set[str]] = defaultdict(set)
    missing: list[str] = []
    for version in history["officialVersions"]:
        for name in ("voicelines.json", "conversations.json"):
            path = catalog_root / version / name
            if not path.is_file():
                missing.append(path.as_posix())
                continue
            for filename, digest in _walk_audio_records(
                json.loads(path.read_text(encoding="utf-8"))
            ):
                result.add(digest)
                filenames_by_sha[digest].add(filename)
    if missing:
        raise ReconciliationError(
            "Missing official history catalogs:\n" + "\n".join(f"- {path}" for path in missing)
        )
    return result, filenames_by_sha


def build_review_lineages(
    filenames_by_sha: dict[str, set[str]], manual_correlations: list[list[str]]
) -> list[list[str]]:
    """Return complete automatic+manual lineages touched by manual correlations."""
    lineage_by_filename = build_filename_lineages(filenames_by_sha, manual_correlations)
    selected_lineages = {
        lineage_by_filename[normalize_filename(filename)]
        for group in manual_correlations
        for filename in group
    }
    grouped: dict[str, list[str]] = defaultdict(list)
    for filename, lineage in lineage_by_filename.items():
        if lineage in selected_lineages:
            grouped[lineage].append(filename)
    return [sorted(grouped[lineage]) for lineage in sorted(grouped)]


def _candidate_id(filenames: Iterable[str], match_key: str) -> str:
    identity = json.dumps(
        [sorted(filenames), match_key], ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def _hazards(texts: set[str]) -> list[str]:
    hazards: list[str] = []
    if any(re.search(r"\d[.,]\d", text) for text in texts):
        hazards.append("numeric-punctuation")
    apostrophes = {bool(re.search(r"['’]", text)) for text in texts}
    if len(apostrophes) > 1:
        hazards.append("apostrophe-variation")
    hyphens = {bool(re.search(r"[-‐‑‒–—]", text)) for text in texts}
    if len(hyphens) > 1:
        hazards.append("hyphen-variation")
    if len({text.casefold() for text in texts}) != len(texts):
        hazards.append("case-or-punctuation-only")
    if len({re.sub(r"[.!?…]+$", "", text.rstrip()) for text in texts}) == 1:
        hazards.append("terminal-punctuation-only")
    return hazards


def load_documents(
    repo: Path, correlations: list[list[str]]
) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for filename in sorted({filename for group in correlations for filename in group}):
        path = repo / "transcripts" / f"{filename}.json"
        if not path.is_file():
            raise ReconciliationError(f"Missing correlated transcript document: {path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("filename") != filename:
            raise ReconciliationError(
                f"Transcript filename mismatch in {path}: {document.get('filename')!r}"
            )
        documents[filename] = document
    return documents


def find_candidates(
    correlations: list[list[str]],
    documents: dict[str, dict[str, Any]],
    official_hashes: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for group in correlations:
        by_match_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for filename in group:
            for revision_index, revision in enumerate(documents[filename]["revisions"]):
                active_hashes = sorted(set(revision_hashes(revision)) & official_hashes)
                text = str(revision.get("text") or "")
                if not active_hashes or not text.strip():
                    continue
                by_match_key[transcript_match_key(text)].append(
                    {
                        "filename": filename,
                        "revisionIndex": revision_index,
                        "sha256": active_hashes,
                        "text": text,
                        "source": str(revision.get("source") or ""),
                    }
                )
        for match_key, occurrences in sorted(by_match_key.items()):
            filenames = sorted({item["filename"] for item in occurrences})
            texts = {item["text"] for item in occurrences}
            if len(filenames) < 2 or len(texts) < 2:
                continue
            highest_rank = max(
                SOURCE_PRIORITY.get(item["source"], -1) for item in occurrences
            )
            highest = [
                item
                for item in occurrences
                if SOURCE_PRIORITY.get(item["source"], -1) == highest_rank
            ]
            highest_texts = Counter(item["text"] for item in highest)
            highest_sources = sorted({item["source"] for item in highest})
            automatic = highest_rank >= SOURCE_PRIORITY["manual"] and len(highest_texts) == 1
            candidate = {
                "id": _candidate_id(filenames, match_key),
                "filenames": filenames,
                "matchKey": match_key,
                "highestAuthority": highest_sources[0],
                "resolution": "automatic" if automatic else "review",
                "hazards": _hazards(texts),
                "variants": [
                    {
                        "text": text,
                        "sources": dict(
                            sorted(
                                Counter(
                                    item["source"]
                                    for item in occurrences
                                    if item["text"] == text
                                ).items()
                            )
                        ),
                        "filenames": sorted(
                            {
                                item["filename"]
                                for item in occurrences
                                if item["text"] == text
                            }
                        ),
                        "recordingHashes": sum(
                            len(item["sha256"])
                            for item in occurrences
                            if item["text"] == text
                        ),
                    }
                    for text in sorted(texts)
                ],
                "occurrences": occurrences,
            }
            if automatic:
                candidate["selectedText"] = next(iter(highest_texts))
                candidate["selectedSource"] = highest_sources[0]
            candidates.append(candidate)
    ids = [candidate["id"] for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ReconciliationError("Punctuation candidate IDs are not unique")
    return candidates


def load_decisions(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != 1 or not isinstance(value.get("decisions"), dict):
        raise ReconciliationError("Decision file must contain schemaVersion 1 and decisions")
    if any(not isinstance(key, str) or not isinstance(text, str) for key, text in value["decisions"].items()):
        raise ReconciliationError("Every punctuation decision must map an ID to text")
    return value["decisions"]


def resolve_candidates(
    candidates: list[dict[str, Any]], decisions: dict[str, str]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    known_ids = {candidate["id"] for candidate in candidates}
    unknown = sorted(set(decisions) - known_ids)
    if unknown and candidates:
        raise ReconciliationError(f"Decision file contains {len(unknown)} unknown candidate IDs")
    targets: dict[str, dict[str, Any]] = {}
    unresolved: list[str] = []
    for candidate in candidates:
        if candidate["resolution"] == "automatic":
            selected_text = candidate["selectedText"]
            selected_source = candidate["selectedSource"]
        elif candidate["id"] in decisions:
            selected_text = decisions[candidate["id"]]
            selected_source = "manual"
            if transcript_match_key(selected_text) != candidate["matchKey"]:
                raise ReconciliationError(
                    f"Decision {candidate['id']} changes wording instead of punctuation/casing"
                )
            candidate["selectedText"] = selected_text
            candidate["selectedSource"] = selected_source
            candidate["resolution"] = "reviewed"
        else:
            unresolved.append(candidate["id"])
            continue
        state = {"text": selected_text, "source": selected_source}
        for occurrence in candidate["occurrences"]:
            for digest in occurrence["sha256"]:
                previous = targets.setdefault(digest, state)
                if previous != state:
                    raise ReconciliationError(f"Recording hash {digest} has conflicting targets")
    return targets, unresolved


def rewrite_documents(
    documents: dict[str, dict[str, Any]], targets: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    changed: dict[str, dict[str, Any]] = {}
    for filename, original in documents.items():
        before_hashes = Counter(
            digest
            for revision in original["revisions"]
            for digest in revision_hashes(revision)
        )
        expanded: list[dict[str, Any]] = []
        for revision in original["revisions"]:
            groups: dict[str, tuple[dict[str, Any], list[str]]] = {}
            original_state = {key: copy.deepcopy(value) for key, value in revision.items() if key != "sha256"}
            for digest in revision_hashes(revision):
                state = copy.deepcopy(targets.get(digest, original_state))
                key = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if key not in groups:
                    groups[key] = (state, [])
                groups[key][1].append(digest)
            for key in sorted(groups):
                state, hashes = groups[key]
                expanded.append({"sha256": sorted(hashes), **state})
        coalesced: list[dict[str, Any]] = []
        by_state: dict[str, dict[str, Any]] = {}
        for revision in expanded:
            state = {key: value for key, value in revision.items() if key != "sha256"}
            key = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if key not in by_state:
                item = {"sha256": [], **state}
                by_state[key] = item
                coalesced.append(item)
            by_state[key]["sha256"].extend(revision_hashes(revision))
        for revision in coalesced:
            revision["sha256"] = sorted(set(revision["sha256"]))
        updated = copy.deepcopy(original)
        updated["revisions"] = coalesced
        after_hashes = Counter(
            digest
            for revision in updated["revisions"]
            for digest in revision_hashes(revision)
        )
        if after_hashes != before_hashes or any(count != 1 for count in after_hashes.values()):
            raise ReconciliationError(f"Reconciliation changed represented hashes in {filename}")
        if updated != original:
            changed[filename] = updated
    return changed


def build_report(
    candidates: list[dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    unresolved: list[str],
    changed: dict[str, dict[str, Any]],
    official_hashes: set[str],
    applied: bool,
) -> dict[str, Any]:
    public_candidates = []
    for candidate in candidates:
        public_candidates.append(
            {key: value for key, value in candidate.items() if key != "occurrences"}
        )
    resolutions = Counter(candidate["resolution"] for candidate in candidates)
    return {
        "schemaVersion": 1,
        "applied": applied,
        "policy": {
            "equivalence": "casefolded text without Unicode punctuation or whitespace",
            "sourcePriority": ["official", "manual", "generated"],
            "generatedOnlyResolution": "reviewed decision promoted to manual",
            "scope": "recording SHA-256 values present in official history catalogs",
        },
        "statistics": {
            "officialRecordingHashes": len(official_hashes),
            "candidateClusters": len(candidates),
            "automaticClusters": resolutions["automatic"],
            "reviewedClusters": resolutions["reviewed"],
            "unresolvedClusters": len(unresolved),
            "targetRecordingHashes": len(targets),
            "changedFiles": len(changed),
        },
        "unresolved": unresolved,
        "candidates": public_candidates,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--game", default="deadlock")
    parser.add_argument("--catalog-root", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-reconciliation", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.approve_reconciliation:
        parser.error("--apply requires --approve-reconciliation")

    repo = args.repo.resolve()
    catalog_root = (args.catalog_root or repo / ".cache" / "search-index" / "versions").resolve()
    correlation_path = repo / "config" / args.game / "voice-line-history-correlations.json"
    correlation_value = json.loads(correlation_path.read_text(encoding="utf-8"))
    correlations = correlation_value["correlations"]
    official_hashes, filenames_by_sha = load_official_catalog(repo, catalog_root, args.game)
    review_lineages = build_review_lineages(filenames_by_sha, correlations)
    documents = load_documents(repo, review_lineages)
    candidates = find_candidates(review_lineages, documents, official_hashes)
    targets, unresolved = resolve_candidates(candidates, load_decisions(args.decisions))
    changed = rewrite_documents(documents, targets)
    if args.apply and unresolved:
        raise ReconciliationError(
            f"Refusing to apply with {len(unresolved)} unresolved punctuation decisions"
        )
    if args.apply:
        for filename, document in changed.items():
            path = repo / "transcripts" / f"{filename}.json"
            path.write_text(canonical_json(document), encoding="utf-8")
    report = build_report(candidates, targets, unresolved, changed, official_hashes, args.apply)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(canonical_json(report), encoding="utf-8")
    print(canonical_json(report["statistics"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
