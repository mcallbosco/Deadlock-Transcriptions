from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.apply_character_name_review_corrections import (
    apply_document,
    build_targets,
    load_judgment_corrections,
    reconcile_judgment_corrections,
)


def digest(character: str) -> str:
    return character * 64


class CharacterNameReviewCorrectionTests(unittest.TestCase):
    def test_loads_list_and_wrapped_agent_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = {"id": "one", "previousSelectedText": "bad", "correctedText": "good"}
            second = {"id": "two", "previousSelectedText": "old", "correctedText": "new"}
            (root / "judgment-corrections-01.json").write_text(
                json.dumps([first]), encoding="utf-8"
            )
            (root / "judgment-corrections-02.json").write_text(
                json.dumps({"schemaVersion": 1, "corrections": [second]}), encoding="utf-8"
            )

            corrections = load_judgment_corrections(root)

        self.assertEqual([item["id"] for item in corrections], ["one", "two"])
        self.assertEqual(corrections[0]["reviewFile"], "judgment-corrections-01.json")

    def test_agent_judgment_targets_every_hash_and_becomes_manual(self) -> None:
        left, right = digest("a"), digest("b")
        item = {
            "id": "transcripts/hero/ping/line.mp3.json#1000",
            "path": "transcripts/hero/ping/line.mp3.json",
            "filename": "hero/ping/line.mp3",
            "options": [
                {"revisionIndex": 0, "text": "Hazes on bridge.", "hashes": [left]},
                {"revisionIndex": 1, "text": "Haze on bridge.", "hashes": [right]},
            ],
        }
        decisions = {
            item["id"]: {
                "id": item["id"],
                "action": "choose",
                "selectedText": "Hazes on bridge.",
            }
        }
        recommendation = {
            "id": item["id"],
            "previousSelectedText": "Hazes on bridge.",
            "correctedText": "Haze is on the bridge.",
            "reason": "Sibling callout grammar.",
            "confidence": "high",
            "reviewFile": "judgment-corrections-01.json",
        }

        targets, corrections = build_targets([item], decisions, [recommendation])
        updated, changes = apply_document(
            {
                "schemaVersion": 3,
                "filename": item["filename"],
                "revisions": [
                    {"sha256": [left, right], "text": "Hazes on bridge.", "source": "generated"}
                ],
            },
            item["path"],
            targets,
        )

        self.assertEqual(len(corrections), 1)
        self.assertEqual(len(changes), 2)
        self.assertEqual(
            updated["revisions"],
            [{"sha256": [left, right], "text": "Haze is on the bridge.", "source": "manual"}],
        )

    def test_two_audit_rejections_remove_recommendation(self) -> None:
        correction = {"id": "line", "correctedText": "Maybe."}
        objections = {
            "line": [
                {"recommendedAction": "reject", "reason": "Unsupported."},
                {"recommendedAction": "reject", "reason": "No sibling evidence."},
            ]
        }

        accepted, rejected = reconcile_judgment_corrections([correction], objections)

        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 1)


if __name__ == "__main__":
    unittest.main()
