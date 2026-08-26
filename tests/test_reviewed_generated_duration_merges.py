from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.apply_reviewed_generated_duration_merges import (
    apply_targets_to_document,
    reconcile_audit_objections,
    reconcile_target_conflicts,
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

    def test_novel_correction_becomes_manual_for_every_item_hash(self) -> None:
        left = digest("e")
        right = digest("f")
        item = {
            "id": "transcripts/hero/ping/line.mp3.json#1000",
            "path": "transcripts/hero/ping/line.mp3.json",
            "filename": "hero/ping/line.mp3",
            "options": [
                {"revisionIndex": 0, "text": "Ship's inmate.", "model": "test", "hashes": [left]},
                {"revisionIndex": 1, "text": "Shiv inmate.", "model": "test", "hashes": [right]},
            ],
        }
        decision = {
            "id": item["id"],
            "action": "correct",
            "selectedRevisionIndex": None,
            "selectedText": "Shiv's in mid.",
            "confidence": "high",
            "rationale": "Filename and sibling callouts establish the phrase.",
        }

        targets, reviewed, statistics = selected_targets([item], {item["id"]: decision})
        document = {
            "schemaVersion": 3,
            "filename": item["filename"],
            "revisions": [
                {"sha256": [left], "text": "Ship's inmate.", "source": "generated", "model": "test"},
                {"sha256": [right], "text": "Shiv inmate.", "source": "generated", "model": "test"},
            ],
        }
        updated, changes = apply_targets_to_document(document, item["path"], targets)

        self.assertEqual(reviewed, [])
        self.assertEqual(statistics["correct_high"], 1)
        self.assertEqual(len(changes), 2)
        self.assertEqual(
            updated["revisions"],
            [{"sha256": [left, right], "text": "Shiv's in mid.", "source": "manual"}],
        )

    def test_cross_audit_can_reject_or_replace_a_selection(self) -> None:
        decisions = {
            "reject-me": {"id": "reject-me", "action": "choose", "selectedText": "Wrong"},
            "replace-me": {"id": "replace-me", "action": "correct", "selectedText": "Maybe"},
        }
        objections = [
            {
                "id": "reject-me",
                "recommendedAction": "reject",
                "replacementText": None,
                "reason": "Unsupported template.",
            },
            {
                "id": "replace-me",
                "recommendedAction": "replace",
                "replacementText": "Right.",
                "reason": "Official sibling evidence.",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "audit-01-02.json").write_text(json.dumps(objections), encoding="utf-8")
            reconciled, loaded = reconcile_audit_objections(decisions, root)

        self.assertEqual(len(loaded), 2)
        self.assertEqual(reconciled["reject-me"]["action"], "review")
        self.assertEqual(reconciled["replace-me"]["action"], "correct")
        self.assertEqual(reconciled["replace-me"]["selectedText"], "Right.")

    def test_shared_hash_conflict_resolution_aligns_both_items(self) -> None:
        decisions = {
            "old-name": {"id": "old-name", "action": "correct", "selectedText": "Inferno."},
            "new-name": {"id": "new-name", "action": "correct", "selectedText": "Infernus."},
        }
        payload = {
            "schemaVersion": 1,
            "groups": [
                {
                    "itemIds": ["old-name", "new-name"],
                    "hashes": [digest("a")],
                    "action": "resolve",
                    "text": "Inferno.",
                    "reason": "Generated option preserves the spoken historical name.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-conflict-resolutions.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            reconciled, groups = reconcile_target_conflicts(decisions, root)

        self.assertEqual(len(groups), 1)
        self.assertEqual(reconciled["old-name"]["selectedText"], "Inferno.")
        self.assertEqual(reconciled["new-name"]["selectedText"], "Inferno.")


if __name__ == "__main__":
    unittest.main()
