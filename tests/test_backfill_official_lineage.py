import copy
import unittest

from tools.backfill_official_lineage import plan_documents


def revision(hashes, text, **metadata):
    return {"sha256": hashes, "text": text, "source": "official", **metadata}


def document(filename, *revisions):
    return {"schemaVersion": 3, "filename": filename, "revisions": list(revisions)}


class OfficialLineageBackfillTests(unittest.TestCase):
    def fixture(self):
        documents = {
            "older.mp3": document("older.mp3", revision(["old", "unrelated"], "The Troubador", note="retained")),
            "alias.mp3": document("alias.mp3", revision(["old"], "The Troubador")),
            "official.mp3": document("official.mp3", revision(["authority"], "The Troubadour")),
            "inherited.mp3": document("inherited.mp3", revision(["other"], "The Troubadour")),
        }
        plan = {
            "schemaVersion": 1, "baseCommit": "base", "excludedEntitySubstitutions": [],
            "unprovenHashesExcluded": ["unrelated"],
            "corrections": [{"sha256": "old", "previousText": "The Troubador", "text": "The Troubadour",
                             "filenames": ["older.mp3", "alias.mp3"], "kind": "wording/spelling"}],
            "groups": [{"sha256": ["old", "authority"], "text": "The Troubadour", "officialDestinations": [
                {"filename": "official.mp3", "sha256": "authority", "text": "The Troubadour"}]}],
        }
        return documents, plan

    def test_restores_destination_and_all_aliases_without_changing_unrelated_members(self):
        documents, plan = self.fixture()
        untouched = copy.deepcopy(documents)
        changed, report = plan_documents(documents, plan)
        self.assertEqual(documents, untouched)
        self.assertNotIn("inherited.mp3", changed)
        self.assertEqual(changed["official.mp3"]["revisions"], [revision(["authority", "old"], "The Troubadour")])
        self.assertEqual(changed["older.mp3"]["revisions"], [revision(["old"], "The Troubadour", note="retained"),
                                                              revision(["unrelated"], "The Troubador", note="retained")])
        self.assertEqual(changed["alias.mp3"]["revisions"][0]["text"], "The Troubadour")
        self.assertEqual(report["statistics"]["officialHashMembershipsAdded"], 1)
        self.assertEqual(report["statistics"]["changedExistingOccurrencesByKind"], {"wording/spelling": 2})
        rerun, second_report = plan_documents({**documents, **changed}, plan)
        self.assertEqual(rerun, {})
        self.assertEqual(second_report["statistics"]["officialHashMembershipsAdded"], 0)

    def test_same_wording_link_retains_both_original_files(self):
        documents, plan = self.fixture()
        plan["corrections"] = []
        plan["groups"][0]["sha256"] = ["other", "authority"]
        changed, _ = plan_documents(documents, plan)
        self.assertEqual(set(changed), {"official.mp3"})
        self.assertEqual(changed["official.mp3"]["revisions"][0]["sha256"], ["authority", "other"])

    def test_drift_and_conflicting_authorities_fail_before_mutation(self):
        for drift in ("alias", "authority", "group", "missing_alias", "extra_alias"):
            with self.subTest(drift=drift):
                documents, plan = self.fixture()
                if drift == "alias": documents["alias.mp3"]["revisions"][0]["text"] = "Changed wording"
                if drift == "authority": documents["official.mp3"]["revisions"][0]["text"] = "Changed official"
                if drift == "group":
                    plan["groups"].append({**plan["groups"][0], "text": "Contradiction"})
                if drift == "missing_alias": del documents["alias.mp3"]
                if drift == "extra_alias": documents["unexpected.mp3"] = document("unexpected.mp3", revision(["old"], "The Troubador"))
                untouched = copy.deepcopy(documents)
                with self.assertRaises(ValueError): plan_documents(documents, plan)
                self.assertEqual(documents, untouched)

    def test_excluded_hashes_cannot_be_corrected_or_added(self):
        for kind in ("unproven", "entity"):
            with self.subTest(kind=kind):
                documents, plan = self.fixture()
                if kind == "unproven": plan["unprovenHashesExcluded"].append("old")
                else: plan["excludedEntitySubstitutions"].append({"sha256": "old"})
                with self.assertRaises(ValueError): plan_documents(documents, plan)

    def test_destination_hash_already_in_old_revision_is_coalesced(self):
        documents, plan = self.fixture()
        documents["official.mp3"]["revisions"].append(revision(["old"], "The Troubador"))
        plan["corrections"][0]["filenames"].append("official.mp3")
        changed, report = plan_documents(documents, plan)
        self.assertEqual(changed["official.mp3"]["revisions"], [revision(["authority", "old"], "The Troubadour")])
        self.assertEqual(report["statistics"]["officialHashMembershipsAdded"], 0)


if __name__ == "__main__":
    unittest.main()
