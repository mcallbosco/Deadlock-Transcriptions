from __future__ import annotations

import unittest

from tools.apply_reviewed_generated_duration_merges import (
    apply_targets_to_document,
    selected_targets,
)


def digest(character: str) -> str:
    return character * 64


class ReviewedGeneratedDurationMergeTests(unittest.TestCase):
    def test_selected_option_becomes_target_for_every_item_hash(self) -> None:
        left = digest("a")
        right = digest("b")
        item = {
            "id": "transcripts/hero/line.mp3.json#1000",
            "path": "transcripts/hero/line.mp3.json",
            "filename": "hero/line.mp3",
            "durationMs": 1000,
            "options": [
                {"revisionIndex": 0, "text": "Wrong name.", "model": "test", "hashes": [left]},
                {"revisionIndex": 1, "text": "Right name.", "model": "test", "hashes": [right]},
            ],
        }
        decisions = {
            item["id"]: {
                "id": item["id"],
                "action": "choose",
                "selectedRevisionIndex": 1,
                "selectedText": "Right name.",
                "confidence": "high",
                "rationale": "Filename context resolves the name.",
            }
        }

        targets, reviewed, statistics = selected_targets([item], decisions)

        self.assertEqual(reviewed, [])
        self.assertEqual(statistics["choose_high"], 1)
        self.assertEqual(set(targets), {left, right})
        document = {
            "schemaVersion": 3,
            "filename": "hero/line.mp3",
            "revisions": [
                {"sha256": [left], "text": "Wrong name.", "source": "generated", "model": "test"},
                {"sha256": [right], "text": "Right name.", "source": "generated", "model": "test"},
            ],
        }
        updated, changes = apply_targets_to_document(document, item["path"], targets)
        self.assertEqual(len(changes), 1)
        self.assertEqual(
            updated["revisions"],
            [
                {
                    "sha256": [left, right],
                    "text": "Right name.",
                    "source": "generated",
                    "model": "test",
                }
            ],
        )

    def test_review_decision_creates_no_target(self) -> None:
        item = {
            "id": "transcripts/hero/line.mp3.json#1000",
            "options": [
                {"revisionIndex": 0, "text": "One", "model": "test", "hashes": [digest("c")]},
                {"revisionIndex": 1, "text": "Two", "model": "test", "hashes": [digest("d")]},
            ],
        }
        decision = {
            "id": item["id"],
            "action": "review",
            "selectedRevisionIndex": None,
            "selectedText": None,
            "confidence": "low",
            "rationale": "No contextual evidence.",
        }

        targets, reviewed, statistics = selected_targets([item], {item["id"]: decision})

        self.assertEqual(targets, {})
        self.assertEqual(len(reviewed), 1)
        self.assertEqual(statistics["review_low"], 1)


if __name__ == "__main__":
    unittest.main()
