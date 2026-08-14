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

from audit_legacy_contributions import (  # noqa: E402
    CommitRecord,
    RawChange,
    audit,
    classify_commit,
    compare_legacy_documents,
    render_markdown,
    safe_output_path,
    target_matches,
    AuditError,
)


def legacy_document(filename: str, text: str) -> dict[str, object]:
    return {
        "voiceline_id": filename.removesuffix(".mp3"),
        "timestamp": "2026-01-01T00:00:00",
        "segments": [{"start": 0, "end": 1, "text": text, "part": 1}],
    }


def target_document(filename: str, text: str, source: str, sha: str) -> dict[str, object]:
    revision: dict[str, object] = {
        "sha256": [sha],
        "text": text,
        "source": source,
    }
    if source == "generated":
        revision["model"] = "test-model"
    return {"schemaVersion": 3, "filename": filename, "revisions": [revision]}


class DocumentComparisonTests(unittest.TestCase):
    def test_text_only_change_is_detected(self) -> None:
        old = legacy_document("hero_line.mp3", "Wrong line")
        new = legacy_document("hero_line.mp3", "Correct line")

        changes, text_only, before, after = compare_legacy_documents(old, new, "fixture")

        self.assertTrue(text_only)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].before, "Wrong line")
        self.assertEqual(changes[0].after, "Correct line")
        self.assertEqual(before, "Wrong line")
        self.assertEqual(after, "Correct line")

    def test_metadata_change_is_not_text_only(self) -> None:
        old = legacy_document("hero_line.mp3", "Wrong line")
        new = legacy_document("hero_line.mp3", "Correct line")
        new["timestamp"] = "2026-02-01T00:00:00"

        _changes, text_only, _before, _after = compare_legacy_documents(old, new, "fixture")

        self.assertFalse(text_only)


class CommitClassificationTests(unittest.TestCase):
    def commit(self, **overrides: object) -> CommitRecord:
        values: dict[str, object] = {
            "commit": "a" * 40,
            "parents": ["b" * 40],
            "author_name": "Contributor",
            "author_email": "contributor@users.noreply.github.com",
            "author_date": "2026-01-01T00:00:00Z",
            "subject": "Correct transcript",
            "changes": [RawChange("c" * 40, "d" * 40, "M", "data/test.json")],
        }
        values.update(overrides)
        return CommitRecord(**values)  # type: ignore[arg-type]

    def test_explicit_official_import_is_excluded(self) -> None:
        commit = self.commit()
        self.assertEqual(classify_commit(commit, {commit.commit}, 500), "excluded_official_import")

    def test_bulk_commit_is_excluded(self) -> None:
        commit = self.commit(
            changes=[
                RawChange("c" * 40, "d" * 40, "M", f"data/{index}.json")
                for index in range(501)
            ]
        )
        self.assertEqual(classify_commit(commit, set(), 500), "excluded_bulk")

    def test_bot_commit_requires_review(self) -> None:
        commit = self.commit(
            author_name="automation[bot]",
            author_email="bot@users.noreply.github.com",
        )
        self.assertEqual(classify_commit(commit, set(), 500), "review_bot_authored")


class TargetMatchingTests(unittest.TestCase):
    def test_multiple_nonofficial_sha_revisions_are_ambiguous(self) -> None:
        record: dict[str, object] = {
            "legacyPath": "data/hero_line.mp3.json",
            "beforeFullText": "Wrong line",
            "currentFullText": "Correct line",
        }
        target_index = {
            "hero_line.mp3.json": [
                {
                    "path": "transcripts/hero/hero_line.mp3.json",
                    "filename": "hero/hero_line.mp3",
                    "revisions": [
                        {
                            "sha256": ["1" * 64],
                            "text": "Wrong line",
                            "source": "generated",
                        },
                        {
                            "sha256": ["2" * 64],
                            "text": "Wrong line",
                            "source": "generated",
                        },
                    ],
                }
            ]
        }

        target_matches(record, target_index)

        self.assertEqual(record["status"], "ambiguous_revision")
        self.assertEqual(len(record["targetMatches"]), 2)

    def test_null_sha_revision_requires_review(self) -> None:
        record: dict[str, object] = {
            "legacyPath": "data/hero_line.mp3.json",
            "beforeFullText": "Wrong line",
            "currentFullText": "Correct line",
        }
        target_index = {
            "hero_line.mp3.json": [
                {
                    "path": "transcripts/hero/hero_line.mp3.json",
                    "filename": "hero/hero_line.mp3",
                    "revisions": [
                        {"sha256": [], "text": "Wrong line", "source": "generated"}
                    ],
                }
            ]
        }

        target_matches(record, target_index)

        self.assertEqual(record["status"], "review_missing_sha")


class AuditIntegrationTests(unittest.TestCase):
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

    def make_fixture_repository(self) -> tuple[str, str]:
        self.write_json("data/foo.mp3.json", legacy_document("foo.mp3", "Wrong foo"))
        self.write_json("data/bar.mp3.json", legacy_document("bar.mp3", "Wrong bar"))
        self.commit("Initial generated data", "Owner", "owner@example.com", "2026-01-01T00:00:00Z")

        self.write_json("data/foo.mp3.json", legacy_document("foo.mp3", "Correct foo"))
        self.write_json("data/bar.mp3.json", legacy_document("bar.mp3", "Correct bar"))
        legacy_commit = self.commit(
            "Correct two transcripts",
            "Alice Contributor",
            "alice@users.noreply.github.com",
            "2026-01-02T00:00:00Z",
        )

        self.git("switch", "--orphan", "target")
        self.write_json(
            "transcripts/hero/foo.mp3.json",
            target_document("hero/foo.mp3", "Wrong foo", "generated", "1" * 64),
        )
        self.write_json(
            "transcripts/hero/bar.mp3.json",
            target_document("hero/bar.mp3", "Wrong bar", "official", "2" * 64),
        )
        target_commit = self.commit(
            "Import v2 transcripts",
            "Owner",
            "owner@example.com",
            "2026-01-03T00:00:00Z",
        )
        return legacy_commit, target_commit

    def test_audit_preserves_author_metadata_and_blocks_official_revision(self) -> None:
        legacy_commit, target_commit = self.make_fixture_repository()

        report = audit(
            repo=self.repo,
            legacy_ref=legacy_commit,
            target_ref=target_commit,
            legacy_prefix="data",
            target_prefix="transcripts",
            bulk_threshold=500,
            official_commits=set(),
        )

        records = {record["legacyPath"]: record for record in report["records"]}
        candidate = records["data/foo.mp3.json"]
        blocked = records["data/bar.mp3.json"]
        self.assertEqual(candidate["status"], "candidate_manual")
        self.assertEqual(candidate["author"]["name"], "Alice Contributor")
        self.assertEqual(candidate["author"]["email"], "alice@users.noreply.github.com")
        self.assertEqual(candidate["author"]["date"], "2026-01-02T00:00:00Z")
        self.assertEqual(candidate["targetMatches"][0]["proposedAction"], "replace_text_and_mark_manual")
        self.assertEqual(blocked["status"], "blocked_official")
        self.assertEqual(blocked["targetMatches"][0]["proposedAction"], "protected")
        self.assertFalse(report["policy"]["officialRevisionsMutable"])
        self.assertEqual(report["summary"]["officialRevisions"], 1)

        markdown = render_markdown(report)
        self.assertIn("Audit only", markdown)
        self.assertIn("`blocked_official`", markdown)

    def test_report_output_cannot_be_below_transcripts(self) -> None:
        with self.assertRaises(AuditError):
            safe_output_path(self.repo, "transcripts/report.json", ("transcripts", "config"))


if __name__ == "__main__":
    unittest.main()
