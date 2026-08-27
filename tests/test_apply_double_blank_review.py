from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.apply_double_blank_review import apply_review


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class ApplyDoubleBlankReviewTests(unittest.TestCase):
    def test_applies_manual_nonspeech_and_noted_official_merge(self) -> None:
        manual_hash, nonspeech_hash, official_hash, unrelated_hash = (character * 64 for character in "abcd")
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            transcript = repo / "transcripts/hero/lines.mp3.json"
            write_json(
                transcript,
                {
                    "schemaVersion": 3,
                    "filename": "hero/lines.mp3",
                    "revisions": [
                        {"sha256": [manual_hash, unrelated_hash], "text": "old", "source": "generated", "model": "old"},
                        {"sha256": [nonspeech_hash], "text": "grunt?", "source": "generated", "model": "old"},
                        {"sha256": [official_hash], "text": "wrong", "source": "generated", "model": "old"},
                        {"sha256": ["e" * 64], "text": "WOAH!", "source": "official"},
                    ],
                },
            )
            report = repo / "report.json"
            write_json(
                report,
                {
                    "held": [
                        {"recordingId": "1", "allRecordingHashes": [manual_hash], "items": [{"path": "transcripts/hero/lines.mp3.json"}]},
                        {"recordingId": "2", "allRecordingHashes": [nonspeech_hash], "items": [{"path": "transcripts/hero/lines.mp3.json"}]},
                        {"recordingId": "3", "allRecordingHashes": [official_hash], "items": [{"path": "transcripts/hero/lines.mp3.json"}]},
                    ]
                },
            )
            decisions = repo / "decisions.json"
            write_json(
                decisions,
                {
                    "decisions": [
                        {"recordingId": "1", "status": "transcript", "text": "Correct line."},
                        {"recordingId": "2", "status": "nonspeech", "text": ""},
                        {"recordingId": "3", "status": "hold", "notes": "Merge this with official."},
                    ]
                },
            )
            result = apply_review(repo, report, decisions, apply=True)
            self.assertEqual(result["manualRecordings"], 1)
            self.assertEqual(result["nonspeechRecordings"], 1)
            self.assertEqual(result["officialMergeRecordings"], 1)
            revisions = json.loads(transcript.read_text(encoding="utf-8"))["revisions"]
            states = {
                digest: (revision["text"], revision["source"])
                for revision in revisions
                for digest in revision["sha256"]
            }
            self.assertEqual(states[manual_hash], ("Correct line.", "manual"))
            self.assertEqual(states[nonspeech_hash], ("", "skippednonspeech"))
            self.assertEqual(states[official_hash], ("WOAH!", "official"))
            self.assertEqual(states[unrelated_hash], ("old", "generated"))

    def test_rejects_incomplete_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "transcripts").mkdir()
            report = repo / "report.json"
            decisions = repo / "decisions.json"
            write_json(report, {"held": [{"recordingId": "1", "allRecordingHashes": ["a" * 64], "items": []}]})
            write_json(decisions, {"decisions": []})
            with self.assertRaisesRegex(ValueError, "Expected decisions for all 1"):
                apply_review(repo, report, decisions, apply=False)


if __name__ == "__main__":
    unittest.main()
