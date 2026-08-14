from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.content_sync import (
    ContentSyncError,
    ContentSyncPlanner,
    PlannedWrite,
    R2JsonStore,
    RepositoryValidation,
    StoredJson,
    SyncPlan,
    canonical_json,
    deploy_plan,
    validate_repository,
    verify_public_writes,
)


SHA = "a" * 64
CDN = "https://cdn.example.test"


class MemoryStore:
    def __init__(self, values: dict[str, dict[str, Any]]) -> None:
        self.values = values
        self.events: list[str] = []

    def get_json(self, key: str) -> StoredJson:
        value = self.values.get(key)
        body = canonical_json(value) if value is not None else None
        return StoredJson(key, value, body, f'"etag-{key}"' if value is not None else None)

    def put_json(self, write: PlannedWrite) -> None:
        self.events.append(write.key)
        self.values[write.key] = write.value


class PublicMemoryStore(MemoryStore):
    def url(self, key: str) -> str:
        return f"{CDN}/{key}"


class FakeR2Client:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.puts.append(kwargs)


class ContentSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)
        (self.repo / "transcripts" / "hero").mkdir(parents=True)
        (self.repo / "config" / "deadlock").mkdir(parents=True)
        self.transcript_path = self.repo / "transcripts" / "hero" / "line.mp3.json"
        self.write_transcript("old text", "official")
        self.write_json(
            self.repo / "config" / "deadlock" / "transcription-vocabulary.json",
            {},
        )
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Tests")
        self.git("config", "user.email", "tests@example.test")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout.decode("utf-8")

    def commit(self, message: str) -> None:
        self.git("add", ".")
        self.git("commit", "-m", message)

    @staticmethod
    def write_json(path: Path, value: dict[str, Any], indent: int | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=indent) + "\n", encoding="utf-8")

    def write_transcript(self, text: str, source: str) -> None:
        revision: dict[str, Any] = {"sha256": [SHA], "text": text, "source": source}
        if source == "generated":
            revision["model"] = "test-model"
        self.write_json(
            self.transcript_path,
            {
                "schemaVersion": 3,
                "filename": "hero/line.mp3",
                "revisions": [revision],
            },
            indent=2,
        )

    def published(self, text: str = "old text", official: bool = True) -> dict[str, dict[str, Any]]:
        prefix = "deadlock/versions/v1"
        record = {
            "filename": "hero/line.mp3",
            "audioKey": f"sha256/{SHA[:2]}/{SHA}.mp3",
            "transcription": text,
            "keep": "unchanged",
        }
        if official:
            record["officialtranscription"] = True
        voice = {"hero": {"lines": [dict(record)]}}
        conversation = {"conversations": [{"lines": [dict(record)]}]}
        inventory_files = {}
        for name, value in (("voicelines.json", voice), ("conversations.json", conversation)):
            body = canonical_json(value)
            inventory_files[name] = {
                "size": len(body),
                "sha256": "old-hash",
                "contentType": "application/json; charset=utf-8",
                "mutable": True,
            }
        entry = {
            "id": "v1",
            "label": "Version 1",
            "contentRevision": 2,
            "voiceLineUrl": f"{CDN}/{prefix}/voicelines.json",
            "conversationUrl": f"{CDN}/{prefix}/conversations.json",
        }
        return {
            "deadlock/manifest.json": {
                "schemaVersion": 1,
                "game": "deadlock",
                "latestVersion": "v1",
                "versions": [entry],
            },
            f"{prefix}/voicelines.json": voice,
            f"{prefix}/conversations.json": conversation,
            f"{prefix}/publish-inventory.json": {
                "schemaVersion": 2,
                "contentRevision": 2,
                "files": inventory_files,
            },
            f"{prefix}/release.json": {
                "schemaVersion": 1,
                "id": "v1",
                "contentRevision": 2,
                "fileCount": 2,
                "totalBytes": sum(item["size"] for item in inventory_files.values()),
            },
        }

    def target_plan(self, store: MemoryStore) -> SyncPlan:
        self.write_transcript("corrected text", "manual")
        self.commit("correct transcript")
        return ContentSyncPlanner(self.repo, store, cdn_base_url=CDN).build(base=self.base)

    def test_updates_every_occurrence_and_metadata_once(self) -> None:
        plan = self.target_plan(MemoryStore(self.published()))

        self.assertTrue(plan.deployable, plan.to_markdown())
        self.assertEqual(plan.matched_records, 2)
        self.assertEqual(len(plan.record_changes), 2)
        self.assertEqual(plan.affected_versions, ["v1"])
        self.assertEqual(
            [write.phase for write in plan.sorted_writes()],
            ["content", "content", "metadata", "metadata", "manifest"],
        )
        for key in (
            "deadlock/versions/v1/voicelines.json",
            "deadlock/versions/v1/conversations.json",
        ):
            aggregate = next(write.value for write in plan.writes if write.key == key)
            record = next(item for item, _path, _sha in self._walk(aggregate))
            self.assertEqual(record["transcription"], "corrected text")
            self.assertNotIn("officialtranscription", record)
            self.assertEqual(record["keep"], "unchanged")
        manifest = next(write.value for write in plan.writes if write.key == "deadlock/manifest.json")
        self.assertEqual(manifest["versions"][0]["contentRevision"], 3)

    @staticmethod
    def _walk(value: Any):
        from tools.content_sync import walk_audio_records

        return walk_audio_records(value)

    def test_third_state_blocks_without_becoming_deployable(self) -> None:
        values = self.published()
        values["deadlock/versions/v1/conversations.json"]["conversations"][0]["lines"][0][
            "transcription"
        ] = "out-of-band edit"
        plan = self.target_plan(MemoryStore(values))

        self.assertFalse(plan.deployable)
        self.assertEqual(plan.conflict_count, 1)

    def test_formatting_only_direct_config_change_is_source_noop(self) -> None:
        path = self.repo / "config" / "deadlock" / "versions" / "v1" / "character-names.json"
        value = {"schemaVersion": 1, "game": "deadlock", "names": {"hero": "Hero"}}
        self.write_json(path, value)
        self.commit("add overlay")
        config_base = self.git("rev-parse", "HEAD").strip()
        path.write_text(json.dumps(value, indent=4) + "\n", encoding="utf-8")
        self.commit("format overlay")
        published = self.published()
        published["deadlock/versions/v1/character-names.json"] = value

        plan = ContentSyncPlanner(
            self.repo, MemoryStore(published), cdn_base_url=CDN
        ).build(base=config_base)

        self.assertTrue(plan.deployable, plan.to_markdown())
        self.assertEqual(plan.config_changes[0]["status"], "source_noop")
        self.assertEqual(plan.writes, [])
        self.assertEqual(plan.affected_versions, [])

    def test_generator_input_change_blocks_phase_one(self) -> None:
        self.write_json(
            self.repo / "config" / "deadlock" / "character-mappings.json",
            {},
        )
        self.commit("change generator input")
        plan = ContentSyncPlanner(
            self.repo, MemoryStore(self.published()), cdn_base_url=CDN
        ).build(base=self.base)

        self.assertFalse(plan.deployable)
        self.assertEqual(
            plan.unsupported_paths,
            ["config/deadlock/character-mappings.json"],
        )

    def test_planning_rejects_uncommitted_content(self) -> None:
        self.write_transcript("uncommitted", "manual")
        with self.assertRaisesRegex(ContentSyncError, "clean committed content tree"):
            ContentSyncPlanner(
                self.repo, MemoryStore(self.published()), cdn_base_url=CDN
            ).build(base=self.base)

    def test_validation_enforces_transcript_schema(self) -> None:
        value = json.loads(self.transcript_path.read_text(encoding="utf-8"))
        value["extra"] = True
        value["revisions"][0].pop("source")
        self.write_json(self.transcript_path, value)
        report = validate_repository(self.repo)
        self.assertFalse(report.valid)
        self.assertTrue(any("unexpected fields" in item for item in report.errors))
        self.assertTrue(any("missing source" in item for item in report.errors))

    def test_r2_writes_use_create_and_replace_preconditions(self) -> None:
        client = FakeR2Client()
        store = R2JsonStore("bucket", "https://account.r2.example", client=client)
        store.put_json(PlannedWrite("replace.json", {"a": 1}, '"etag"', "content", "test"))
        store.put_json(PlannedWrite("create.json", {"a": 1}, None, "content", "test"))
        self.assertEqual(client.puts[0]["IfMatch"], '"etag"')
        self.assertEqual(client.puts[1]["IfNoneMatch"], "*")

    def test_r2_precondition_failure_stops_the_write(self) -> None:
        class PreconditionFailed(Exception):
            response = {
                "Error": {"Code": "PreconditionFailed"},
                "ResponseMetadata": {"HTTPStatusCode": 412},
            }

        class FailingClient:
            @staticmethod
            def put_object(**_kwargs: Any) -> None:
                raise PreconditionFailed()

        store = R2JsonStore("bucket", "https://account.r2.example", client=FailingClient())
        with self.assertRaisesRegex(ContentSyncError, "precondition failed"):
            store.put_json(
                PlannedWrite("replace.json", {"a": 1}, '"etag"', "content", "test")
            )

    def test_partial_rerun_finishes_metadata_without_second_revision(self) -> None:
        store = MemoryStore(self.published())
        first = self.target_plan(store)
        for write in first.sorted_writes():
            if write.phase == "content" or write.key.endswith("publish-inventory.json"):
                store.values[write.key] = write.value

        second = ContentSyncPlanner(self.repo, store, cdn_base_url=CDN).build(base=self.base)

        self.assertTrue(second.deployable, second.to_markdown())
        self.assertEqual(second.version_revisions[0]["proposed"], 3)
        self.assertEqual(
            [write.key for write in second.sorted_writes()],
            ["deadlock/versions/v1/release.json", "deadlock/manifest.json"],
        )

    def test_manifest_precedes_verified_private_cursor_only(self) -> None:
        validation = RepositoryValidation(repo=self.repo)
        plan = SyncPlan(
            repository="owner/repo",
            base_commit=self.base,
            target_commit="b" * 40,
            game="deadlock",
            baseline=False,
            created_at="2026-01-01T00:00:00Z",
            validation=validation,
            writes=[
                PlannedWrite("deadlock/manifest.json", {"phase": 3}, '"m"', "manifest", "m"),
                PlannedWrite("deadlock/v/content.json", {"phase": 1}, '"c"', "content", "c"),
                PlannedWrite("deadlock/v/release.json", {"phase": 2}, '"r"', "metadata", "r"),
            ],
        )
        values = {write.key: write.value for write in plan.writes}
        r2 = MemoryStore({})
        public = PublicMemoryStore(values)
        result = deploy_plan(
            plan,
            r2,  # type: ignore[arg-type]
            public,  # type: ignore[arg-type]
            StoredJson("cursor", None, None, None),
            "deadlock/_internal/transcript-sync.json",
        )
        self.assertEqual(
            r2.events,
            [
                "deadlock/v/content.json",
                "deadlock/v/release.json",
                "deadlock/manifest.json",
                "deadlock/_internal/transcript-sync.json",
            ],
        )
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(
            result["completedWrites"],
            [
                "deadlock/v/content.json",
                "deadlock/v/release.json",
                "deadlock/manifest.json",
            ],
        )
        self.assertTrue(result["cursorWritten"])

    def test_public_verification_retries_transient_read_errors(self) -> None:
        write = PlannedWrite(
            "deadlock/categories.json",
            {"schemaVersion": 1},
            '"etag"',
            "content",
            "test",
        )

        class FlakyPublicStore(PublicMemoryStore):
            calls = 0

            def get_json(self, key: str) -> StoredJson:
                self.calls += 1
                if self.calls == 1:
                    raise ContentSyncError(
                        f"Could not read {self.url(key)}: HTTP 403"
                    )
                return super().get_json(key)

        public = FlakyPublicStore({write.key: write.value})
        delays: list[float] = []
        verify_public_writes([write], public, attempts=3, sleep_fn=delays.append)

        self.assertEqual(public.calls, 2)
        self.assertEqual(delays, [1])


if __name__ == "__main__":
    unittest.main()
