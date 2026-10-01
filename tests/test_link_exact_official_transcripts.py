import copy
import unittest

from tools.link_exact_official_transcripts import plan_documents


class ExactOfficialHashLinkTests(unittest.TestCase):
    def documents(self):
        return {
            "old.mp3": {"schemaVersion": 3, "filename": "old.mp3", "revisions": [
                {"sha256": ["a" * 64], "text": "Seven's in mid.", "source": "generated", "model": "test"},
            ]},
            "official.mp3": {"schemaVersion": 3, "filename": "official.mp3", "revisions": [
                {"sha256": ["b" * 64], "text": "Seven's in mid!", "source": "official"},
            ]},
        }

    def test_links_source_hash_in_official_group_and_preserves_original_file(self):
        documents = self.documents()
        original = copy.deepcopy(documents)
        changed, report = plan_documents(documents, {"line": list(documents)})
        self.assertEqual(changed["old.mp3"]["revisions"], [
            {"sha256": ["a" * 64], "text": "Seven's in mid!", "source": "official"},
        ])
        self.assertEqual(changed["official.mp3"]["revisions"], [
            {"sha256": ["a" * 64, "b" * 64], "text": "Seven's in mid!", "source": "official"},
        ])
        self.assertEqual(documents, original)
        self.assertEqual(report["statistics"]["officialHashMembershipsAdded"], 1)
        repeated, _ = plan_documents({**documents, **changed}, {"line": list(documents)})
        self.assertEqual(repeated, {})

    def test_does_not_link_identical_text_across_unrelated_lineages(self):
        documents = self.documents()
        changed, _ = plan_documents(documents, {"old": ["old.mp3"], "official": ["official.mp3"]})
        self.assertEqual(changed, {})

    def test_does_not_merge_wording_differences(self):
        documents = self.documents()
        documents["old.mp3"]["revisions"][0]["text"] = "Seven is in mid!"
        changed, _ = plan_documents(documents, {"line": list(documents)})
        self.assertEqual(changed, {})

    def test_ambiguous_official_punctuation_is_left_unchanged(self):
        documents = self.documents()
        documents["other.mp3"] = {"schemaVersion": 3, "filename": "other.mp3", "revisions": [
            {"sha256": ["c" * 64], "text": "SEVEN'S IN MID?", "source": "official"},
        ]}
        changed, report = plan_documents(documents, {"line": list(documents)})
        self.assertEqual(changed, {})
        self.assertEqual(report["statistics"]["ambiguousGroupsSkipped"], 1)

    def test_unselected_hash_in_source_group_is_preserved_when_alias_is_split(self):
        documents = self.documents()
        documents["alias.mp3"] = {"schemaVersion": 3, "filename": "alias.mp3", "revisions": [
            {"sha256": ["a" * 64, "c" * 64], "text": "Seven's in mid.", "source": "manual"},
        ]}
        changed, _ = plan_documents(documents, {"line": ["old.mp3", "official.mp3"], "alias": ["alias.mp3"]})
        self.assertEqual(changed["alias.mp3"]["revisions"], [
            {"sha256": ["a" * 64], "text": "Seven's in mid!", "source": "official"},
            {"sha256": ["c" * 64], "text": "Seven's in mid.", "source": "manual"},
        ])

    def test_a_conflicting_existing_official_alias_blocks_that_hash(self):
        documents = self.documents()
        documents["alias.mp3"] = {"schemaVersion": 3, "filename": "alias.mp3", "revisions": [
            {"sha256": ["a" * 64], "text": "Different official words.", "source": "official"},
        ]}
        changed, report = plan_documents(documents, {"line": ["old.mp3", "official.mp3"], "alias": ["alias.mp3"]})
        self.assertEqual(changed, {})
        self.assertEqual(report["blockedHashes"], ["a" * 64])


if __name__ == "__main__":
    unittest.main()
