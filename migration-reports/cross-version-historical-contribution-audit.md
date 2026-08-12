# Cross-version historical contribution audit

> Review only: this report did not modify transcripts or categories.

## Dataset and grain

- Published version manifests scanned: **17**
- Historical epochs entering this diagnostic: **329**
- Previously resolved or officially protected epochs excluded: **193**
- Candidate grain: one epoch, one transcript path, one audio SHA, and one exact text state.

## Checks performed

- Filename coverage across every version listed by the live root manifest.
- Exact normalized text-state matching against SHA-addressed target revisions.
- Path, SHA, state-position, and history uniqueness.
- Official-source protection and current-HEAD conflict detection.
- Temporal consistency with the release active when the correction was committed.

## Findings

| Status | Epochs | Share |
| --- | ---: | ---: |
| `no_exact_state_across_manifests` | 303 | 92.1% |
| `not_in_any_manifest` | 10 | 3.0% |
| `ambiguous_exact_revision` | 6 | 1.8% |
| `candidate_historical_version_review` | 6 | 1.8% |
| `protected_official_match` | 3 | 0.9% |
| `ambiguous_path` | 1 | 0.3% |

## Newly recoverable review candidates

| Legacy path | Author/date | Before | After | SHA | Matching versions | Action |
| --- | --- | --- | --- | --- | --- | --- |
| `data/gigawatt_ping_see_astro_on_roof.mp3.json` | Sloan (2025-10-17T15:16:11-04:00) | Holidays on the roof! | Holliday's on the roof! | `c6be3915437c` | `map-rework, four-heros, winter-update, raven-park, matchmaking-update` | `mark_manual` |
| `data/haze_ping_see_synth_01.mp3.json` | Mcall (2025-08-27T21:23:41-04:00) | Icy Pocket. | I see Pocket. | `8bf77be9372a` | `ranked-update, mirage-update` | `mark_manual` |
| `data/kelvin_ping_see_gigawatt_01.mp3.json` | Mcall (2025-08-27T21:40:43-04:00) | I see seven! | I see Seven! | `6d3a1497a1c3` | `hero-labs-update, ranked-update, mirage-update, 247-matchmaking, wall-jump-update, post-shiv-update, deadlock-shiv, deadlock-public-access, deadlock-base` | `replay_and_mark_manual` |
| `data/mirage_desperation_power3_04.mp3.json` | Miles Calloway (2026-01-20T23:51:11-05:00) | For the dune! | For the Djinn! | `1c373e68af66` | `map-rework, four-heros, winter-update, raven-park, matchmaking-update` | `mark_manual` |
| `data/mirage_ping_see_gigawatt_01.mp3.json` | Mcall (2025-08-27T21:40:43-04:00) | I see seven! | I see Seven! | `1357f63f961b` | `map-rework, four-heros, winter-update, raven-park, matchmaking-update` | `replay_and_mark_manual` |
| `data/yamato_ping_see_lash_01.mp3.json` | Mcall (2025-08-27T21:23:41-04:00) | Icy lush. | I see lush. | `c7dc468e5179` | `map-rework, four-heros, winter-update, raven-park, matchmaking-update, hero-labs-update, ranked-update` | `mark_manual` |

## Risk and recommendation

Manifest integrity checks found **0** conflicting filename mappings and **0** invalid audio keys.

These candidates have strong structural evidence but a temporal mismatch:
their recording SHA appears only in snapshots other than the version active
when the correction was committed. Review the audio/text intent before any
application. Official, ambiguous, missing, and current-manual conflicts must
not be applied automatically. Candidate confidence is high for identity and
text lineage but medium overall until the correction's semantic intent is
confirmed.
