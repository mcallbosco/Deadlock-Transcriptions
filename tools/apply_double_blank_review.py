#!/usr/bin/env python3
"""Validate or apply decisions from the double-blank audio reviewer."""

from __future__ import annotations

import argparse
import copy
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_REPORT = Path("migration-reports/gpt-transcribe-double-blank-review.json")
DEFAULT_DECISIONS = Path("migration-reports/gpt-transcribe-double-blank-decisions.json")
DEFAULT_MERGE_REVIEW = Path("migration-reports/gpt-transcribe-double-blank-merge-review.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def transcript_documents(transcripts: Path) -> dict[Path, dict[str, Any]]:
    documents: dict[Path, dict[str, Any]] = {}
    for path in transcripts.rglob("*.json"):
        document = read_json(path)
        if isinstance(document, dict) and isinstance(document.get("revisions"), list):
            documents[path] = document
    return documents


def official_text_for(row: dict[str, Any], repo: Path) -> str:
    texts: set[str] = set()
    for item in row.get("items", []):
        path = repo / item["path"]
        document = read_json(path)
        texts.update(
            revision["text"]
            for revision in document.get("revisions", [])
            if revision.get("source") == "official"
            and isinstance(revision.get("text"), str)
            and revision["text"].strip()
        )
    if len(texts) != 1:
        raise ValueError(
            f'{row["recordingId"]}: official merge note requires exactly one current official text; found {sorted(texts)!r}'
        )
    return next(iter(texts))


def desired_states(
    repo: Path,
    report_path: Path,
    decisions_path: Path,
    merge_review_path: Path | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    report = read_json(report_path)
    review = read_json(decisions_path)
    rows = {row["recordingId"]: row for row in report.get("held", [])}
    decisions = review.get("decisions", [])
    if len(decisions) != len(rows):
        raise ValueError(f"Expected decisions for all {len(rows)} held recordings; found {len(decisions)}")
    by_recording: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        recording_id = decision.get("recordingId")
        if recording_id not in rows:
            raise ValueError(f"Decision references unknown recordingId {recording_id!r}")
        if recording_id in by_recording:
            raise ValueError(f"Duplicate decision for recordingId {recording_id}")
        by_recording[recording_id] = decision
    if set(by_recording) != set(rows):
        missing = sorted(set(rows) - set(by_recording))
        raise ValueError(f"Missing decisions for recordingIds: {missing[:5]!r}")

    states: dict[str, dict[str, str]] = {}
    recording_states: dict[str, dict[str, str]] = {}
    for recording_id, row in rows.items():
        decision = by_recording[recording_id]
        status = decision.get("status")
        if status == "transcript":
            text = str(decision.get("text") or "").strip()
            if not text:
                raise ValueError(f"{recording_id}: transcript decision is blank")
            desired = {"text": text, "source": "manual"}
        elif status == "nonspeech":
            desired = {"text": "", "source": "skippednonspeech"}
        elif status == "hold" and "official" in str(decision.get("notes") or "").casefold():
            desired = {"text": official_text_for(row, repo), "source": "official"}
        else:
            raise ValueError(f"{recording_id}: unresolved decision status {status!r}")
        recording_states[recording_id] = desired
        hashes = row.get("allRecordingHashes")
        if not isinstance(hashes, list) or not hashes:
            raise ValueError(f"{recording_id}: allRecordingHashes must be a nonempty array")
        for digest in hashes:
            previous = states.get(digest)
            if previous is not None and previous != desired:
                raise ValueError(f"Conflicting desired states for SHA-256 {digest}")
            states[digest] = desired

    merge_counts = {"officialMergeCandidates": 0, "reviewedMergeCandidates": 0, "mergedCandidateHashes": 0}
    if merge_review_path is not None:
        merge_review = read_json(merge_review_path)
        for candidate in merge_review.get("officialMerges", []):
            recording_id = candidate.get("recordingId")
            if recording_id not in rows:
                raise ValueError(f"Official merge references unknown recordingId {recording_id!r}")
            desired = {"text": candidate["candidateText"], "source": "official"}
            verify_merge_candidate(repo, candidate, desired, expected_source="official")
            recording_states[recording_id] = desired
            for digest in rows[recording_id]["allRecordingHashes"]:
                states[digest] = desired
            add_candidate_hashes(states, candidate, desired)
            merge_counts["officialMergeCandidates"] += 1
            merge_counts["mergedCandidateHashes"] += len(candidate["candidateHashes"])
        for candidate in merge_review.get("reviewedMerges", []):
            recording_id = candidate.get("recordingId")
            if recording_id not in rows:
                raise ValueError(f"Reviewed merge references unknown recordingId {recording_id!r}")
            desired = recording_states[recording_id]
            verify_merge_candidate(repo, candidate, desired)
            add_candidate_hashes(states, candidate, desired)
            merge_counts["reviewedMergeCandidates"] += 1
            merge_counts["mergedCandidateHashes"] += len(candidate["candidateHashes"])

    counts = {"manual": 0, "skippednonspeech": 0, "official": 0}
    for desired in recording_states.values():
        counts[desired["source"]] += 1
    counts.update(merge_counts)
    return states, counts


def verify_merge_candidate(
    repo: Path,
    candidate: dict[str, Any],
    desired: dict[str, str],
    expected_source: str | None = None,
) -> None:
    path = repo / candidate["path"]
    source = candidate.get("candidateSource")
    if expected_source is not None and source != expected_source:
        raise ValueError(f"{path}: expected a {expected_source} merge candidate, found {source!r}")
    hashes = set(candidate.get("candidateHashes") or [])
    if not hashes:
        raise ValueError(f"{path}: merge candidate has no hashes")
    document = read_json(path)
    audited = [
        revision
        for revision in document.get("revisions", [])
        if revision.get("text") == candidate.get("candidateText")
        and revision.get("source") == source
        and hashes <= set(revision.get("sha256") or [])
    ]
    applied = [
        revision
        for revision in document.get("revisions", [])
        if revision.get("text") == desired["text"]
        and revision.get("source") == desired["source"]
        and hashes <= set(revision.get("sha256") or [])
    ]
    if len(audited) != 1 and len(applied) != 1:
        raise ValueError(f"{path}: reviewed merge candidate no longer has its exact audited state")


def add_candidate_hashes(
    states: dict[str, dict[str, str]],
    candidate: dict[str, Any],
    desired: dict[str, str],
) -> None:
    for digest in candidate["candidateHashes"]:
        previous = states.get(digest)
        if previous is not None and previous != desired:
            raise ValueError(f"Conflicting reviewed merge states for SHA-256 {digest}")
        states[digest] = desired


def update_document(document: dict[str, Any], states: dict[str, dict[str, str]]) -> tuple[dict[str, Any], set[str]]:
    updated = copy.deepcopy(document)
    retained: list[dict[str, Any]] = []
    encountered: set[str] = set()
    desired_hashes: dict[tuple[str, str], list[str]] = defaultdict(list)
    for revision in document.get("revisions", []):
        hashes = revision.get("sha256")
        if not isinstance(hashes, list):
            raise ValueError("revision sha256 must be an array")
        remaining = []
        for digest in hashes:
            desired = states.get(digest)
            if desired is None:
                remaining.append(digest)
            else:
                encountered.add(digest)
                desired_hashes[(desired["text"], desired["source"])].append(digest)
        if remaining:
            kept = copy.deepcopy(revision)
            kept["sha256"] = remaining
            retained.append(kept)

    for (text, source), hashes in desired_hashes.items():
        target = next(
            (
                revision
                for revision in retained
                if revision.get("text") == text and revision.get("source") == source
            ),
            None,
        )
        if target is None:
            target = {"sha256": [], "text": text, "source": source}
            retained.append(target)
        target["sha256"] = sorted(set(target["sha256"]) | set(hashes))
        target.pop("model", None)
    updated["revisions"] = retained
    return updated, encountered


def apply_review(
    repo: Path,
    report_path: Path,
    decisions_path: Path,
    apply: bool,
    merge_review_path: Path | None = None,
) -> dict[str, int]:
    states, recording_counts = desired_states(repo, report_path, decisions_path, merge_review_path)
    documents = transcript_documents(repo / "transcripts")
    occurrences: dict[str, int] = defaultdict(int)
    changed: dict[Path, dict[str, Any]] = {}
    for path, document in documents.items():
        updated, encountered = update_document(document, states)
        for digest in encountered:
            occurrences[digest] += 1
        if updated != document:
            changed[path] = updated
    missing = sorted(set(states) - set(occurrences))
    if missing:
        raise ValueError(f"Reviewed SHA-256 values are absent from current transcripts: {missing[:5]!r}")
    if apply:
        for path, document in changed.items():
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    return {
        "recordings": (
            recording_counts["manual"]
            + recording_counts["skippednonspeech"]
            + recording_counts["official"]
        ),
        "manualRecordings": recording_counts["manual"],
        "nonspeechRecordings": recording_counts["skippednonspeech"],
        "officialMergeRecordings": recording_counts["official"],
        "officialMergeCandidates": recording_counts["officialMergeCandidates"],
        "reviewedMergeCandidates": recording_counts["reviewedMergeCandidates"],
        "mergedCandidateHashes": recording_counts["mergedCandidateHashes"],
        "recordingHashes": len(states),
        "changedFiles": len(changed),
        "hashOccurrences": sum(occurrences.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--merge-review", type=Path, default=DEFAULT_MERGE_REVIEW)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    report = args.report if args.report.is_absolute() else repo / args.report
    decisions = args.decisions if args.decisions.is_absolute() else repo / args.decisions
    merge_review = args.merge_review if args.merge_review.is_absolute() else repo / args.merge_review
    result = apply_review(repo, report, decisions, args.apply, merge_review)
    result["mode"] = "apply" if args.apply else "validate"
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
