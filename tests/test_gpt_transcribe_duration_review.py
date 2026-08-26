from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.gpt_transcribe_duration_review import (
    PROMPT_PREFIX,
    build_transcription_prompt,
    group_review_items,
    option_comparisons,
)


def digest(character: str) -> str:
    return character * 64


class GptTranscribeDurationReviewTests(unittest.TestCase):
    def test_prompt_matches_dlsoundutilities_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vocabulary = Path(temporary) / "vocabulary.json"
            vocabulary.write_text(
                json.dumps({"Characters": ["Wrecker"], "Guidelines": ["Be exact."]}),
                encoding="utf-8",
            )
            self.assertEqual(
                build_transcription_prompt(vocabulary),
                PROMPT_PREFIX + '{"Characters":["Wrecker"],"Guidelines":["Be exact."]}',
            )

    def test_shared_hashes_collapse_items_into_one_recording_group(self) -> None:
        left = digest("a")
        shared = digest("b")
        right = digest("c")
        items = [
            {
                "id": "first#1000",
                "durationMs": 1000,
                "options": [
                    {"text": "First", "hashes": [left]},
                    {"text": "Second", "hashes": [shared]},
                ],
            },
            {
                "id": "alias#1000",
                "durationMs": 1000,
                "options": [
                    {"text": "Second", "hashes": [shared]},
                    {"text": "Third", "hashes": [right]},
                ],
            },
        ]
        locations = {
            left: {
                "sha256": left,
                "audioKey": "left.mp3",
                "audioUrl": "https://example/left.mp3",
                "filename": "left.mp3",
                "durationMs": 1000,
                "versionId": "new",
                "versionIndex": 0,
            },
            right: {
                "sha256": right,
                "audioKey": "right.mp3",
                "audioUrl": "https://example/right.mp3",
                "filename": "right.mp3",
                "durationMs": 1000,
                "versionId": "old",
                "versionIndex": 2,
            },
        }

        groups = group_review_items(items, locations)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["hashes"], [left, shared, right])
        self.assertEqual(groups[0]["representative"]["sha256"], left)
        self.assertEqual(len(groups[0]["items"]), 2)

    def test_option_comparisons_prioritize_normalized_exact_match(self) -> None:
        recording = {
            "items": [
                {
                    "options": [
                        {"text": "I see Wrecker!"},
                        {"text": "I see record."},
                    ]
                }
            ]
        }

        comparisons = option_comparisons(recording, "I see Wrecker.")

        self.assertEqual(comparisons[0]["text"], "I see Wrecker!")
        self.assertTrue(comparisons[0]["normalizedExactMatch"])


if __name__ == "__main__":
    unittest.main()
