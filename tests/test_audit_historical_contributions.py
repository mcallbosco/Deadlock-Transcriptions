from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_historical_contributions import audit_historical  # noqa: E402


def legacy_document(filename: str, text: str) -> dict[str, object]:
    return {
        "voiceline_id": filename.removesuffix(".mp3"),
        "timestamp": "2026-01-01T00:00:00",
        "segments": [{"start": 0, "end": 1, "text": text, "part": 1}],
    }


def revision(text: str, source: str, sha: str) -> dict[str, str]:
    value = {"sha256": sha, "text": text, "source": source}
    if source == "generated":
        value["model"] = "test-model"
    return value


def target_document(filename: str, revisions: list[dict[str, str]]) -> dict[str, object]:
    return {"schemaVersion": 2, "filename": filename, "revisions": revisions}


class HistoricalAuditIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.git("init", "-b", "old")
        self.git("config", "user.name", "Migration Operator")
        self.git("config", "user.email", "operator@example.com")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if result.returncode:
            self.fail(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout.strip()

    def write_json(self, relative: str, value: object) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def commit(self, message: str, name: str, email: str, date: str) -> str:
        self.git("add", ".")
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_AUTHOR_NAME": name,
                "GIT_AUTHOR_EMAIL": email,
                "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_NAME": "Migration Operator",
                "GIT_COMMITTER_EMAIL": "operator@example.com",
                "GIT_COMMITTER_DATE": date,
            }
        )
        self.git("commit", "-m", message, env=environment)
        return self.git("rev-parse", "HEAD")

    def test_deleted_corrections_require_a_unique_generated_revision(self) -> None:
        names = ("replay", "marked", "official", "ambiguous")
        for name in names:
            self.write_json(
                f"data/{name}.mp3.json", legacy_document(f"{name}.mp3", f"Wrong {name}")
            )
        self.commit("Initial transcripts", "Owner", "owner@example.com", "2026-01-01T00:00:00Z")

        for name in names:
            self.write_json(
                f"data/{name}.mp3.json", legacy_document(f"{name}.mp3", f"Correct {name}")
            )
        alice_commit = self.commit(
            "Correct transcripts",
            "Alice Contributor",
            "alice@users.noreply.github.com",
            "2026-01-02T00:00:00Z",
        )

        for name in names:
            (self.repo / f"data/{name}.mp3.json").unlink()
        legacy_commit = self.commit(
            "Remove obsolete transcripts", "Owner", "owner@example.com", "2026-01-03T00:00:00Z"
        )

        self.git("switch", "--orphan", "target")
        self.write_json(
            "transcripts/hero/replay.mp3.json",
            target_document("hero/replay.mp3", [revision("Wrong replay", "generated", "1" * 64)]),
        )
        self.write_json(
            "transcripts/hero/marked.mp3.json",
            target_document("hero/marked.mp3", [revision("Correct marked", "generated", "2" * 64)]),
        )
        self.write_json(
            "transcripts/hero/official.mp3.json",
            target_document("hero/official.mp3", [revision("Wrong official", "official", "3" * 64)]),
        )
        self.write_json(
            "transcripts/hero/ambiguous.mp3.json",
            target_document(
                "hero/ambiguous.mp3",
                [
                    revision("Wrong ambiguous", "generated", "4" * 64),
                    revision("Wrong ambiguous", "generated", "5" * 64),
                ],
            ),
        )
        target_commit = self.commit(
            "Import v2 transcripts", "Owner", "owner@example.com", "2026-01-04T00:00:00Z"
        )

        report = audit_historical(
            repo=self.repo,
            legacy_ref=legacy_commit,
            target_ref=target_commit,
            legacy_prefix="data",
            target_prefix="transcripts",
            bulk_threshold=500,
            official_commits=set(),
        )
        records = {record["legacyPath"]: record for record in report["records"]}

        replay = records["data/replay.mp3.json"]
        self.assertEqual(replay["status"], "candidate_replay")
        self.assertEqual(replay["replayEvents"][0]["legacyCommit"], alice_commit)
        self.assertEqual(replay["replayEvents"][0]["author"]["name"], "Alice Contributor")
        self.assertEqual(replay["selectedTarget"]["sha256"], "1" * 64)

        marked = records["data/marked.mp3.json"]
        self.assertEqual(marked["status"], "candidate_mark_manual")
        self.assertEqual(marked["attributionEvent"]["author"]["email"], "alice@users.noreply.github.com")

        official = records["data/official.mp3.json"]
        self.assertEqual(official["status"], "protected_official")
        self.assertEqual(official["targetMatches"][0]["proposedAction"], "protected")

        ambiguous = records["data/ambiguous.mp3.json"]
        self.assertEqual(ambiguous["status"], "ambiguous_revision")
        self.assertNotIn("selectedTarget", ambiguous)
        self.assertEqual(report["summary"]["candidateActionsOnDeletedPaths"], 2)
        self.assertFalse(report["policy"]["officialRevisionsMutable"])


if __name__ == "__main__":
    unittest.main()
