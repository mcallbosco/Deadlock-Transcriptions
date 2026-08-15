import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.apply_ognb_transcript_review import ReviewError, apply_review


SHA = "a" * 64
FIELDS = [
    "sha256",
    "current_transcript",
    "recommended_transcript",
    "decision",
    "needs_manual_review",
    "apply_recommended",
]


class ApplyOgnbTranscriptReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.transcripts = self.root / "transcripts"
        self.transcripts.mkdir()
        self.review = self.root / "review.csv"

    def tearDown(self):
        self.temp.cleanup()

    def write_transcript(self, name="line.json", text="bad", source="generated"):
        path = self.transcripts / name
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 3,
                    "filename": name.removesuffix(".json"),
                    "revisions": [
                        {
                            "sha256": [SHA],
                            "text": text,
                            "source": source,
                            "model": "test-model",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_review(self, **overrides):
        row = {
            "sha256": SHA,
            "current_transcript": "bad",
            "recommended_transcript": "good",
            "decision": "use_legacy",
            "needs_manual_review": "false",
            "apply_recommended": "true",
            **overrides,
        }
        with self.review.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(row)

    def test_applies_review_to_every_filename_alias(self):
        first = self.write_transcript("first.json")
        second = self.write_transcript("second.json")
        self.write_review()

        statistics = apply_review(self.transcripts, self.review, apply=True)

        self.assertEqual(statistics["changedFiles"], 2)
        self.assertEqual(statistics["duplicateFilenameAliases"], 1)
        for path in (first, second):
            revision = json.loads(path.read_text(encoding="utf-8"))["revisions"][0]
            self.assertEqual(
                revision,
                {
                    "sha256": [SHA],
                    "text": "good",
                    "source": "generated",
                    "model": "test-model",
                },
            )

    def test_rejects_stale_current_transcript(self):
        self.write_transcript(text="changed")
        self.write_review()

        with self.assertRaisesRegex(ReviewError, "no longer matches"):
            apply_review(self.transcripts, self.review, apply=False)

    def test_rejects_selected_manual_review_row(self):
        self.write_transcript()
        self.write_review(decision="manual_review", needs_manual_review="true")

        with self.assertRaisesRegex(ReviewError, "unresolved manual-review"):
            apply_review(self.transcripts, self.review, apply=False)


if __name__ == "__main__":
    unittest.main()
