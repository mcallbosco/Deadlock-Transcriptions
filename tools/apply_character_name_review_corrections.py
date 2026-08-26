#!/usr/bin/env python3
"""Apply PR-review corrections and character-name repairs to touched duration merges."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from apply_reviewed_generated_duration_merges import load_review
    from audit_fuzzy_transcript_matches import canonical_json
    from transcript_schema import compact_revisions, revision_hashes
except ModuleNotFoundError:  # Imported as tools.apply_character_name_review_corrections.
    from tools.apply_reviewed_generated_duration_merges import load_review
    from tools.audit_fuzzy_transcript_matches import canonical_json
    from tools.transcript_schema import compact_revisions, revision_hashes


# Filename token -> (preferred current name, every accepted spoken name).
CHARACTERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "atlas": ("Abrams", ("Abrams", "Atlas")),
    "airheart": ("Airheart", ("Airheart",)),
    "fencer": ("Apollo", ("Apollo", "Fencer")),
    "bebop": ("Bebop", ("Bebop",)),
    "punkgoat": ("Billy", ("Billy", "Punkgoat")),
    "boho": ("Boho", ("Boho",)),
    "bomber": ("Bomber", ("Bomber",)),
    "cadence": ("Cadence", ("Cadence",)),
    "nano": ("Calico", ("Calico", "Nano")),
    "unicorn": ("Celeste", ("Celeste", "Unicorn", "Pepper")),
    "doorman": ("The Doorman", ("Doorman", "The Doorman")),
    "drifter": ("Drifter", ("Drifter",)),
    "druid": ("Druid", ("Druid",)),
    "dynamo": ("Dynamo", ("Dynamo", "Professor Dynamo", "Prof Dynamo")),
    "slork": ("Slork", ("Fathom", "Slork")),
    "fortuna": ("Fortuna", ("Fortuna",)),
    "graf": ("Graf", ("Graf", "Graffiti Girl")),
    "necro": ("Graves", ("Graves", "Necro", "Necromancer", "Gravedigger")),
    "orion": ("Grey Talon", ("Grey Talon", "Orion", "Archer")),
    "gunslinger": ("Gunslinger", ("Gunslinger",)),
    "haze": ("Haze", ("Haze",)),
    "astro": ("Holliday", ("Holliday", "Astro")),
    "inferno": ("Infernus", ("Infernus", "Inferno")),
    "tengu": ("Ivy", ("Ivy", "Tengu")),
    "kali": ("Kali", ("Kali",)),
    "kelvin": ("Kelvin", ("Kelvin",)),
    "ghost": ("Geist", ("Lady Geist", "Geist", "Ghost")),
    "lash": ("Lash", ("Lash",)),
    "forge": ("McGinnis", ("McGinnis", "Forge")),
    "vampirebat": ("Mina", ("Mina", "Vampire Bat", "VampireBat")),
    "mirage": ("Mirage", ("Mirage",)),
    "krill": ("Krill", ("Mo & Krill", "Krill", "Digger")),
    "opera": ("Opera", ("Opera",)),
    "bookworm": ("Paige", ("Paige", "Bookworm")),
    "chrono": ("Paradox", ("Paradox", "Chrono")),
    "synth": ("Pocket", ("Pocket", "Synth")),
    "operative": ("Raven", ("Raven", "Operative")),
    "familiar": ("Rem", ("Rem", "Familiar")),
    "rutger": ("Rutger", ("Rutger",)),
    "gigawatt": ("Seven", ("Seven", "Gigawatt")),
    "shieldguy": ("Shield Guy", ("Shield Guy", "ShieldGuy")),
    "shiv": ("Shiv", ("Shiv",)),
    "werewolf": ("Silver", ("Silver", "Werewolf", "Shapeshifter")),
    "magician": ("Sinclair", ("Sinclair", "Magician")),
    "skyrunner": ("Skyrunner", ("Skyrunner",)),
    "swan": ("Swan", ("Swan",)),
    "testhero": ("Test Hero", ("Test Hero",)),
    "yakuza": ("The Boss", ("The Boss", "Boss", "Big Boss", "Yakuza")),
    "thumper": ("Thumper", ("Thumper",)),
    "tokamak": ("Tokamak", ("Tokamak",)),
    "trapper": ("Trapper", ("Trapper",)),
    "vandal": ("Vandal", ("Vandal",)),
    "priest": ("Venator", ("Venator", "Priest")),
    "frank": ("Victor", ("Victor", "Frank")),
    "hornet": ("Vindicta", ("Vindicta", "Hornet")),
    "viscous": ("Viscous", ("Viscous",)),
    "viper": ("Vyper", ("Vyper", "Viper")),
    "warden": ("Warden", ("Warden",)),
    "wraith": ("Wraith", ("Wraith",)),
    "wrecker": ("Wrecker", ("Wrecker",)),
    "yamato": ("Yamato", ("Yamato",)),
}


EXPLICIT_CORRECTIONS = {
    "transcripts/bebop/ping/bebop_ping_dynamo_was_here.mp3.json": "Dynamo was here.",
    "transcripts/bebop/ping/bebop_ping_ivy_in_mid.mp3.json": "Ivy's in mid.",
    "transcripts/bebop/ping/bebop_ping_murphy_in_mid.mp3.json": "Murphy's in mid.",
    "transcripts/bebop/ping/bebop_ping_purple_help_01.mp3.json": "Purple needs help.",
    "transcripts/bebop/ping/bebop_ping_with_fairfax.mp3.json": "I'm with you, Fairfax.",
    "transcripts/butcher/rr_test_21_ping_careful_bull_01.mp3.json": "Careful, Bull!",
    "transcripts/butcher/rr_test_21_ping_kelvin_headed_to_orange.mp3.json": "Kelvin's headed to orange!",
    "transcripts/butcher/rr_test_21_ping_kelvin_headed_to_yellow.mp3.json": "Kelvin's headed to yellow.",
    "transcripts/butcher/rr_test_21_ping_see_ghost.mp3.json": "I see Ghost.",
    "transcripts/butcher/rr_test_21_ping_see_hornet_on_bridge.mp3.json": "Hornet's on the bridge!",
    "transcripts/gigawatt/ping/gigawatt_ping_careful_the_boss_01.mp3.json": "Careful, Boss.",
    "transcripts/gigawatt/ping/gigawatt_ping_need_help_green.mp3.json": "Need help on green.",
    "transcripts/atlas/ping/abrams_ping_astro_dead.mp3.json": "Holliday is dead.",
    "transcripts/atlas/ping/abrams_ping_attack_shiv.mp3.json": "Let's take out Shiv.",
    "transcripts/atlas/ping/abrams_ping_cadence_was_here.mp3.json": "Cadence was here.",
    "transcripts/atlas/ping/abrams_ping_can_heal_rutger.mp3.json": "Rutger, I can heal you.",
    "transcripts/atlas/ping/abrams_ping_careful_forge_01.mp3.json": "Careful, McGinnis.",
    "transcripts/atlas/ping/abrams_ping_careful_slork_02.mp3.json": "Careful, Slork.",
    "transcripts/atlas/ping/abrams_ping_careful_wraith_01.mp3.json": "Careful, Wraith.",
    "transcripts/atlas/ping/abrams_ping_geist_was_here.mp3.json": "Geist was here.",
    "transcripts/atlas/ping/abrams_ping_geist_was_here_1.mp3.json": "Geist was here.",
    "transcripts/atlas/ping/abrams_ping_ghost_was_here.mp3.json": "Geist was here.",
    "transcripts/atlas/ping/abrams_ping_ghost_was_here_1.mp3.json": "Geist was here.",
    "transcripts/atlas/ping/abrams_ping_lash_on_top_of_garage.mp3.json": "Lash is on top of the garage.",
    "transcripts/atlas/ping/abrams_ping_lash_on_top_of_mid.mp3.json": "Lash on top of mid.",
    "transcripts/atlas/ping/abrams_ping_missing_purple_01.mp3.json": "Missing purple.",
    "transcripts/atlas/ping/abrams_ping_orange_help_01.mp3.json": "Orange needs help.",
    "transcripts/atlas/ping/abrams_ping_orion_dead.mp3.json": "Grey Talon is dead.",
    "transcripts/atlas/ping/abrams_ping_rutger_was_here.mp3.json": "Rutger was here.",
    "transcripts/atlas/ping/abrams_ping_see_cadence_01.mp3.json": "I see Cadence.",
    "transcripts/atlas/ping/abrams_ping_see_lash_on_roof.mp3.json": "Lash is on the roof.",
    "transcripts/atlas/ping/abrams_ping_shiv_dead.mp3.json": "Shiv is dead.",
    "transcripts/atlas/ping/abrams_ping_slork_in_mid.mp3.json": "Slork's in mid.",
    "transcripts/atlas/ping/abrams_ping_slork_missing_01.mp3.json": "Slork's missing.",
    "transcripts/atlas/ping/abrams_ping_slork_on_top_of_garage.mp3.json": "Slork's on top of the garage.",
    "transcripts/atlas/ping/abrams_ping_stun_synth_01.mp3.json": "Stun Pocket.",
    "transcripts/atlas/ping/abrams_ping_stun_wraith_01.mp3.json": "Stun Wraith.",
    "transcripts/atlas/ping/abrams_ping_viscous_dead.mp3.json": "Viscous is dead.",
    "transcripts/atlas/ping/abrams_ping_yamato_in_mid.mp3.json": "Yamato's in mid.",
    "transcripts/atlas/abrams_ally_hornet_killed_in_lane_01.mp3.json": "They took out Vendetta.",
}


def load_judgment_corrections(review_dir: Path) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []
    for path in sorted(review_dir.glob("judgment-corrections-[0-9][0-9].json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        entries = payload.get("corrections", []) if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            raise ValueError(f"{path}: expected a correction array")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{path}: correction must be an object")
            correction = copy.deepcopy(entry)
            correction["reviewFile"] = path.name
            corrections.append(correction)
    return corrections


def load_audit_objections(review_dir: Path) -> dict[str, list[dict[str, Any]]]:
    objections: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(review_dir.glob("judgment-audit-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        entries = payload.get("objections", []) if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            raise ValueError(f"{path}: expected an objection array")
        for entry in entries:
            objection = copy.deepcopy(entry)
            objection["auditFile"] = path.name
            objections[str(entry["id"])].append(objection)
    return objections


def reconcile_judgment_corrections(
    corrections: list[dict[str, Any]], objections: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for correction in corrections:
        item_objections = objections.get(str(correction["id"]), [])
        replacement_texts = {
            str(item["replacementText"])
            for item in item_objections
            if item.get("recommendedAction") == "replace" and item.get("replacementText")
        }
        reject_count = sum(item.get("recommendedAction") == "reject" for item in item_objections)
        if len(replacement_texts) == 1:
            replacement_text = replacement_texts.pop()
            if replacement_text == correction.get("previousSelectedText"):
                rejected.append(
                    {
                        **correction,
                        "auditResolution": "original-retained",
                        "auditObjections": item_objections,
                    }
                )
                continue
            correction = copy.deepcopy(correction)
            correction["correctedText"] = replacement_text
            correction["auditResolution"] = "replacement"
            correction["auditObjections"] = item_objections
            accepted.append(correction)
        elif len(replacement_texts) > 1 or reject_count >= 2:
            rejected.append({**correction, "auditObjections": item_objections})
        else:
            if item_objections:
                correction = copy.deepcopy(correction)
                correction["auditResolution"] = "original-retained"
                correction["auditObjections"] = item_objections
            accepted.append(correction)
    return accepted, rejected


def build_targets(
    items: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    judgment_corrections: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    targets: dict[str, dict[str, Any]] = {}
    corrections: list[dict[str, Any]] = []
    item_by_id = {item["id"]: item for item in items}

    seen_ids: set[str] = set()
    for recommendation in judgment_corrections:
        item_id = str(recommendation["id"])
        if item_id in seen_ids:
            raise ValueError(f"duplicate judgment correction for {item_id}")
        seen_ids.add(item_id)
        item = item_by_id.get(item_id)
        if item is None:
            raise ValueError(f"unknown judgment correction item {item_id}")
        decision = decisions[item_id]
        if decision.get("action") != "choose":
            raise ValueError(f"judgment correction does not target a chosen item: {item_id}")
        previous_text = str(recommendation["previousSelectedText"])
        if previous_text != decision.get("selectedText"):
            raise ValueError(f"judgment correction has stale selected text: {item_id}")
        if item["path"] in EXPLICIT_CORRECTIONS:
            continue
        corrected = str(recommendation["correctedText"])
        if corrected == previous_text:
            raise ValueError(f"judgment correction is a no-op: {item_id}")
        hashes = sorted({digest for option in item["options"] for digest in option["hashes"]})
        for digest in hashes:
            target = {"text": corrected, "source": "manual", "itemId": item_id}
            previous = targets.setdefault(digest, target)
            if previous["text"] != corrected:
                raise ValueError(f"SHA-256 {digest} has conflicting agent corrections")
        corrections.append(
            {
                "id": item_id,
                "path": item["path"],
                "previousSelectedText": previous_text,
                "correctedText": corrected,
                "reason": "agent-judgment",
                "reviewReason": recommendation.get("reason"),
                "confidence": recommendation.get("confidence"),
                "reviewFile": recommendation.get("reviewFile"),
                "auditResolution": recommendation.get("auditResolution"),
                "auditObjections": recommendation.get("auditObjections", []),
                "hashes": hashes,
            }
        )

    for item in items:
        decision = decisions[item["id"]]
        if item["path"] in EXPLICIT_CORRECTIONS:
            corrected = EXPLICIT_CORRECTIONS[item["path"]]
            reason = "review-comment"
            selected_text = decision.get("selectedText")
            if selected_text is None:
                selected_text = " / ".join(option["text"] for option in item["options"])
        else:
            continue
        hashes = sorted({digest for option in item["options"] for digest in option["hashes"]})
        for digest in hashes:
            target = {"text": corrected, "source": "manual", "itemId": item["id"]}
            previous = targets.setdefault(digest, target)
            if previous["text"] != corrected:
                raise ValueError(f"SHA-256 {digest} has conflicting character-name corrections")
        corrections.append(
            {
                "id": item["id"],
                "path": item["path"],
                "previousSelectedText": selected_text,
                "correctedText": corrected,
                "reason": reason,
                "hashes": hashes,
            }
        )
    return targets, corrections


def add_missing_explicit_targets(
    repo: Path,
    targets: dict[str, dict[str, Any]],
    corrections: list[dict[str, Any]],
) -> None:
    covered = {
        item["path"]: item for item in corrections if item["reason"] == "review-comment"
    }
    for relative_path, corrected in EXPLICIT_CORRECTIONS.items():
        document = json.loads((repo / relative_path).read_text(encoding="utf-8-sig"))
        hashes = sorted(
            {digest for revision in document["revisions"] for digest in revision_hashes(revision)}
        )
        item_id = f"review-comment:{relative_path}"
        correction = covered.get(relative_path)
        if correction is not None:
            item_id = correction["id"]
            correction["hashes"] = hashes
        for digest in hashes:
            target = {"text": corrected, "source": "manual", "itemId": item_id}
            targets[digest] = target
        if correction is not None:
            continue
        corrections.append(
            {
                "id": item_id,
                "path": relative_path,
                "previousSelectedText": " / ".join(
                    str(revision.get("text") or "") for revision in document["revisions"]
                ),
                "correctedText": corrected,
                "reason": "review-comment",
                "hashes": hashes,
            }
        )


def _hash_counts(document: dict[str, Any]) -> Counter[str]:
    return Counter(digest for revision in document["revisions"] for digest in revision_hashes(revision))


def apply_document(
    document: dict[str, Any], relative_path: str, targets: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated = copy.deepcopy(document)
    before = _hash_counts(updated)
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for revision in updated["revisions"]:
        retained: list[str] = []
        replacements: dict[str, list[str]] = defaultdict(list)
        for digest in revision_hashes(revision):
            target = targets.get(digest)
            if target is None or (
                revision.get("source") == "manual" and revision.get("text") == target["text"]
            ):
                retained.append(digest)
                continue
            replacements[target["text"]].append(digest)
            changes.append(
                {
                    "path": relative_path,
                    "sha256": digest,
                    "previousText": revision.get("text"),
                    "correctedText": target["text"],
                    "itemId": target["itemId"],
                }
            )
        if retained:
            preserved = copy.deepcopy(revision)
            preserved["sha256"] = sorted(retained)
            output.append(preserved)
        for text, hashes in replacements.items():
            output.append({"sha256": sorted(hashes), "text": text, "source": "manual"})
    updated["revisions"] = compact_revisions(output)
    after = _hash_counts(updated)
    if before != after or any(count != 1 for count in after.values()):
        raise ValueError(f"{relative_path}: character-name correction changed or duplicated hashes")
    return updated, changes


def apply_repo(
    repo: Path, targets: dict[str, dict[str, Any]], *, apply: bool
) -> tuple[list[dict[str, Any]], int]:
    changes: list[dict[str, Any]] = []
    changed_files = 0
    for path in sorted((repo / "transcripts").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        relative_path = path.relative_to(repo).as_posix()
        updated, document_changes = apply_document(document, relative_path, targets)
        if document_changes:
            changed_files += 1
            changes.extend(document_changes)
            if apply:
                path.write_text(canonical_json(updated), encoding="utf-8")
    return changes, changed_files


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--review-dir",
        type=Path,
        default=Path("migration-reports/generated-duration-review"),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    review_dir = args.review_dir if args.review_dir.is_absolute() else repo / args.review_dir
    items, decisions = load_review(review_dir)
    recommendations = load_judgment_corrections(review_dir)
    objections = load_audit_objections(review_dir)
    accepted_recommendations, rejected_recommendations = reconcile_judgment_corrections(
        recommendations, objections
    )
    targets, corrections = build_targets(items, decisions, accepted_recommendations)
    add_missing_explicit_targets(repo, targets, corrections)
    changes, changed_files = apply_repo(repo, targets, apply=args.apply)
    report = {
        "schemaVersion": 1,
        "applied": args.apply,
        "statistics": {
            "correctedReviewItems": len(corrections),
            "explicitReviewComments": sum(item["reason"] == "review-comment" for item in corrections),
            "agentJudgmentCorrections": sum(item["reason"] == "agent-judgment" for item in corrections),
            "rejectedAfterAudit": len(rejected_recommendations),
            "targetHashes": len(targets),
            "changedFiles": changed_files,
            "changedHashOccurrences": len(changes),
        },
        "corrections": corrections,
        "rejectedRecommendations": rejected_recommendations,
        "changes": changes,
    }
    if args.apply:
        report_path = review_dir / "character-name-corrections.json"
        if report_path.exists():
            previous_report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            previous_changes = previous_report.get("changes", [])
            change_key = lambda item: (item["path"], item["sha256"], item["correctedText"])
            merged_changes = {
                change_key(item): item for item in [*previous_changes, *report["changes"]]
            }
            report["changes"] = list(merged_changes.values())
            report["statistics"]["changedHashOccurrences"] = len(report["changes"])
            report["statistics"]["changedFiles"] = len(
                {item["path"] for item in report["changes"]}
            )
        report_path.write_text(
            canonical_json(report), encoding="utf-8"
        )
    print(canonical_json({"applied": args.apply, "statistics": report["statistics"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
