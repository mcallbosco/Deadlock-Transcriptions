from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_latest_version_contributions import (  # noqa: E402
    apply_changes,
    plan_changes,
)
from audit_latest_version_contributions import (  # noqa: E402
    build_manifest_index,
    classify_records,
)


def base_record(name: str, before: str, current: str) -> dict[str, object]:
    return {
        "status": "candidate_manual",
        "legacyPath": f"data/{name}.mp3.json",
        "legacyCommit": name[0] * 40,
        "legacySubject": "Correct transcript",
        "author": {
            "name": "Alice",
            "email": "alice@example.com",
            "date": "2026-01-01T00:00:00Z",
        },
        "beforeFullText": before,
        "currentFullText": current,
        "changedSegments": [{"index": 0, "before": before, "after": current}],
        "targetMatches": [
            {
                "path": f"transcripts/hero/{name}.mp3.json",
                "filename": f"hero/{name}.mp3",
                "sha256": "f" * 64,
                "source": "generated",
                "proposedAction": "mark_manual",
            }
        ],
    }


def target_document(name: str, text: str, source: str, sha256: str) -> dict[str, object]:
    revision: dict[str, object] = {"sha256": sha256, "text": text, "source": source}
    if source == "generated":
        revision["model"] = "test-model"
    return {"schemaVersion": 2, "filename": f"hero/{name}.mp3", "revisions": [revision]}


class LatestVersionAuditTests(unittest.TestCase):
    def test_only_exact_latest_states_are_candidates(self) -> None:
        hashes = {name: str(index) * 64 for index, name in enumerate(("before", "current", "diverged", "official"), 1)}
        manifest = {
            "hero": {
                "category": [
                    {
                        "filename": f"hero/{name}.mp3",
                        "audioKey": f"sha256/{sha[:2]}/{sha}.mp3",
                    }
                    for name, sha in hashes.items()
                ]
            }
        }
        index, stats = build_manifest_index(json.dumps(manifest).encode())
        current_report = {
            "records": [
                base_record("before", "Wrong before", "Correct before"),
                base_record("current", "Wrong current", "Correct current"),
                base_record("diverged", "Wrong divergent", "Correct divergent"),
                base_record("official", "Wrong official", "Correct official"),
                base_record("absent", "Wrong absent", "Correct absent"),
            ]
        }
        documents = {
            "transcripts/hero/before.mp3.json": target_document(
                "before", "Wrong before", "generated", hashes["before"]
            ),
            "transcripts/hero/current.mp3.json": target_document(
                "current", "Correct current", "generated", hashes["current"]
            ),
            "transcripts/hero/diverged.mp3.json": target_document(
                "diverged", "Different recording", "generated", hashes["diverged"]
            ),
            "transcripts/hero/official.mp3.json": target_document(
                "official", "Wrong official", "official", hashes["official"]
            ),
        }

        records = classify_records(current_report, documents, index)
        by_path = {value["legacyPath"]: value for value in records}

        self.assertEqual(stats["conflictingFilenames"], 0)
        self.assertEqual(by_path["data/before.mp3.json"]["status"], "candidate_latest_manual")
        self.assertEqual(
            by_path["data/before.mp3.json"]["selectedTarget"]["proposedAction"],
            "replace_text_and_mark_manual",
        )
        self.assertEqual(by_path["data/current.mp3.json"]["status"], "candidate_latest_manual")
        self.assertEqual(by_path["data/diverged.mp3.json"]["status"], "review_latest_text_diverged")
        self.assertEqual(by_path["data/official.mp3.json"]["status"], "protected_latest_official")
        self.assertEqual(
            by_path["data/official.mp3.json"]["selectedTarget"]["proposedAction"], "protected"
        )
        self.assertEqual(by_path["data/absent.mp3.json"]["status"], "not_in_version_manifest")


class LatestVersionApplyTests(unittest.TestCase):
    def test_apply_changes_only_selected_latest_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/hero/line.mp3.json"
            path.parent.mkdir(parents=True)
            latest_sha = "1" * 64
            old_sha = "2" * 64
            document = {
                "schemaVersion": 2,
                "filename": "hero/line.mp3",
                "revisions": [
                    {"sha256": old_sha, "text": "Old recording", "source": "generated", "model": "old"},
                    {
                        "sha256": latest_sha,
                        "text": "Wrong line",
                        "source": "generated",
                        "model": "latest",
                    },
                ],
            }
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            report = {
                "mode": "latest-version-audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "officialRevisionsMutable": False,
                    "latestManifestHashRequired": True,
                    "divergentLatestTextMayAutoApply": False,
                },
                "records": [
                    {
                        "status": "candidate_latest_manual",
                        "legacyCommit": "a" * 40,
                        "author": {"name": "Alice", "email": "alice@example.com"},
                        "currentFullText": "Correct line",
                        "selectedTarget": {
                            "path": "transcripts/hero/line.mp3.json",
                            "sha256": latest_sha,
                            "source": "generated",
                            "originalText": "Wrong line",
                            "proposedAction": "replace_text_and_mark_manual",
                        },
                    }
                ],
            }

            changes = plan_changes(repo, report)
            apply_changes(changes)
            updated = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(updated["revisions"][0], document["revisions"][0])
            self.assertEqual(updated["revisions"][1]["text"], "Correct line")
            self.assertEqual(updated["revisions"][1]["source"], "manual")
            self.assertNotIn("model", updated["revisions"][1])


if __name__ == "__main__":
    unittest.main()
