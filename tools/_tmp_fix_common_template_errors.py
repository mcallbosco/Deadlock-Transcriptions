#!/usr/bin/env python3
"""Fix repeated, template-backed ASR errors without renaming heroes.

This intentionally changes only the action/location wording around a spoken
name. It never maps a transcript name from an internal/beta name to a release
name. Orion/Grey Talon files are excluded because they are handled by PR #216.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

TRANSCRIPTS = Path("transcripts")
MIN_DISTINCT_FILES = 2
SOURCE_PRIORITY = {"official": 3, "manual": 2, "generated": 1}


def excluded_path(rel: str) -> bool:
    lowered = rel.lower()
    return "orion" in lowered or "grey_talon" in lowered


def sub(pattern: str, replacement: str, text: str) -> tuple[str, bool]:
    result, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)
    return result, count > 0


def apply_rules(rel: str, text: str, enabled: set[str] | None = None) -> tuple[str, list[str]]:
    """Return transformed text and rule IDs, preserving every target name."""
    if excluded_path(rel):
        return text, []

    lowered = rel.lower()
    current = text
    applied: list[str] = []

    def run(rule_id: str, pattern: str, replacement: str) -> None:
        nonlocal current
        if enabled is not None and rule_id not in enabled:
            return
        updated, changed = sub(pattern, replacement, current)
        if changed:
            current = updated
            applied.append(rule_id)

    if "_can_heal_" in lowered:
        run("can_hear_to_heal", r"\bI can hear you\b", "I can heal you")

    if "_stun_" in lowered:
        run(
            "stun_command_mishear",
            r"^(\s*)(?:stand|stone|spawn|done)\s*,?\s+",
            r"\1Stun ",
        )

    if "_saw_" in lowered:
        run(
            "saw_command_mishear",
            r"^(\s*)I\s+(?:show|shall|so)\s+",
            r"\1I saw ",
        )
        run("saw_command_mishear", r"^(\s*)Playstyle\s+", r"\1I saw ")

    if "_with_" in lowered:
        run(
            "with_command_mishear",
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
        run(
            "garage_location_mishear",
            r"\bon top of the Mirage\b",
            "on top of the garage",
        )

    if "_under_garage" in lowered:
        run("garage_location_mishear", r"\bunder the Grash\b", "under the garage")

    if "_on_roof" in lowered:
        run("roof_location_mishear", r"\bon the ropes\b", "on the roof")

    if "_attack_" in lowered:
        run(
            "attack_command_mishear",
            r"^(\s*)(?:This tick has|This takes|Let's check out)\s+",
            r"\1Let's take out ",
        )

    return current, applied


def normalised_text(text: str) -> str:
    text = " ".join(text.split()).strip()
    text = re.sub(r"[.!?]+$", "", text)
    return text.casefold()


def merge_hashes(target: dict, source: dict) -> None:
    hashes: list[str] = []
    for value in list(target.get("sha256", [])) + list(source.get("sha256", [])):
        if value not in hashes:
            hashes.append(value)
    target["sha256"] = hashes


def merge_revisions(revisions: list[dict]) -> tuple[list[dict], int]:
    """Merge corrected duplicates while retaining authoritative provenance."""
    removed: set[int] = set()
    merge_count = 0

    # Prefer official/manual text when a corrected generated row differs only
    # by terminal punctuation or capitalization.
    authoritative = [
        (idx, rev)
        for idx, rev in enumerate(revisions)
        if rev.get("source") in {"official", "manual"}
    ]
    for idx, rev in enumerate(revisions):
        if idx in removed or rev.get("source") != "generated":
            continue
        key = normalised_text(str(rev.get("text", "")))
        matches = [
            (auth_idx, auth)
            for auth_idx, auth in authoritative
            if auth_idx not in removed and normalised_text(str(auth.get("text", ""))) == key
        ]
        if not matches:
            continue
        auth_idx, auth = max(matches, key=lambda item: SOURCE_PRIORITY.get(item[1].get("source", ""), 0))
        merge_hashes(auth, rev)
        removed.add(idx)
        merge_count += 1

    # Merge exact duplicates at the same provenance level. For generated rows,
    # require the same model so model attribution is not lost.
    for idx, rev in enumerate(revisions):
        if idx in removed:
            continue
        for other_idx in range(idx + 1, len(revisions)):
            if other_idx in removed:
                continue
            other = revisions[other_idx]
            if rev.get("text") != other.get("text"):
                continue

            rev_source = rev.get("source", "")
            other_source = other.get("source", "")
            if rev_source == other_source == "generated" and rev.get("model") != other.get("model"):
                continue
            if rev_source not in {"official", "manual"} and other_source not in {"official", "manual"}:
                if rev_source != other_source:
                    continue

            if SOURCE_PRIORITY.get(other_source, 0) > SOURCE_PRIORITY.get(rev_source, 0):
                merge_hashes(other, rev)
                removed.add(idx)
                merge_count += 1
                break

            merge_hashes(rev, other)
            removed.add(other_idx)
            merge_count += 1

    return [rev for idx, rev in enumerate(revisions) if idx not in removed], merge_count


def iter_generated_candidates() -> Iterable[tuple[str, int, str, str, list[str]]]:
    for path in TRANSCRIPTS.rglob("*.mp3.json"):
        rel = path.as_posix()
        if excluded_path(rel):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for index, revision in enumerate(data.get("revisions", [])):
            if revision.get("source") != "generated":
                continue
            text = revision.get("text")
            if not isinstance(text, str):
                continue
            updated, rules = apply_rules(rel, text)
            if updated != text:
                yield rel, index, text, updated, rules


def main() -> None:
    candidates_by_rule: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for rel, _index, old, new, rules in iter_generated_candidates():
        for rule in set(rules):
            candidates_by_rule[rule].append((rel, old, new))

    enabled = {
        rule
        for rule, candidates in candidates_by_rule.items()
        if len({rel for rel, _old, _new in candidates}) >= MIN_DISTINCT_FILES
    }

    print("Candidate rule counts:")
    for rule in sorted(candidates_by_rule):
        candidates = candidates_by_rule[rule]
        distinct = len({rel for rel, _old, _new in candidates})
        state = "ENABLED" if rule in enabled else "SKIPPED_ONE_OFF"
        print(f"  {rule}: {len(candidates)} revisions in {distinct} files [{state}]")

    changed_files: list[str] = []
    corrections_by_rule: dict[str, int] = defaultdict(int)
    total_merges = 0

    for path in TRANSCRIPTS.rglob("*.mp3.json"):
        rel = path.as_posix()
        if excluded_path(rel):
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        revisions = data.get("revisions", [])
        changed = False

        for revision in revisions:
            if revision.get("source") != "generated":
                continue
            text = revision.get("text")
            if not isinstance(text, str):
                continue
            updated, rules = apply_rules(rel, text, enabled)
            if updated == text:
                continue
            revision["text"] = updated
            changed = True
            for rule in set(rules):
                corrections_by_rule[rule] += 1

        if not changed:
            continue

        merged, merge_count = merge_revisions(revisions)
        data["revisions"] = merged
        total_merges += merge_count
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed_files.append(rel)

    print("Applied corrections:")
    for rule in sorted(corrections_by_rule):
        print(f"  {rule}: {corrections_by_rule[rule]}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Merged duplicate revisions: {total_merges}")

    if not changed_files:
        raise SystemExit("No repeated template-backed errors were found.")


if __name__ == "__main__":
    main()
