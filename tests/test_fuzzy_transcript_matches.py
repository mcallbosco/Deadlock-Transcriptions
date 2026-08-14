from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_fuzzy_transcript_matches import (
    build_report,
    confidence_for_similarity,
    fuzzy_similarity,
    markdown_report,
)
from tools.apply_fuzzy_generated_official_matches import (
    excluded_official_terms,
    plan_document,
)
from tools.reconcile_fuzzy_official_aliases import (
    official_targets,
    reconcile_document,
)
from tools.review_generated_fuzzy_batch import apply_operation
from tools.reconcile_reviewed_fuzzy_aliases import reconcile_document as reconcile_reviewed_aliases


def revision(digest: str, text: str, source: str = "generated") -> dict[str, object]:
    return {"sha256": [digest * 64], "text": text, "source": source}


class FuzzyTranscriptMatchTests(unittest.TestCase):
    def test_confidence_thresholds_are_inclusive(self) -> None:
        self.assertEqual(confidence_for_similarity(0.95), "high")
        self.assertEqual(confidence_for_similarity(0.90), "medium")
        self.assertEqual(confidence_for_similarity(0.80), "low")
        self.assertIsNone(confidence_for_similarity(0.799999))

    def test_similarity_uses_v3_normalization(self) -> None:
        self.assertEqual(fuzzy_similarity("Lady Geist.", "LADY-GEIST?"), 1.0)
        self.assertGreater(
            fuzzy_similarity("Dynamo turned the tide.", "Dynamo turned the tides."),
            0.95,
        )

    def test_report_excludes_exact_matches_and_cross_file_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo = Path(temporary_directory)
            root = repo / "transcripts" / "hero"
            root.mkdir(parents=True)
            first = {
                "schemaVersion": 3,
                "filename": "hero_line_01.mp3",
                "revisions": [
                    revision("1", "Lady Geist."),
                    revision("2", "LADY-GEIST?", "manual"),
                    revision("3", "Dynamo turned the tide."),
                    revision("4", "Dynamo turned the tides.", "official"),
                ],
            }
            second = {
                "schemaVersion": 3,
                "filename": "hero_line_02.mp3",
                "revisions": [revision("5", "Dynamo turned the tide again.")],
            }
            (root / "hero_line_01.mp3.json").write_text(json.dumps(first))
            (root / "hero_line_02.mp3.json").write_text(json.dumps(second))

            report = build_report(repo)

        candidates = report["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["confidence"], "high")
        self.assertEqual(candidates[0]["left"]["revisionIndex"], 2)
        self.assertEqual(candidates[0]["right"]["revisionIndex"], 3)
        self.assertEqual(report["statistics"]["exactNormalizedPairsSkipped"], 1)
        self.assertTrue(report["advisoryOnly"])

    def test_markdown_labels_report_as_advisory(self) -> None:
        report = {
            "statistics": {"candidates": 0},
            "similarity": {
                "thresholds": {"high": 0.95, "medium": 0.9, "low": 0.8}
            },
            "candidatesBySourcePair": {},
            "candidatesByConfidenceAndSourcePair": {
                "high": {},
                "medium": {},
                "low": {},
            },
            "candidates": [],
        }
        rendered = markdown_report(report)
        self.assertIn("advisory only", rendered)
        self.assertIn("require human review", rendered)

    def test_generated_group_merges_into_one_official_group(self) -> None:
        document = {
            "schemaVersion": 3,
            "filename": "hero_line.mp3",
            "revisions": [
                revision("1", "Dynamo turned the tide.", "generated"),
                revision("2", "Dynamo turned the tides.", "official"),
            ],
        }

        updated, operations, exclusions = plan_document(
            document, "transcripts/hero/hero_line.mp3.json"
        )

        self.assertEqual(len(updated["revisions"]), 1)
        self.assertEqual(updated["revisions"][0]["source"], "official")
        self.assertEqual(updated["revisions"][0]["text"], "Dynamo turned the tides.")
        self.assertEqual(updated["revisions"][0]["sha256"], ["1" * 64, "2" * 64])
        self.assertEqual(len(operations), 1)
        self.assertEqual(exclusions, [])

    def test_hidden_king_and_archmother_official_groups_are_excluded(self) -> None:
        for term, official_text in (
            (
                "Hidden King",
                "Complete the ritual, and let the Hidden King guide you to victory.",
            ),
            (
                "Archmother",
                "Complete the ritual, and let the Archmother guide you to victory.",
            ),
        ):
            with self.subTest(term=term):
                document = {
                    "schemaVersion": 3,
                    "filename": "hero_line.mp3",
                    "revisions": [
                        revision(
                            "1",
                            "Complete the ritual, and let me guide you to victory.",
                            "generated",
                        ),
                        revision("2", official_text, "official"),
                    ],
                }

                updated, operations, exclusions = plan_document(
                    document, "transcripts/hero/hero_line.mp3.json"
                )

                self.assertEqual(updated, document)
                self.assertEqual(operations, [])
                self.assertEqual(len(exclusions), 1)
                self.assertEqual(exclusions[0]["matchedTerms"], [term])
                self.assertEqual(excluded_official_terms(official_text), [term])

    def test_alias_reconciliation_splits_only_the_matching_hash(self) -> None:
        source_path = "transcripts/hero/legacy_name.mp3.json"
        alias_path = "transcripts/hero/current_name.mp3.json"
        operations = [
            {
                "path": source_path,
                "officialText": "Holliday's missing",
                "resultingHashes": ["1" * 64],
            }
        ]
        targets = official_targets(operations)
        document = {
            "schemaVersion": 3,
            "filename": "current_name.mp3",
            "revisions": [
                {
                    "sha256": ["1" * 64, "2" * 64],
                    "text": "Holliday is missing.",
                    "source": "generated",
                    "model": "test-model",
                }
            ],
        }

        updated, reconciliations = reconcile_document(document, alias_path, targets)

        self.assertEqual(len(reconciliations), 1)
        self.assertEqual(len(updated["revisions"]), 2)
        by_source = {item["source"]: item for item in updated["revisions"]}
        self.assertEqual(by_source["official"]["sha256"], ["1" * 64])
        self.assertEqual(by_source["official"]["text"], "Holliday's missing")
        self.assertEqual(by_source["generated"]["sha256"], ["2" * 64])
        self.assertEqual(by_source["generated"]["model"], "test-model")

        source_document, source_changes = reconcile_document(
            document, source_path, targets
        )
        self.assertEqual(source_document, document)
        self.assertEqual(source_changes, [])

    def test_alias_targets_reject_conflicting_official_text(self) -> None:
        digest = "1" * 64
        with self.assertRaisesRegex(ValueError, "conflicting official merge targets"):
            official_targets(
                [
                    {
                        "path": "transcripts/hero/one.mp3.json",
                        "officialText": "First official text.",
                        "resultingHashes": [digest],
                    },
                    {
                        "path": "transcripts/hero/two.mp3.json",
                        "officialText": "Second official text.",
                        "resultingHashes": [digest],
                    },
                ]
            )

    def test_reviewed_generated_merge_preserves_unrelated_revisions_and_hashes(self) -> None:
        left = revision("1", "Flash grows stronger.")
        right = revision("2", "Lash grows stronger.")
        right["model"] = "test-model"
        official = revision("3", "The Hidden King calls to Lash.", "official")
        document = {
            "schemaVersion": 3,
            "filename": "patron_male_enemy_lash.mp3",
            "revisions": [left, right, official],
        }
        result_revision = dict(right)
        result_revision["sha256"] = ["1" * 64, "2" * 64]
        operation = {
            "path": "transcripts/patron_male_enemy_lash.mp3.json",
            "members": [
                {"revisionIndex": 0, "revision": left},
                {"revisionIndex": 1, "revision": right},
            ],
            "result": result_revision,
        }

        updated, status = apply_operation(document, operation)

        self.assertEqual(status, "update")
        self.assertEqual(updated["revisions"], [result_revision, official])

    def test_reviewed_generated_merge_requires_exact_member_state(self) -> None:
        left = revision("1", "Original generated text.")
        target = revision("2", "Target.")
        target["sha256"] = ["1" * 64, "2" * 64]
        document = {
            "schemaVersion": 3,
            "filename": "line.mp3",
            "revisions": [revision("1", "Changed generated text."), revision("2", "Target.")],
        }
        operation = {
            "path": "transcripts/line.mp3.json",
            "members": [
                {"revisionIndex": 0, "revision": left},
                {"revisionIndex": 1, "revision": revision("2", "Target.")},
            ],
            "result": target,
        }

        with self.assertRaisesRegex(ValueError, "not found exactly once"):
            apply_operation(document, operation)

    def test_reviewed_alias_reconciliation_splits_only_targeted_hashes(self) -> None:
        document = {
            "schemaVersion": 3,
            "filename": "legacy_alias.mp3",
            "revisions": [
                {
                    "sha256": ["1" * 64, "2" * 64],
                    "text": "Holiday is here.",
                    "source": "generated",
                    "model": "test-model",
                }
            ],
        }
        targets = {
            "1" * 64: {
                "text": "Holliday is here.",
                "source": "generated",
                "model": "test-model",
            }
        }

        updated, rewritten = reconcile_reviewed_aliases(document, targets)

        self.assertEqual(rewritten, 1)
        self.assertEqual(len(updated["revisions"]), 2)
        by_text = {item["text"]: item for item in updated["revisions"]}
        self.assertEqual(by_text["Holliday is here."]["sha256"], ["1" * 64])
        self.assertEqual(by_text["Holiday is here."]["sha256"], ["2" * 64])


if __name__ == "__main__":
    unittest.main()
