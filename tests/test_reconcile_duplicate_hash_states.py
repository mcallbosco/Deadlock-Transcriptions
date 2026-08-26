import json
import tempfile
import unittest
from pathlib import Path

from tools.reconcile_duplicate_hash_states import (
    apply_reconciliation,
    conflicting_relative_paths,
    load_documents,
)


SHA = "a" * 64
SIBLING = "b" * 64


class ReconcileDuplicateHashStatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.transcripts = self.repo / "transcripts"
        self.transcripts.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, *, text, source, hashes=None, model=None):
        path = self.transcripts / name
        revision = {
            "sha256": hashes or [SHA],
            "text": text,
            "source": source,
        }
        if model:
            revision["model"] = model
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 3,
                    "filename": name.removesuffix(".json"),
                    "revisions": [revision],
                }
            ),
            encoding="utf-8",
        )
        return path

    def revision(self, path):
        return json.loads(path.read_text(encoding="utf-8"))["revisions"]

    def test_official_text_and_provenance_win(self):
        generated = self.write(
            "generated.json", text="guess", source="generated", model="model"
        )
        official = self.write("official.json", text="canonical", source="official")

        report = apply_reconciliation(
            self.transcripts,
            {
                "transcripts/generated.json": 200,
                "transcripts/official.json": 100,
            },
            apply=True,
        )

        self.assertEqual(report["statistics"]["winnerSources"], {"official": 1})
        self.assertEqual(
            self.revision(generated)[0],
                {
                    "sha256": [SHA],
                    "text": "canonical",
                    "source": "official",
            },
        )
        self.assertEqual(self.revision(official)[0]["source"], "official")

    def test_manual_wins_over_newer_generated(self):
        generated = self.write("generated.json", text="new guess", source="generated")
        self.write("manual.json", text="reviewed", source="manual")

        apply_reconciliation(
            self.transcripts,
            {
                "transcripts/generated.json": 200,
                "transcripts/manual.json": 100,
            },
            apply=True,
        )

        self.assertEqual(self.revision(generated)[0]["text"], "reviewed")
        self.assertEqual(self.revision(generated)[0]["source"], "manual")

    def test_most_recent_file_wins_within_same_source(self):
        older = self.write("older.json", text="older", source="generated")
        newer = self.write("newer.json", text="newer", source="generated")

        apply_reconciliation(
            self.transcripts,
            {"transcripts/older.json": 100, "transcripts/newer.json": 200},
            apply=True,
        )

        self.assertEqual(self.revision(older)[0]["text"], "newer")
        self.assertEqual(self.revision(newer)[0]["text"], "newer")

    def test_splits_group_when_hashes_choose_different_text(self):
        grouped = self.write(
            "grouped.json",
            text="old",
            source="generated",
            hashes=[SHA, SIBLING],
            model="model",
        )
        self.write("winner.json", text="new", source="manual", hashes=[SHA])

        report = apply_reconciliation(
            self.transcripts,
            {
                "transcripts/grouped.json": 100,
                "transcripts/winner.json": 200,
            },
            apply=True,
        )

        self.assertEqual(report["statistics"]["splitRevisionGroups"], 1)
        self.assertEqual(
            self.revision(grouped),
            [
                {
                    "sha256": [SHA],
                    "text": "new",
                    "source": "manual",
                },
                {
                    "sha256": [SIBLING],
                    "text": "old",
                    "source": "generated",
                    "model": "model",
                },
            ],
        )

    def test_recency_scan_is_scoped_to_conflicting_paths(self):
        self.write("same-a.json", text="same", source="generated", hashes=[SIBLING])
        self.write("same-b.json", text="same", source="manual", hashes=[SIBLING])
        self.write("conflict-a.json", text="old", source="generated")
        self.write("conflict-b.json", text="new", source="manual")

        paths = conflicting_relative_paths(load_documents(self.transcripts), self.repo)

        self.assertEqual(
            paths,
            {"transcripts/conflict-a.json", "transcripts/conflict-b.json"},
        )


if __name__ == "__main__":
    unittest.main()
