from __future__ import annotations

import unittest

from tools.apply_phonetic_lineage_merges import plan
from tools.audit_phonetic_lineage_merges import (
    build_lineages,
    candidate_tier,
    phrase_tokens,
    similarity,
)


def revision(digest: str, text: str, source: str = "generated") -> dict[str, object]:
    value: dict[str, object] = {"sha256": [digest * 64], "text": text, "source": source}
    if source == "generated":
        value["model"] = "test-transcriber"
    return value


class PhoneticLineageMergeTests(unittest.TestCase):
    def test_normalizes_contractions_and_colloquial_pronouns(self) -> None:
        self.assertEqual(phrase_tokens("I'll curse 'em!"), phrase_tokens("I will curse them"))

    def test_separates_strong_and_lower_confidence_examples(self) -> None:
        self.assertEqual(
            candidate_tier(similarity("I'll curse 'em!", "I'll curse them!"))[0],
            "strong",
        )
        self.assertEqual(
            candidate_tier(similarity("Cursing 'em!", "Curse them!"))[0],
            "lower-confidence",
        )

    def test_shared_hash_and_manual_edges_are_transitive(self) -> None:
        documents = {
            "hero/one.mp3": {"revisions": [revision("1", "One")]},
            "hero/two.mp3": {"revisions": [revision("1", "Two")]},
            "hero/three.mp3": {"revisions": [revision("3", "Three")]},
        }
        lineages = build_lineages(
            documents,
            [["hero/two.mp3", "hero/three.mp3"]],
        )
        self.assertEqual(
            next(value for value in lineages.values() if "hero/one.mp3" in value),
            ["hero/one.mp3", "hero/three.mp3", "hero/two.mp3"],
        )

    def test_apply_uses_source_authority_and_reviewed_generated_choice(self) -> None:
        documents = {
            "hero/old.mp3": {
                "revisions": [revision("1", "I'll curse them!")],
            },
            "hero/new.mp3": {
                "revisions": [revision("2", "I'll curse 'em!", "official")],
            },
            "hero/left.mp3": {
                "revisions": [revision("3", "Lives are at stake.")],
            },
            "hero/right.mp3": {
                "revisions": [revision("4", "Lines are at stake.")],
            },
        }
        candidates = [
            {
                "id": "authority",
                "left": {
                    "filename": "hero/old.mp3",
                    "revisionIndex": 0,
                    "text": "I'll curse them!",
                    "source": "generated",
                    "sha256": ["1" * 64],
                },
                "right": {
                    "filename": "hero/new.mp3",
                    "revisionIndex": 0,
                    "text": "I'll curse 'em!",
                    "source": "official",
                    "sha256": ["2" * 64],
                },
            },
            {
                "id": "reviewed",
                "left": {
                    "filename": "hero/left.mp3",
                    "revisionIndex": 0,
                    "text": "Lives are at stake.",
                    "source": "generated",
                    "model": "test-transcriber",
                    "sha256": ["3" * 64],
                },
                "right": {
                    "filename": "hero/right.mp3",
                    "revisionIndex": 0,
                    "text": "Lines are at stake.",
                    "source": "generated",
                    "model": "test-transcriber",
                    "sha256": ["4" * 64],
                },
            },
        ]
        changed, result = plan(
            documents,
            candidates,
            {"reviewed": "Lives are at stake."},
            set(),
        )
        self.assertEqual(result["statistics"]["targetRecordingHashes"], 4)
        self.assertEqual(changed["hero/old.mp3"]["revisions"][0]["source"], "official")
        self.assertEqual(changed["hero/old.mp3"]["revisions"][0]["text"], "I'll curse 'em!")
        self.assertEqual(changed["hero/right.mp3"]["revisions"][0]["source"], "generated")
        self.assertEqual(changed["hero/right.mp3"]["revisions"][0]["model"], "test-transcriber")
        self.assertEqual(changed["hero/right.mp3"]["revisions"][0]["text"], "Lives are at stake.")

        updated_documents = {**documents, **changed}
        repeated, repeated_result = plan(
            updated_documents,
            candidates,
            {"reviewed": "Lives are at stake."},
            set(),
        )
        self.assertEqual(repeated, {})
        self.assertEqual(repeated_result["statistics"]["changedFiles"], 0)


if __name__ == "__main__":
    unittest.main()
