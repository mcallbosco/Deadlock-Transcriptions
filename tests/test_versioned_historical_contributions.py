from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_versioned_historical_contributions import (  # noqa: E402
    apply_changes,
    plan_changes,
)
from audit_latest_version_contributions import build_manifest_index  # noqa: E402
from audit_versioned_historical_contributions import classify_records  # noqa: E402


def event(commit: str, date: str, before: str, after: str) -> dict[str, object]:
    return {
        "legacyCommit": commit,
        "legacySubject": "Correct line",
        "author": {"name": "Alice", "email": "alice@example.com", "date": date},
        "beforeFullText": before,
        "afterFullText": after,
        "changedSegments": [{"index": 0, "before": before, "after": after}],
    }


def epoch(name: str, events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "epochId": f"data/{name}.mp3.json#0",
        "legacyPath": f"data/{name}.mp3.json",
        "legacyPathDeleted": False,
        "initialText": events[0]["beforeFullText"],
        "finalText": events[-1]["afterFullText"],
        "events": events,
    }


def target(name: str, text: str, source: str, sha: str) -> dict[str, object]:
    revision: dict[str, object] = {"sha256": sha, "text": text, "source": source}
    if source == "generated":
        revision["model"] = "test-model"
    return {
        "path": f"transcripts/hero/{name}.mp3.json",
        "filename": f"hero/{name}.mp3",
        "revisions": [revision],
    }


class VersionedHistoricalAuditTests(unittest.TestCase):
    def test_release_window_manifest_hash_and_exact_state_are_all_required(self) -> None:
        names = ("replay", "marked", "official", "diverged", "outside", "boundary")
        hashes = {name: str(index) * 64 for index, name in enumerate(names, 1)}
        manifest = [
            {
                "filename": f"hero/{name}.mp3",
                "audioKey": f"sha256/{sha[:2]}/{sha}.mp3",
            }
            for name, sha in hashes.items()
        ]
        manifest_index, _ = build_manifest_index(json.dumps(manifest).encode())
        historical = {
            "records": [
                epoch("replay", [event("a" * 40, "2025-08-22T12:00:00-04:00", "Wrong", "Right")]),
                epoch("marked", [event("b" * 40, "2025-09-01T12:00:00-04:00", "Bad", "Good")]),
                epoch("official", [event("c" * 40, "2025-10-01T12:00:00-04:00", "No", "Yes")]),
                epoch("diverged", [event("d" * 40, "2025-11-01T12:00:00-04:00", "Old", "New")]),
                epoch("outside", [event("e" * 40, "2026-02-01T12:00:00-05:00", "A", "B")]),
                epoch("boundary", [event("f" * 40, "2025-08-18T23:00:00-04:00", "A", "B")]),
            ]
        }
        target_index = {
            "replay.mp3.json": [target("replay", "Wrong", "generated", hashes["replay"])],
            "marked.mp3.json": [target("marked", "Good", "generated", hashes["marked"])],
            "official.mp3.json": [target("official", "No", "official", hashes["official"])],
            "diverged.mp3.json": [target("diverged", "Different", "generated", hashes["diverged"])],
            "outside.mp3.json": [target("outside", "A", "generated", hashes["outside"])],
            "boundary.mp3.json": [target("boundary", "A", "generated", hashes["boundary"])],
        }
        release = {
            "id": "six-hero-update",
            "activeFrom": date(2025, 8, 18),
            "activeUntilExclusive": date(2026, 1, 22),
        }

        records = classify_records(historical, target_index, manifest_index, release)
        statuses = {record["legacyPath"]: record["status"] for record in records}

        self.assertEqual(statuses["data/replay.mp3.json"], "candidate_replay")
        self.assertEqual(statuses["data/marked.mp3.json"], "candidate_mark_manual")
        self.assertEqual(statuses["data/official.mp3.json"], "protected_official")
        self.assertEqual(statuses["data/diverged.mp3.json"], "review_version_text_diverged")
        self.assertEqual(statuses["data/outside.mp3.json"], "outside_selected_version")
        self.assertEqual(statuses["data/boundary.mp3.json"], "release_boundary_date_review")


class VersionedHistoricalApplyTests(unittest.TestCase):
    def test_only_audited_generated_revision_is_changed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/hero/line.mp3.json"
            path.parent.mkdir(parents=True)
            selected_sha = "1" * 64
            official_sha = "2" * 64
            document = {
                "schemaVersion": 2,
                "filename": "hero/line.mp3",
                "revisions": [
                    {
                        "sha256": selected_sha,
                        "text": "Wrong line",
                        "source": "generated",
                        "model": "test-model",
                    },
                    {
                        "sha256": official_sha,
                        "text": "Official line",
                        "source": "official",
                    },
                ],
            }
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            correction = event(
                "a" * 40,
                "2025-08-22T12:00:00-04:00",
                "Wrong line",
                "Correct line",
            )
            report = {
                "mode": "versioned-historical-audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "officialRevisionsMutable": False,
                    "eligibleTargetSources": ["generated"],
                    "selectedReleaseRequired": True,
                    "crossVersionReplayAllowed": False,
                    "uniqueVersionHashRequired": True,
                    "uniqueHistoryEpochRequired": True,
                    "exactTextAnchorRequired": True,
                    "fuzzyMatchingMayAutoApply": False,
                },
                "records": [
                    {
                        "status": "candidate_replay",
                        "epochId": "data/line.mp3.json#0",
                        "finalText": "Correct line",
                        "replayEvents": [correction],
                        "selectedTarget": {
                            "path": "transcripts/hero/line.mp3.json",
                            "sha256": selected_sha,
                            "source": "generated",
                            "originalText": "Wrong line",
                            "proposedAction": "replay_and_mark_manual",
                        },
                    }
                ],
            }

            changes = plan_changes(repo, report)
            apply_changes(changes)
            updated = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(updated["revisions"][0]["text"], "Correct line")
            self.assertEqual(updated["revisions"][0]["source"], "manual")
            self.assertNotIn("model", updated["revisions"][0])
            self.assertEqual(updated["revisions"][1], document["revisions"][1])


if __name__ == "__main__":
    unittest.main()
