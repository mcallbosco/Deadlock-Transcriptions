#!/usr/bin/env python3
"""Resolve source authority and reconcile aliases for reviewed fuzzy targets."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import revision_hashes
except ModuleNotFoundError:
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import revision_hashes


SOURCE_RANK = {"generated": 1, "manual": 2, "official": 3}


def _state(revision: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in revision.items() if key != "sha256"}


def _state_key(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hashes(document: dict[str, Any]) -> Counter[str]:
    return Counter(
        digest
        for revision in document["revisions"]
        for digest in revision_hashes(revision)
    )


def occurrence_index(repo: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted((repo / "transcripts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        relative_path = path.relative_to(repo).as_posix()
        for index, revision in enumerate(document["revisions"]):
            for digest in revision_hashes(revision):
                result[digest].append(
                    {"path": relative_path, "revisionIndex": index, "revision": revision}
                )
    return result


def resolve_authority(repo: Path, manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = copy.deepcopy(manifest)
    occurrences = occurrence_index(repo)
    promotions: list[dict[str, Any]] = []
    targets_by_hash: dict[str, set[str]] = defaultdict(set)
    for operation in resolved["operations"]:
        authoritative: list[dict[str, Any]] = []
        for digest in revision_hashes(operation["result"]):
            authoritative.extend(
                occurrence
                for occurrence in occurrences[digest]
                if occurrence["revision"].get("source") in {"manual", "official"}
            )
        if authoritative:
            highest_rank = max(SOURCE_RANK[item["revision"]["source"]] for item in authoritative)
            highest = [
                item
                for item in authoritative
                if SOURCE_RANK[item["revision"]["source"]] == highest_rank
            ]
            states = {_state_key(_state(item["revision"])): _state(item["revision"]) for item in highest}
            if len(states) != 1:
                raise ValueError(
                    f"Component {operation['componentId']} has conflicting authoritative alias states"
                )
            authoritative_state = next(iter(states.values()))
            previous = _state(operation["result"])
            operation["result"] = {
                "sha256": revision_hashes(operation["result"]),
                **authoritative_state,
            }
            promotions.append(
                {
                    "componentId": operation["componentId"],
                    "path": operation["path"],
                    "previous": previous,
                    "authoritative": authoritative_state,
                    "evidence": [
                        {"path": item["path"], "revisionIndex": item["revisionIndex"]}
                        for item in highest
                    ],
                }
            )
        target_key = _state_key(_state(operation["result"]))
        for digest in revision_hashes(operation["result"]):
            targets_by_hash[digest].add(target_key)
    conflicts = [digest for digest, targets in targets_by_hash.items() if len(targets) > 1]
    if conflicts:
        raise ValueError(f"Reviewed manifest has conflicting targets for {len(conflicts)} hashes")
    report = {
        "schemaVersion": 1,
        "sourcePriority": ["official", "manual", "generated"],
        "statistics": {"operations": len(resolved["operations"]), "promotions": len(promotions)},
        "promotions": promotions,
    }
    return resolved, report


def reconcile_document(
    document: dict[str, Any], targets: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], int]:
    before = _hashes(document)
    if not any(digest in targets for revision in document["revisions"] for digest in revision_hashes(revision)):
        return copy.deepcopy(document), 0
    updated = copy.deepcopy(document)
    rewritten = 0
    expanded: list[dict[str, Any]] = []
    target_state_keys: set[str] = set()
    for revision in updated["revisions"]:
        groups: dict[str, tuple[dict[str, Any], list[str]]] = {}
        original_state = _state(revision)
        for digest in revision_hashes(revision):
            target = targets.get(digest, original_state)
            key = _state_key(target)
            if digest in targets:
                target_state_keys.add(key)
            if key not in groups:
                groups[key] = (copy.deepcopy(target), [])
            groups[key][1].append(digest)
            if target != original_state:
                rewritten += 1
        for key in sorted(groups):
            state, hashes = groups[key]
            expanded.append({"sha256": sorted(hashes), **state})
    coalesced: list[dict[str, Any]] = []
    by_state: dict[str, dict[str, Any]] = {}
    for revision in expanded:
        state = _state(revision)
        key = _state_key(state)
        if key not in target_state_keys:
            coalesced.append(revision)
            continue
        if key not in by_state:
            item = {"sha256": [], **state}
            by_state[key] = item
            coalesced.append(item)
        by_state[key]["sha256"].extend(revision_hashes(revision))
    for revision in coalesced:
        revision["sha256"] = sorted(set(revision["sha256"]))
    updated["revisions"] = coalesced
    if _hashes(updated) != before:
        raise ValueError("Alias reconciliation changed represented hashes")
    return updated, rewritten


def reconcile_repo(repo: Path, manifest: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    targets: dict[str, dict[str, Any]] = {}
    for operation in manifest["operations"]:
        state = _state(operation["result"])
        for digest in revision_hashes(operation["result"]):
            previous = targets.setdefault(digest, state)
            if previous != state:
                raise ValueError(f"Conflicting reviewed target for {digest}")
    changed_files = 0
    rewritten_hash_occurrences = 0
    for path in sorted((repo / "transcripts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        updated, rewritten = reconcile_document(document, targets)
        if updated != document:
            changed_files += 1
            rewritten_hash_occurrences += rewritten
            if apply:
                path.write_text(canonical_json(updated), encoding="utf-8")
    return {
        "schemaVersion": 1,
        "applied": apply,
        "statistics": {
            "targetHashes": len(targets),
            "changedFiles": changed_files,
            "rewrittenHashOccurrences": rewritten_hash_occurrences,
        },
    }


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--repo", type=Path, default=Path.cwd())
    resolve.add_argument("--manifest", type=Path, required=True)
    resolve.add_argument("--output", type=Path, required=True)
    resolve.add_argument("--report", type=Path, required=True)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--repo", type=Path, default=Path.cwd())
    reconcile.add_argument("--manifest", type=Path, required=True)
    reconcile.add_argument("--result", type=Path, required=True)
    reconcile.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.command == "resolve":
        resolved, report = resolve_authority(repo, manifest)
        _write(args.output, resolved)
        _write(args.report, report)
        print(canonical_json(report["statistics"]), end="")
        return 0
    result = reconcile_repo(repo, manifest, apply=args.apply)
    _write(args.result, result)
    print(canonical_json(result["statistics"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
