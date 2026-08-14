from __future__ import annotations

import unittest

from tools.transcript_schema import (
    compact_revisions,
    revisions_for_hash,
    transcript_match_key,
)


class TranscriptSchemaTests(unittest.TestCase):
    def test_match_key_ignores_case_punctuation_and_whitespace(self) -> None:
        expected = transcript_match_key("Lady Geist.")
        self.assertEqual(transcript_match_key("LADY-GEIST?"), expected)
        self.assertEqual(transcript_match_key(" Lady\tGeist!\n"), expected)
        self.assertEqual(transcript_match_key("LadyGeist"), expected)

    def test_compaction_groups_hashes_and_uses_source_authority(self) -> None:
        generated_hash = "1" * 64
        manual_hash = "2" * 64
        official_hash = "3" * 64
        revisions = compact_revisions(
            [
                {
                    "sha256": [generated_hash],
                    "text": "Lady Geist.",
                    "source": "generated",
                    "model": "test-model",
                },
                {
                    "sha256": [manual_hash],
                    "text": "lady-geist!",
                    "source": "manual",
                },
                {
                    "sha256": [official_hash],
                    "text": "LADY GEIST?",
                    "source": "official",
                },
            ]
        )
        self.assertEqual(
            revisions,
            [
                {
                    "sha256": [generated_hash, manual_hash, official_hash],
                    "text": "LADY GEIST?",
                    "source": "official",
                }
            ],
        )
        self.assertIs(revisions_for_hash({"revisions": revisions}, manual_hash)[0], revisions[0])

    def test_terminal_blank_sources_remain_separate(self) -> None:
        revisions = compact_revisions(
            [
                {"sha256": ["1" * 64], "text": "", "source": "skippedeffort"},
                {"sha256": ["2" * 64], "text": "", "source": "skippednonspeech"},
            ]
        )
        self.assertEqual(len(revisions), 2)


if __name__ == "__main__":
    unittest.main()
