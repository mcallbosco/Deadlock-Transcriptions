from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_versioned_historical_contributions import (  # noqa: E402
    apply_changes,
    plan_changes,
)
from apply_semantic_delta_contributions import (  # noqa: E402
    plan_changes as plan_semantic_delta_changes,
)
from apply_reviewed_low_confidence_contributions import (  # noqa: E402
    plan_changes as plan_reviewed_low_confidence_changes,
)
from apply_cross_version_historical_contributions import (  # noqa: E402
    plan_changes as plan_cross_version_changes,
)
from audit_cross_version_historical_contributions import (  # noqa: E402
    classify_records as classify_cross_version_records,
)
from audit_latest_version_contributions import build_manifest_index  # noqa: E402
from audit_semantic_delta_contributions import (  # noqa: E402
    analyze_record as analyze_semantic_record,
    corrected_equivalent,
    exact_delta_proposal,
)
from audit_versioned_historical_contributions import (  # noqa: E402
    classify_records,
    select_release,
)


def event(commit: str, date: str, before: str, after: str) -> dict[str, object]:
    return {
        "legacyCommit": commit,
        "legacySubject": "Correct line",
        "author": {"name": "Alice", "email": "alice@example.com", "date": date},
        "beforeFullText": before,
        "afterFullText": after,
        "changedSegments": [{"index": 0, "before": before, "after": after}],
    }


def epoch(name: str, events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "epochId": f"data/{name}.mp3.json#0",
        "legacyPath": f"data/{name}.mp3.json",
        "legacyPathDeleted": False,
        "initialText": events[0]["beforeFullText"],
        "finalText": events[-1]["afterFullText"],
        "events": events,
    }


def target(name: str, text: str, source: str, sha: str) -> dict[str, object]:
    revision: dict[str, object] = {"sha256": sha, "text": text, "source": source}
    if source == "generated":
        revision["model"] = "test-model"
    return {
        "path": f"transcripts/hero/{name}.mp3.json",
        "filename": f"hero/{name}.mp3",
        "revisions": [revision],
    }


class VersionedHistoricalAuditTests(unittest.TestCase):
    def test_latest_release_window_may_be_open_ended(self) -> None:
        release = select_release(
            {
                "schemaVersion": 1,
                "dateBasis": "git-author-offset-calendar-date",
                "versions": [
                    {
                        "id": "latest",
                        "activeFrom": "2026-01-22",
                        "activeUntilExclusive": None,
                        "releaseEvidenceUrl": "https://example.com/release",
                    }
                ],
            },
            "latest",
        )

        self.assertEqual(release["activeFrom"], date(2026, 1, 22))
        self.assertIsNone(release["activeUntilExclusive"])

    def test_release_window_manifest_hash_and_exact_state_are_all_required(self) -> None:
        names = ("replay", "marked", "official", "diverged", "outside", "boundary")
        hashes = {name: str(index) * 64 for index, name in enumerate(names, 1)}
        manifest = [
            {
                "filename": f"hero/{name}.mp3",
                "audioKey": f"sha256/{sha[:2]}/{sha}.mp3",
            }
            for name, sha in hashes.items()
        ]
        manifest_index, _ = build_manifest_index(json.dumps(manifest).encode())
        historical = {
            "records": [
                epoch("replay", [event("a" * 40, "2025-08-22T12:00:00-04:00", "Wrong", "Right")]),
                epoch("marked", [event("b" * 40, "2025-09-01T12:00:00-04:00", "Bad", "Good")]),
                epoch("official", [event("c" * 40, "2025-10-01T12:00:00-04:00", "No", "Yes")]),
                epoch("diverged", [event("d" * 40, "2025-11-01T12:00:00-04:00", "Old", "New")]),
                epoch("outside", [event("e" * 40, "2026-02-01T12:00:00-05:00", "A", "B")]),
                epoch("boundary", [event("f" * 40, "2025-08-18T23:00:00-04:00", "A", "B")]),
            ]
        }
        target_index = {
            "replay.mp3.json": [target("replay", "Wrong", "generated", hashes["replay"])],
            "marked.mp3.json": [target("marked", "Good", "generated", hashes["marked"])],
            "official.mp3.json": [target("official", "No", "official", hashes["official"])],
            "diverged.mp3.json": [target("diverged", "Different", "generated", hashes["diverged"])],
            "outside.mp3.json": [target("outside", "A", "generated", hashes["outside"])],
            "boundary.mp3.json": [target("boundary", "A", "generated", hashes["boundary"])],
        }
        release = {
            "id": "six-hero-update",
            "activeFrom": date(2025, 8, 18),
            "activeUntilExclusive": date(2026, 1, 22),
        }

        records = classify_records(historical, target_index, manifest_index, release)
        statuses = {record["legacyPath"]: record["status"] for record in records}

        self.assertEqual(statuses["data/replay.mp3.json"], "candidate_replay")
        self.assertEqual(statuses["data/marked.mp3.json"], "candidate_mark_manual")
        self.assertEqual(statuses["data/official.mp3.json"], "protected_official")
        self.assertEqual(statuses["data/diverged.mp3.json"], "review_version_text_diverged")
        self.assertEqual(statuses["data/outside.mp3.json"], "outside_selected_version")
        self.assertEqual(statuses["data/boundary.mp3.json"], "release_boundary_date_review")


class CrossVersionHistoricalAuditTests(unittest.TestCase):
    def test_cross_version_matches_remain_review_only_and_check_current_head(self) -> None:
        names = ("candidate", "official", "conflict", "diverged")
        hashes = {name: str(index) * 64 for index, name in enumerate(names, 1)}
        records = [
            epoch(
                name,
                [event(name[0] * 40, "2025-10-01T12:00:00-04:00", "Wrong", "Right")],
            )
            for name in names
        ]
        target_index = {
            "candidate.mp3.json": [target("candidate", "Wrong", "generated", hashes["candidate"])],
            "official.mp3.json": [target("official", "Wrong", "official", hashes["official"])],
            "conflict.mp3.json": [target("conflict", "Wrong", "generated", hashes["conflict"])],
            "diverged.mp3.json": [target("diverged", "Different", "generated", hashes["diverged"])],
        }
        current_documents = {
            value[0]["path"]: value[0] for value in target_index.values()
        }
        current_documents["transcripts/hero/conflict.mp3.json"] = target(
            "conflict", "Other manual correction", "manual", hashes["conflict"]
        )
        catalog = {
            f"hero/{name}.mp3": {
                sha: [
                    {
                        "versionId": "older-version",
                        "versionLabel": "Older Version",
                        "versionOrder": 2,
                        "manifestEvidence": [],
                    }
                ]
            }
            for name, sha in hashes.items()
        }
        assignments = {
            record["epochId"]: [
                {"versionId": "six-hero-update", "status": "review_version_text_diverged"}
            ]
            for record in records
        }

        results = classify_cross_version_records(
            records, assignments, target_index, current_documents, catalog
        )
        statuses = {record["legacyPath"]: record["status"] for record in results}

        self.assertEqual(
            statuses["data/candidate.mp3.json"], "candidate_historical_version_review"
        )
        self.assertEqual(statuses["data/official.mp3.json"], "protected_official_match")
        self.assertEqual(statuses["data/conflict.mp3.json"], "conflict_current_manual")
        self.assertEqual(
            statuses["data/diverged.mp3.json"], "no_exact_state_across_manifests"
        )

    def test_approved_cross_version_candidate_plans_an_exact_generated_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/hero/line.mp3.json"
            path.parent.mkdir(parents=True)
            sha = "a" * 64
            document = {
                "schemaVersion": 2,
                "filename": "hero/line.mp3",
                "revisions": [
                    {
                        "sha256": sha,
                        "text": "Wrong",
                        "source": "generated",
                        "model": "test-model",
                    }
                ],
            }
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            correction = event(
                "a" * 40, "2025-10-01T12:00:00-04:00", "Wrong", "Right"
            )
            target_evidence = {
                "path": "transcripts/hero/line.mp3.json",
                "filename": "hero/line.mp3",
                "sha256": sha,
                "source": "generated",
                "originalText": "Wrong",
                "statePositions": [0],
                "manifestVersions": [{"versionId": "older-version"}],
                "proposedAction": "replay_and_mark_manual",
            }
            report = {
                "mode": "cross-version-historical-audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "reportOnly": True,
                    "officialRevisionsMutable": False,
                    "eligibleTargetSources": ["generated"],
                    "allRootManifestVersionsScanned": True,
                    "uniqueTranscriptPathRequired": True,
                    "uniqueAudioRevisionRequired": True,
                    "uniqueHistoryEpochRequired": True,
                    "exactTextAnchorRequired": True,
                    "currentHeadConflictCheckRequired": True,
                    "temporalMismatchMayAutoApply": False,
                    "fuzzyMatchingMayAutoApply": False,
                },
                "records": [
                    {
                        "status": "candidate_historical_version_review",
                        "epochId": "data/line.mp3.json#0",
                        "exactMatches": [target_evidence],
                        "selectedTarget": target_evidence,
                        "assignedReleaseResults": [
                            {"versionId": "six-hero-update", "status": "diverged"}
                        ],
                        "desiredText": "Right",
                        "attributionEvents": [correction],
                    }
                ],
            }

            changes = plan_cross_version_changes(repo, report)

            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0]["after"]["text"], "Right")
            self.assertEqual(changes[0]["after"]["source"], "manual")
            self.assertNotIn("model", changes[0]["after"])


class SemanticDeltaAuditTests(unittest.TestCase):
    def test_corrected_equivalent_ignores_nonsemantic_punctuation(self) -> None:
        self.assertTrue(corrected_equivalent("Stun abrams.", "Stun Abrams.", "Stun Abrams!"))
        self.assertFalse(corrected_equivalent("Stun abrams.", "Stun Abrams.", "Stone Abrams!"))

    def test_exact_delta_requires_all_outside_words_for_high_confidence(self) -> None:
        exact = exact_delta_proposal(
            "Vipers on the Roof.", "Vypers on the Roof.", "Vipers on the roof!"
        )
        partial = exact_delta_proposal(
            "They took our Shiv!", "They took out Shiv!", "They took our ship!"
        )

        self.assertEqual(exact["proposedText"], "Vypers on the roof!")
        self.assertTrue(exact["outsideTokensEquivalent"])
        self.assertEqual(partial["proposedText"], "They took out ship!")
        self.assertFalse(partial["outsideTokensEquivalent"])

    def test_semantic_analysis_never_promotes_partial_context_to_high(self) -> None:
        sha = "a" * 64
        record = {
            "epochId": "data/line.mp3.json#0",
            "legacyPath": "data/line.mp3.json",
            "legacyPathDeleted": True,
            "initialText": "They took our Shiv!",
            "finalText": "They took out Shiv!",
            "events": [
                event("a" * 40, "2025-10-01T12:00:00-04:00", "They took our Shiv!", "They took out Shiv!")
            ],
            "selectedTarget": {
                "path": "transcripts/hero/line.mp3.json",
                "filename": "hero/line.mp3",
                "sha256": sha,
                "source": "generated",
                "originalText": "They took our ship!",
            },
        }
        current = {
            "sha256": sha,
            "text": "They took our ship!",
            "source": "generated",
            "model": "test-model",
        }

        result = analyze_semantic_record(record, current)

        self.assertEqual(result["status"], "review_exact_delta_partial_context")
        self.assertEqual(result["confidence"], "medium")
        self.assertEqual(result["proposedText"], "They took out ship!")


class SemanticDeltaApplyTests(unittest.TestCase):
    def test_applies_reviewed_override_without_touching_official_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/bebop/ping/line.mp3.json"
            path.parent.mkdir(parents=True)
            selected_sha = "1" * 64
            official_sha = "2" * 64
            document = {
                "schemaVersion": 2,
                "filename": "bebop/ping/line.mp3",
                "revisions": [
                    {
                        "sha256": selected_sha,
                        "text": "Stan Abrams!",
                        "source": "generated",
                        "model": "test-model",
                    },
                    {
                        "sha256": official_sha,
                        "text": "Official line",
                        "source": "official",
                    },
                ],
            }
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            report = {
                "mode": "semantic-delta-audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "reportOnly": True,
                    "officialRevisionsMutable": False,
                    "eligibleTargetSources": ["generated"],
                    "noExactStateAcrossAnyManifestRequired": True,
                    "dateSelectedSixHeroShaRequired": True,
                    "currentHeadConflictCheckRequired": True,
                    "highConfidenceOutsideTokensMustAgree": True,
                    "semanticDeltaMayAutoApply": False,
                    "fuzzyMatchingMayAutoApply": False,
                },
                "records": [
                    {
                        "status": "candidate_corrected_equivalent",
                        "confidence": "high",
                        "epochId": "data/bebop_ping_stun_atlas_01.mp3.json#0",
                        "legacyPath": "data/bebop_ping_stun_atlas_01.mp3.json",
                        "events": [event("a" * 40, "2025-08-22T12:00:00-04:00", "Stan abrams", "Stan Abrams")],
                        "proposedAction": "mark_manual_preserve_v2_text",
                        "proposedText": "Stan Abrams!",
                        "selectedTarget": {
                            "path": "transcripts/bebop/ping/line.mp3.json",
                            "sha256": selected_sha,
                            "source": "generated",
                            "originalText": "Stan Abrams!",
                        },
                    }
                ],
            }
            decisions = {
                "schemaVersion": 1,
                "approval": {
                    "confidence": "high",
                    "statuses": sorted(
                        {
                            "candidate_corrected_equivalent",
                            "candidate_exact_delta_transfer",
                        }
                    ),
                    "candidateCount": 1,
                },
                "overrides": [
                    {
                        "legacyPath": "data/bebop_ping_stun_atlas_01.mp3.json",
                        "text": "Stun Abrams!",
                        "reason": "Reviewer correction.",
                    }
                ],
            }

            changes = plan_semantic_delta_changes(repo, report, decisions)
            apply_changes(changes)
            updated = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(updated["revisions"][0]["text"], "Stun Abrams!")
            self.assertEqual(updated["revisions"][0]["source"], "manual")
            self.assertNotIn("model", updated["revisions"][0])
            self.assertEqual(updated["revisions"][1], document["revisions"][1])

    def test_applies_only_reviewed_external_low_confidence_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/krill/line.mp3.json"
            path.parent.mkdir(parents=True)
            selected_sha = "3" * 64
            document = {
                "schemaVersion": 2,
                "filename": "krill/line.mp3",
                "revisions": [
                    {
                        "sha256": selected_sha,
                        "text": "I like pocket too!",
                        "source": "generated",
                        "model": "test-model",
                    }
                ],
            }
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            report = {
                "mode": "semantic-delta-audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "reportOnly": True,
                    "officialRevisionsMutable": False,
                    "eligibleTargetSources": ["generated"],
                    "noExactStateAcrossAnyManifestRequired": True,
                    "dateSelectedSixHeroShaRequired": True,
                    "currentHeadConflictCheckRequired": True,
                    "highConfidenceOutsideTokensMustAgree": True,
                    "semanticDeltaMayAutoApply": False,
                    "fuzzyMatchingMayAutoApply": False,
                },
                "records": [
                    {
                        "status": "review_low_semantic_similarity",
                        "confidence": "low",
                        "epochId": "data/krill_kill_synth_01.mp3.json#0",
                        "legacyPath": "data/krill_kill_synth_01.mp3.json",
                        "events": [
                            event(
                                "b" * 40,
                                "2025-10-31T11:39:01-04:00",
                                "I LIKED Pocket 2!",
                                "I LIKED Pocket too!",
                            )
                        ],
                        "finalText": "I LIKED Pocket too!",
                        "selectedTarget": {
                            "path": "transcripts/krill/line.mp3.json",
                            "sha256": selected_sha,
                            "source": "generated",
                            "originalText": "I like pocket too!",
                        },
                    }
                ],
            }
            report["records"][0]["events"][0]["author"] = {
                "name": "Jules",
                "email": "jules@example.com",
                "date": "2025-10-31T11:39:01-04:00",
            }
            decisions = {
                "schemaVersion": 1,
                "approval": {
                    "confidence": "low",
                    "status": "review_low_semantic_similarity",
                    "requiresExternalEvent": True,
                    "includeMixedUserExternalEpochs": True,
                    "excludedAuthorEmails": ["owner@example.com"],
                    "excludedAuthorIdentityContains": ["copilot"],
                    "candidateCount": 1,
                },
                "overrides": [
                    {
                        "legacyPath": "data/krill_kill_synth_01.mp3.json",
                        "text": "I liked Pocket too!",
                        "reason": "Reviewer correction.",
                    }
                ],
            }

            changes = plan_reviewed_low_confidence_changes(repo, report, decisions)
            apply_changes(changes)
            updated = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(updated["revisions"][0]["text"], "I liked Pocket too!")
            self.assertEqual(updated["revisions"][0]["source"], "manual")
            self.assertNotIn("model", updated["revisions"][0])

    def test_semantic_analysis_flags_suspicious_internal_capitalization(self) -> None:
        sha = "b" * 64
        record = {
            "epochId": "data/spanish.mp3.json#0",
            "legacyPath": "data/spanish.mp3.json",
            "legacyPathDeleted": True,
            "initialText": "Nadie amenaza a mis amigos!",
            "finalText": "Nadie aMinaza a mis amigos!",
            "events": [
                event(
                    "b" * 40,
                    "2025-10-01T12:00:00-04:00",
                    "Nadie amenaza a mis amigos!",
                    "Nadie aMinaza a mis amigos!",
                )
            ],
            "selectedTarget": {
                "path": "transcripts/hero/spanish.mp3.json",
                "filename": "hero/spanish.mp3",
                "sha256": sha,
                "source": "generated",
                "originalText": "Nadie amenaza a mis amigos.",
            },
        }
        current = {
            "sha256": sha,
            "text": "Nadie amenaza a mis amigos.",
            "source": "generated",
            "model": "test-model",
        }

        result = analyze_semantic_record(record, current)

        self.assertEqual(result["status"], "review_suspicious_delta_transfer")
        self.assertEqual(result["confidence"], "medium")


class VersionedHistoricalApplyTests(unittest.TestCase):
    def test_only_audited_generated_revision_is_changed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            path = repo / "transcripts/hero/line.mp3.json"
            path.parent.mkdir(parents=True)
            selected_sha = "1" * 64
            official_sha = "2" * 64
            document = {
                "schemaVersion": 2,
                "filename": "hero/line.mp3",
                "revisions": [
                    {
                        "sha256": selected_sha,
                        "text": "Wrong line",
                        "source": "generated",
                        "model": "test-model",
                    },
                    {
                        "sha256": official_sha,
                        "text": "Official line",
                        "source": "official",
                    },
                ],
            }
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            correction = event(
                "a" * 40,
                "2025-08-22T12:00:00-04:00",
                "Wrong line",
                "Correct line",
            )
            report = {
                "mode": "versioned-historical-audit-only",
                "target": {"prefix": "transcripts"},
                "policy": {
                    "officialRevisionsMutable": False,
                    "eligibleTargetSources": ["generated"],
                    "selectedReleaseRequired": True,
                    "crossVersionReplayAllowed": False,
                    "uniqueVersionHashRequired": True,
                    "uniqueHistoryEpochRequired": True,
                    "exactTextAnchorRequired": True,
                    "fuzzyMatchingMayAutoApply": False,
                },
                "records": [
                    {
                        "status": "candidate_replay",
                        "epochId": "data/line.mp3.json#0",
                        "finalText": "Correct line",
                        "replayEvents": [correction],
                        "selectedTarget": {
                            "path": "transcripts/hero/line.mp3.json",
                            "sha256": selected_sha,
                            "source": "generated",
                            "originalText": "Wrong line",
                            "proposedAction": "replay_and_mark_manual",
                        },
                    }
                ],
            }

            changes = plan_changes(repo, report)
            apply_changes(changes)
            updated = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(updated["revisions"][0]["text"], "Correct line")
            self.assertEqual(updated["revisions"][0]["source"], "manual")
            self.assertNotIn("model", updated["revisions"][0])
            self.assertEqual(updated["revisions"][1], document["revisions"][1])


if __name__ == "__main__":
    unittest.main()
