from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.double_blank_review_server import DecisionStore, load_queue


class DoubleBlankReviewServerTests(unittest.TestCase):
    def test_load_queue_requires_held_rows_with_recording_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            report.write_text(
                json.dumps({"held": [{"recordingId": "a" * 64}]}),
                encoding="utf-8",
            )
            self.assertEqual(load_queue(report), [{"recordingId": "a" * 64}])

            report.write_text(json.dumps({"held": [{}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid held row"):
                load_queue(report)

    def test_store_validates_and_persists_transcript_decision(self) -> None:
        recording_id = "a" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "decisions.json"
            store = DecisionStore(path, [recording_id])
            decision = store.put(
                recording_id,
                {
                    "status": "transcript",
                    "text": "  Headed to Yellow.  ",
                    "notes": " clear encode B ",
                    "preferredHash": "b" * 64,
                },
            )
            self.assertEqual(decision["text"], "Headed to Yellow.")
            self.assertEqual(decision["notes"], "clear encode B")
            reloaded = DecisionStore(path, [recording_id])
            self.assertEqual(reloaded.decisions[recording_id]["text"], "Headed to Yellow.")
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schemaVersion"], 1)
            self.assertEqual(len(document["decisions"]), 1)

    def test_store_rejects_blank_transcript_and_unknown_recording(self) -> None:
        recording_id = "a" * 64
        with tempfile.TemporaryDirectory() as temporary:
            store = DecisionStore(Path(temporary) / "decisions.json", [recording_id])
            with self.assertRaisesRegex(ValueError, "requires nonblank text"):
                store.put(recording_id, {"status": "transcript", "text": ""})
            with self.assertRaisesRegex(ValueError, "Unknown recordingId"):
                store.put("b" * 64, {"status": "hold"})

    def test_nonspeech_clears_text_and_delete_is_persisted(self) -> None:
        recording_id = "a" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "decisions.json"
            store = DecisionStore(path, [recording_id])
            decision = store.put(recording_id, {"status": "nonspeech", "text": "discard me"})
            self.assertEqual(decision["text"], "")
            store.delete(recording_id)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["decisions"], [])


if __name__ == "__main__":
    unittest.main()
