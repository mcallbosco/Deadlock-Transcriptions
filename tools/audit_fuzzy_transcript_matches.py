#!/usr/bin/env python3
"""Report near-matching transcript groups without modifying transcript data."""

from __future__ import annotations

import argparse
import difflib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

try:
    from transcript_schema import TRANSCRIPT_SCHEMA_VERSION, transcript_match_key
except ModuleNotFoundError:  # Imported as tools.audit_fuzzy_transcript_matches.
    from tools.transcript_schema import TRANSCRIPT_SCHEMA_VERSION, transcript_match_key


CONFIDENCE_THRESHOLDS = {"high": 0.95, "medium": 0.90, "low": 0.80}
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def fuzzy_similarity(left: str, right: str) -> float:
    """Compare text after applying the schema-v3 exact-match normalization."""
    left_key = transcript_match_key(left)
    right_key = transcript_match_key(right)
    if not left_key or not right_key:
        return 0.0
    return difflib.SequenceMatcher(None, left_key, right_key, autojunk=False).ratio()


def confidence_for_similarity(similarity: float) -> str | None:
    for confidence in ("high", "medium", "low"):
        if similarity >= CONFIDENCE_THRESHOLDS[confidence]:
            return confidence
    return None


def _revision_summary(revision: dict[str, Any], index: int) -> dict[str, Any]:
    result = {
        "revisionIndex": index,
        "sha256": revision.get("sha256", []),
        "text": str(revision.get("text") or ""),
        "source": str(revision.get("source") or ""),
    }
    if revision.get("model"):
        result["model"] = revision["model"]
    return result


def candidates_for_document(
    document: dict[str, Any], relative_path: str
) -> tuple[list[dict[str, Any]], Counter[str]]:
    revisions = document.get("revisions")
    if document.get("schemaVersion") != TRANSCRIPT_SCHEMA_VERSION or not isinstance(
        revisions, list
    ):
        raise ValueError(f"{relative_path}: expected a schema-v3 transcript document")

    candidates: list[dict[str, Any]] = []
    statistics: Counter[str] = Counter()
    for (left_index, left), (right_index, right) in combinations(enumerate(revisions), 2):
        statistics["withinFilePairs"] += 1
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise ValueError(f"{relative_path}: revision must be an object")
        left_text = str(left.get("text") or "")
        right_text = str(right.get("text") or "")
        left_key = transcript_match_key(left_text)
        right_key = transcript_match_key(right_text)
        if not left_key or not right_key:
            statistics["blankPairsSkipped"] += 1
            continue
        if left_key == right_key:
            statistics["exactNormalizedPairsSkipped"] += 1
            continue
        statistics["fuzzyPairsCompared"] += 1
        similarity = fuzzy_similarity(left_text, right_text)
        confidence = confidence_for_similarity(similarity)
        if confidence is None:
            continue
        source_pair = sorted(
            (str(left.get("source") or ""), str(right.get("source") or ""))
        )
        candidates.append(
            {
                "path": relative_path,
                "filename": str(document.get("filename") or ""),
                "confidence": confidence,
                "similarity": round(similarity, 6),
                "normalizedLengths": [len(left_key), len(right_key)],
                "sourcePair": source_pair,
                "left": _revision_summary(left, left_index),
                "right": _revision_summary(right, right_index),
            }
        )
        statistics[f"{confidence}ConfidenceCandidates"] += 1
    return candidates, statistics


def build_report(repo: Path) -> dict[str, Any]:
    transcript_root = repo / "transcripts"
    if not transcript_root.is_dir():
        raise ValueError(f"Transcript directory does not exist: {transcript_root}")

    candidates: list[dict[str, Any]] = []
    statistics: Counter[str] = Counter()
    source_pairs: Counter[str] = Counter()
    confidence_source_pairs: dict[str, Counter[str]] = {
        confidence: Counter() for confidence in ("high", "medium", "low")
    }
    for path in sorted(transcript_root.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        relative_path = path.relative_to(repo).as_posix()
        revisions = document.get("revisions")
        statistics["files"] += 1
        if isinstance(revisions, list):
            statistics["revisionGroups"] += len(revisions)
        document_candidates, document_statistics = candidates_for_document(
            document, relative_path
        )
        candidates.extend(document_candidates)
        statistics.update(document_statistics)
        for candidate in document_candidates:
            source_pair = " + ".join(candidate["sourcePair"])
            source_pairs[source_pair] += 1
            confidence_source_pairs[candidate["confidence"]][source_pair] += 1

    candidates.sort(
        key=lambda candidate: (
            CONFIDENCE_ORDER[candidate["confidence"]],
            -candidate["similarity"],
            candidate["path"],
            candidate["left"]["revisionIndex"],
            candidate["right"]["revisionIndex"],
        )
    )
    statistics["candidates"] = len(candidates)
    for key in (
        "withinFilePairs",
        "blankPairsSkipped",
        "exactNormalizedPairsSkipped",
        "fuzzyPairsCompared",
        "highConfidenceCandidates",
        "mediumConfidenceCandidates",
        "lowConfidenceCandidates",
    ):
        statistics.setdefault(key, 0)
    return {
        "schemaVersion": 1,
        "transcriptSchemaVersion": TRANSCRIPT_SCHEMA_VERSION,
        "scope": "revision groups within the same transcript file",
        "advisoryOnly": True,
        "normalization": {
            "caseInsensitive": True,
            "ignoreUnicodePunctuation": True,
            "ignoreWhitespace": True,
        },
        "similarity": {
            "algorithm": "difflib.SequenceMatcher ratio over normalized text",
            "exactNormalizedMatchesExcluded": True,
            "thresholds": CONFIDENCE_THRESHOLDS,
        },
        "statistics": dict(statistics),
        "candidatesBySourcePair": dict(sorted(source_pairs.items())),
        "candidatesByConfidenceAndSourcePair": {
            confidence: dict(sorted(counts.items()))
            for confidence, counts in confidence_source_pairs.items()
        },
        "candidates": candidates,
    }


def _markdown_text(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def markdown_report(report: dict[str, Any], *, limit_per_level: int = 100) -> str:
    statistics = report["statistics"]
    lines = [
        "# Fuzzy transcript candidate audit",
        "",
        "This report is advisory only. Candidates are possible equivalents, not approved merges.",
        "Comparison is limited to revision groups in the same transcript file. Exact schema-v3",
        "matches are excluded because they are already grouped.",
        "",
        "## Confidence bands",
        "",
        "| Confidence | Similarity | Candidates |",
        "| --- | ---: | ---: |",
    ]
    for confidence in ("high", "medium", "low"):
        threshold = report["similarity"]["thresholds"][confidence]
        count = statistics.get(f"{confidence}ConfidenceCandidates", 0)
        lines.append(f"| {confidence.title()} | ≥ {threshold:.0%} | {count:,} |")
    lines.extend(
        [
            "",
            "Similarity is the `difflib.SequenceMatcher` ratio after ignoring case, Unicode",
            "punctuation, and whitespace. Even high-confidence pairs require human review because",
            "small changes can alter names, subjects, negation, or gameplay meaning.",
            "",
            "## Coverage",
            "",
            f"- Transcript files: {statistics.get('files', 0):,}",
            f"- Revision groups: {statistics.get('revisionGroups', 0):,}",
            f"- Within-file pairs: {statistics.get('withinFilePairs', 0):,}",
            f"- Nonblank, non-exact pairs compared: {statistics.get('fuzzyPairsCompared', 0):,}",
            f"- Candidates: {statistics.get('candidates', 0):,}",
            "",
            "The complete candidate set, including hashes and normalized lengths, is in",
            "`fuzzy-transcript-candidates.json`.",
            "",
            "## Source combinations",
            "",
            "| Sources | High | Medium | Low | Total |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    source_pairs = report["candidatesBySourcePair"]
    by_confidence = report["candidatesByConfidenceAndSourcePair"]
    for source_pair, total in source_pairs.items():
        lines.append(
            "| {source_pair} | {high:,} | {medium:,} | {low:,} | {total:,} |".format(
                source_pair=_markdown_text(source_pair),
                high=by_confidence["high"].get(source_pair, 0),
                medium=by_confidence["medium"].get(source_pair, 0),
                low=by_confidence["low"].get(source_pair, 0),
                total=total,
            )
        )

    candidates = report["candidates"]
    for confidence in ("high", "medium", "low"):
        matching = [c for c in candidates if c["confidence"] == confidence]
        lines.extend(
            [
                "",
                f"## {confidence.title()} confidence",
                "",
                f"Showing {min(len(matching), limit_per_level):,} of {len(matching):,} candidates.",
                "",
                "| Similarity | Path | Sources | Left text | Right text |",
                "| ---: | --- | --- | --- | --- |",
            ]
        )
        for candidate in matching[:limit_per_level]:
            lines.append(
                "| {similarity:.2%} | `{path}` | {sources} | {left} | {right} |".format(
                    similarity=candidate["similarity"],
                    path=_markdown_text(candidate["path"]),
                    sources=_markdown_text(" / ".join(candidate["sourcePair"])),
                    left=_markdown_text(candidate["left"]["text"]),
                    right=_markdown_text(candidate["right"]["text"]),
                )
            )
    return "\n".join(lines) + "\n"


def write_report(
    report: dict[str, Any], json_path: Path, markdown_path: Path, *, limit_per_level: int
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(canonical_json(report), encoding="utf-8")
    markdown_path.write_text(
        markdown_report(report, limit_per_level=limit_per_level), encoding="utf-8"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("migration-reports/fuzzy-transcript-candidates.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("migration-reports/fuzzy-transcript-candidates.md"),
    )
    parser.add_argument("--markdown-limit", type=int, default=100)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    json_path = args.json_output if args.json_output.is_absolute() else repo / args.json_output
    markdown_path = (
        args.markdown_output
        if args.markdown_output.is_absolute()
        else repo / args.markdown_output
    )
    report = build_report(repo)
    write_report(
        report,
        json_path,
        markdown_path,
        limit_per_level=max(0, args.markdown_limit),
    )
    print(canonical_json({"statistics": report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
