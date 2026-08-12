# Cross-version current contribution audit

> Review only: this report did not modify transcripts or categories.

## Dataset and grain

- OGNB active-SHA text divergences: **15**
- Published version manifests scanned: **17**
- Candidate grain: one correction, one transcript path, one older audio SHA, and one exact text state.

## Findings

| Status | Corrections | Share |
| --- | ---: | ---: |
| `candidate_cross_version_current_review` | 13 | 86.7% |
| `ambiguous_exact_revision` | 2 | 13.3% |

## Unique older-SHA review candidates

| Legacy path | Author/date | Before | After | SHA | Matching versions | Action |
| --- | --- | --- | --- | --- | --- | --- |
| `data/bookworm_ping_gigawatt_check_items.mp3.json` | Valvify (2026-06-18T12:45:37+01:00) | Check out what's 7-Bot. | Check out what Seven bought. | `ec4f4d33ff91` | `shop-rework` | `mark_manual` |
| `data/gigawatt_ally_astro_lasso_victim_01.mp3.json` | Sloan (2025-10-17T15:16:11-04:00) | Hollidaytropgum | Holliday trapped them. | `f6f57e731dc2` | `hero-labs-update, ranked-update, mirage-update, 247-matchmaking, wall-jump-update` | `mark_manual` |
| `data/gigawatt_ping_atlas_was_here.mp3.json` | Sloan (2025-10-17T15:57:02-04:00) | Hey Bruce, what's he got? | Abrams was here. | `3cb6fda9a0a9` | `map-rework, four-heros, winter-update, raven-park, matchmaking-update` | `mark_manual` |
| `data/gigawatt_ping_ignore_viscous.mp3.json` | retrogradual (2025-10-17T14:22:57-04:00) | Ignore viscous | Ignore Viscous. | `bf0c3a4a10c7` | `hero-labs-update, ranked-update, mirage-update, 247-matchmaking, wall-jump-update` | `mark_manual` |
| `data/gigawatt_ping_with_atlas.mp3.json` | Sloan (2025-10-17T15:57:02-04:00) | I'm with you Abrams. | I'm with you, Abrams. | `ddca32d251c7` | `hero-labs-update, ranked-update, mirage-update, 247-matchmaking, wall-jump-update` | `mark_manual` |
| `data/krill_ping_stun_gigawatt_01.mp3.json` | Mcall (2025-08-27T21:40:43-04:00) | Stun seven! | Stun Seven! | `bb93410b6483` | `matchmaking-update` | `replay_and_mark_manual` |
| `data/priest_ping_defend_blue_02.mp3.json` | RatHugs (2026-02-06T12:41:15-05:00) | DEFEND BROADWAY | Defend Broadway! | `f4d1478e21ec` | `six-hero-update, shop-rework` | `mark_manual` |
| `data/priest_ping_saw_bebop.mp3.json` | RatHugs (2026-02-06T12:29:32-05:00) | I SAW BEBOP | I saw Bebop! | `5f5513c7dd2b` | `six-hero-update, shop-rework` | `mark_manual` |
| `data/priest_ping_stun_chrono_01.mp3.json` | RatHugs (2026-02-06T12:05:41-05:00) | STUN PARADOX | Stun Paradox! | `bfd45da9104f` | `six-hero-update, shop-rework` | `mark_manual` |
| `data/vampirebat_ping_ignore_orion.mp3.json` | Mugi (2026-01-29T13:25:52-08:00) | Ignore it, Grey Talon! | Ignore Grey Talon! | `ac6840df4f37` | `shop-rework` | `replay_and_mark_manual` |
| `data/vampirebat_ping_viper_dead.mp3.json` | Mcall (2025-08-27T22:24:34-04:00) | Viper is dead. | Vyper is dead. | `6302452e6b16` | `shop-rework` | `replay_and_mark_manual` |
| `data/viper_ping_lash_check_items.mp3.json` | Valvify (2026-06-18T12:45:37+01:00) | Check out with LashBot. | Check out what Lash bought. | `3532213e84fb` | `hero-labs-update` | `mark_manual` |
| `data/viper_ping_saw_atlas.mp3.json` | Mcall (2025-08-27T21:40:43-04:00) | I saw abrams! | I saw Abrams! | `18eebf28aa0b` | `hero-labs-update` | `mark_manual` |

## Interpretation

The correction date selected OGNB's active SHA for the first pass, but the
legacy repository did not store an audio hash. Every divergence here has an
exact state on at least one older SHA. Unique generated matches are suitable
for explicit review; multiple-SHA matches remain ambiguous. No semantic text
transfer is needed for this set.
