from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from tools.content_tags import tag_conflict_errors

from tools.reconcile_correlated_punctuation import (
    ReconciliationError,
    build_review_lineages,
    find_candidates,
    main,
    resolve_candidates,
    rewrite_documents,
)


def revision(digit: str, text: str, source: str, model: str | None = None):
    value = {"sha256": [digit * 64], "text": text, "source": source}
    if model:
        value["model"] = model
    return value


class CorrelatedPunctuationTests(unittest.TestCase):
    def documents(self, left, right):
        return {
            "old.mp3": {"schemaVersion": 3, "filename": "old.mp3", "revisions": [left]},
            "new.mp3": {"schemaVersion": 3, "filename": "new.mp3", "revisions": [right]},
        }

    def candidates(self, documents):
        return find_candidates(
            [["old.mp3", "new.mp3"]], documents, {"1" * 64, "2" * 64}
        )

    def test_apply_blocks_cross_file_tag_conflicts_before_writing(self):
        left = revision("1", "Example.", "official")
        left["tags"] = ["insults"]
        documents = self.documents(left, revision("2", "example", "generated"))
        original = copy.deepcopy(documents)
        correlations = [["old.mp3", "new.mp3"]]
        self.assertEqual(tag_conflict_errors(documents, correlations), [])
        with (
            mock.patch("tools.reconcile_correlated_punctuation.load_official_catalog", return_value=({"1" * 64, "2" * 64}, {})),
            mock.patch("tools.reconcile_correlated_punctuation.build_review_lineages", return_value=correlations),
            mock.patch("tools.reconcile_correlated_punctuation.load_documents", return_value=documents),
            mock.patch("pathlib.Path.read_text", return_value=json.dumps({"correlations": correlations})),
            mock.patch("pathlib.Path.write_text") as write,
        ):
            with self.assertRaisesRegex(ReconciliationError, "Conflicting content tags in logical group"):
                main(["--apply", "--approve-reconciliation"])
        write.assert_not_called()
        self.assertEqual(documents, original)

    def test_reconciliation_accepts_equivalent_tags_across_aliases(self):
        left = revision("1", "Example.", "official")
        right = revision("2", "example", "generated")
        left["tags"], right["tags"] = ["nicknames", "insults"], ["insults", "nicknames"]
        documents = self.documents(left, right)
        targets, _ = resolve_candidates(self.candidates(documents), {})
        correlations = [["old.mp3", "new.mp3"]]
        changed = rewrite_documents(documents, targets, correlations=correlations)
        self.assertEqual(changed["new.mp3"]["revisions"][0]["tags"], ["insults", "nicknames"])
        self.assertEqual(tag_conflict_errors({**documents, **changed}, correlations), [])

    def test_reconciliation_keeps_unrelated_matching_text_independent(self):
        left = revision("1", "Example.", "official")
        left["tags"] = ["insults"]
        documents = self.documents(left, revision("2", "example", "generated"))
        changed = rewrite_documents(documents, {"2" * 64: {"text": "Example.", "source": "manual"}}, correlations=[])
        self.assertNotIn("tags", changed["new.mp3"]["revisions"][0])

    def test_official_text_and_provenance_win(self):
        documents = self.documents(
            revision("1", "Hello, Abrams.", "generated", "model"),
            revision("2", "Hello Abrams!", "official"),
        )
        candidates = self.candidates(documents)
        targets, unresolved = resolve_candidates(candidates, {})
        changed = rewrite_documents(documents, targets, correlations=[["old.mp3", "new.mp3"]])
        self.assertEqual(unresolved, [])
        self.assertEqual(
            changed["old.mp3"]["revisions"],
            [{"sha256": ["1" * 64], "text": "Hello Abrams!", "source": "official"}],
        )

    def test_review_lineages_include_transitive_sha_aliases(self):
        first = "1" * 64
        second = "2" * 64
        lineages = build_review_lineages(
            {
                first: {"old.mp3", "bridge.mp3"},
                second: {"bridge.mp3", "extra.mp3"},
                "3" * 64: {"unrelated.mp3"},
                "4" * 64: {"renamed.mp3"},
            },
            [["old.mp3", "renamed.mp3"]],
        )
        self.assertEqual(
            lineages,
            [["bridge.mp3", "extra.mp3", "old.mp3", "renamed.mp3"]],
        )

    def test_manual_beats_generated(self):
        documents = self.documents(
            revision("1", "Stop that brat.", "generated"),
            revision("2", "Stop that brat!", "manual"),
        )
        candidates = self.candidates(documents)
        targets, unresolved = resolve_candidates(candidates, {})
        self.assertEqual(unresolved, [])
        self.assertEqual(targets["1" * 64]["source"], "manual")

    def test_generated_only_requires_review_and_becomes_manual(self):
        documents = self.documents(
            revision("1", "Wake up, Holliday.", "generated", "one"),
            revision("2", "Wake up, Holliday!", "generated", "two"),
        )
        candidates = self.candidates(documents)
        targets, unresolved = resolve_candidates(candidates, {})
        self.assertEqual(targets, {})
        self.assertEqual(unresolved, [candidates[0]["id"]])
        targets, unresolved = resolve_candidates(
            candidates, {candidates[0]["id"]: "Wake up, Holliday!"}
        )
        changed = rewrite_documents(documents, targets, correlations=[["old.mp3", "new.mp3"]])
        self.assertEqual(unresolved, [])
        self.assertEqual(changed["old.mp3"]["revisions"][0]["source"], "manual")
        self.assertNotIn("model", changed["old.mp3"]["revisions"][0])

    def test_same_rank_manual_conflict_requires_review(self):
        documents = self.documents(
            revision("1", "Vindicta, I can heal ya!", "manual"),
            revision("2", "Vindicta I can heal ya.", "manual"),
        )
        candidates = self.candidates(documents)
        _, unresolved = resolve_candidates(candidates, {})
        self.assertEqual(unresolved, [candidates[0]["id"]])

    def test_different_wording_is_not_a_candidate(self):
        documents = self.documents(
            revision("1", "Do not stop.", "generated"),
            revision("2", "Don't stop.", "official"),
        )
        self.assertEqual(self.candidates(documents), [])

    def test_review_cannot_change_wording(self):
        documents = self.documents(
            revision("1", "Stop that brat.", "generated"),
            revision("2", "Stop that brat!", "generated"),
        )
        candidates = self.candidates(documents)
        with self.assertRaises(ReconciliationError):
            resolve_candidates(candidates, {candidates[0]["id"]: "Stop this brat!"})

    def test_only_official_hashes_are_rewritten(self):
        inactive = "3" * 64
        left = revision("1", "Hello.", "generated")
        left["sha256"].append(inactive)
        documents = self.documents(left, revision("2", "Hello!", "manual"))
        candidates = self.candidates(documents)
        targets, _ = resolve_candidates(candidates, {})
        changed = rewrite_documents(documents, targets, correlations=[["old.mp3", "new.mp3"]])
        by_text = {item["text"]: item for item in changed["old.mp3"]["revisions"]}
        self.assertEqual(by_text["Hello!"]["sha256"], ["1" * 64])
        self.assertEqual(by_text["Hello."]["sha256"], [inactive])

    def test_apply_is_idempotent(self):
        documents = self.documents(
            revision("1", "Hello.", "generated"),
            revision("2", "Hello!", "official"),
        )
        candidates = self.candidates(documents)
        targets, _ = resolve_candidates(candidates, {})
        changed = rewrite_documents(documents, targets, correlations=[["old.mp3", "new.mp3"]])
        merged = {**documents, **changed}
        self.assertEqual(self.candidates(merged), [])
        self.assertEqual(
            resolve_candidates([], {candidates[0]["id"]: "Hello!"}), ({}, [])
        )
        self.assertEqual(rewrite_documents(merged, {}, correlations=[["old.mp3", "new.mp3"]]), {})


if __name__ == "__main__":
    unittest.main()
