#!/usr/bin/env python3
"""Rebuild the common-template correction diff with target-name safeguards."""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

TRANSCRIPTS = Path("transcripts")
MIN_DISTINCT_FILES = 2
SOURCE_PRIORITY = {"official": 3, "manual": 2, "generated": 1}

# These aliases are used only to decide whether text after a misheard command
# plausibly names the filename's target. No alias is ever written into a line.
ALIAS_GROUPS = [
    ({"atlas", "abrams"}, {"Abrams", "Atlas"}),
    ({"airheart"}, {"Airheart"}),
    ({"fencer", "apollo"}, {"Apollo", "Fencer"}),
    ({"bebop"}, {"Bebop"}),
    ({"punkgoat", "billy"}, {"Billy", "Punkgoat"}),
    ({"boho"}, {"Boho"}),
    ({"bomber"}, {"Bomber"}),
    ({"cadence"}, {"Cadence"}),
    ({"nano", "calico"}, {"Calico", "Nano"}),
    ({"unicorn", "celeste", "pepper"}, {"Celeste", "Unicorn", "Pepper"}),
    ({"doorman"}, {"Doorman", "The Doorman"}),
    ({"drifter"}, {"Drifter"}),
    ({"druid"}, {"Druid"}),
    ({"dynamo", "prof"}, {"Dynamo", "Professor Dynamo", "Prof Dynamo"}),
    ({"slork", "fathom"}, {"Fathom", "Slork"}),
    ({"fortuna"}, {"Fortuna"}),
    ({"graf"}, {"Graf", "Graffiti Girl"}),
    ({"necro", "graves"}, {"Graves", "Necro", "Necromancer", "Gravedigger"}),
    ({"orion", "grey_talon", "archer"}, {"Grey Talon", "Orion", "Archer"}),
    ({"gunslinger"}, {"Gunslinger"}),
    ({"haze"}, {"Haze"}),
    ({"astro", "holliday"}, {"Holliday", "Astro"}),
    ({"inferno", "infernus"}, {"Infernus", "Inferno"}),
    ({"tengu", "ivy"}, {"Ivy", "Tengu"}),
    ({"kali"}, {"Kali"}),
    ({"kelvin"}, {"Kelvin"}),
    ({"ghost", "geist"}, {"Lady Geist", "Geist", "Ghost"}),
    ({"lash"}, {"Lash"}),
    ({"forge", "mcginnis"}, {"McGinnis", "Forge"}),
    ({"vampirebat", "mina"}, {"Mina", "Vampire Bat", "VampireBat"}),
    ({"mirage", "sandeep"}, {"Mirage", "Sandeep"}),
    ({"krill", "digger"}, {"Mo & Krill", "Mo and Krill", "Krill", "Digger"}),
    ({"opera"}, {"Opera"}),
    ({"bookworm", "paige"}, {"Paige", "Bookworm"}),
    ({"chrono", "paradox"}, {"Paradox", "Chrono"}),
    ({"synth", "pocket", "fairfax"}, {"Pocket", "Synth", "Fairfax"}),
    ({"operative", "raven"}, {"Raven", "Operative"}),
    ({"familiar", "rem"}, {"Rem", "Familiar"}),
    ({"rutger"}, {"Rutger"}),
    ({"gigawatt", "seven"}, {"Seven", "7", "Gigawatt"}),
    ({"shieldguy"}, {"Shield Guy", "ShieldGuy"}),
    ({"shiv"}, {"Shiv"}),
    ({"werewolf", "silver"}, {"Silver", "Werewolf", "Shapeshifter"}),
    ({"magician", "sinclair"}, {"Sinclair", "Magician"}),
    ({"skyrunner"}, {"Skyrunner"}),
    ({"swan"}, {"Swan"}),
    ({"testhero"}, {"Test Hero"}),
    ({"yakuza", "boss", "the_boss"}, {"The Boss", "Boss", "Big Boss", "Yakuza"}),
    ({"thumper"}, {"Thumper"}),
    ({"tokamak"}, {"Tokamak"}),
    ({"trapper"}, {"Trapper"}),
    ({"vandal"}, {"Vandal"}),
    ({"priest", "venator"}, {"Venator", "Priest"}),
    ({"frank", "victor"}, {"Victor", "Frank"}),
    ({"hornet", "vindicta"}, {"Vindicta", "Hornet"}),
    ({"viscous"}, {"Viscous"}),
    ({"viper", "vyper"}, {"Vyper", "Viper"}),
    ({"warden"}, {"Warden"}),
    ({"wraith"}, {"Wraith"}),
    ({"wrecker"}, {"Wrecker"}),
    ({"yamato"}, {"Yamato"}),
]

TOKEN_TO_ALIASES: dict[str, set[str]] = {}
for tokens, aliases in ALIAS_GROUPS:
    for token in tokens:
        TOKEN_TO_ALIASES[token] = set(aliases) | {token.replace("_", " ")}


def excluded_path(rel: str) -> bool:
    lowered = rel.lower()
    return "orion" in lowered or "grey_talon" in lowered


def norm(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", value)


def parse_target_token(rel: str, marker: str) -> str | None:
    stem = Path(rel).name.removesuffix(".mp3.json")
    lowered = stem.lower()
    index = lowered.find(marker)
    if index < 0:
        return None
    token = lowered[index + len(marker) :]
    token = re.sub(r"(?:_old)?(?:_0?\d+)?(?:_\d+)?$", "", token)
    return token or None


def aliases_for_target(token: str | None) -> set[str]:
    if not token:
        return set()
    aliases = set(TOKEN_TO_ALIASES.get(token, set()))
    aliases.add(token.replace("_", " "))
    return aliases


def looks_like_target(candidate: str, token: str | None) -> bool:
    aliases = aliases_for_target(token)
    if not aliases:
        return False

    candidate = re.sub(r"^[\s,]*(?:a|an|the)\s+", "", candidate, flags=re.IGNORECASE)
    candidate_norm = norm(candidate)
    if not candidate_norm:
        return False

    best = 0.0
    for alias in aliases:
        alias_norm = norm(alias)
        if not alias_norm:
            continue
        if candidate_norm == alias_norm:
            return True
        if min(len(candidate_norm), len(alias_norm)) >= 3 and (
            candidate_norm in alias_norm or alias_norm in candidate_norm
        ):
            return True
        best = max(best, SequenceMatcher(None, candidate_norm, alias_norm).ratio())
    return best >= 0.65


def replace(pattern: str, replacement: str, text: str) -> tuple[str, bool]:
    result, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)
    return result, count > 0


def guarded_prefix_rule(
    rel: str,
    text: str,
    marker: str,
    pattern: str,
    replacement: str,
    remainder_group: int = 2,
) -> tuple[str, bool]:
    match = re.match(pattern, text, flags=re.IGNORECASE)
    if not match:
        return text, False
    token = parse_target_token(rel, marker)
    if not looks_like_target(match.group(remainder_group), token):
        return text, False
    return re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE), True


def apply_rules(rel: str, text: str, enabled: set[str] | None = None) -> tuple[str, list[str]]:
    if excluded_path(rel):
        return text, []

    lowered = rel.lower()
    current = text
    applied: list[str] = []

    def run(rule_id: str, pattern: str, replacement: str) -> None:
        nonlocal current
        if enabled is not None and rule_id not in enabled:
            return
        updated, changed = replace(pattern, replacement, current)
        if changed:
            current = updated
            applied.append(rule_id)

    def run_guarded(rule_id: str, marker: str, pattern: str, replacement: str) -> None:
        nonlocal current
        if enabled is not None and rule_id not in enabled:
            return
        updated, changed = guarded_prefix_rule(rel, current, marker, pattern, replacement)
        if changed:
            current = updated
            applied.append(rule_id)

    if "_can_heal_" in lowered:
        run("can_hear_to_heal", r"\bI can hear you\b", "I can heal you")

    if "_stun_" in lowered:
        run_guarded(
            "stun_command_mishear",
            "_stun_",
            r"^(\s*)(?:stand|stone|spawn|done)\s*,?\s+(.+)$",
            r"\1Stun \2",
        )

    if "_saw_" in lowered:
        run_guarded(
            "saw_command_mishear",
            "_saw_",
            r"^(\s*)I\s+(?:show|shall|so)\s+(.+)$",
            r"\1I saw \2",
        )
        run_guarded(
            "saw_command_mishear",
            "_saw_",
            r"^(\s*)Playstyle\s+(.+)$",
            r"\1I saw \2",
        )

    if "_with_" in lowered:
        run_guarded(
            "with_command_mishear",
            "_with_",
            r"^(\s*)I wish you\s+(.+)$",
            r"\1I'm with you, \2",
        )

    if "_almost_respawn" in lowered:
        run("almost_respawn_wording", r"\bis on my back\b", "is almost back")
        run("almost_respawn_wording", r"\bis almost packed\b", "is almost back")

    if "_in_mid" in lowered:
        run("mid_location_mishear", r"\bin men\b", "in mid")

    if "_on_top_of_mid" in lowered:
        run("mid_location_mishear", r"\bon top of me\b", "on top of mid")

    if "_on_top_of_garage" in lowered:
        run("garage_location_mishear", r"\bon top of the Mirage\b", "on top of the garage")

    if "_under_garage" in lowered:
        run("garage_location_mishear", r"\bunder the Grash\b", "under the garage")

    if "_on_roof" in lowered:
        run("roof_location_mishear", r"\bon the ropes\b", "on the roof")

    if "_attack_" in lowered:
        run_guarded(
            "attack_command_mishear",
            "_attack_",
            r"^(\s*)(?:This tick has|This takes|Let's check out)\s+(.+)$",
            r"\1Let's take out \2",
        )

    return current, applied


def normalised_text(text: str) -> str:
    text = " ".join(text.split()).strip()
    return re.sub(r"[.!?]+$", "", text).casefold()


def merge_hashes(target: dict, source: dict) -> None:
    combined: list[str] = []
    for value in list(target.get("sha256", [])) + list(source.get("sha256", [])):
        if value not in combined:
            combined.append(value)
    target["sha256"] = combined


def merge_revisions(revisions: list[dict]) -> tuple[list[dict], int]:
    removed: set[int] = set()
    merges = 0

    authoritative = [
        (idx, rev)
        for idx, rev in enumerate(revisions)
        if rev.get("source") in {"official", "manual"}
    ]
    for idx, rev in enumerate(revisions):
        if rev.get("source") != "generated":
            continue
        matches = [
            (auth_idx, auth)
            for auth_idx, auth in authoritative
            if normalised_text(str(auth.get("text", ""))) == normalised_text(str(rev.get("text", "")))
        ]
        if matches:
            _auth_idx, auth = max(matches, key=lambda item: SOURCE_PRIORITY[item[1]["source"]])
            merge_hashes(auth, rev)
            removed.add(idx)
            merges += 1

    for idx, rev in enumerate(revisions):
        if idx in removed:
            continue
        for other_idx in range(idx + 1, len(revisions)):
            if other_idx in removed:
                continue
            other = revisions[other_idx]
            if rev.get("text") != other.get("text"):
                continue
            if rev.get("source") == other.get("source") == "generated" and rev.get("model") != other.get("model"):
                continue
            if SOURCE_PRIORITY.get(other.get("source", ""), 0) > SOURCE_PRIORITY.get(rev.get("source", ""), 0):
                merge_hashes(other, rev)
                removed.add(idx)
                merges += 1
                break
            merge_hashes(rev, other)
            removed.add(other_idx)
            merges += 1

    return [rev for idx, rev in enumerate(revisions) if idx not in removed], merges


def restore_previous_diff_to_base() -> str:
    base = subprocess.check_output(
        ["git", "merge-base", "origin/main", "HEAD"], text=True
    ).strip()
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}...HEAD", "--", "transcripts"],
        text=True,
    ).splitlines()
    for start in range(0, len(changed), 100):
        batch = changed[start : start + 100]
        if batch:
            subprocess.run(["git", "checkout", base, "--", *batch], check=True)
    print(f"Restored {len(changed)} prior transcript changes to base {base[:12]}")
    return base


def collect_candidates() -> dict[str, list[tuple[str, str, str]]]:
    result: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path in TRANSCRIPTS.rglob("*.mp3.json"):
        rel = path.as_posix()
        if excluded_path(rel):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for revision in data.get("revisions", []):
            if revision.get("source") != "generated" or not isinstance(revision.get("text"), str):
                continue
            old = revision["text"]
            new, rules = apply_rules(rel, old)
            if new == old:
                continue
            for rule in set(rules):
                result[rule].append((rel, old, new))
    return result


def main() -> None:
    restore_previous_diff_to_base()
    candidates = collect_candidates()
    enabled = {
        rule
        for rule, rows in candidates.items()
        if len({rel for rel, _old, _new in rows}) >= MIN_DISTINCT_FILES
    }

    print("Refined candidate counts:")
    for rule in sorted(candidates):
        rows = candidates[rule]
        files = len({rel for rel, _old, _new in rows})
        print(f"  {rule}: {len(rows)} revisions in {files} files " + ("[ENABLED]" if rule in enabled else "[SKIPPED_ONE_OFF]"))

    changed_files = 0
    correction_counts: dict[str, int] = defaultdict(int)
    merge_count = 0

    for path in TRANSCRIPTS.rglob("*.mp3.json"):
        rel = path.as_posix()
        if excluded_path(rel):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        revisions = data.get("revisions", [])
        changed = False
        for revision in revisions:
            if revision.get("source") != "generated" or not isinstance(revision.get("text"), str):
                continue
            old = revision["text"]
            new, rules = apply_rules(rel, old, enabled)
            if new == old:
                continue
            revision["text"] = new
            changed = True
            for rule in set(rules):
                correction_counts[rule] += 1
        if not changed:
            continue
        data["revisions"], merges = merge_revisions(revisions)
        merge_count += merges
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed_files += 1

    print("Applied refined corrections:")
    for rule in sorted(correction_counts):
        print(f"  {rule}: {correction_counts[rule]}")
    print(f"Changed files: {changed_files}")
    print(f"Merged duplicate revisions: {merge_count}")

    if not changed_files:
        raise SystemExit("No refined common corrections remained.")


if __name__ == "__main__":
    main()
