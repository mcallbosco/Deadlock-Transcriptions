from __future__ import annotations

import unittest

from tools.voiceline_history import (
    OfficialCatalog,
    VoiceLineHistoryError,
    build_history,
    canonical_json,
    history_shard,
    normalize_filename,
    sha256_bytes,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


def catalog(version_id: str, *records: dict) -> OfficialCatalog:
    value = {"hero": {"lines": list(records)}}
    return OfficialCatalog(
        id=version_id,
        label=version_id.upper(),
        content_revision=1,
        value=value,
        sha256=sha256_bytes(canonical_json(value)),
    )


def catalog_with_conversations(version_id: str, *records: dict) -> OfficialCatalog:
    voice_lines = {"hero": {"lines": []}}
    conversations = {"conversations": [{"lines": list(records)}]}
    return OfficialCatalog(
        id=version_id,
        label=version_id.upper(),
        content_revision=1,
        value=voice_lines,
        sha256=sha256_bytes(canonical_json(voice_lines)),
        conversation_value=conversations,
        conversation_sha256=sha256_bytes(canonical_json(conversations)),
    )


def record(filename: str, sha: str, voiceline_id: str = "duplicate-id") -> dict:
    return {
        "filename": filename,
        "voiceline_id": voiceline_id,
        "audioKey": f"sha256/{sha[:2]}/{sha}.mp3",
        "transcription": "catalog text is not authoritative",
    }


class VoiceLineHistoryTests(unittest.TestCase):
    def test_includes_conversation_only_recordings_in_filename_history(self) -> None:
        result = build_history(
            [
                catalog_with_conversations(
                    "v1", record("hero/conversation_01.mp3", SHA_A)
                ),
                catalog_with_conversations(
                    "v2", record("hero/conversation_01.mp3", SHA_B)
                ),
            ],
            {
                SHA_A: ("First conversation recording", True),
                SHA_B: ("Replacement conversation recording", True),
            },
        )

        filename = "hero/conversation_01.mp3"
        line = result.shards[history_shard(filename)]["lines"][filename]
        self.assertEqual(line["versionCount"], 2)
        self.assertEqual(len(line["events"]), 2)
        self.assertIn("conversationSha256", result.versions[0])

    def test_builds_filename_history_and_collapses_unchanged_ranges(self) -> None:
        result = build_history(
            [
                catalog("v1", record("Hero/Line.mp3", SHA_A)),
                catalog("v2", record("hero\\line.mp3", SHA_A)),
                catalog("v3", record("hero/line.mp3", SHA_B)),
            ],
            {
                SHA_A: ("First recording", True),
                SHA_B: ("Replacement recording", False),
            },
        )

        filename = "hero/line.mp3"
        line = result.shards[history_shard(filename)]["lines"][filename]
        self.assertEqual(result.presence["filenames"], [filename])
        self.assertEqual(result.presence["criterion"], "multiple-events")
        self.assertEqual(result.transcript_differences["filenames"], [filename])
        self.assertEqual(
            result.transcript_differences["criterion"],
            "transcription-text-differences",
        )
        self.assertEqual(line["versionCount"], 3)
        self.assertEqual(
            line["events"],
            [
                {
                    "fromVersion": "v1",
                    "throughVersion": "v2",
                    "audioKey": f"sha256/aa/{SHA_A}.mp3",
                    "transcription": "First recording",
                    "officialtranscription": True,
                    "voicelineId": "duplicate-id",
                },
                {
                    "fromVersion": "v3",
                    "throughVersion": "v3",
                    "audioKey": f"sha256/bb/{SHA_B}.mp3",
                    "transcription": "Replacement recording",
                    "voicelineId": "duplicate-id",
                },
            ],
        )

    def test_absence_breaks_a_version_range(self) -> None:
        result = build_history(
            [
                catalog("v1", record("hero/line.mp3", SHA_A)),
                catalog("v2"),
                catalog("v3", record("hero/line.mp3", SHA_A)),
            ],
            {SHA_A: ("Text", False)},
        )

        line = result.shards[history_shard("hero/line.mp3")]["lines"][
            "hero/line.mp3"
        ]
        self.assertEqual(len(line["events"]), 2)
        self.assertEqual(line["events"][0]["throughVersion"], "v1")
        self.assertEqual(line["events"][1]["fromVersion"], "v3")
        self.assertEqual(result.presence["filenames"], ["hero/line.mp3"])
        self.assertEqual(result.transcript_differences["filenames"], [])

    def test_recording_replacement_with_unchanged_text_has_no_transcript_difference(self) -> None:
        result = build_history(
            [
                catalog("v1", record("hero/line.mp3", SHA_A)),
                catalog("v2", record("hero/line.mp3", SHA_B)),
            ],
            {SHA_A: ("Same text", False), SHA_B: ("Same text", True)},
        )

        self.assertEqual(result.presence["filenames"], ["hero/line.mp3"])
        self.assertEqual(result.transcript_differences["filenames"], [])

    def test_unchanged_recording_has_empty_indexes(self) -> None:
        result = build_history(
            [
                catalog("v1", record("Hero/Line.mp3", SHA_A)),
                catalog("v2", record("hero\\line.mp3", SHA_A)),
            ],
            {SHA_A: ("Same text", False)},
        )

        self.assertEqual(result.presence["filenames"], [])
        self.assertEqual(result.presence["lineCount"], 0)
        self.assertEqual(result.transcript_differences["filenames"], [])
        self.assertEqual(result.transcript_differences["lineCount"], 0)

    def test_indexes_use_sorted_normalized_filenames(self) -> None:
        result = build_history(
            [
                catalog(
                    "v1",
                    record("Hero/Zed.mp3", SHA_A),
                    record("Hero\\Alpha.mp3", SHA_B),
                ),
                catalog(
                    "v2",
                    record("hero/zed.mp3", SHA_B),
                    record("hero/alpha.mp3", SHA_A),
                ),
            ],
            {SHA_A: ("One", False), SHA_B: ("Two", False)},
        )

        expected = ["hero/alpha.mp3", "hero/zed.mp3"]
        self.assertEqual(result.presence["filenames"], expected)
        self.assertEqual(result.transcript_differences["filenames"], expected)

    def test_empty_catalog_produces_stable_empty_indexes(self) -> None:
        result = build_history([catalog("v1")], {})

        self.assertEqual(result.presence["filenames"], [])
        self.assertEqual(result.presence["lineCount"], 0)
        self.assertEqual(result.transcript_differences["filenames"], [])
        self.assertEqual(result.transcript_differences["lineCount"], 0)

    def test_duplicate_voiceline_ids_do_not_merge_different_filenames(self) -> None:
        result = build_history(
            [
                catalog(
                    "v1",
                    record("hero/one.mp3", SHA_A),
                    record("hero/two.mp3", SHA_B),
                ),
                catalog(
                    "v2",
                    record("hero/one.mp3", SHA_A),
                    record("hero/two.mp3", SHA_B),
                ),
            ],
            {SHA_A: ("One", False), SHA_B: ("Two", False)},
        )

        lines = {
            filename
            for shard in result.shards.values()
            for filename in shard["lines"]
        }
        self.assertEqual(lines, {"hero/one.mp3", "hero/two.mp3"})

    def test_repository_transcript_state_is_required(self) -> None:
        with self.assertRaisesRegex(VoiceLineHistoryError, SHA_A):
            build_history([catalog("v1", record("hero/line.mp3", SHA_A))], {})

    def test_same_filename_with_two_recordings_in_one_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(VoiceLineHistoryError, "different recordings"):
            build_history(
                [
                    catalog(
                        "v1",
                        record("Hero/Line.mp3", SHA_A),
                        record("hero\\line.mp3", SHA_B),
                    )
                ],
                {SHA_A: ("One", False), SHA_B: ("Two", False)},
            )

    def test_filename_normalization_and_sharding_are_stable(self) -> None:
        self.assertEqual(normalize_filename(" Hero\\Line.mp3 "), "hero/line.mp3")
        self.assertEqual(history_shard("Hero\\Line.mp3"), history_shard("hero/line.mp3"))
        self.assertRegex(history_shard("hero/line.mp3"), r"^[0-9a-f]{2}$")


if __name__ == "__main__":
    unittest.main()
