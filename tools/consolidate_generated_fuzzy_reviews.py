#!/usr/bin/env python3
"""Validate review shards and build exact apply/deferred manifests."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import revision_hashes
except ModuleNotFoundError:
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import revision_hashes


VERDICTS = {"apply", "medium", "unresolved", "invalid", "keep_separate"}


def load_decisions(queue_path: Path, shard_paths: list[Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    queue_sha = hashlib.sha256(queue_path.read_bytes()).hexdigest()
    by_id = {item["componentId"]: item for item in queue["components"]}
    decisions: list[dict[str, Any]] = []
    seen: set[int] = set()
    for shard_path in sorted(shard_paths):
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        if shard.get("schemaVersion") != 1 or shard.get("queueSha256") != queue_sha:
            raise ValueError(f"{shard_path}: wrong schema or queue SHA-256")
        expected_range = shard.get("range")
        if not (
            isinstance(expected_range, list)
            and len(expected_range) == 2
            and all(isinstance(item, int) for item in expected_range)
        ):
            raise ValueError(f"{shard_path}: invalid range")
        shard_decisions = shard.get("decisions")
        if not isinstance(shard_decisions, list):
            raise ValueError(f"{shard_path}: decisions must be an array")
        expected_ids = set(range(expected_range[0], expected_range[1] + 1))
        actual_ids = {item.get("componentId") for item in shard_decisions if isinstance(item, dict)}
        if actual_ids != expected_ids or len(shard_decisions) != len(expected_ids):
            raise ValueError(f"{shard_path}: decisions do not exactly cover its range")
        for decision in shard_decisions:
            component_id = decision["componentId"]
            if component_id in seen or component_id not in by_id:
                raise ValueError(f"{shard_path}: duplicate or unknown component {component_id}")
            seen.add(component_id)
            verdict = decision.get("verdict")
            confidence = decision.get("judgmentConfidence")
            selected = decision.get("selectedRevisionIndex")
            evidence = decision.get("evidence")
            if verdict not in VERDICTS or confidence not in {"high", "medium", "low"}:
                raise ValueError(f"{shard_path}: invalid verdict/confidence for {component_id}")
            if not isinstance(evidence, str) or not evidence.strip():
                raise ValueError(f"{shard_path}: missing evidence for {component_id}")
            if verdict == "apply" and confidence != "high":
                raise ValueError(f"{shard_path}: apply {component_id} is not high confidence")
            if verdict in {"apply", "medium"}:
                if selected not in by_id[component_id]["componentRevisionIndices"]:
                    raise ValueError(f"{shard_path}: invalid selected revision for {component_id}")
            elif selected is not None:
                raise ValueError(f"{shard_path}: non-selection {component_id} has selected revision")
            decisions.append(copy.deepcopy(decision))
    decisions.sort(key=lambda item: item["componentId"])
    return queue, decisions


def operation(component: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    revisions = {item["revisionIndex"]: item["revision"] for item in component["allRevisions"]}
    members = [
        {"revisionIndex": index, "revision": copy.deepcopy(revisions[index])}
        for index in component["componentRevisionIndices"]
    ]
    if any(member["revision"].get("source") != "generated" for member in members):
        raise ValueError(f"Component {component['componentId']} is not all generated")
    selected = copy.deepcopy(revisions[decision["selectedRevisionIndex"]])
    selected["sha256"] = sorted(
        {
            digest
            for member in members
            for digest in revision_hashes(member["revision"])
        }
    )
    return {
        "componentId": component["componentId"],
        "path": component["path"],
        "filename": component["filename"],
        "candidateConfidence": "high",
        "similarity": component["maxSimilarity"],
        "recommendation": "selectedRevisionIndex",
        "selectedRevisionIndex": decision["selectedRevisionIndex"],
        "judgmentConfidence": decision["judgmentConfidence"],
        "evidence": decision["evidence"],
        "members": members,
        "result": selected,
    }


def build_reports(queue: dict[str, Any], decisions: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    components = {item["componentId"]: item for item in queue["components"]}
    counts = Counter(item["verdict"] for item in decisions)
    reviewed: list[dict[str, Any]] = []
    apply_operations: list[dict[str, Any]] = []
    for decision in decisions:
        component = components[decision["componentId"]]
        item = {
            "componentId": decision["componentId"],
            "path": component["path"],
            "filename": component["filename"],
            "similarity": component["maxSimilarity"],
            **decision,
            "componentRevisionIndices": component["componentRevisionIndices"],
            "revisions": [
                value
                for value in component["allRevisions"]
                if value["revisionIndex"] in component["componentRevisionIndices"]
            ],
        }
        reviewed.append(item)
        if decision["verdict"] == "apply":
            apply_operations.append(operation(component, decision))
    summary = {
        "schemaVersion": 1,
        "queueComponents": queue["statistics"]["components"],
        "reviewedComponents": len(decisions),
        "statistics": dict(sorted(counts.items())),
        "decisions": reviewed,
    }
    manifest = {
        "schemaVersion": 1,
        "batch": "complete-remaining-high-pass",
        "decision": "apply",
        "statistics": {"components": len(apply_operations)},
        "operations": apply_operations,
    }
    return summary, manifest


def markdown_report(report: dict[str, Any]) -> str:
    stats = report["statistics"]
    lines = [
        "# Generated/generated complete high-confidence review",
        "",
        f"Reviewed **{report['reviewedComponents']:,}** of **{report['queueComponents']:,}** queued components.",
        "",
        "| Verdict | Components |",
        "| --- | ---: |",
    ]
    for verdict in ("apply", "medium", "unresolved", "invalid", "keep_separate"):
        lines.append(f"| {verdict.replace('_', ' ').title()} | {stats.get(verdict, 0):,} |")
    lines.extend(["", "## Deferred decisions", "", "| ID | Verdict | Path | Recommendation | Evidence |", "| ---: | --- | --- | ---: | --- |"]) 
    for item in report["decisions"]:
        if item["verdict"] == "apply":
            continue
        evidence = item["evidence"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {item['componentId']} | {item['verdict']} | `{item['path']}` | "
            f"{item.get('selectedRevisionIndex')} | {evidence} |"
        )
    return "\n".join(lines) + "\n"


def medium_report(report: dict[str, Any]) -> dict[str, Any]:
    candidates = [item for item in report["decisions"] if item["verdict"] == "medium"]
    return {
        "schemaVersion": 1,
        "decision": "needs user review",
        "statistics": {"components": len(candidates)},
        "candidates": candidates,
    }


def medium_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Generated/generated medium recommendations — complete high pass",
        "",
        "These recommendations were not applied. Different hashes can be distinct recordings,",
        "and prototype/final names plus patron-era dialogue remain separate.",
        "",
        "| ID | Path | Similarity | Recommended revision | Component readings | Evidence |",
        "| ---: | --- | ---: | ---: | --- | --- |",
    ]
    for item in report["candidates"]:
        readings = "<br>".join(
            f"r{value['revisionIndex']}: {value['revision']['text']} "
            f"(`{', '.join(digest[:12] for digest in revision_hashes(value['revision']))}`)"
            for value in item["revisions"]
        )
        clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {item['componentId']} | `{clean(item['path'])}` | {item['similarity']:.2%} | "
            f"{item['selectedRevisionIndex']} | {clean(readings)} | {clean(item['evidence'])} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--shards", type=Path, nargs="+", required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-markdown", type=Path, required=True)
    parser.add_argument("--apply-manifest", type=Path, required=True)
    parser.add_argument("--medium-json", type=Path, required=True)
    parser.add_argument("--medium-markdown", type=Path, required=True)
    args = parser.parse_args()
    queue, decisions = load_decisions(args.queue, args.shards)
    report, manifest = build_reports(queue, decisions)
    args.report_json.write_text(canonical_json(report), encoding="utf-8")
    args.report_markdown.write_text(markdown_report(report), encoding="utf-8")
    args.apply_manifest.write_text(canonical_json(manifest), encoding="utf-8")
    medium = medium_report(report)
    args.medium_json.write_text(canonical_json(medium), encoding="utf-8")
    args.medium_markdown.write_text(medium_markdown(medium), encoding="utf-8")
    print(canonical_json({"reviewed": len(decisions), **report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
