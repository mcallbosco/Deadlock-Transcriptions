#!/usr/bin/env python3
"""Find cross-file transcript merge candidates inside voice-line lineages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.transcript_schema import SOURCE_PRIORITY, revision_hashes, transcript_match_key
    from tools.voiceline_history import normalize_filename
except ModuleNotFoundError:
    from transcript_schema import SOURCE_PRIORITY, revision_hashes, transcript_match_key
    from voiceline_history import normalize_filename


WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
COLLOQUIAL = {
    "em": ("them",),
    "ya": ("you",),
    "gonna": ("going", "to"),
    "wanna": ("want", "to"),
    "gotta": ("got", "to"),
    "kinda": ("kind", "of"),
    "outta": ("out", "of"),
    "lemme": ("let", "me"),
}
CONTRACTIONS = {
    "i'm": ("i", "am"),
    "i'll": ("i", "will"),
    "i've": ("i", "have"),
    "i'd": ("i", "would"),
    "you're": ("you", "are"),
    "you'll": ("you", "will"),
    "you've": ("you", "have"),
    "we're": ("we", "are"),
    "we'll": ("we", "will"),
    "we've": ("we", "have"),
    "they're": ("they", "are"),
    "they'll": ("they", "will"),
    "they've": ("they", "have"),
    "he's": ("he", "is"),
    "she's": ("she", "is"),
    "it's": ("it", "is"),
    "that's": ("that", "is"),
    "there's": ("there", "is"),
    "what's": ("what", "is"),
    "can't": ("can", "not"),
    "won't": ("will", "not"),
    "don't": ("do", "not"),
    "doesn't": ("does", "not"),
    "didn't": ("did", "not"),
    "isn't": ("is", "not"),
    "aren't": ("are", "not"),
    "wasn't": ("was", "not"),
    "weren't": ("were", "not"),
    "couldn't": ("could", "not"),
    "wouldn't": ("would", "not"),
    "shouldn't": ("should", "not"),
}


class AuditError(ValueError):
    """Raised when the transcript lineage inputs are malformed."""


class Components:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, value: str) -> None:
        self.parent.setdefault(value, value)

    def find(self, value: str) -> str:
        self.add(value)
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        self.parent[second] = first


@dataclass(frozen=True)
class Occurrence:
    filename: str
    revision_index: int
    text: str
    source: str
    hashes: tuple[str, ...]
    model: str | None = None


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def phrase_tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    tokens: list[str] = []
    for token in WORD_RE.findall(normalized):
        expanded = CONTRACTIONS.get(token)
        if expanded is None:
            expanded = COLLOQUIAL.get(token.lstrip("'"), (token.lstrip("'"),))
        tokens.extend(expanded)
    return tuple(tokens)


def soundex(token: str) -> str:
    """Return a compact English-oriented phonetic key for candidate discovery."""
    if not token:
        return ""
    replacements = str.maketrans(
        {
            "b": "1", "f": "1", "p": "1", "v": "1",
            "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2",
            "d": "3", "t": "3", "l": "4", "m": "5", "n": "5", "r": "6",
        }
    )
    first = token[0]
    encoded = token[1:].translate(replacements)
    encoded = re.sub(r"[^1-6]", "0", encoded)
    encoded = re.sub(r"(.)\1+", r"\1", encoded).replace("0", "")
    return (first + encoded + "000")[:4]


def similarity(left: str, right: str) -> dict[str, Any]:
    left_tokens = phrase_tokens(left)
    right_tokens = phrase_tokens(right)
    left_phrase = " ".join(left_tokens)
    right_phrase = " ".join(right_tokens)
    character = SequenceMatcher(None, left_phrase, right_phrase).ratio()
    phonetic_left = " ".join(soundex(token) for token in left_tokens)
    phonetic_right = " ".join(soundex(token) for token in right_tokens)
    phonetic = SequenceMatcher(None, phonetic_left, phonetic_right).ratio()
    token = SequenceMatcher(None, left_tokens, right_tokens).ratio()
    length_ratio = min(len(left_phrase), len(right_phrase)) / max(len(left_phrase), len(right_phrase), 1)
    return {
        "character": character,
        "token": token,
        "phonetic": phonetic,
        "lengthRatio": length_ratio,
        "leftNormalized": left_phrase,
        "rightNormalized": right_phrase,
        "leftPhonetic": phonetic_left,
        "rightPhonetic": phonetic_right,
    }


def candidate_tier(scores: dict[str, Any]) -> tuple[str | None, str | None]:
    character = scores["character"]
    length_ratio = scores["lengthRatio"]
    if scores["leftNormalized"] == scores["rightNormalized"]:
        return "strong", "same normalized spoken phrase"
    if character >= 0.98 and length_ratio >= 0.90:
        return "strong", "near-identical normalized wording"
    if character >= 0.85 and length_ratio >= 0.70:
        return "lower-confidence", "recognizable speech-to-text near-match"
    if character >= 0.70 and length_ratio >= 0.60:
        return "lower-confidence", "possible phonetic or wording match requires review"
    return None, None


def load_inputs(repo: Path, game: str) -> tuple[dict[str, dict[str, Any]], list[list[str]]]:
    documents: dict[str, dict[str, Any]] = {}
    for path in sorted((repo / "transcripts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        filename = document.get("filename")
        if not isinstance(filename, str) or not filename:
            raise AuditError(f"{path}: missing filename")
        documents[normalize_filename(filename)] = document
    correlation_path = repo / "config" / game / "voice-line-history-correlations.json"
    value = json.loads(correlation_path.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != 1 or not isinstance(value.get("correlations"), list):
        raise AuditError(f"{correlation_path}: invalid correlation document")
    correlations = [list(group) for group in value["correlations"]]
    return documents, correlations


def build_lineages(
    documents: dict[str, dict[str, Any]], correlations: list[list[str]]
) -> dict[str, list[str]]:
    components = Components()
    filenames_by_hash: dict[str, list[str]] = defaultdict(list)
    for filename, document in documents.items():
        components.add(filename)
        for revision in document.get("revisions", []):
            for digest in revision_hashes(revision):
                filenames_by_hash[digest].append(filename)
    for filenames in filenames_by_hash.values():
        ordered = sorted(set(filenames))
        for filename in ordered[1:]:
            components.union(ordered[0], filename)
    for index, group in enumerate(correlations):
        ordered = sorted({normalize_filename(value) for value in group})
        if len(ordered) < 2:
            raise AuditError(f"manual correlation {index} has fewer than two filenames")
        missing = sorted(set(ordered) - set(documents))
        if missing:
            raise AuditError(f"manual correlation {index} has missing transcripts: {missing}")
        for filename in ordered[1:]:
            components.union(ordered[0], filename)
    grouped: dict[str, list[str]] = defaultdict(list)
    for filename in documents:
        grouped[components.find(filename)].append(filename)
    return {lineage: sorted(filenames) for lineage, filenames in grouped.items()}


def select_survivor(left: Occurrence, right: Occurrence) -> Occurrence:
    left_rank = SOURCE_PRIORITY.get(left.source, -1)
    right_rank = SOURCE_PRIORITY.get(right.source, -1)
    if left_rank != right_rank:
        return left if left_rank > right_rank else right
    left_votes = (len(left.hashes), len(left.text), left.text.casefold())
    right_votes = (len(right.hashes), len(right.text), right.text.casefold())
    return left if left_votes >= right_votes else right


def _candidate_id(lineage: str, left: Occurrence, right: Occurrence) -> str:
    identity = [
        lineage,
        left.filename,
        left.revision_index,
        right.filename,
        right.revision_index,
    ]
    return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()[:20]


def find_candidates(
    documents: dict[str, dict[str, Any]], lineages: dict[str, list[str]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for lineage, filenames in sorted(lineages.items()):
        if len(filenames) < 2:
            continue
        occurrences: list[Occurrence] = []
        for filename in filenames:
            for revision_index, revision in enumerate(documents[filename].get("revisions", [])):
                text = str(revision.get("text") or "")
                source = str(revision.get("source") or "")
                hashes = tuple(sorted(revision_hashes(revision)))
                if text.strip() and source in SOURCE_PRIORITY and hashes:
                    model = revision.get("model")
                    occurrences.append(
                        Occurrence(
                            filename,
                            revision_index,
                            text,
                            source,
                            hashes,
                            model if isinstance(model, str) else None,
                        )
                    )
        for left_index, left in enumerate(occurrences):
            for right in occurrences[left_index + 1 :]:
                if left.filename == right.filename:
                    continue
                if transcript_match_key(left.text) == transcript_match_key(right.text):
                    continue
                scores = similarity(left.text, right.text)
                tier, rationale = candidate_tier(scores)
                if tier is None:
                    continue
                survivor = select_survivor(left, right)
                same_authority = left.source == right.source
                candidates.append(
                    {
                        "id": _candidate_id(lineage, left, right),
                        "tier": tier,
                        "rationale": rationale,
                        "lineage": lineage,
                        "aliases": filenames,
                        "left": {
                            "filename": left.filename,
                            "revisionIndex": left.revision_index,
                            "text": left.text,
                            "source": left.source,
                            "sha256": list(left.hashes),
                            **({"model": left.model} if left.model is not None else {}),
                        },
                        "right": {
                            "filename": right.filename,
                            "revisionIndex": right.revision_index,
                            "text": right.text,
                            "source": right.source,
                            "sha256": list(right.hashes),
                            **({"model": right.model} if right.model is not None else {}),
                        },
                        "proposed": {
                            "text": survivor.text,
                            "source": survivor.source,
                            "selectedFrom": survivor.filename,
                            "resolution": (
                                "review-required" if same_authority else "source-authority"
                            ),
                        },
                        "scores": {
                            key: round(value, 4) if isinstance(value, float) else value
                            for key, value in scores.items()
                        },
                    }
                )
    return candidates


def markdown_report(candidates: list[dict[str, Any]], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"Candidates: **{len(candidates):,}**",
        "",
        "| ID | Left | Right | Proposed survivor | Text similarity | Phonetic similarity |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for item in candidates:
        left = item["left"]
        right = item["right"]
        proposed = item["proposed"]
        text_score = item["scores"]["character"]
        phonetic_score = item["scores"]["phonetic"]
        cell = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        lines.append(
            "| `{id}` | `{left_file}` — {left_text} ({left_source}) | "
            "`{right_file}` — {right_text} ({right_source}) | {proposed_text} ({proposed_source}; {resolution}) | {text_score:.1%} | {phonetic_score:.1%} |".format(
                id=item["id"],
                left_file=cell(left["filename"]),
                left_text=cell(left["text"]),
                left_source=left["source"],
                right_file=cell(right["filename"]),
                right_text=cell(right["text"]),
                right_source=right["source"],
                proposed_text=cell(proposed["text"]),
                proposed_source=proposed["source"],
                resolution=proposed["resolution"],
                text_score=text_score,
                phonetic_score=phonetic_score,
            )
        )
    return "\n".join(lines) + "\n"


def write_report(root: Path, candidates: list[dict[str, Any]], title: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    value = {"schemaVersion": 1, "candidateCount": len(candidates), "candidates": candidates}
    (root / "candidates.json").write_text(canonical_json(value), encoding="utf-8")
    (root / "candidates.md").write_text(markdown_report(candidates, title), encoding="utf-8")


def build_report(repo: Path, game: str = "deadlock") -> dict[str, Any]:
    documents, correlations = load_inputs(repo, game)
    lineages = build_lineages(documents, correlations)
    candidates = find_candidates(documents, lineages)
    by_tier = {
        tier: [item for item in candidates if item["tier"] == tier]
        for tier in ("strong", "lower-confidence")
    }
    return {
        "statistics": {
            "transcriptFiles": len(documents),
            "manualCorrelationGroups": len(correlations),
            "multiFileLineages": sum(len(value) > 1 for value in lineages.values()),
            "strongCandidates": len(by_tier["strong"]),
            "lowerConfidenceCandidates": len(by_tier["lower-confidence"]),
        },
        **by_tier,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--game", default="deadlock")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("migration-reports/phonetic-lineage-merges"),
    )
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    report = build_report(repo, args.game)
    output_root = args.output_root if args.output_root.is_absolute() else repo / args.output_root
    write_report(output_root / "strong", report["strong"], "Strong phonetic lineage merge candidates")
    write_report(
        output_root / "lower-confidence",
        report["lower-confidence"],
        "Lower-confidence phonetic lineage merge candidates",
    )
    (output_root / "summary.json").write_text(
        canonical_json({"schemaVersion": 1, **report["statistics"]}), encoding="utf-8"
    )
    print(canonical_json(report["statistics"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
