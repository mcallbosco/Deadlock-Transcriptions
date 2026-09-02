from __future__ import annotations

import unittest

from tools.voiceline_search import (
    CONVERSATION_DESTINATION,
    NORMAL_DESTINATION,
    SearchCatalog,
    build_search_index,
)


def line(filename: str, sha: str, text: str, voiceline_id: str) -> dict:
    return {
        "filename": filename,
        "audioKey": f"sha256/{sha[:2]}/{sha}.mp3",
        "transcription": text,
        "voiceline_id": voiceline_id,
        "duration": 1.25,
    }


def catalog(
    version_id: str,
    voice_lines: list[dict],
    conversation_lines: list[dict] | None = None,
) -> SearchCatalog:
    conversations = []
    if conversation_lines:
        conversations.append(
            {
                "conversation_id": "hero_friend_convo01",
                "speakers": ["hero", "friend"],
                "lines": conversation_lines,
            }
        )
    return SearchCatalog(
        id=version_id,
        label=version_id.title(),
        voice_lines={"hero": {"Match": {"Start": voice_lines}}},
        conversations={"conversations": conversations},
    )


def transcript_states(*records: dict, official: bool = False) -> dict[str, tuple[str, bool]]:
    return {
        record["audioKey"].split("/")[-1].removesuffix(".mp3"): (
            record["transcription"],
            official,
        )
        for record in records
    }


class VoiceLineSearchTests(unittest.TestCase):
    def test_builds_lineage_states_for_latest_applicable_selection(self) -> None:
        old_sha = "11" * 32
        new_sha = "22" * 32
        old = line("hero/old_name.mp3", old_sha, "old keyword", "old_name")
        current = line("hero/old_name.mp3", new_sha, "current wording", "old_name")
        renamed = line("hero/new_name.mp3", new_sha, "current wording", "new_name")
        conversation_copy = {
            **renamed,
            "speaker": "hero",
            "part": 1,
            "variation": 1,
        }
        build = build_search_index(
            [
                catalog("v1", [old]),
                catalog("v2", [current]),
                catalog("v3", [renamed], [conversation_copy]),
            ],
            "deadlock",
            transcript_states(old, current, renamed),
        )

        self.assertEqual(build.lineages, 1)
        self.assertEqual(build.states, 3)
        strings = build.value["strings"]
        record = build.value["records"][0]
        self.assertEqual(strings[record[0]], "hero/old_name.mp3")
        self.assertEqual(
            [strings[index] for index in record[1]],
            ["hero/new_name.mp3", "hero/old_name.mp3"],
        )

        encoded_states = record[2]
        newest_matching_old = next(
            state
            for state in reversed(encoded_states)
            if any("old keyword" in strings[variant[0]] for variant in state[2])
        )
        self.assertEqual(newest_matching_old[:2], [0, 0])
        newest_matching_current = next(
            state
            for state in reversed(encoded_states)
            if any("current wording" in strings[variant[0]] for variant in state[2])
        )
        self.assertEqual(newest_matching_current[:2], [2, 2])
        destination_types = {
            destination[0]
            for variant in newest_matching_current[2]
            for destination in variant[2]
        }
        self.assertEqual(
            destination_types,
            {NORMAL_DESTINATION, CONVERSATION_DESTINATION},
        )

    def test_collapses_identical_consecutive_search_states(self) -> None:
        first = line("hero/line.mp3", "ab" * 32, "Same words", "line")
        reencoded = line("hero/line.mp3", "cd" * 32, "Same words", "line")
        build = build_search_index(
            [catalog("v1", [first]), catalog("v2", [reencoded])],
            "deadlock",
            transcript_states(first, reencoded),
        )
        self.assertEqual(build.states, 1)
        self.assertEqual(build.value["records"][0][2][0][:2], [0, 1])
        strings = build.value["strings"]
        encoded_audio_sha = build.value["records"][0][2][0][2][0][1]
        self.assertEqual(
            strings[encoded_audio_sha],
            "zc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc3Nzc0",
        )

    def test_uses_current_repository_text_instead_of_catalog_correction_history(self) -> None:
        sha = "34" * 32
        stale = line("hero/line.mp3", sha, "They killed Pocket!", "line")
        corrected = line("hero/line.mp3", sha, "I killed Pocket!", "line")
        build = build_search_index(
            [catalog("v1", [stale]), catalog("v2", [corrected])],
            "deadlock",
            {sha: ("I killed Pocket!", True)},
        )
        self.assertEqual(build.states, 1)
        strings = build.value["strings"]
        variant = build.value["records"][0][2][0][2][0]
        self.assertEqual(strings[variant[0]], "I killed Pocket!")
        self.assertEqual(variant[3], 1)
        self.assertNotIn("They killed Pocket!", strings)

    def test_repository_state_resolves_conflicting_alias_catalog_text(self) -> None:
        sha = "56" * 32
        first = line("hero/first.mp3", sha, "stale first", "first")
        second = line("hero/second.mp3", sha, "stale second", "second")
        build = build_search_index(
            [catalog("v1", [first, second])],
            "deadlock",
            {sha: ("authoritative text", False)},
        )
        self.assertEqual(build.lineages, 1)
        self.assertEqual(build.variants, 1)
        strings = build.value["strings"]
        variant = build.value["records"][0][2][0][2][0]
        self.assertEqual(strings[variant[0]], "authoritative text")
        self.assertEqual(len(variant[2]), 2)

    def test_manual_correlations_match_history_lineages(self) -> None:
        atlas = line("hero/atlas_line.mp3", "78" * 32, "prototype", "atlas")
        abrams = line("hero/abrams_line.mp3", "9a" * 32, "current", "abrams")
        build = build_search_index(
            [catalog("v1", [atlas, abrams])],
            "deadlock",
            transcript_states(atlas, abrams),
            [["hero/atlas_line.mp3", "hero/abrams_line.mp3"]],
        )

        self.assertEqual(build.lineages, 1)
        self.assertEqual(build.variants, 2)
        self.assertEqual(
            build.value["lineageSources"],
            ["audio-sha256", "manual-correlations"],
        )
        strings = build.value["strings"]
        aliases = [strings[index] for index in build.value["records"][0][1]]
        self.assertEqual(
            aliases,
            ["hero/abrams_line.mp3", "hero/atlas_line.mp3"],
        )


if __name__ == "__main__":
    unittest.main()
