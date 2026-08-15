#!/usr/bin/env python3
"""Converge duplicate recording hashes using source authority and Git recency."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.transcript_schema import SOURCE_PRIORITY


class ReconciliationError(ValueError):
    """Raised when duplicate recording states cannot be reconciled safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def published_state(revision: dict[str, Any]) -> tuple[str, bool]:
    return (
        str(revision.get("text") or ""),
        revision.get("source") == "official",
    )


def git_recency(
    history_repo: Path, ref: str, relative_paths: set[str]
) -> dict[str, int]:
    if not relative_paths:
        return {}
    process = subprocess.Popen(
        [
            "git",
            "-C",
            str(history_repo),
            "log",
            ref,
            "--format=__COMMIT__%ct",
            "--name-only",
            "--",
            "transcripts",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    timestamp = 0
    result: dict[str, int] = {}
    for raw_line in process.stdout:
        line = raw_line.rstrip("\r\n")
        if line.startswith("__COMMIT__"):
            timestamp = int(line.removeprefix("__COMMIT__"))
        elif line in relative_paths and line not in result:
            result[line] = timestamp
            if len(result) == len(relative_paths):
                process.terminate()
                break
    process.wait()
    assert process.stderr is not None
    stderr = process.stderr.read()
    if process.returncode not in {0, -15, 1}:
        raise ReconciliationError(f"Could not inspect Git recency: {stderr.strip()}")
    missing = relative_paths - set(result)
    if missing:
        raise ReconciliationError(
            f"Git history has no edit timestamp for: {sorted(missing)[:5]}"
        )
    return result


def load_documents(transcripts: Path) -> dict[Path, dict[str, Any]]:
    return {
        path: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(transcripts.rglob("*.json"))
    }


def plan_reconciliation(
    transcripts: Path,
    recency: dict[str, int],
) -> tuple[dict[Path, dict[str, Any]], dict[str, Any]]:
    documents = load_documents(transcripts)
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path, document in documents.items():
        relative = path.relative_to(transcripts.parent).as_posix()
        for index, revision in enumerate(document.get("revisions", [])):
            for digest in revision.get("sha256", []):
                occurrences[digest].append(
                    {
                        "path": relative,
                        "index": index,
                        "revision": revision,
                        "recency": recency.get(relative, 0),
                    }
                )

    winners: dict[str, dict[str, Any]] = {}
    decisions: list[dict[str, Any]] = []
    for digest, candidates in sorted(occurrences.items()):
        if len({published_state(item["revision"]) for item in candidates}) <= 1:
            continue
        winner = max(
            candidates,
            key=lambda item: (
                SOURCE_PRIORITY.get(str(item["revision"].get("source") or ""), -1),
                item["recency"],
                item["path"],
                -item["index"],
            ),
        )
        if SOURCE_PRIORITY.get(str(winner["revision"].get("source") or ""), -1) < 0:
            raise ReconciliationError(f"{digest} has no recognized source authority")
        winners[digest] = winner
        decisions.append(
            {
                "sha256": digest,
                "winner": {
                    "path": winner["path"],
                    "revisionIndex": winner["index"],
                    "source": winner["revision"].get("source"),
                    "text": winner["revision"].get("text"),
                    "lastFileEditUnix": winner["recency"],
                },
                "candidates": [
                    {
                        "path": item["path"],
                        "revisionIndex": item["index"],
                        "source": item["revision"].get("source"),
                        "text": item["revision"].get("text"),
                        "lastFileEditUnix": item["recency"],
                    }
                    for item in candidates
                ],
            }
        )

    changes: dict[Path, dict[str, Any]] = {}
    split_revisions = 0
    for path, original in documents.items():
        updated = copy.deepcopy(original)
        replacements: list[dict[str, Any]] = []
        for revision in updated.get("revisions", []):
            grouped: dict[tuple[str, str, str | None], list[str]] = defaultdict(list)
            for digest in revision.get("sha256", []):
                winner = winners.get(digest)
                desired = winner["revision"] if winner is not None else revision
                state = (
                    str(desired.get("text") or ""),
                    str(desired.get("source") or ""),
                    desired.get("model"),
                )
                grouped[state].append(digest)
            if len(grouped) > 1:
                split_revisions += 1
            for (text, source, model), hashes in grouped.items():
                replacement = copy.deepcopy(revision)
                replacement["sha256"] = hashes
                replacement["text"] = text
                replacement["source"] = source
                if model is not None:
                    replacement["model"] = model
                else:
                    replacement.pop("model", None)
                replacements.append(replacement)
        updated["revisions"] = replacements
        if updated != original:
            changes[path] = updated

    winner_sources = Counter(
        str(item["winner"]["source"]) for item in decisions
    )
    report = {
        "schemaVersion": 1,
        "policy": {
            "sourcePriority": ["official", "manual", "generated"],
            "tieBreaker": "most_recent_file_edit_then_path",
            "winnerProvenanceAppliedToEveryDuplicateHashOccurrence": True,
        },
        "statistics": {
            "reconciledHashes": len(winners),
            "changedFiles": len(changes),
            "splitRevisionGroups": split_revisions,
            "winnerSources": dict(sorted(winner_sources.items())),
        },
        "decisions": decisions,
    }
    return changes, report


def apply_reconciliation(
    transcripts: Path,
    recency: dict[str, int],
    *,
    apply: bool,
) -> dict[str, Any]:
    changes, report = plan_reconciliation(transcripts, recency)
    if apply:
        for path, document in changes.items():
            path.write_text(canonical_json(document), encoding="utf-8")
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--history-repo", type=Path)
    parser.add_argument("--recency-ref", default="HEAD")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-reconciliation", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.approve_reconciliation:
        parser.error("--apply requires --approve-reconciliation")
    try:
        repo = args.repo.resolve()
        transcripts = repo / "transcripts"
        documents = load_documents(transcripts)
        paths = {path.relative_to(repo).as_posix() for path in documents}
        history_repo = (args.history_repo or repo).resolve()
        recency = git_recency(history_repo, args.recency_ref, paths)
        report = apply_reconciliation(transcripts, recency, apply=args.apply)
        if args.output_json:
            output = args.output_json
            if not output.is_absolute():
                output = repo / output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(canonical_json(report), encoding="utf-8")
        print(json.dumps(report["statistics"], indent=2))
        if not args.apply:
            print("Dry run only; pass --apply --approve-reconciliation to write files.")
        return 0
    except (OSError, json.JSONDecodeError, ReconciliationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
