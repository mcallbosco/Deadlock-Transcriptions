#!/usr/bin/env python3
"""Build and apply exact reviewed generated/generated fuzzy-match batches."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import revision_hashes
except ModuleNotFoundError:  # Imported as tools.review_generated_fuzzy_batch.
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import revision_hashes


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hashes(document: dict[str, Any]) -> Counter[str]:
    return Counter(
        digest
        for revision in document["revisions"]
        for digest in revision_hashes(revision)
    )


def _component_nodes(
    rows: list[dict[str, Any]], candidate: dict[str, Any]
) -> set[int]:
    adjacency: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        if row["path"] != candidate["path"]:
            continue
        left = row["left"]["revisionIndex"]
        right = row["right"]["revisionIndex"]
        adjacency[left].add(right)
        adjacency[right].add(left)
    nodes: set[int] = set()
    pending = [candidate["left"]["revisionIndex"]]
    while pending:
        index = pending.pop()
        if index in nodes:
            continue
        nodes.add(index)
        pending.extend(adjacency[index])
    return nodes


def _review_entry(
    repo: Path,
    all_rows: list[dict[str, Any]],
    high_rows: list[dict[str, Any]],
    decision: dict[str, Any],
    side_field: str,
) -> dict[str, Any]:
    candidate_index = decision["candidateIndex"]
    if not isinstance(candidate_index, int) or not 0 <= candidate_index < len(high_rows):
        raise ValueError(f"Invalid high-confidence candidate index: {candidate_index}")
    candidate = high_rows[candidate_index]
    if candidate["path"] != decision["path"]:
        raise ValueError(
            f"Candidate {candidate_index} path changed: {candidate['path']} != {decision['path']}"
        )
    side = decision[side_field]
    if side not in {"left", "right"}:
        raise ValueError(f"Candidate {candidate_index} has invalid side: {side}")
    document = json.loads((repo / candidate["path"]).read_text(encoding="utf-8"))
    nodes = _component_nodes(all_rows, candidate)
    members = [
        {"revisionIndex": index, "revision": copy.deepcopy(document["revisions"][index])}
        for index in sorted(nodes)
    ]
    if any(item["revision"].get("source") != "generated" for item in members):
        raise ValueError(f"{candidate['path']}: reviewed component is not all generated")
    selected_index = candidate[side]["revisionIndex"]
    selected = copy.deepcopy(document["revisions"][selected_index])
    merged_hashes = sorted(
        {
            digest
            for item in members
            for digest in revision_hashes(item["revision"])
        }
    )
    result = copy.deepcopy(selected)
    result["sha256"] = merged_hashes
    return {
        "candidateIndex": candidate_index,
        "path": candidate["path"],
        "filename": candidate["filename"],
        "candidateConfidence": candidate["confidence"],
        "similarity": candidate["similarity"],
        "recommendation": side,
        "evidence": decision["evidence"],
        "members": members,
        "selectedRevisionIndex": selected_index,
        "result": result,
    }


def build_batch(
    repo: Path,
    candidate_report_path: Path,
    decisions_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = json.loads(candidate_report_path.read_text(encoding="utf-8"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    all_rows = [
        row
        for row in report["candidates"]
        if row["sourcePair"] == ["generated", "generated"]
        and row["confidence"] in {"high", "medium"}
    ]
    high_rows = [row for row in all_rows if row["confidence"] == "high"]
    high = [
        _review_entry(repo, all_rows, high_rows, decision, "selectedSide")
        for decision in decisions["highDecisions"]
    ]
    medium = [
        _review_entry(repo, all_rows, high_rows, decision, "recommendedSide")
        for decision in decisions["mediumDecisions"]
    ]
    metadata = {
        "schemaVersion": 1,
        "batch": decisions["batch"],
        "sourceCandidateReport": candidate_report_path.relative_to(repo).as_posix(),
        "sourceCandidateReportSha256": _file_sha256(candidate_report_path),
        "reviewDecisions": decisions_path.relative_to(repo).as_posix(),
        "reviewDecisionsSha256": _file_sha256(decisions_path),
        "selection": decisions["selection"],
    }
    return (
        {**metadata, "decision": "apply", "statistics": {"components": len(high)}, "operations": high},
        {**metadata, "decision": "needs user review", "statistics": {"components": len(medium)}, "candidates": medium},
    )


def medium_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Generated/generated medium review — batch 1",
        "",
        "These recommendations were deliberately not applied. Each has plausible competing",
        "readings and requires user review. Prototype/final character names and older",
        "Amber Hand/Sapphire Flame patron dialogue remain distinct from later",
        "Archmother/Hidden King transcripts.",
        "",
        "| # | Path | Similarity | Recommendation | Left/component texts | Evidence |",
        "| ---: | --- | ---: | --- | --- | --- |",
    ]
    for number, item in enumerate(report["candidates"], 1):
        texts = "<br>".join(
            f"r{member['revisionIndex']}: {member['revision']['text']} "
            f"(`{', '.join(d[:12] for d in revision_hashes(member['revision']))}`)"
            for member in item["members"]
        )
        cell = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {number} | `{cell(item['path'])}` | {item['similarity']:.2%} | "
            f"{item['recommendation'].upper()} | {cell(texts)} | {cell(item['evidence'])} |"
        )
    return "\n".join(lines) + "\n"


def apply_operation(
    document: dict[str, Any], operation: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    updated = copy.deepcopy(document)
    revisions = updated["revisions"]
    result = operation["result"]
    member_hashes = sorted(
        {
            digest
            for member in operation["members"]
            for digest in revision_hashes(member["revision"])
        }
    )
    if revision_hashes(result) != member_hashes:
        raise ValueError(f"{operation['path']}: result hashes do not match reviewed members")
    if result.get("source") != "generated" or any(
        member["revision"].get("source") != "generated"
        for member in operation["members"]
    ):
        raise ValueError(f"{operation['path']}: reviewed merge must remain generated")
    if result in revisions:
        if any(member["revision"] in revisions for member in operation["members"]):
            raise ValueError(f"{operation['path']}: partial reviewed merge state")
        return updated, "noop"
    located: list[int] = []
    for member in operation["members"]:
        matches = [
            index for index, revision in enumerate(revisions) if revision == member["revision"]
        ]
        if len(matches) != 1:
            raise ValueError(
                f"{operation['path']}: expected reviewed revision state was not found exactly once"
            )
        located.append(matches[0])
    if len(set(located)) != len(located):
        raise ValueError(f"{operation['path']}: reviewed members overlap")
    before_hashes = _hashes(updated)
    insert_at = min(located)
    member_indices = set(located)
    remaining = [
        revision for index, revision in enumerate(revisions) if index not in member_indices
    ]
    remaining.insert(insert_at, copy.deepcopy(result))
    updated["revisions"] = remaining
    if _hashes(updated) != before_hashes:
        raise ValueError(f"{operation['path']}: reviewed merge changed represented hashes")
    return updated, "update"


def apply_manifest(repo: Path, manifest: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    statuses: Counter[str] = Counter()
    changes: list[dict[str, Any]] = []
    operations_by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for operation in manifest["operations"]:
        operations_by_path[operation["path"]].append(operation)
    for relative_path, operations in sorted(operations_by_path.items()):
        path = repo / relative_path
        original = json.loads(path.read_text(encoding="utf-8"))
        updated = original
        for operation in operations:
            updated, status = apply_operation(updated, operation)
            statuses[status] += 1
            changes.append({"path": relative_path, "status": status, "result": operation["result"]})
        if apply and updated != original:
            path.write_text(canonical_json(updated), encoding="utf-8")
    return {
        "schemaVersion": 1,
        "batch": manifest["batch"],
        "applied": apply,
        "statistics": dict(statuses),
        "changes": changes,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--repo", type=Path, default=Path.cwd())
    build.add_argument("--candidate-report", type=Path, required=True)
    build.add_argument("--decisions", type=Path, required=True)
    build.add_argument("--high-manifest", type=Path, required=True)
    build.add_argument("--medium-json", type=Path, required=True)
    build.add_argument("--medium-markdown", type=Path, required=True)
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--repo", type=Path, default=Path.cwd())
    apply_parser.add_argument("--manifest", type=Path, required=True)
    apply_parser.add_argument("--result-json", type=Path, required=True)
    apply_parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if args.command == "build":
        high, medium = build_batch(
            repo, (repo / args.candidate_report).resolve(), (repo / args.decisions).resolve()
        )
        _write_json(repo / args.high_manifest, high)
        _write_json(repo / args.medium_json, medium)
        markdown_path = repo / args.medium_markdown
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(medium_markdown(medium), encoding="utf-8")
        print(canonical_json({"high": high["statistics"], "medium": medium["statistics"]}), end="")
        return 0
    manifest = json.loads((repo / args.manifest).read_text(encoding="utf-8"))
    result = apply_manifest(repo, manifest, apply=args.apply)
    _write_json(repo / args.result_json, result)
    print(canonical_json(result["statistics"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
