#!/usr/bin/env python3
"""Apply an exported phonetic review queue as transitive transcript groups."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.audit_phonetic_lineage_merges import canonical_json, load_inputs
    from tools.reconcile_correlated_punctuation import rewrite_documents
    from tools.transcript_schema import revision_hashes
except ModuleNotFoundError:
    from audit_phonetic_lineage_merges import canonical_json, load_inputs
    from reconcile_correlated_punctuation import rewrite_documents
    from transcript_schema import revision_hashes


class ReviewApplyError(ValueError):
    """Raised when a review export is stale or internally inconsistent."""


class DisjointSet:
    def __init__(self) -> None:
        self.parents: dict[str, str] = {}

    def find(self, value: str) -> str:
        parent = self.parents.setdefault(value, value)
        if parent != value:
            self.parents[value] = self.find(parent)
        return self.parents[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parents[right_root] = left_root


def state_for_side(side: dict[str, Any]) -> dict[str, str]:
    return {
        key: side[key]
        for key in ("text", "source", "model")
        if isinstance(side.get(key), str)
    }


def state_key(state: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(state.items()))


def current_states(
    documents: dict[str, dict[str, Any]],
) -> dict[str, dict[tuple[tuple[str, str], ...], dict[str, str]]]:
    result: dict[str, dict[tuple[tuple[str, str], ...], dict[str, str]]] = defaultdict(dict)
    for document in documents.values():
        for revision in document.get("revisions", []):
            state = state_for_side(revision)
            for digest in revision_hashes(revision):
                result[digest][state_key(state)] = state
    return result


def load_candidates(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        rows = value.get("candidates")
        if value.get("schemaVersion") != 1 or not isinstance(rows, list):
            raise ReviewApplyError(f"invalid candidate report: {path}")
        for candidate in rows:
            candidate_id = candidate.get("id")
            if not isinstance(candidate_id, str) or candidate_id in by_id:
                raise ReviewApplyError(f"duplicate or invalid candidate ID: {candidate_id!r}")
            candidates.append(candidate)
            by_id[candidate_id] = candidate
    return candidates, by_id


def plan(
    documents: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    review: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    judgments = review.get("judgments")
    if review.get("schemaVersion") not in (1, 2) or not isinstance(judgments, dict):
        raise ReviewApplyError("review export must contain schemaVersion 1 or 2 and judgments")
    unknown = sorted(set(judgments) - set(by_id))
    if unknown:
        raise ReviewApplyError(f"review contains unknown candidate IDs: {', '.join(unknown)}")
    corrections = review.get("corrections", {})
    if not isinstance(corrections, dict) or any(
        not isinstance(candidate_id, str) or not isinstance(text, str)
        for candidate_id, text in corrections.items()
    ):
        raise ReviewApplyError("review corrections must map candidate IDs to exact text")
    invalid_corrections = sorted(set(corrections) - set(judgments))
    if invalid_corrections:
        raise ReviewApplyError(
            "corrections reference unreviewed candidates: " + ", ".join(invalid_corrections)
        )

    dsu = DisjointSet()
    approved: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    separate: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate_id, judgment in judgments.items():
        candidate = by_id[candidate_id]
        decision = judgment.get("decision")
        if decision == "separate":
            separate.append((candidate, judgment))
            continue
        if decision == "unsure":
            continue
        if decision not in ("left", "right"):
            raise ReviewApplyError(f"candidate {candidate_id} has invalid decision {decision!r}")
        side = candidate[decision]
        if judgment.get("selectedText") != side["text"]:
            raise ReviewApplyError(f"candidate {candidate_id} has stale selected text")
        hashes = list(dict.fromkeys((*candidate["left"]["sha256"], *candidate["right"]["sha256"])))
        for digest in hashes[1:]:
            dsu.union(hashes[0], digest)
        selected_state = {**side}
        if candidate_id in corrections:
            selected_state["text"] = corrections[candidate_id]
        approved.append((candidate, judgment, selected_state))

    component_hashes: dict[str, set[str]] = defaultdict(set)
    for digest in dsu.parents:
        component_hashes[dsu.find(digest)].add(digest)
    component_choices: dict[str, list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for item in approved:
        component_choices[dsu.find(item[0]["left"]["sha256"][0])].append(item)

    targets: dict[str, dict[str, str]] = {}
    operations: list[dict[str, Any]] = []
    for root, hashes in component_hashes.items():
        choices = component_choices[root]
        latest = max(choices, key=lambda item: str(item[1].get("updatedAt", "")))
        target = state_for_side(latest[2])
        for digest in hashes:
            targets[digest] = target
        operations.append(
            {
                "candidateIds": sorted(item[0]["id"] for item in choices),
                "target": target,
                "selectedByLatestCandidate": latest[0]["id"],
                "reviewedAt": latest[1].get("updatedAt"),
                "recordingHashes": len(hashes),
            }
        )

    current = current_states(documents)
    restored: list[str] = []
    separate_conflicts: list[str] = []
    for candidate, _judgment in separate:
        left_hashes = candidate["left"]["sha256"]
        right_hashes = candidate["right"]["sha256"]
        left_roots = {dsu.find(digest) for digest in left_hashes if digest in dsu.parents}
        right_roots = {dsu.find(digest) for digest in right_hashes if digest in dsu.parents}
        if left_roots & right_roots:
            separate_conflicts.append(candidate["id"])
            continue
        if any(digest in targets for digest in (*left_hashes, *right_hashes)):
            continue
        observed = [
            next(iter(current.get(digest, {}).values()))
            if len(current.get(digest, {})) == 1
            else None
            for digest in (*left_hashes, *right_hashes)
        ]
        original_left = state_for_side(candidate["left"])
        original_right = state_for_side(candidate["right"])
        if (
            original_left != original_right
            and observed
            and all(value == observed[0] for value in observed)
            and observed[0] in (original_left, original_right)
        ):
            for digest in left_hashes:
                targets[digest] = original_left
            for digest in right_hashes:
                targets[digest] = original_right
            restored.append(candidate["id"])

    if separate_conflicts:
        raise ReviewApplyError(
            "keep-separate judgments overlap approved merge groups: "
            + ", ".join(sorted(separate_conflicts))
        )

    audit_dsu = DisjointSet()
    for candidate in candidates:
        hashes = list(dict.fromkeys((*candidate["left"]["sha256"], *candidate["right"]["sha256"])))
        for digest in hashes[1:]:
            audit_dsu.union(hashes[0], digest)
    audit_states: dict[str, set[tuple[tuple[str, str], ...]]] = defaultdict(set)
    audit_hashes: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        for side_name in ("left", "right"):
            side = candidate[side_name]
            key = state_key(state_for_side(side))
            for digest in side["sha256"]:
                root = audit_dsu.find(digest)
                audit_states[root].add(key)
                audit_hashes[root].add(digest)
    allowed: dict[str, set[tuple[tuple[str, str], ...]]] = defaultdict(set)
    for root, hashes in audit_hashes.items():
        for digest in hashes:
            allowed[digest].update(audit_states[root])
    for digest, target in targets.items():
        allowed[digest].add(state_key(target))
    stale = sorted(
        digest
        for digest in targets
        if digest not in current or not set(current[digest]).issubset(allowed[digest])
    )
    if stale:
        raise ReviewApplyError(
            "review would overwrite recording hashes changed after the audit: "
            + ", ".join(stale[:10])
        )

    changed = rewrite_documents(documents, targets)
    statistics = {
        "reviewedCandidates": len(judgments),
        "approvedCandidates": len(approved),
        "separateCandidates": len(separate),
        "unsureCandidates": sum(
            judgment.get("decision") == "unsure" for judgment in judgments.values()
        ),
        "mergedComponents": len(component_hashes),
        "restoredSeparateCandidates": len(restored),
        "targetRecordingHashes": len(targets),
        "changedFiles": len(changed),
        "targetsBySource": dict(sorted(Counter(value["source"] for value in targets.values()).items())),
    }
    return changed, {
        "statistics": statistics,
        "operations": sorted(operations, key=lambda item: item["candidateIds"]),
        "restoredSeparateCandidateIds": sorted(restored),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--game", default="deadlock")
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-reviewed-phonetic-merges", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.approve_reviewed_phonetic_merges:
        parser.error("--apply requires --approve-reviewed-phonetic-merges")
    repo = args.repo.resolve()
    resolve = lambda path: path if path.is_absolute() else repo / path
    candidate_paths = [
        repo / "migration-reports/phonetic-lineage-merges/strong/candidates.json",
        repo / "migration-reports/phonetic-lineage-merges/lower-confidence/candidates.json",
    ]
    candidates, by_id = load_candidates(candidate_paths)
    review = json.loads(resolve(args.review).read_text(encoding="utf-8"))
    documents, _ = load_inputs(repo, args.game)
    changed, result = plan(documents, candidates, by_id, review)
    result = {"schemaVersion": 1, "applied": args.apply, **result}
    if args.apply:
        for filename, document in changed.items():
            (repo / "transcripts" / f"{filename}.json").write_text(
                canonical_json(document), encoding="utf-8"
            )
    if args.output_json:
        output = resolve(args.output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(canonical_json(result), encoding="utf-8")
    print(canonical_json(result["statistics"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
