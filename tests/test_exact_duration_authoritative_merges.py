from __future__ import annotations

import unittest

from tools.apply_exact_duration_authoritative_merges import (
    plan_authoritative_merges,
    reconcile_document,
)


def digest(value: str) -> str:
    return value * 64


class ExactDurationAuthoritativeMergeTests(unittest.TestCase):
    def test_merges_only_the_generated_hash_with_an_exact_target_duration(self) -> None:
        generated_exact = digest("a")
        generated_other = digest("b")
        official = digest("c")
        document = {
            "schemaVersion": 3,
            "filename": "hero/line.mp3",
            "revisions": [
                {
                    "sha256": [generated_exact, generated_other],
                    "text": "Generated subtitle",
                    "source": "generated",
                    "model": "test",
                },
                {
                    "sha256": [official],
                    "text": "Official subtitle",
                    "source": "official",
                },
            ],
        }
        manifest_audio = {
            "hero/line.mp3": {
                generated_exact: {1000},
                generated_other: {1001},
                official: {1000},
            }
        }

        updated, operations, ambiguous = plan_authoritative_merges(
            document, "transcripts/hero/line.mp3.json", manifest_audio
        )

        self.assertEqual(ambiguous, 0)
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["movedGeneratedHashes"], [generated_exact])
        self.assertEqual(
            updated["revisions"],
            [
                {
                    "sha256": [generated_other],
                    "text": "Generated subtitle",
                    "source": "generated",
                    "model": "test",
                },
                {
                    "sha256": [generated_exact, official],
                    "text": "Official subtitle",
                    "source": "official",
                },
            ],
        )

    def test_reconciliation_updates_only_the_selected_hash(self) -> None:
        selected = digest("d")
        untouched = digest("e")
        document = {
            "schemaVersion": 3,
            "filename": "hero/alias.mp3",
            "revisions": [
                {
                    "sha256": [selected, untouched],
                    "text": "Generated subtitle",
                    "source": "generated",
                    "model": "test",
                }
            ],
        }

        updated, reconciliations = reconcile_document(
            document,
            "transcripts/hero/alias.mp3.json",
            {selected: {"text": "Official subtitle", "source": "official"}},
        )

        self.assertEqual(len(reconciliations), 1)
        self.assertEqual(reconciliations[0]["sha256"], selected)
        self.assertEqual(
            updated["revisions"],
            [
                {
                    "sha256": [untouched],
                    "text": "Generated subtitle",
                    "source": "generated",
                    "model": "test",
                },
                {
                    "sha256": [selected],
                    "text": "Official subtitle",
                    "source": "official",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
