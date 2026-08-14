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


if __name__ == "__main__":
    unittest.main()
