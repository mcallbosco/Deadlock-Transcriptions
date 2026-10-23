from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest import mock

from tools.content_sync import ContentSyncError, ContentSyncPlanner, StoredJson, compact_json, deploy_plan, validate_repository
from tools.content_tags import assignment_errors, build_artifacts, project_conversation_tags, validate_definitions
from tools.set_content_tags import plan_group_tags
from tools.transcript_schema import compact_revisions, preserve_revision_tags
from tools.link_exact_official_transcripts import plan_documents as link_official
from tools.apply_reviewed_generated_duration_merges import apply_targets_to_document
from tools.voiceline_search import build_search_index
import test_content_sync as sync_tests
from test_content_sync import CDN, SHA, SHA_B, PublicMemoryStore
from test_voiceline_search import catalog, line, transcript_states

DEFINITIONS = [{"id": "nicknames", "label": "Nicknames"}, {"id": "insults", "label": "Insults"}]


def document(filename, hashes, text="Example", tags=None):
    revision = {"sha256": hashes, "text": text, "source": "manual"}
    if tags is not None:
        revision["tags"] = tags
    return {"schemaVersion": 3, "filename": filename, "revisions": [revision]}


class TagUnitTests(unittest.TestCase):
    def test_compaction_preserves_tags_independently_of_source_priority(self):
        revisions = [document("a", [SHA], tags=["nicknames", "insults"])["revisions"][0],
                     {"sha256": [SHA_B], "text": "EXAMPLE!", "source": "official", "tags": ["insults", "nicknames"]}]
        result = compact_revisions(revisions)
        self.assertEqual(result, [{"sha256": [SHA, SHA_B], "text": "EXAMPLE!", "source": "official", "tags": ["insults", "nicknames"]}])
        revisions[1].pop("tags")
        with self.assertRaisesRegex(ValueError, "Conflicting content tags"):
            compact_revisions(revisions)

    def test_reconstructed_corrections_and_official_linking_keep_tags(self):
        original = document("hero/a.mp3", [SHA], tags=["nicknames"])
        updated, _ = apply_targets_to_document(original, "transcripts/hero/a.mp3.json", {
            SHA: {"text": "Corrected", "source": "manual", "itemId": "test"},
        })
        self.assertEqual(updated["revisions"][0]["tags"], ["nicknames"])
        official = document("hero/b.mp3", [SHA_B], tags=["nicknames"])
        official["revisions"][0]["source"] = "official"
        docs = {original["filename"]: original, official["filename"]: official}
        changes, _ = link_official(docs, {"lineage": list(docs)})
        self.assertEqual(changes["hero/a.mp3"]["revisions"][0]["tags"], ["nicknames"])
        self.assertEqual(changes["hero/b.mp3"]["revisions"][0]["sha256"], [SHA, SHA_B])
        official["revisions"][0]["tags"] = ["insults"]
        with self.assertRaisesRegex(ValueError, "Conflicting content tags"):
            link_official(docs, {"lineage": list(docs)})
        with self.assertRaisesRegex(ValueError, "Conflicting content tags"):
            preserve_revision_tags([*original["revisions"], *official["revisions"]], [{"sha256":[SHA,SHA_B],"text":"Merged","source":"official"}])

    def test_alias_helper_updates_complete_group_and_duplicate_hashes_only(self):
        docs = {"hero/a.mp3": document("hero/a.mp3", [SHA, SHA_B]),
                "hero/alias.mp3": document("hero/alias.mp3", [SHA]),
                "other/a.mp3": document("other/a.mp3", ["c"*64])}
        changed = plan_group_tags(docs, [], "hero/a.mp3", SHA, ["nicknames"])
        self.assertEqual(set(changed), {"hero/a.mp3", "hero/alias.mp3"})
        self.assertEqual(changed["hero/a.mp3"]["revisions"][0]["tags"], ["nicknames"])
        self.assertNotIn("tags", docs["hero/a.mp3"]["revisions"][0])
        self.assertEqual(assignment_errors({**docs, **changed}, DEFINITIONS, []), [])
        changed["hero/alias.mp3"]["revisions"][0]["tags"] = []
        errors = assignment_errors({**docs, **changed}, DEFINITIONS, [])
        self.assertTrue(any("Conflicting content tags for" in error for error in errors))
        self.assertTrue(any("logical group" in error for error in errors))

    def test_correlated_aliases_and_blanks_keep_editor_boundaries(self):
        docs = {"hero/a.mp3": document("hero/a.mp3", [SHA]), "hero/b.mp3": document("hero/b.mp3", [SHA_B])}
        changes = plan_group_tags(docs, [["hero/a.mp3", "hero/b.mp3"]], "hero/a.mp3", SHA, ["insults"])
        self.assertEqual(len(changes), 2)
        for value in docs.values():
            value["revisions"][0].update(text="", source="skippedeffort")
        changes = plan_group_tags(docs, [["hero/a.mp3", "hero/b.mp3"]], "hero/a.mp3", SHA, ["insults"])
        self.assertEqual(list(changes), ["hero/a.mp3"])

    def test_alias_lookup_normalizes_names_without_changing_document_keys(self):
        for filename in ("Hero/a.mp3", "hero\\a.mp3"):
            with self.subTest(filename=filename):
                docs = {filename: document(filename, [SHA]), "hero/b.mp3": document("hero/b.mp3", [SHA_B])}
                correlations = [["hero/a.mp3", "hero/b.mp3"]]
                changes = plan_group_tags(docs, correlations, filename, SHA, ["insults"])
                self.assertEqual(set(changes), set(docs))
                self.assertEqual(changes[filename]["filename"], filename)
                self.assertEqual(assignment_errors({**docs, **changes}, DEFINITIONS, correlations), [])
                changes["hero/b.mp3"]["revisions"][0].pop("tags")
                self.assertTrue(any("logical group" in error for error in assignment_errors(changes, DEFINITIONS, correlations)))

    def test_definitions_reject_unknown_duplicate_and_invalid_values(self):
        for tags in [[{"id": "bad id", "label": "Name"}], DEFINITIONS*2, [{"id":"insults","label":""}]]:
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                validate_definitions({"schemaVersion": 1, "game":"deadlock", "tags":tags}, "deadlock")
        errors = assignment_errors({"a": document("a", [SHA], tags=["missing"])}, DEFINITIONS, [])
        self.assertIn("undefined content tags", errors[0])

    def test_artifact_addresses_exact_bytes_and_order_is_deterministic(self):
        first = build_artifacts("deadlock", DEFINITIONS, {SHA_B:("nicknames",), SHA:("nicknames", "insults")}, CDN)
        second = build_artifacts("deadlock", list(reversed(DEFINITIONS)), {SHA:("insults", "nicknames"), SHA_B:("nicknames",)}, CDN)
        self.assertEqual(first, second)
        for key, value in first:
            self.assertIn(hashlib.sha256(compact_json(value)).hexdigest(), key)
        for entry in first[-1][1]["tags"]:
            membership = next(value for key, value in first if entry["membership"]["url"] == f"{CDN}/{key}")
            self.assertEqual(entry["membership"]["bytes"], len(compact_json(membership)))
            self.assertEqual(entry["membership"]["recordingCount"], len(membership["hashes"]))

    def test_conversation_variations_union_removal_and_legacy_metadata(self):
        value = {"conversations": [{"tags": {"content": ["legacy"]}, "lines": [
            {"filename": "a.mp3", "audioKey": f"sha256/aa/{SHA}.mp3"},
            {"variations": [{"audioKey": f"sha256/bb/{SHA_B}.mp3"}, {"filename":"unknown.mp3"}]},
            {"part":3},
        ]}]}
        project_conversation_tags(value, {SHA:("nicknames",), SHA_B:("insults",)})
        conversation = value["conversations"][0]
        self.assertEqual(conversation["contentTags"], ["insults", "nicknames"])
        self.assertEqual(conversation["lines"][0]["contentTags"], ["nicknames"])
        self.assertEqual(conversation["lines"][1]["variations"][0]["contentTags"], ["insults"])
        self.assertEqual(conversation["lines"][2]["contentTags"], [])
        self.assertEqual(project_conversation_tags(value, {SHA:("nicknames",), SHA_B:("insults",)}), 0)
        project_conversation_tags(value, {})
        self.assertEqual(conversation["contentTags"], [])
        self.assertEqual(conversation["tags"], {"content":["legacy"]})

    def test_nested_conversation_layouts_and_metadata_remain_supported(self):
        recording = {"audioKey": f"sha256/aa/{SHA}.mp3"}
        line = {"variations": {"alternate": [recording]}, "metadata": {"label": "keep"}}
        conversation = {"lines": [line, {}]}
        value = {"historical": [{"custom": {"conversation": conversation}}]}
        self.assertEqual(project_conversation_tags(value, {SHA: ("insults",)}), 4)
        self.assertEqual(recording["contentTags"], ["insults"])
        self.assertEqual(line["contentTags"], ["insults"])
        self.assertEqual(conversation["lines"][1]["contentTags"], [])
        self.assertEqual(line["metadata"], {"label": "keep"})
        self.assertEqual(project_conversation_tags(value, {SHA: ("insults",)}), 0)
        self.assertEqual(project_conversation_tags(value, {}), 3)

    def test_historical_search_does_not_collapse_different_tag_sets(self):
        old, new = line("hero/a.mp3", SHA, "same", "a"), line("hero/a.mp3", SHA_B, "same", "a")
        inputs = [catalog("v1", [old]), catalog("v2", [new])]
        states = transcript_states(old, new)
        self.assertEqual(build_search_index(inputs,"deadlock",states).states, 1)
        self.assertEqual(build_search_index(inputs,"deadlock",states,content_tags={SHA:("insults",)}).states, 2)
        self.assertEqual(build_search_index(inputs,"deadlock",states,content_tags={SHA:("insults",),SHA_B:("insults",)}).states, 1)


class TagPublishingTests(unittest.TestCase):
    setUp = sync_tests.ContentSyncTests.setUp
    tearDown = sync_tests.ContentSyncTests.tearDown
    git = sync_tests.ContentSyncTests.git
    commit = sync_tests.ContentSyncTests.commit
    write_json = staticmethod(sync_tests.ContentSyncTests.write_json)
    write_transcript = sync_tests.ContentSyncTests.write_transcript
    published = sync_tests.ContentSyncTests.published
    add_version_metadata = sync_tests.ContentSyncTests.add_version_metadata

    def prepare(self, tags=None):
        self.write_json(self.repo / "config/deadlock/content-tags.json", {"schemaVersion":1,"game":"deadlock","tags":DEFINITIONS})
        if tags is not None:
            doc = json.loads(self.transcript_path.read_text())
            doc["revisions"][0]["tags"] = tags
            self.write_json(self.transcript_path, doc)
        self.commit("configure tags")
        store = PublicMemoryStore(self.published())
        return store, self.plan(store)

    def plan(self, store, base=None):
        return ContentSyncPlanner(self.repo, store, cdn_base_url=CDN).build(base=base or self.base)

    def deploy(self, store, plan):
        return deploy_plan(plan, store, store, store.get_json("private/cursor.json"), "private/cursor.json")

    def test_tag_only_update_publishes_then_reruns_without_writes(self):
        store, plan = self.prepare(["nicknames"])
        self.assertTrue(plan.deployable, plan.to_markdown())
        self.deploy(store, plan)
        conversation = store.values["deadlock/versions/v1/conversations.json"]["conversations"][0]
        self.assertEqual(conversation["contentTags"], ["nicknames"])
        self.assertEqual(conversation["lines"][0]["contentTags"], ["nicknames"])
        self.assertEqual(conversation["lines"][0]["transcription"], "old text")
        self.assertEqual(store.values["deadlock/manifest.json"]["versions"][0]["contentRevision"], 3)
        second = self.plan(store)
        self.assertTrue(second.deployable, second.to_markdown())
        self.assertEqual(second.writes, [])

    def test_removal_clears_membership_and_conversations_without_deleting_artifacts(self):
        store, plan = self.prepare(["nicknames"])
        self.deploy(store, plan)
        previous_keys = set(store.values)
        base = self.git("rev-parse", "HEAD").strip()
        self.write_transcript("old text", "official")
        self.commit("remove tag")
        removed = self.plan(store, base)
        self.deploy(store, removed)
        self.assertTrue(previous_keys <= store.values.keys())
        conversation = store.values["deadlock/versions/v1/conversations.json"]["conversations"][0]
        self.assertEqual(conversation["contentTags"], [])
        catalogue_key = store.values["deadlock/manifest.json"]["contentTagsCatalogUrl"].removeprefix(CDN+"/")
        entry = next(tag for tag in store.values[catalogue_key]["tags"] if tag["id"] == "nicknames")
        self.assertEqual(entry["membership"]["recordingCount"], 0)

    def test_first_publication_materializes_untagged_historical_and_custom_versions(self):
        store, _ = self.prepare()
        for version in ("old-hidden", "custom"):
            entry = copy.deepcopy(store.values["deadlock/manifest.json"]["versions"][0])
            entry.update(id=version, hidden=True, kind="custom" if version == "custom" else "official")
            for field in ("voiceLineUrl", "conversationUrl"):
                old_key = entry[field].removeprefix(CDN+"/")
                entry[field] = entry[field].replace("/v1/", f"/{version}/")
                store.values[entry[field].removeprefix(CDN+"/")] = copy.deepcopy(store.values[old_key])
            store.values["deadlock/manifest.json"]["versions"].append(entry)
            self.add_version_metadata(store.values, version)
        plan = self.plan(store)
        self.assertEqual(plan.content_tags["changedConversationExports"], 3)
        self.deploy(store, plan)
        for version in ("v1", "old-hidden", "custom"):
            self.assertEqual(store.values[f"deadlock/versions/{version}/conversations.json"]["conversations"][0]["contentTags"], [])

    def test_dependency_is_verified_before_catalogue_and_manifest(self):
        store, plan = self.prepare(["nicknames"])
        manifest_before = copy.deepcopy(store.values["deadlock/manifest.json"])
        class MissingPublic:
            def get_json(self, key):
                return StoredJson(key, None, None, None)
            def url(self, key):
                return f"{CDN}/{key}"
        with mock.patch("tools.content_sync.time.sleep"), self.assertRaisesRegex(ContentSyncError, "verification failed"):
            deploy_plan(plan, store, MissingPublic(), store.get_json("private/cursor.json"), "private/cursor.json")
        self.assertEqual(store.values["deadlock/manifest.json"], manifest_before)
        self.assertFalse(any("/catalog/" in key for key in store.events))
        self.assertNotIn("private/cursor.json", store.values)
        retry = self.plan(store)
        self.deploy(store, retry)
        self.assertIn("contentTagsCatalogUrl", store.values["deadlock/manifest.json"])

    def test_reused_catalogue_must_be_public_before_manifest_switch(self):
        store, plan = self.prepare(["nicknames"])
        for write in plan.sorted_writes():
            if write.phase in {"tag-membership", "tag-catalog"}:
                store.put_json(write)
        retry = self.plan(store)
        self.assertFalse(any(write.phase.startswith("tag-") for write in retry.writes))
        def stale(writes, public_store):
            if any(write.phase == "tag-catalog" for write in writes):
                raise ContentSyncError("stale catalogue")
        with mock.patch("tools.content_sync.verify_public_writes", side_effect=stale), self.assertRaisesRegex(ContentSyncError, "stale catalogue"):
            self.deploy(store, retry)
        self.assertNotIn("contentTagsCatalogUrl", store.values["deadlock/manifest.json"])
        self.assertNotIn("private/cursor.json", store.values)

    def test_final_verification_reads_each_object_once_and_includes_reused_tags(self):
        store, plan = self.prepare(["nicknames"])
        for write in plan.tag_dependencies:
            if write.phase == "tag-membership":
                store.put_json(write)
        plan = self.plan(store)
        calls = []
        def observe(writes, public_store):
            writes = list(writes)
            calls.append([write.key for write in writes])
            for write in writes:
                self.assertEqual(public_store.get_json(write.key).body, write.body())
        with mock.patch("tools.content_sync.verify_public_writes", side_effect=observe):
            result = self.deploy(store, plan)
        final = calls[-1]
        self.assertEqual(len(final), len(set(final)))
        self.assertEqual(result["verifiedUrls"], len(final))
        self.assertEqual(set(final), {write.key for write in plan.writes + plan.tag_dependencies})
        self.assertTrue({write.key for write in plan.tag_dependencies} <= set(calls[-2]))

    def test_manifest_precondition_failure_never_advances_cursor(self):
        store, plan = self.prepare(["nicknames"])
        put = store.put_json
        def conditional(write):
            if write.key == "deadlock/manifest.json":
                raise ContentSyncError("R2 precondition failed")
            put(write)
        with mock.patch.object(store, "put_json", side_effect=conditional), self.assertRaisesRegex(ContentSyncError, "precondition"):
            self.deploy(store, plan)
        self.assertNotIn("private/cursor.json", store.values)
        self.assertNotIn("contentTagsCatalogUrl", store.values["deadlock/manifest.json"])
        self.deploy(store, self.plan(store))
        self.assertIn("contentTagsCatalogUrl", store.values["deadlock/manifest.json"])

    def test_partial_content_upload_recovers_metadata_and_manifest(self):
        store, plan = self.prepare(["insults"])
        for write in plan.sorted_writes():
            if write.phase == "metadata":
                break
            store.put_json(write)
        retry = self.plan(store)
        self.assertTrue(retry.deployable, retry.to_markdown())
        self.deploy(store, retry)
        inventory = store.values["deadlock/versions/v1/publish-inventory.json"]
        body = store.bodies["deadlock/versions/v1/conversations.json"]
        self.assertEqual(inventory["files"]["conversations.json"]["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(inventory["contentRevision"], 3)

    def test_immutable_corruption_and_referenced_definition_removal_block(self):
        store, plan = self.prepare(["nicknames"])
        self.deploy(store, plan)
        key = plan.tag_dependencies[0].key
        store.bodies[key] = b'{}'
        self.assertFalse(self.plan(store).deployable)
        self.write_json(self.repo / "config/deadlock/content-tags.json", {"schemaVersion":1,"game":"deadlock","tags":[]})
        validation = validate_repository(self.repo)
        self.assertTrue(any("undefined content tags" in error for error in validation.errors))
