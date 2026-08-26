from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.gpt_transcribe_duration_review import (
    PROMPT_PREFIX,
    analyze_results,
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

    def test_analysis_separates_nonblank_exact_and_blank_results(self) -> None:
        exact_id = digest("d")
        blank_id = digest("e")
        queue = {
            "model": "gpt-transcribe",
            "recordings": [
                {
                    "recordingId": exact_id,
                    "items": [
                        {
                            "id": "exact#1000",
                            "path": "transcripts/exact.json",
                            "filename": "exact.mp3",
                            "durationMs": 1000,
                            "options": [
                                {"text": "Wrecker!", "hashes": [digest("f")], "model": "old"},
                                {"text": "Record.", "hashes": [digest("0")], "model": "old"},
                            ],
                        }
                    ],
                },
                {
                    "recordingId": blank_id,
                    "items": [
                        {
                            "id": "blank#500",
                            "path": "transcripts/blank.json",
                            "filename": "blank.mp3",
                            "durationMs": 500,
                            "options": [
                                {"text": "Noise", "hashes": [digest("1")], "model": "old"},
                                {"text": "", "hashes": [digest("2")], "model": "old"},
                            ],
                        }
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            results = Path(temporary) / "results.jsonl"
            results.write_text(
                "\n".join(
                    json.dumps(result)
                    for result in [
                        {
                            "recordingId": exact_id,
                            "status": "success",
                            "representativeSha256": digest("f"),
                            "transcription": "Wrecker.",
                        },
                        {
                            "recordingId": blank_id,
                            "status": "success",
                            "representativeSha256": digest("1"),
                            "transcription": "",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            analysis = analyze_results(queue, results)

        self.assertEqual(analysis["statistics"]["nonblankExactExistingItems"], 1)
        self.assertEqual(analysis["statistics"]["blankExactItems"], 1)
        self.assertEqual(len(analysis["nonblankExactExistingCandidates"]), 1)


if __name__ == "__main__":
    unittest.main()
