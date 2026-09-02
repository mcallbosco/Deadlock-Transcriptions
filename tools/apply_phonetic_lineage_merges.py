#!/usr/bin/env python3
"""Apply a reviewed strong phonetic-lineage merge report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.audit_phonetic_lineage_merges import canonical_json, load_inputs
    from tools.reconcile_correlated_punctuation import rewrite_documents
    from tools.transcript_schema import SOURCE_PRIORITY, revision_hashes
except ModuleNotFoundError:
    from audit_phonetic_lineage_merges import canonical_json, load_inputs
    from reconcile_correlated_punctuation import rewrite_documents
    from transcript_schema import SOURCE_PRIORITY, revision_hashes


class ApplyError(ValueError):
    """Raised when reviewed candidates no longer match the transcript tree."""


def load_review(path: Path) -> tuple[dict[str, str], set[str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != 1:
        raise ApplyError("review decisions must use schemaVersion 1")
    decisions = value.get("decisions")
    skipped = value.get("skipped", [])
    if not isinstance(decisions, dict) or not isinstance(skipped, list):
        raise ApplyError("review decisions must contain decisions and skipped")
    if any(not isinstance(key, str) or not isinstance(text, str) for key, text in decisions.items()):
        raise ApplyError("every review decision must map a candidate ID to exact text")
    if any(not isinstance(value, str) for value in skipped):
        raise ApplyError("every skipped candidate ID must be a string")
    return decisions, set(skipped)


def validate_occurrence(
    documents: dict[str, dict[str, Any]],
    value: dict[str, Any],
    target: dict[str, str],
) -> None:
    filename = value["filename"]
    document = documents.get(filename)
    if document is None:
        raise ApplyError(f"candidate transcript no longer exists: {filename}")
    allowed = {
        (value["text"], value["source"]),
        (target["text"], target["source"]),
    }
    for digest in value["sha256"]:
        matches = [
            revision
            for revision in document.get("revisions", [])
            if digest in revision_hashes(revision)
        ]
        if len(matches) != 1:
            raise ApplyError(f"candidate hash {digest} is not unique in {filename}")
        current = (matches[0].get("text"), matches[0].get("source"))
        if current not in allowed:
            raise ApplyError(f"candidate state changed for hash {digest} in {filename}")


def selected_state(
    candidate: dict[str, Any], decisions: dict[str, str]
) -> dict[str, str]:
    left = candidate["left"]
    right = candidate["right"]
    left_rank = SOURCE_PRIORITY.get(left["source"], -1)
    right_rank = SOURCE_PRIORITY.get(right["source"], -1)
    if left_rank != right_rank:
        winner = left if left_rank > right_rank else right
        return {"text": winner["text"], "source": winner["source"]}
    decision = decisions.get(candidate["id"])
    if decision is None:
        raise ApplyError(f"same-authority candidate {candidate['id']} requires review")
    available = {left["text"], right["text"]}
    if decision not in available:
        raise ApplyError(f"decision {candidate['id']} must select one audited transcript")
    return {
        "text": decision,
        "source": "manual" if left["source"] == "generated" else left["source"],
    }


def plan(
    documents: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    decisions: dict[str, str],
    skipped: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    known = {candidate["id"] for candidate in candidates}
    unknown = sorted((set(decisions) | skipped) - known)
    if unknown:
        raise ApplyError(f"review contains unknown candidate IDs: {', '.join(unknown)}")
    targets: dict[str, dict[str, str]] = {}
    applied: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate["id"] in skipped:
            continue
        state = selected_state(candidate, decisions)
        validate_occurrence(documents, candidate["left"], state)
        validate_occurrence(documents, candidate["right"], state)
        for side in ("left", "right"):
            for digest in candidate[side]["sha256"]:
                previous = targets.setdefault(digest, state)
                if previous != state:
                    raise ApplyError(
                        f"recording hash {digest} has conflicting targets: {previous} vs {state}"
                    )
        applied.append({"id": candidate["id"], "target": state})
    changed = rewrite_documents(documents, targets)
    statistics = {
        "candidatePairs": len(candidates),
        "appliedPairs": len(applied),
        "skippedPairs": len(skipped),
        "targetRecordingHashes": len(targets),
        "changedFiles": len(changed),
        "targetsBySource": dict(sorted(Counter(value["source"] for value in targets.values()).items())),
    }
    return changed, {"statistics": statistics, "operations": applied}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--game", default="deadlock")
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("migration-reports/phonetic-lineage-merges/strong/candidates.json"),
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path("migration-reports/phonetic-lineage-merges/strong/decisions.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-reviewed-phonetic-merges", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.approve_reviewed_phonetic_merges:
        parser.error("--apply requires --approve-reviewed-phonetic-merges")
    repo = args.repo.resolve()
    resolve = lambda path: path if path.is_absolute() else repo / path
    report = json.loads(resolve(args.candidates).read_text(encoding="utf-8"))
    candidates = report.get("candidates")
    if report.get("schemaVersion") != 1 or not isinstance(candidates, list):
        raise ApplyError("candidate report must contain schemaVersion 1 and candidates")
    decisions, skipped = load_review(resolve(args.decisions))
    documents, _ = load_inputs(repo, args.game)
    changed, result = plan(documents, candidates, decisions, skipped)
    result = {"schemaVersion": 1, "applied": args.apply, **result}
    if args.apply:
        for filename, document in changed.items():
            (repo / "transcripts" / f"{filename}.json").write_text(
                canonical_json(document), encoding="utf-8"
            )
    output_path = args.output_json
    if output_path is None and args.apply:
        output_path = Path("migration-reports/phonetic-lineage-merges/strong/apply-result.json")
    if output_path is not None:
        output = resolve(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(canonical_json(result), encoding="utf-8")
    print(canonical_json(result["statistics"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
