#!/usr/bin/env python3
"""Rank active-SHA text divergences for conservative semantic-delta review.

This report is limited to Six Hero epochs that have no exact legacy state on
any published manifest SHA. It never edits transcripts. High confidence means
the corrected words are already present or the exact legacy edit span can be
transferred while every other lexical token agrees; it is not permission to
apply the result automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from apply_current_contributions import read_json
from audit_legacy_contributions import AuditError, git, normalize_text, safe_output_path
from transcript_schema import revisions_for_hash


REPORT_SCHEMA_VERSION = 1
WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def word_tokens(value: str) -> list[dict[str, Any]]:
    return [
        {"value": match.group(), "start": match.start(), "end": match.end()}
        for match in WORD.finditer(value)
    ]


def word_values(value: str, casefold: bool = False) -> list[str]:
    values = [token["value"] for token in word_tokens(value)]
    return [item.casefold() for item in values] if casefold else values


def word_similarity(left: str, right: str) -> float:
    return SequenceMatcher(
        None, word_values(left, True), word_values(right, True), autojunk=False
    ).ratio()


def corrected_equivalent(before: str, after: str, target: str) -> bool:
    before_exact = word_values(before)
    after_exact = word_values(after)
    target_exact = word_values(target)
    before_folded = word_values(before, True)
    after_folded = word_values(after, True)
    target_folded = word_values(target, True)
    return (
        target_exact == after_exact and before_exact != after_exact
    ) or (
        target_folded == after_folded and before_folded != after_folded
    )


def one_lexical_edit(before: str, after: str) -> dict[str, Any] | None:
    before_values = word_values(before)
    after_values = word_values(after)
    changes = [
        opcode
        for opcode in SequenceMatcher(
            None, before_values, after_values, autojunk=False
        ).get_opcodes()
        if opcode[0] != "equal"
    ]
    if len(changes) != 1:
        return None
    tag, before_start, before_end, after_start, after_end = changes[0]
    return {
        "kind": tag,
        "beforeStart": before_start,
        "beforeEnd": before_end,
        "afterStart": after_start,
        "afterEnd": after_end,
        "oldTokens": before_values[before_start:before_end],
        "newTokens": after_values[after_start:after_end],
    }


def occurrences(values: list[str], needle: list[str]) -> list[int]:
    if not needle:
        return []
    return [
        index
        for index in range(len(values) - len(needle) + 1)
        if values[index : index + len(needle)] == needle
    ]


def exact_delta_proposal(before: str, after: str, target: str) -> dict[str, Any] | None:
    edit = one_lexical_edit(before, after)
    if edit is None or not edit["oldTokens"] or not edit["newTokens"]:
        return None
    target_tokens = word_tokens(target)
    target_values = [token["value"] for token in target_tokens]
    matches = occurrences(target_values, edit["oldTokens"])
    if len(matches) != 1:
        return None
    target_start = matches[0]
    target_end = target_start + len(edit["oldTokens"])
    after_tokens = word_tokens(after)
    replacement = after[
        after_tokens[edit["afterStart"]]["start"] : after_tokens[edit["afterEnd"] - 1]["end"]
    ]
    raw_start = target_tokens[target_start]["start"]
    raw_end = target_tokens[target_end - 1]["end"]
    proposed = target[:raw_start] + replacement + target[raw_end:]
    before_values = word_values(before)
    outside_before = [
        value.casefold()
        for value in (
            before_values[: edit["beforeStart"]]
            + before_values[edit["beforeEnd"] :]
        )
    ]
    outside_target = [
        value.casefold()
        for value in target_values[:target_start] + target_values[target_end:]
    ]
    return {
        "proposedText": proposed,
        "oldTokens": edit["oldTokens"],
        "newTokens": edit["newTokens"],
        "targetTokenPosition": target_start,
        "outsideTokensEquivalent": outside_before == outside_target,
        "suspiciousInternalCapitalization": any(
            token[:1].islower() and any(character.isupper() for character in token[1:])
            for token in edit["newTokens"]
        ),
    }


def analyze_record(record: dict[str, Any], current_revision: dict[str, Any]) -> dict[str, Any]:
    before = record["initialText"]
    after = record["finalText"]
    target = record["selectedTarget"]["originalText"]
    result = {
        "epochId": record["epochId"],
        "legacyPath": record["legacyPath"],
        "legacyPathDeleted": record["legacyPathDeleted"],
        "events": record["events"],
        "initialText": before,
        "finalText": after,
        "selectedTarget": record["selectedTarget"],
        "metrics": {
            "initialToTargetWordSimilarity": word_similarity(before, target),
            "finalToTargetWordSimilarity": word_similarity(after, target),
            "legacyEditWordSimilarity": word_similarity(before, after),
        },
        "confidence": "low",
        "proposedAction": "review",
        "reason": "",
    }
    if current_revision.get("source") == "official":
        result.update(
            status="protected_current_official",
            reason="The selected revision is official on the current branch.",
        )
        return result
    if current_revision.get("source") == "manual":
        result.update(
            status="current_revision_already_manual",
            reason="The selected revision is already manual on the current branch.",
        )
        return result
    if current_revision.get("source") != "generated":
        result.update(
            status="review_current_non_generated_source",
            reason="The selected revision is no longer generated.",
        )
        return result
    if current_revision.get("text") != target:
        result.update(
            status="current_revision_changed",
            reason="The selected revision text changed after the source audit.",
        )
        return result

    if corrected_equivalent(before, after, target):
        result.update(
            status="candidate_corrected_equivalent",
            confidence="high",
            proposedAction="mark_manual_preserve_v2_text",
            proposedText=target,
            reason="The v3 lexical content matches the corrected legacy state, ignoring punctuation or casing that did not carry semantic identity.",
        )
        return result

    proposal = exact_delta_proposal(before, after, target)
    if proposal is not None:
        result["deltaEvidence"] = proposal
        result["proposedText"] = proposal["proposedText"]
        result["proposedAction"] = "apply_exact_delta_and_mark_manual"
        if proposal["suspiciousInternalCapitalization"]:
            result.update(
                status="review_suspicious_delta_transfer",
                confidence="medium",
                reason="The exact edit span transfers, but the corrected token contains unexpected internal capitalization and may be a mechanical false positive.",
            )
        elif proposal["outsideTokensEquivalent"]:
            result.update(
                status="candidate_exact_delta_transfer",
                confidence="high",
                reason="The exact legacy edit span occurs once in v3 and every lexical token outside that span agrees.",
            )
        else:
            result.update(
                status="review_exact_delta_partial_context",
                confidence="medium",
                reason="The exact legacy edit span occurs once, but the legacy and v3 texts also differ outside the edited span.",
            )
        return result

    if result["metrics"]["finalToTargetWordSimilarity"] >= 0.8:
        result.update(
            status="review_near_semantic_match",
            confidence="medium",
            reason="The corrected legacy and v3 texts are lexically similar, but the edit cannot be transferred by one unique exact span.",
        )
    else:
        result.update(
            status="review_low_semantic_similarity",
            reason="The corrected legacy and v3 texts differ too much for deterministic delta transfer.",
        )
    return result


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    high = [record for record in report["records"] if record["confidence"] == "high"]
    medium_delta = [
        record
        for record in report["records"]
        if record["status"]
        in {"review_exact_delta_partial_context", "review_suspicious_delta_transfer"}
    ]
    lines = [
        "# Six Hero semantic-delta contribution audit",
        "",
        "> Review only: this report did not modify transcripts or categories.",
        "",
        "## Dataset and grain",
        "",
        f"- Six Hero active-SHA divergences: **{summary['sixHeroActiveShaDivergences']:,}**",
        f"- Epochs with exact evidence on another SHA, or a protected/ambiguous resolution: **{summary['excludedByCrossVersionEvidence']:,}**",
        f"- Epochs with no exact state on any published SHA: **{summary['semanticDeltaEpochs']:,}**",
        "- Proposal grain: one historical correction epoch and one date-selected Six Hero SHA.",
        "",
        "## Checks performed",
        "",
        "- Confirmed each epoch has no exact state across all 17 published manifests.",
        "- Rechecked the selected SHA against the current branch and protected official/manual sources.",
        "- Compared lexical similarity before and after the legacy correction.",
        "- Allowed a high-confidence transfer only when corrected lexical content already matches, or one exact edit span is unique and all outside tokens agree.",
        "",
        "## Findings",
        "",
        "| Status | Epochs | Share | Confidence |",
        "| --- | ---: | ---: | --- |",
    ]
    for status, count in sorted(
        summary["recordsByStatus"].items(), key=lambda item: (-item[1], item[0])
    ):
        share = count / summary["semanticDeltaEpochs"] if summary["semanticDeltaEpochs"] else 0
        confidence = report["statusConfidence"].get(status, "review")
        lines.append(f"| `{status}` | {count:,} | {share:.1%} | {confidence} |")
    lines.extend(
        [
            "",
            "## High-confidence proposals",
            "",
            "| Legacy path | legacy before | legacy after | v3 active | Proposal | Action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in high:
        values = [
            record["legacyPath"],
            record["initialText"],
            record["finalText"],
            record["selectedTarget"]["originalText"],
            record["proposedText"],
        ]
        values = [value.replace("|", "\\|").replace("\n", " ") for value in values]
        lines.append(
            f"| `{values[0]}` | {values[1]} | {values[2]} | {values[3]} | {values[4]} | `{record['proposedAction']}` |"
        )
    if not high:
        lines.append("| _None_ |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Medium-confidence exact-span proposals",
            "",
            "These preserve v3 wording outside the exact legacy edit, but independent",
            "differences remain elsewhere in the line and require closer review.",
            "",
            "| Legacy path | legacy before | legacy after | v3 active | Proposal |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for record in medium_delta:
        values = [
            record["legacyPath"],
            record["initialText"],
            record["finalText"],
            record["selectedTarget"]["originalText"],
            record["proposedText"],
        ]
        values = [value.replace("|", "\\|").replace("\n", " ") for value in values]
        lines.append(
            f"| `{values[0]}` | {values[1]} | {values[2]} | {values[3]} | {values[4]} |"
        )
    if not medium_delta:
        lines.append("| _None_ |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Risk and recommendation",
            "",
            "High confidence is structural, not an automatic approval: the legacy format",
            "still lacks an audio hash. Review these proposals first, then preserve original",
            "authors for accepted corrections. Medium and low tiers should remain unchanged",
            "until a person confirms the semantic intent or audio provides stronger evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank Six Hero active-SHA divergences for semantic-delta review."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--six-hero-audit",
        type=Path,
        default=Path("migration-reports/six-hero-update-historical-contribution-audit.json"),
    )
    parser.add_argument(
        "--cross-version-audit",
        type=Path,
        default=Path("migration-reports/cross-version-historical-contribution-audit.json"),
    )
    parser.add_argument(
        "--output-json",
        default="migration-reports/six-hero-semantic-delta-contribution-audit.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="migration-reports/six-hero-semantic-delta-contribution-audit.md",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = Path(str(git(args.repo.resolve(), "rev-parse", "--show-toplevel")).strip())
        six_path = args.six_hero_audit if args.six_hero_audit.is_absolute() else repo / args.six_hero_audit
        cross_path = args.cross_version_audit if args.cross_version_audit.is_absolute() else repo / args.cross_version_audit
        six = read_json(six_path)
        cross = read_json(cross_path)
        if six.get("mode") != "versioned-historical-audit-only":
            raise AuditError("The Six Hero input is not a versioned historical audit.")
        if cross.get("mode") != "cross-version-historical-audit-only":
            raise AuditError("The cross-version input is not a cross-version historical audit.")
        eligible_ids = {
            record["epochId"]
            for record in cross.get("records", [])
            if record.get("status") == "no_exact_state_across_manifests"
        }
        divergent = [
            record
            for record in six.get("records", [])
            if record.get("status") == "review_version_text_diverged"
        ]
        selected = [record for record in divergent if record["epochId"] in eligible_ids]
        if len(selected) != len(eligible_ids):
            raise AuditError("The Six Hero and cross-version audit grains do not agree.")

        records: list[dict[str, Any]] = []
        for record in selected:
            target = record["selectedTarget"]
            path = repo / Path(*target["path"].split("/"))
            document = read_json(path)
            revisions = revisions_for_hash(document, target["sha256"])
            if len(revisions) != 1:
                raise AuditError(
                    f"Expected one current revision {target['path']}@{target['sha256']}; found {len(revisions)}."
                )
            records.append(analyze_record(record, revisions[0]))
        records.sort(
            key=lambda value: (
                {"high": 0, "medium": 1, "low": 2}.get(value["confidence"], 3),
                -value["metrics"]["finalToTargetWordSimilarity"],
                value["legacyPath"],
            )
        )
        statuses = Counter(record["status"] for record in records)
        confidences = Counter(record["confidence"] for record in records)
        authors = Counter(
            (event["author"]["name"], event["author"]["email"])
            for record in records
            if record["confidence"] == "high"
            for event in record["events"]
        )
        report = {
            "schemaVersion": REPORT_SCHEMA_VERSION,
            "mode": "semantic-delta-audit-only",
            "inputs": {
                "sixHeroAudit": {
                    "path": six_path.relative_to(repo).as_posix(),
                    "contentSha256": hashlib.sha256(six_path.read_bytes()).hexdigest(),
                },
                "crossVersionAudit": {
                    "path": cross_path.relative_to(repo).as_posix(),
                    "contentSha256": hashlib.sha256(cross_path.read_bytes()).hexdigest(),
                },
                "observedHeadCommit": str(git(repo, "rev-parse", "HEAD")).strip(),
            },
            "target": six["target"],
            "policy": {
                "reportOnly": True,
                "officialRevisionsMutable": False,
                "eligibleTargetSources": ["generated"],
                "noExactStateAcrossAnyManifestRequired": True,
                "dateSelectedSixHeroShaRequired": True,
                "currentHeadConflictCheckRequired": True,
                "highConfidenceOutsideTokensMustAgree": True,
                "semanticDeltaMayAutoApply": False,
                "fuzzyMatchingMayAutoApply": False,
            },
            "statusConfidence": {
                "candidate_corrected_equivalent": "high",
                "candidate_exact_delta_transfer": "high",
                "review_exact_delta_partial_context": "medium",
                "review_suspicious_delta_transfer": "medium",
                "review_near_semantic_match": "medium",
                "review_low_semantic_similarity": "low",
            },
            "summary": {
                "sixHeroActiveShaDivergences": len(divergent),
                "excludedByCrossVersionEvidence": len(divergent) - len(selected),
                "semanticDeltaEpochs": len(records),
                "highConfidenceProposals": confidences["high"],
                "mediumConfidenceReviews": confidences["medium"],
                "lowConfidenceReviews": confidences["low"],
                "recordsByStatus": dict(sorted(statuses.items())),
                "highConfidenceAuthors": [
                    {"name": name, "email": email, "actions": count}
                    for (name, email), count in sorted(
                        authors.items(), key=lambda item: (-item[1], item[0])
                    )
                ],
            },
            "records": records,
        }
        protected: Iterable[str] = (six["target"]["prefix"], "data", "config")
        json_path = safe_output_path(repo, args.output_json, protected)
        markdown_path = safe_output_path(repo, args.output_markdown, protected)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"Wrote {json_path}")
        print(f"Wrote {markdown_path}")
        print(json.dumps(report["summary"]["recordsByStatus"], indent=2))
        return 0
    except (AuditError, KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
