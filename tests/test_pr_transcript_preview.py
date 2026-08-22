from __future__ import annotations

import io
import json
import unittest
import zipfile

from tools.pr_transcript_preview import (
    COMMENT_MARKER,
    MAX_COMMENT_CHARS,
    PreviewError,
    build_preview_payload,
    _load_artifact_reports,
    _resolve_pr_number,
    aggregate_record_changes,
    build_comment,
)


SHA = "a" * 64


def record_change(
    sha: str = SHA,
    *,
    version: str = "ognb",
    before: str = "old text",
    current: str = "old text",
    desired: str = "new text",
    path: str = "transcripts/pocket/pocket_select_01.mp3.json",
    status: str = "update",
) -> dict:
    return {
        "status": status,
        "version": version,
        "sha256": sha,
        "sourcePaths": [path],
        "current": {"text": current, "officialtranscription": False},
        "expectedOldStates": [
            {"text": before, "source": "generated", "officialtranscription": False}
        ],
        "desired": {
            "text": desired,
            "source": "manual",
            "officialtranscription": False,
        },
    }


class PreviewRenderingTests(unittest.TestCase):
    def test_aggregates_version_fanout_and_builds_one_audio_button(self) -> None:
        first = record_change(version="ognb", desired="fixed @reviewers <script>")
        second = record_change(version="six-hero-update", desired="fixed @reviewers <script>")
        plan = {
            "deployable": True,
            "recordChanges": [first, second],
            "unmatchedHashes": [],
        }

        changes = aggregate_record_changes(plan)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["versions"], ["ognb", "six-hero-update"])

        body = build_comment(
            plan,
            {"errors": []},
            run_url="https://github.com/example/repo/actions/runs/1",
            head_sha="b" * 40,
        )
        audio_url = f"https://cdn.vlviewer.com/deadlock/audio/sha256/aa/{SHA}.mp3"
        self.assertEqual(body.count(audio_url), 1)
        self.assertIn("fixed @\u200breviewers &lt;script&gt;", body)
        self.assertNotIn("@reviewers", body)
        self.assertIn("ognb, six-hero-update", body)
        self.assertTrue(body.startswith(COMMENT_MARKER))

    def test_mass_update_is_bounded_and_summarized(self) -> None:
        records = []
        for index in range(250):
            sha = f"{index:064x}"
            records.append(
                record_change(
                    sha,
                    path=f"transcripts/hero{index % 3}/line_{index}.mp3.json",
                )
            )
        plan = {"deployable": True, "recordChanges": records, "unmatchedHashes": []}
        body = build_comment(
            plan,
            {"errors": []},
            run_url="https://github.com/example/repo/actions/runs/2",
            head_sha="c" * 40,
        )
        self.assertIn("Unique recordings changed: **250**", body)
        self.assertIn("Showing 25 of 250", body)
        self.assertEqual(body.count("▶ Play audio"), 25)
        self.assertLessEqual(len(body), MAX_COMMENT_CHARS)
        self.assertIn("`hero0`", body)

    def test_compact_payload_preserves_unique_recording_summary(self) -> None:
        plan = {
            "targetCommit": "f" * 40,
            "deployable": True,
            "validation": {"valid": True, "errors": []},
            "recordChanges": [
                record_change(version="ognb"),
                record_change(version="six-hero-update"),
            ],
            "errors": [],
            "unmatchedHashes": [],
        }
        compact = build_preview_payload(plan)
        self.assertEqual(len(compact["previewChanges"]), 1)
        self.assertEqual(
            compact["previewChanges"][0]["versions"],
            ["ognb", "six-hero-update"],
        )
        body = build_comment(
            compact,
            None,
            run_url="https://github.com/example/repo/actions/runs/5",
            head_sha="f" * 40,
        )
        self.assertIn("Unique recordings changed: **1**", body)
        self.assertEqual(body.count("▶ Play audio"), 1)

    def test_shows_three_way_state_when_cdn_differs_from_base(self) -> None:
        plan = {
            "deployable": False,
            "recordChanges": [
                record_change(current="unexpected CDN", status="conflict")
            ],
            "unmatchedHashes": [],
        }
        body = build_comment(
            plan,
            {"errors": []},
            run_url="https://github.com/example/repo/actions/runs/3",
            head_sha="d" * 40,
            workflow_conclusion="failure",
        )
        self.assertIn("**Before:**", body)
        self.assertIn("**Live CDN:**", body)
        self.assertIn("**After:**", body)
        self.assertIn("CDN conflict; this change is blocked", body)

    def test_missing_plan_leaves_a_non_stale_failure_comment(self) -> None:
        body = build_comment(
            None,
            {"errors": ["bad <json> from @person"]},
            run_url="https://github.com/example/repo/actions/runs/4",
            head_sha="e" * 40,
            workflow_conclusion="failure",
        )
        self.assertIn("Preview unavailable", body)
        self.assertIn("bad &lt;json&gt; from @\u200bperson", body)
        self.assertIn("plan was not produced", body)


class ArtifactSafetyTests(unittest.TestCase):
    def test_loads_only_expected_json_reports(self) -> None:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("content-sync/plan.json", json.dumps({"deployable": True}))
            archive.writestr("content-sync/validation.json", json.dumps({"valid": True}))
            archive.writestr("ignored.txt", "ignored")
        plan, validation = _load_artifact_reports(stream.getvalue())
        self.assertEqual(plan, {"deployable": True})
        self.assertEqual(validation, {"valid": True})

    def test_prefers_compact_preview_without_reading_full_plan(self) -> None:
        stream = io.BytesIO()
        compact = {"schemaVersion": 1, "previewChanges": []}
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("content-sync/plan.json", "x" * (20 * 1024 * 1024 + 1))
            archive.writestr("content-sync/preview.json", json.dumps(compact))
        plan, validation = _load_artifact_reports(stream.getvalue())
        self.assertEqual(plan, compact)
        self.assertIsNone(validation)

    def test_rejects_duplicate_reports(self) -> None:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("one/plan.json", "{}")
            archive.writestr("two/plan.json", "{}")
        with self.assertRaises(PreviewError):
            _load_artifact_reports(stream.getvalue())

    def test_resolves_pr_from_workflow_event_without_network(self) -> None:
        event = {"workflow_run": {"pull_requests": [{"number": 42}]}}
        self.assertEqual(
            _resolve_pr_number(
                event,
                [],
                api_url="https://api.github.com",
                repository="example/repo",
                token="unused",
            ),
            42,
        )


if __name__ == "__main__":
    unittest.main()
