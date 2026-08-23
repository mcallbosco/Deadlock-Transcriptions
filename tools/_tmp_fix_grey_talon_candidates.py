#!/usr/bin/env python3
import json
import re
from pathlib import Path

CANDIDATE_PATHS = {'transcripts/announcer/female_patron/patron_female_tutorial_combat_enemy_orion_info.mp3.json',
 'transcripts/announcer/female_patron/patron_female_weak_ally_orion_killing_streak_03.mp3.json',
 'transcripts/atlas/abrams_ally_orion_killed_in_lane_01.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_almost_respawn.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_almost_respawn_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_check_items.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_check_items_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_dead.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_dead_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_missing_01.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_missing_01_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_on_top_of_garage.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_on_top_of_garage_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_on_top_of_mid.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_on_top_of_mid_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_under_garage.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_under_garage_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_was_here.mp3.json',
 'transcripts/atlas/ping/abrams_ping_grey_talon_was_here_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_almost_respawn.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_almost_respawn_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_check_items.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_check_items_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_dead.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_dead_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_missing_01.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_missing_01_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_on_top_of_garage.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_on_top_of_garage_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_on_top_of_mid.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_on_top_of_mid_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_under_garage.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_under_garage_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_orion_was_here.mp3.json',
 'transcripts/atlas/ping/abrams_ping_saw_orion.mp3.json',
 'transcripts/atlas/ping/abrams_ping_see_grey_talon_01.mp3.json',
 'transcripts/atlas/ping/abrams_ping_see_grey_talon_01_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_see_grey_talon_on_bridge.mp3.json',
 'transcripts/atlas/ping/abrams_ping_see_grey_talon_on_bridge_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_see_orion_01.mp3.json',
 'transcripts/atlas/ping/abrams_ping_see_orion_01_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_see_orion_on_bridge_1.mp3.json',
 'transcripts/atlas/ping/abrams_ping_with_orion.mp3.json',
 'transcripts/bookworm/ping/bookworm_ping_orion_was_here.mp3.json',
 'transcripts/chrono/ping/chrono_ping_orion_almost_respawn.mp3.json',
 'transcripts/chrono/ping/chrono_ping_orion_check_items.mp3.json',
 'transcripts/chrono/ping/chrono_ping_saw_orion.mp3.json',
 'transcripts/chrono/ping/chrono_ping_see_orion_01.mp3.json',
 'transcripts/chrono/ping/chrono_ping_with_orion.mp3.json',
 'transcripts/dynamo/ping/prof_ping_can_heal_orion.mp3.json',
 'transcripts/dynamo/ping/prof_ping_careful_orion_03.mp3.json',
 'transcripts/dynamo/ping/prof_ping_ignore_orion.mp3.json',
 'transcripts/dynamo/ping/prof_ping_orion_almost_respawn.mp3.json',
 'transcripts/dynamo/ping/prof_ping_orion_check_items.mp3.json',
 'transcripts/dynamo/ping/prof_ping_orion_missing_01.mp3.json',
 'transcripts/dynamo/ping/prof_ping_orion_on_top_of_garage.mp3.json',
 'transcripts/dynamo/ping/prof_ping_saw_orion.mp3.json',
 'transcripts/dynamo/ping/prof_ping_see_orion_on_bridge.mp3.json',
 'transcripts/dynamo/ping/prof_ping_stun_orion_01.mp3.json',
 'transcripts/dynamo/prof_ally_orion_missile_stops_ult_03.mp3.json',
 'transcripts/dynamo/prof_kill_orion_05.mp3.json',
 'transcripts/forge/ping/mcginnis_ping_saw_grey_talon.mp3.json',
 'transcripts/forge/ping/mcginnis_ping_saw_orion.mp3.json',
 'transcripts/frank/ping/frank_ping_orion_almost_respawn.mp3.json',
 'transcripts/frank/ping/frank_ping_orion_check_items.mp3.json',
 'transcripts/frank/ping/frank_ping_orion_dead.mp3.json',
 'transcripts/frank/ping/frank_ping_orion_was_here.mp3.json',
 'transcripts/frank/ping/frank_ping_saw_orion.mp3.json',
 'transcripts/ghost/ping/geist_ping_grey_talon_almost_respawn.mp3.json',
 'transcripts/ghost/ping/geist_ping_grey_talon_on_top_of_mid.mp3.json',
 'transcripts/ghost/ping/geist_ping_grey_talon_was_here.mp3.json',
 'transcripts/ghost/ping/geist_ping_orion_almost_respawn.mp3.json',
 'transcripts/ghost/ping/geist_ping_orion_on_top_of_mid.mp3.json',
 'transcripts/ghost/ping/geist_ping_orion_was_here.mp3.json',
 'transcripts/ghost/ping/geist_ping_with_grey_talon.mp3.json',
 'transcripts/ghost/ping/geist_ping_with_orion.mp3.json',
 'transcripts/gigawatt/gigawatt_kill_orion_03.mp3.json',
 'transcripts/gigawatt/ping/gigawatt_ping_orion_dead.mp3.json',
 'transcripts/gigawatt/ping/gigawatt_ping_orion_on_top_of_garage.mp3.json',
 'transcripts/gigawatt/ping/gigawatt_ping_orion_on_top_of_mid.mp3.json',
 'transcripts/gigawatt/ping/gigawatt_ping_see_orion_01.mp3.json',
 'transcripts/gigawatt/ping/gigawatt_ping_stun_orion_01.mp3.json',
 'transcripts/haze/ping/haze_ping_ignore_orion.mp3.json',
 'transcripts/haze/ping/haze_ping_orion_almost_respawn.mp3.json',
 'transcripts/haze/ping/haze_ping_orion_check_items.mp3.json',
 'transcripts/haze/ping/haze_ping_orion_dead.mp3.json',
 'transcripts/haze/ping/haze_ping_see_orion_01.mp3.json',
 'transcripts/haze/ping/haze_ping_stun_orion_01.mp3.json',
 'transcripts/inferno/inferno_enemy_orion_see_missile_03.mp3.json',
 'transcripts/inferno/ping/inferno_ping_orion_check_items.mp3.json',
 'transcripts/inferno/ping/inferno_ping_orion_was_here.mp3.json',
 'transcripts/inferno/ping/inferno_ping_saw_orion.mp3.json',
 'transcripts/inferno/ping/inferno_ping_see_orion_01.mp3.json',
 'transcripts/inferno/ping/inferno_ping_with_orion.mp3.json',
 'transcripts/lash/ping/lash_ping_orion_almost_respawn.mp3.json',
 'transcripts/lash/ping/lash_ping_orion_check_items.mp3.json',
 'transcripts/lash/ping/lash_ping_orion_was_here.mp3.json',
 'transcripts/lash/ping/lash_ping_stun_orion_01.mp3.json',
 'transcripts/magician/ping/magician_savannah_ping_stun_orion_01.mp3.json',
 'transcripts/mirage/ping/mirage_ping_attack_orion.mp3.json',
 'transcripts/mirage/ping/mirage_ping_orion_almost_respawn.mp3.json',
 'transcripts/mirage/ping/mirage_ping_orion_dead.mp3.json',
 'transcripts/mirage/ping/mirage_ping_orion_was_here.mp3.json',
 'transcripts/mirage/ping/mirage_ping_saw_orion.mp3.json',
 'transcripts/mirage/ping/mirage_ping_stun_orion_01.mp3.json',
 'transcripts/mirage/ping/mirage_ping_with_orion.mp3.json',
 'transcripts/operative/ping/operative_ping_careful_orion_01.mp3.json',
 'transcripts/operative/ping/operative_ping_orion_in_mid.mp3.json',
 'transcripts/pocket/ping/pocket_ping_grey_talon_in_mid.mp3.json',
 'transcripts/pocket/ping/pocket_ping_grey_talon_missing_01.mp3.json',
 'transcripts/pocket/ping/pocket_ping_orion_in_mid.mp3.json',
 'transcripts/pocket/ping/pocket_ping_orion_missing_01.mp3.json',
 'transcripts/pocket/ping/pocket_ping_saw_grey_talon.mp3.json',
 'transcripts/pocket/ping/pocket_ping_saw_orion.mp3.json',
 'transcripts/pocket/ping/pocket_ping_see_grey_talon_on_roof.mp3.json',
 'transcripts/pocket/ping/pocket_ping_see_orion_on_roof.mp3.json',
 'transcripts/priest/ping/priest_ping_orion_in_mid.mp3.json',
 'transcripts/priest/ping/priest_ping_saw_orion.mp3.json',
 'transcripts/priest/ping/priest_ping_see_orion_on_roof.mp3.json',
 'transcripts/priest/ping/priest_ping_with_orion.mp3.json',
 'transcripts/slork/ping/slork_ping_can_heal_orion.mp3.json',
 'transcripts/slork/ping/slork_ping_careful_orion_03.mp3.json',
 'transcripts/slork/ping/slork_ping_orion_check_items.mp3.json',
 'transcripts/slork/ping/slork_ping_orion_in_mid.mp3.json',
 'transcripts/slork/ping/slork_ping_orion_on_top_of_garage.mp3.json',
 'transcripts/slork/ping/slork_ping_orion_on_top_of_mid.mp3.json',
 'transcripts/slork/ping/slork_ping_orion_under_garage.mp3.json',
 'transcripts/slork/ping/slork_ping_saw_orion.mp3.json',
 'transcripts/slork/ping/slork_ping_see_orion_01.mp3.json',
 'transcripts/slork/ping/slork_ping_see_orion_on_roof.mp3.json',
 'transcripts/slork/ping/slork_ping_stun_orion_01.mp3.json',
 'transcripts/synth/ping/pocket_ping_grey_talon_in_mid.mp3.json',
 'transcripts/synth/ping/pocket_ping_grey_talon_missing_01.mp3.json',
 'transcripts/synth/ping/pocket_ping_orion_in_mid.mp3.json',
 'transcripts/synth/ping/pocket_ping_orion_missing_01.mp3.json',
 'transcripts/synth/ping/pocket_ping_saw_grey_talon.mp3.json',
 'transcripts/synth/ping/pocket_ping_saw_orion.mp3.json',
 'transcripts/synth/ping/pocket_ping_see_grey_talon_on_roof.mp3.json',
 'transcripts/synth/ping/pocket_ping_see_orion_on_roof.mp3.json',
 'transcripts/tengu/ivy_kill_orion_02.mp3.json',
 'transcripts/tengu/ping/ivy_ping_attack_orion.mp3.json',
 'transcripts/tengu/ping/ivy_ping_can_heal_orion.mp3.json',
 'transcripts/tengu/ping/ivy_ping_careful_orion_02.mp3.json',
 'transcripts/tengu/ping/ivy_ping_careful_orion_03.mp3.json',
 'transcripts/tengu/ping/ivy_ping_ignore_orion.mp3.json',
 'transcripts/tengu/ping/ivy_ping_orion_almost_respawn.mp3.json',
 'transcripts/tengu/ping/ivy_ping_orion_check_items.mp3.json',
 'transcripts/tengu/ping/ivy_ping_orion_on_top_of_garage.mp3.json',
 'transcripts/tengu/ping/ivy_ping_orion_was_here.mp3.json',
 'transcripts/tengu/ping/ivy_ping_saw_orion.mp3.json',
 'transcripts/tengu/ping/ivy_ping_see_orion_01.mp3.json',
 'transcripts/tengu/ping/ivy_ping_see_orion_on_roof.mp3.json',
 'transcripts/tengu/ping/ivy_ping_stun_orion_01.mp3.json',
 'transcripts/tengu/ping/ivy_ping_with_orion.mp3.json',
 'transcripts/tengu/ping/tengu_ping_orion_check_items.mp3.json',
 'transcripts/tengu/ping/tengu_ping_with_orion.mp3.json',
 'transcripts/trapper/ping/trapper_ping_can_heal_orion.mp3.json',
 'transcripts/trapper/ping/trapper_ping_careful_orion_02.mp3.json',
 'transcripts/trapper/ping/trapper_ping_orion_almost_respawn.mp3.json',
 'transcripts/trapper/ping/trapper_ping_orion_check_items.mp3.json',
 'transcripts/trapper/ping/trapper_ping_orion_missing_01.mp3.json',
 'transcripts/trapper/ping/trapper_ping_orion_under_garage.mp3.json',
 'transcripts/trapper/ping/trapper_ping_orion_was_here.mp3.json',
 'transcripts/trapper/ping/trapper_ping_saw_orion.mp3.json',
 'transcripts/trapper/ping/trapper_ping_see_orion_on_roof.mp3.json',
 'transcripts/vampirebat/ping/vampirebat_ping_orion_almost_respawn.mp3.json',
 'transcripts/viper/ping/viper_ping_orion_check_items.mp3.json',
 'transcripts/viper/ping/viper_ping_orion_under_garage.mp3.json',
 'transcripts/warden/ping/warden_ping_can_heal_grey_talon.mp3.json',
 'transcripts/warden/ping/warden_ping_ignore_grey_talon.mp3.json',
 'transcripts/warden/ping/warden_ping_orion_almost_respawn.mp3.json',
 'transcripts/warden/ping/warden_ping_orion_check_items.mp3.json',
 'transcripts/warden/ping/warden_ping_orion_was_here.mp3.json',
 'transcripts/warden/ping/warden_ping_saw_grey_talon.mp3.json',
 'transcripts/warden/warden_enemy_orion_see_missile_01.mp3.json',
 'transcripts/wraith/ping/wraith_ping_orion_almost_respawn.mp3.json',
 'transcripts/wraith/ping/wraith_ping_orion_check_items.mp3.json',
 'transcripts/wraith/ping/wraith_ping_saw_orion.mp3.json',
 'transcripts/wraith/ping/wraith_ping_stun_orion_01.mp3.json'}

SOURCE_PRIORITY = {"official": 3, "manual": 2, "generated": 1}

SUSPICIOUS = re.compile(
    r"(?i)(?:\ba\s+)?\bgreat\s+(?:talent|talon)(?:'s|s)?\b|\bgreat\s+(?:talent|talon)bot\b"
)


def canonicalize(text: str, rel_path: str) -> str:
    # The bot/bought pass is already on main. This only guards against a stale
    # glued Talonbot form in one of the supplied check-items candidates.
    if "_check_items" in rel_path:
        text = re.sub(
            r"(?i)\b(?:a\s+)?great\s+(?:talent|talon)\s*(?:bot|bots|boss)\b",
            "Grey Talon bought",
            text,
        )

    # Correct only the proper-name recognition. Different revisions under one
    # filename can correspond to genuinely different recordings/wording, so do
    # not normalize the rest of the sentence from filename context alone.
    text = re.sub(r"(?i)\ba\s+great\s+(?:talent|talon)\b", "Grey Talon", text)
    text = re.sub(r"(?i)\bgreat\s+(?:talent|talon)'s\b", "Grey Talon's", text)
    # Whisper commonly hears the contraction "'s" as a plural "s" here.
    text = re.sub(r"(?i)\bgreat\s+(?:talents|talons)\b", "Grey Talon's", text)
    text = re.sub(r"(?i)\bgreat\s+(?:talent|talon)\b", "Grey Talon", text)
    return text


def merge_exact_duplicates(revisions):
    out = []
    for rev in revisions:
        match_idx = None
        for i, existing in enumerate(out):
            if existing.get("text") != rev.get("text"):
                continue

            e_source = existing.get("source", "")
            r_source = rev.get("source", "")
            if e_source in ("official", "manual") or r_source in ("official", "manual"):
                match_idx = i
                break

            # Preserve generated model provenance unless it is the same model.
            if e_source == r_source == "generated" and existing.get("model") == rev.get("model"):
                match_idx = i
                break

        if match_idx is None:
            out.append(rev)
            continue

        existing = out[match_idx]
        e_priority = SOURCE_PRIORITY.get(existing.get("source", ""), 0)
        r_priority = SOURCE_PRIORITY.get(rev.get("source", ""), 0)

        if r_priority > e_priority:
            base, other = rev, existing
            out[match_idx] = base
        else:
            base, other = existing, rev

        hashes = []
        for h in list(base.get("sha256", [])) + list(other.get("sha256", [])):
            if h not in hashes:
                hashes.append(h)
        base["sha256"] = hashes

    return out


def main():
    changed_files = []
    corrected_revisions = 0
    additional_files = []

    for path in Path("transcripts").rglob("*.mp3.json"):
        rel = path.as_posix()
        context = rel.lower()
        if "orion" not in context and "grey_talon" not in context:
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        revisions = data.get("revisions", [])
        file_changed = False
        targeted_file = rel in CANDIDATE_PATHS
        extra_hit = False

        for rev in revisions:
            text = rev.get("text")
            if not isinstance(text, str) or not SUSPICIOUS.search(text):
                continue

            source = rev.get("source", "")
            # Official text is authoritative. Manual rows are changed only when
            # their file was explicitly supplied by the user; the broader re-scan
            # is restricted to generated ASR revisions.
            if source == "official":
                continue
            if source == "manual" and not targeted_file:
                continue
            if source not in ("generated", "manual"):
                continue

            corrected = canonicalize(text, rel)
            if corrected == text:
                continue

            rev["text"] = corrected
            corrected_revisions += 1
            file_changed = True
            if not targeted_file:
                extra_hit = True

        if not file_changed:
            continue

        data["revisions"] = merge_exact_duplicates(revisions)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed_files.append(rel)
        if extra_hit:
            additional_files.append(rel)

    print(f"Corrected revisions: {corrected_revisions}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Additional rescan files outside supplied list: {len(additional_files)}")
    for rel in additional_files:
        print(f"EXTRA {rel}")

    if not changed_files:
        raise SystemExit("No Grey Talon transcript corrections were needed on current main.")


if __name__ == "__main__":
    main()
