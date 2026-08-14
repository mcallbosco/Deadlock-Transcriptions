from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_current_contributions import (  # noqa: E402
    AuditError,
    apply_changes,
    candidate_action,
    plan_changes,
)


class ApplyCurrentContributionTests(unittest.TestCase):
    def test_plan_and_apply_change_only_the_selected_nonofficial_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/hero/line.mp3.json"
            path.parent.mkdir(parents=True)
            document = {
                "schemaVersion": 3,
                "filename": "hero/line.mp3",
                "revisions": [
                    {
                        "sha256": ["1" * 64],
                        "text": "Wrong line",
                        "source": "generated",
                        "model": "test-model",
                    },
                    {"sha256": ["2" * 64], "text": "Official line", "source": "official"},
                ],
            }
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            report = {
                "mode": "audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "officialRevisionsMutable": False,
                    "uniqueNonOfficialRevisionRequired": True,
                },
                "records": [
                    {
                        "status": "candidate_manual",
                        "legacyPath": "data/line.mp3.json",
                        "legacyCommit": "a" * 40,
                        "author": {
                            "name": "Alice",
                            "email": "alice@example.com",
                            "date": "2026-01-01T00:00:00Z",
                        },
                        "beforeFullText": "Wrong line",
                        "currentFullText": "Correct line",
                        "targetMatches": [
                            {
                                "path": "transcripts/hero/line.mp3.json",
                                "sha256": "1" * 64,
                                "source": "generated",
                                "proposedAction": "replace_text_and_mark_manual",
                            }
                        ],
                    }
                ],
            }

            changes = plan_changes(repo, report)
            self.assertEqual(len(changes), 1)
            apply_changes(changes)

            updated = json.loads(path.read_text(encoding="utf-8"))
            generated, official = updated["revisions"]
            self.assertEqual(generated["text"], "Correct line")
            self.assertEqual(generated["source"], "manual")
            self.assertNotIn("model", generated)
            self.assertEqual(official, document["revisions"][1])

    def test_candidate_action_rejects_multiple_revisions(self) -> None:
        record = {
            "legacyPath": "data/line.mp3.json",
            "targetMatches": [
                {"source": "generated", "proposedAction": "mark_manual"},
                {"source": "generated", "proposedAction": "mark_manual"},
            ],
        }
        with self.assertRaises(AuditError):
            candidate_action(record)

    def test_plan_rejects_different_hashes_in_the_same_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/hero/line.mp3.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 3,
                        "filename": "hero/line.mp3",
                        "revisions": [
                            {
                                "sha256": ["1" * 64, "3" * 64],
                                "text": "Wrong line",
                                "source": "generated",
                                "model": "test-model",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            records = []
            for index, digest in enumerate(("1" * 64, "3" * 64)):
                records.append(
                    {
                        "status": "candidate_manual",
                        "legacyPath": f"data/line-{index}.mp3.json",
                        "legacyCommit": str(index + 1) * 40,
                        "author": {"name": "Alice", "email": "alice@example.com"},
                        "beforeFullText": "Wrong line",
                        "currentFullText": "Correct line",
                        "targetMatches": [
                            {
                                "path": "transcripts/hero/line.mp3.json",
                                "sha256": digest,
                                "source": "generated",
                                "proposedAction": "replace_text_and_mark_manual",
                            }
                        ],
                    }
                )
            report = {
                "mode": "audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "officialRevisionsMutable": False,
                    "uniqueNonOfficialRevisionRequired": True,
                },
                "records": records,
            }
            with self.assertRaisesRegex(AuditError, "same transcript group"):
                plan_changes(repo, report)


if __name__ == "__main__":
    unittest.main()
