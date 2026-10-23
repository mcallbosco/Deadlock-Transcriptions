from __future__ import annotations

import unittest

from tools.apply_phonetic_review_export import plan
from tools.reconcile_correlated_punctuation import ReconciliationError


def side(filename: str, digest: str, text: str) -> dict[str, object]:
    return {
        "filename": filename,
        "sha256": [digest * 64],
        "text": text,
        "source": "generated",
        "model": "test-transcriber",
    }


def document(digest: str, text: str) -> dict[str, object]:
    return {
        "revisions": [
            {
                "sha256": [digest * 64],
                "text": text,
                "source": "generated",
                "model": "test-transcriber",
            }
        ]
    }


class ApplyPhoneticReviewExportTests(unittest.TestCase):
    def test_review_cannot_merge_cross_file_groups_with_conflicting_tags(self):
        candidate = {"id": "merge", "left": side("a.mp3", "a", "Alpha"), "right": side("b.mp3", "b", "Alfa")}
        documents = {"a.mp3": document("a", "Alpha"), "b.mp3": document("b", "Alfa")}
        documents["a.mp3"]["revisions"][0]["tags"] = ["insults"]
        review = {"schemaVersion": 1, "judgments": {"merge": {"decision": "left", "selectedText": "Alpha", "updatedAt": "2026-01-01T00:00:00Z"}}}
        with self.assertRaisesRegex(ReconciliationError, "Conflicting content tags"):
            plan(documents, [candidate], {"merge": candidate}, review, correlations=[list(documents)])
        self.assertEqual(documents["b.mp3"]["revisions"][0]["text"], "Alfa")

    def test_latest_choice_resolves_transitive_component(self) -> None:
        candidates = [
            {"id": "first", "left": side("a.mp3", "a", "Alpha"), "right": side("b.mp3", "b", "Alfa")},
            {"id": "later", "left": side("b.mp3", "b", "Alfa"), "right": side("c.mp3", "c", "Alpha corrected")},
        ]
        documents = {
            "a.mp3": document("a", "Alpha"),
            "b.mp3": document("b", "Alfa"),
            "c.mp3": document("c", "Alpha corrected"),
        }
        review = {
            "schemaVersion": 1,
            "judgments": {
                "first": {"decision": "left", "selectedText": "Alpha", "updatedAt": "2026-01-01T00:00:00Z"},
                "later": {"decision": "right", "selectedText": "Alpha corrected", "updatedAt": "2026-01-01T00:01:00Z"},
            },
        }

        changed, result = plan(documents, candidates, {item["id"]: item for item in candidates}, review, correlations=[list(documents)])

        self.assertEqual(result["statistics"]["mergedComponents"], 1)
        self.assertEqual(result["statistics"]["approvedCandidates"], 2)
        updated = {**documents, **changed}
        for filename in documents:
            self.assertEqual(updated[filename]["revisions"][0]["text"], "Alpha corrected")

    def test_structured_correction_overrides_selected_machine_text(self) -> None:
        candidates = [
            {"id": "corrected", "left": side("a.mp3", "a", "wrong words"), "right": side("b.mp3", "b", "worse words")},
        ]
        documents = {"a.mp3": document("a", "wrong words"), "b.mp3": document("b", "worse words")}
        review = {
            "schemaVersion": 1,
            "judgments": {
                "corrected": {"decision": "left", "selectedText": "wrong words", "updatedAt": "2026-01-01T00:00:00Z"},
            },
            "corrections": {"corrected": "right words"},
        }

        changed, _result = plan(documents, candidates, {"corrected": candidates[0]}, review, correlations=[list(documents)])

        self.assertEqual(changed["a.mp3"]["revisions"][0]["text"], "right words")
        self.assertEqual(changed["b.mp3"]["revisions"][0]["text"], "right words")

    def test_keep_separate_restores_a_previously_unified_pair(self) -> None:
        candidates = [
            {"id": "separate", "left": side("a.mp3", "a", "Inferno"), "right": side("b.mp3", "b", "Infernus")},
        ]
        documents = {"a.mp3": document("a", "Infernus"), "b.mp3": document("b", "Infernus")}
        review = {
            "schemaVersion": 1,
            "judgments": {"separate": {"decision": "separate", "updatedAt": "2026-01-01T00:00:00Z"}},
        }

        changed, result = plan(documents, candidates, {"separate": candidates[0]}, review, correlations=[list(documents)])

        self.assertEqual(result["restoredSeparateCandidateIds"], ["separate"])
        self.assertEqual(changed["a.mp3"]["revisions"][0]["text"], "Inferno")
        self.assertNotIn("b.mp3", changed)


if __name__ == "__main__":
    unittest.main()
