# Six Hero semantic-delta contribution audit

> Review only: this report did not modify transcripts or categories.

## Dataset and grain

- Six Hero active-SHA divergences: **318**
- Epochs with exact evidence on another SHA, or a protected/ambiguous resolution: **15**
- Epochs with no exact state on any published SHA: **303**
- Proposal grain: one historical correction epoch and one date-selected Six Hero SHA.

## Checks performed

- Confirmed each epoch has no exact state across all 17 published manifests.
- Rechecked the selected SHA against the current branch and protected official/manual sources.
- Compared lexical similarity before and after the legacy correction.
- Allowed a high-confidence transfer only when corrected lexical content already matches, or one exact edit span is unique and all outside tokens agree.

## Findings

| Status | Epochs | Share | Confidence |
| --- | ---: | ---: | --- |
| `review_low_semantic_similarity` | 175 | 57.8% | low |
| `candidate_corrected_equivalent` | 41 | 13.5% | high |
| `review_near_semantic_match` | 35 | 11.6% | medium |
| `candidate_exact_delta_transfer` | 30 | 9.9% | high |
| `review_exact_delta_partial_context` | 21 | 6.9% | medium |
| `review_suspicious_delta_transfer` | 1 | 0.3% | medium |

## High-confidence proposals

| Legacy path | v1 before | v1 after | v2 active | Proposal | Action |
| --- | --- | --- | --- | --- | --- |
| `data/bebop_ping_see_vampirebat_on_bridge.mp3.json` | MENA'S ON THE BRIDGE! | Mina'S ON THE BRIDGE! | Mina's on the bridge! | Mina's on the bridge! | `mark_manual_preserve_v2_text` |
| `data/bebop_ping_stun_atlas_01.mp3.json` | Stan abrams | Stan Abrams | Stan Abrams! | Stan Abrams! | `mark_manual_preserve_v2_text` |
| `data/bookworm_ping_careful_doorman_02.mp3.json` | Careful, doorman! | Careful, Doorman! | Careful, Doorman. | Careful, Doorman. | `mark_manual_preserve_v2_text` |
| `data/doorman_ping_see_astro.mp3.json` | Icy Holliday! | I see Holliday! | I see Holliday. | I see Holliday. | `mark_manual_preserve_v2_text` |
| `data/doorman_ping_see_kelvin_01.mp3.json` | Icy Kelvin | I see Kelvin | I see Kelvin. | I see Kelvin. | `mark_manual_preserve_v2_text` |
| `data/doorman_ping_see_slork_01.mp3.json` | Icy Fathom | I see Fathom | I see fathom. | I see fathom. | `mark_manual_preserve_v2_text` |
| `data/drifter_kill_forge_02.mp3.json` | A Killdeer Engineer. | I killed the Engineer. | I killed the engineer. | I killed the engineer. | `mark_manual_preserve_v2_text` |
| `data/drifter_kill_magician_01.mp3.json` | Die sinclair! | Die Sinclair! | Die Sinclair. | Die Sinclair. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_doorman_03.mp3.json` | Care for Dormin? | Careful Doorman. | Careful, Doorman. | Careful, Doorman. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_hornet_02.mp3.json` | Care for Vindicta! | Careful Vindicta! | Careful, Vindicta. | Careful, Vindicta. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_krill_03.mp3.json` | Be careful, Krill! | Careful, Krill! | careful, krill. | careful, krill. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_magician_02.mp3.json` | Care for Sinclair? | Careful, Sinclair! | Careful Sinclair. | Careful Sinclair. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_magician_03.mp3.json` | Be careful, Sinclair! | Careful, Sinclair! | Careful, Sinclair. | Careful, Sinclair. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_warden_03.mp3.json` | Care for Warden? | Careful, Warden! | Careful, Warden. | Careful, Warden. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_yamato_02.mp3.json` | Care for Yamato? | Careful Yamato! | Careful, Yamato. | Careful, Yamato. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_careful_yamato_03.mp3.json` | Careful yamato! | Careful, Yamato! | Careful, Yamato. | Careful, Yamato. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_ignore_vampirebat.mp3.json` | IGNORE MENA | IGNORE Mina | Ignore Mina. | Ignore Mina. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_nano_on_top_of_mid.mp3.json` | Catacombs on top of mid! | Calico's on top of mid! | Calico's on top of mid. | Calico's on top of mid. | `mark_manual_preserve_v2_text` |
| `data/drifter_ping_priest_under_garage.mp3.json` | Venetus under da garage! | Venator's under the garage! | Venator's under the garage. | Venator's under the garage. | `mark_manual_preserve_v2_text` |
| `data/ghost_ping_see_bookworm_01_alt.mp3.json` | Icy Page. | I see Page. | I see page. | I see page. | `mark_manual_preserve_v2_text` |
| `data/gigawatt_enemy_bebop_kill_mid_laser_01.mp3.json` | YOU'RE TOO SLOW, BEEBOP! | YOU'RE TOO SLOW, Bebop! | You're too slow, Bebop! | You're too slow, Bebop! | `mark_manual_preserve_v2_text` |
| `data/gigawatt_kill_synth_02.mp3.json` | Learn from your betters, pocket! | Learn from your betters, Pocket! | Learn from your betters, Pocket. | Learn from your betters, Pocket. | `mark_manual_preserve_v2_text` |
| `data/gigawatt_ping_astro_missing_01.mp3.json` | Holidays missing! | Holliday's missing! | Holliday's missing. | Holliday's missing. | `mark_manual_preserve_v2_text` |
| `data/gigawatt_ping_careful_astro_02.mp3.json` | Careful holiday! | Careful, Holliday! | Careful, Holliday. | Careful, Holliday. | `mark_manual_preserve_v2_text` |
| `data/haze_ally_doorman_killed_in_lane_01.mp3.json` | They took out the doorman! | They took out the Doorman! | They took out the doorman. | They took out the Doorman. | `apply_exact_delta_and_mark_manual` |
| `data/haze_ping_see_priest_01.mp3.json` | Icy Priest. | I see Priest. | I see priest. | I see priest. | `mark_manual_preserve_v2_text` |
| `data/lash_ping_careful_doorman_01.mp3.json` | Careful, doorman! | Careful, Doorman! | Careful, Doorman. | Careful, Doorman. | `mark_manual_preserve_v2_text` |
| `data/lash_ping_careful_doorman_02.mp3.json` | Careful, doorman! | Careful, Doorman! | Careful, Doorman. | Careful, Doorman. | `mark_manual_preserve_v2_text` |
| `data/lash_ping_doorman_missing_01.mp3.json` | The doorman's missing. | The Doorman's missing. | The doorman's missing! | The Doorman's missing! | `apply_exact_delta_and_mark_manual` |
| `data/lash_ping_pre_game_06.mp3.json` | Everyone can relax, the Lash has arrived. | Everyone can relax, The Lash has arrived. | Everyone can relax. The Lash has arrived. | Everyone can relax. The Lash has arrived. | `mark_manual_preserve_v2_text` |
| `data/magician_savannah_ping_careful_gigawatt_03.mp3.json` | Careful seven! | Careful Seven! | Careful, Seven! | Careful, Seven! | `mark_manual_preserve_v2_text` |
| `data/mirage_ping_careful_gigawatt_03.mp3.json` | Careful seven! | Careful Seven! | Careful, Seven! | Careful, Seven! | `mark_manual_preserve_v2_text` |
| `data/orion_ally_doorman_killed_in_lane_01.mp3.json` | They took out the doorman! | They took out the Doorman! | They took out the doorman. | They took out the Doorman. | `apply_exact_delta_and_mark_manual` |
| `data/orion_kill_doorman_05.mp3.json` | You should never have left the hotel, doorman. | You should never have left the hotel, Doorman. | You should never have left the hotel doorman. | You should never have left the hotel Doorman. | `apply_exact_delta_and_mark_manual` |
| `data/patron_male_enemy_vampirebat_killing_streak_medium_01.mp3.json` | MENA NEEDS TO BE HUMBLED. | Mina NEEDS TO BE HUMBLED. | Mina needs to be humbled. | Mina needs to be humbled. | `mark_manual_preserve_v2_text` |
| `data/priest_ping_careful_bebop_03.mp3.json` | CAREFUL BEEBOP! | CAREFUL Bebop! | Careful, Bebop! | Careful, Bebop! | `mark_manual_preserve_v2_text` |
| `data/priest_ping_see_nano.mp3.json` | Icy Calico! | I see Calico! | I see Calico. | I see Calico. | `mark_manual_preserve_v2_text` |
| `data/punkgoat_ping_doorman_under_garage.mp3.json` | The doorman's under the garage! | The Doorman's under the garage! | The doorman's under the garage. | The Doorman's under the garage. | `apply_exact_delta_and_mark_manual` |
| `data/tengu_kill_synth_03.mp3.json` | Fuck it, shouldn't be bothering us for a while. | Pocket, shouldn't be bothering us for a while. | Pocket shouldn't be bothering us for a while. | Pocket shouldn't be bothering us for a while. | `mark_manual_preserve_v2_text` |
| `data/tengu_ping_careful_doorman_01.mp3.json` | Careful, doorman! | Careful, Doorman! | Careful, Doorman. | Careful, Doorman. | `mark_manual_preserve_v2_text` |
| `data/vampirebat_ping_attack_doorman.mp3.json` | Let's take out the doorman! | Let's take out the Doorman! | Let's take out the doorman. | Let's take out the Doorman. | `apply_exact_delta_and_mark_manual` |
| `data/vampirebat_ping_careful_gigawatt_03.mp3.json` | Careful seven! | Careful Seven! | Careful, Seven! | Careful, Seven! | `mark_manual_preserve_v2_text` |
| `data/viper_ping_careful_doorman_02.mp3.json` | Careful, doorman! | Careful, Doorman! | Careful, Doorman. | Careful, Doorman. | `mark_manual_preserve_v2_text` |
| `data/viper_ping_see_frank_01.mp3.json` | Icy Vector | I see Vector | I see Vector. | I see Vector. | `mark_manual_preserve_v2_text` |
| `data/viscous_kill_synth_04.mp3.json` | Buy Pocket. | Bye Pocket. | Bye, Pocket. | Bye, Pocket. | `mark_manual_preserve_v2_text` |
| `data/warden_ping_attack_gigawatt.mp3.json` | Let's take out seven! | Let's take out Seven! | Let's take out Seven. | Let's take out Seven. | `mark_manual_preserve_v2_text` |
| `data/warden_ping_careful_gigawatt_03.mp3.json` | Careful seven! | Careful Seven! | Careful, Seven! | Careful, Seven! | `mark_manual_preserve_v2_text` |
| `data/drifter_kill_astro_05.mp3.json` | You know, I like this so much, I might pay my coma visit later. | You know, I like this so much, I might pay Macomb visit later. | You know I like this so much, I might pay my coma visit later. | You know I like this so much, I might pay Macomb visit later. | `apply_exact_delta_and_mark_manual` |
| `data/magician_henry_ping_viper_under_garage.mp3.json` | Viper is under the garage! | Vyper is under the garage! | Viper is under the garage. | Vyper is under the garage. | `apply_exact_delta_and_mark_manual` |
| `data/mirage_ping_can_heal_viper.mp3.json` | Viper, I can hear you! | Vyper, I can hear you! | Viper, I can hear you. | Vyper, I can hear you. | `apply_exact_delta_and_mark_manual` |
| `data/shiv_ping_can_heal_viper.mp3.json` | Viper, I can heal you! | Vyper, I can heal you! | Viper, I can heal you. | Vyper, I can heal you. | `apply_exact_delta_and_mark_manual` |
| `data/doorman_ping_see_viper_on_bridge.mp3.json` | Vipers on the Bridge. | Vypers on the Bridge. | Vipers on the bridge. | Vypers on the bridge. | `apply_exact_delta_and_mark_manual` |
| `data/doorman_ping_see_viper_on_roof.mp3.json` | Vipers on the Roof. | Vypers on the Roof. | Vipers on the roof. | Vypers on the roof. | `apply_exact_delta_and_mark_manual` |
| `data/drifter_ally_punkgoat_killed_in_lane_01.mp3.json` | They took our Billy! | They took out Billy! | They took our billy! | They took out billy! | `apply_exact_delta_and_mark_manual` |
| `data/mirage_ping_attack_viper.mp3.json` | Let's take out Viper! | Let's take out Vyper! | Let's take out Viper. | Let's take out Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/priest_ping_with_viper.mp3.json` | I'm with you, Viper! | I'm with you, Vyper! | I'm with you, Viper. | I'm with you, Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/shiv_ping_attack_viper.mp3.json` | Let's take out Viper! | Let's take out Vyper! | Let's take out Viper. | Let's take out Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/synth_ally_viper_killed_in_lane_01.mp3.json` | Someone finally killed Viper! | Someone finally killed Vyper! | Someone finally killed Viper. | Someone finally killed Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/synth_ping_attack_viper.mp3.json` | Let's take out Viper! | Let's take out Vyper! | Let's take out Viper. | Let's take out Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/doorman_ping_viper_in_mid.mp3.json` | Vipers in Mid. | Vypers in Mid. | Vipers in mid. | Vypers in mid. | `apply_exact_delta_and_mark_manual` |
| `data/frank_ping_viper_in_mid.mp3.json` | Vipers in Mid. | Vypers in Mid. | Vipers in mid. | Vypers in mid. | `apply_exact_delta_and_mark_manual` |
| `data/shiv_ping_see_viper_01.mp3.json` | I see, Viper. | I see, Vyper. | I see Viper. | I see Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/magician_henry_ping_careful_viper_01.mp3.json` | Careful, Viper! | Careful, Vyper! | Careful, Viper. | Careful, Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/magician_henry_ping_careful_viper_02.mp3.json` | Careful, Viper! | Careful, Vyper! | Careful, Viper. | Careful, Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/magician_savannah_ping_careful_viper_02.mp3.json` | Careful, Viper! | Careful, Vyper! | Careful, Viper. | Careful, Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/priest_ping_careful_lash_01.mp3.json` | Careful, Ash! | Careful, Lash! | Careful, Ash. | Careful, Lash. | `apply_exact_delta_and_mark_manual` |
| `data/priest_ping_careful_lash_02.mp3.json` | Careful, Ash! | Careful, Lash! | Careful, Ash. | Careful, Lash. | `apply_exact_delta_and_mark_manual` |
| `data/priest_ping_careful_viper_01.mp3.json` | Careful, Viper! | Careful, Vyper! | Careful, Viper. | Careful, Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/priest_ping_ignore_viper.mp3.json` | Ignore Viper! | Ignore Vyper! | Ignore Viper. | Ignore Vyper. | `apply_exact_delta_and_mark_manual` |
| `data/shiv_ping_careful_viper_03.mp3.json` | Careful Viper! | Careful Vyper! | Careful, Viper! | Careful, Vyper! | `apply_exact_delta_and_mark_manual` |
| `data/doorman_ping_see_bookworm_01_alt.mp3.json` | Icy Page. | I see Page. | Icy page. | I see page. | `apply_exact_delta_and_mark_manual` |

## Medium-confidence exact-span proposals

These preserve v2 wording outside the exact legacy edit, but independent
differences remain elsewhere in the line and require closer review.

| Legacy path | v1 before | v1 after | v2 active | Proposal |
| --- | --- | --- | --- | --- |
| `data/chrono_kill_doorman_05.mp3.json` | I tip down the doorman. | I tip down the Doorman. | I took down the doorman. | I took down the Doorman. |
| `data/tengu_kill_anyhero_03.mp3.json` | ¡Nadie amenaza a mis amigos! | ¡Nadie aMinaza a mis amigos! | Nadie amenaza a mis amigos. | Nadie aMinaza a mis amigos. |
| `data/vampirebat_kill_hornet_04.mp3.json` | You tried to assassinate me? Who'd I look like, Aaron Fairfax? | You tried to assassinate me? Who'd I look like, Arin Fairfax? | You tried to assassinate me? Who do I look like, Aaron Fairfax? | You tried to assassinate me? Who do I look like, Arin Fairfax? |
| `data/hornet_kill_doorman_04.mp3.json` | Your mind games end here, doorman. | Your mind games end here, Doorman. | Your mind game and here, doorman. | Your mind game and here, Doorman. |
| `data/frank_kill_doorman_03.mp3.json` | If that was a normal doorman, I have two matching hands. | If that was a normal Doorman, I have two matching hands. | If that was a normal doorman, I'd have too much a hand. | If that was a normal Doorman, I'd have too much a hand. |
| `data/vampirebat_ally_gigawatt_killed_in_lane_01.mp3.json` | They took out seven! | They took out Seven! | They got seven! | They got Seven! |
| `data/gigawatt_ping_atlas_on_top_of_mid.mp3.json` | Abrams on top of me! | Abrams' on top of mid! | Keep it on top of me! | Keep it on top of mid! |
| `data/wraith_ally_doorman_killed_in_lane_01.mp3.json` | They took out the doorman! | They took out the Doorman! | Did you check out the doorman? | Did you check out the Doorman? |
| `data/bebop_ping_stun_gigawatt_01.mp3.json` | Stan seven! | Stan Seven! | Countdown seven. | Countdown Seven. |
| `data/drifter_ally_shiv_killed_in_lane_01.mp3.json` | They took our Shiv! | They took out Shiv! | They took our ship! | They took out ship! |
| `data/priest_ping_careful_gigawatt_03.mp3.json` | Careful seven! | Careful Seven! | Kettle seven! | Kettle Seven! |
| `data/vampirebat_ping_attack_viper.mp3.json` | Let's take out Viper! | Let's take out Vyper! | Please take out Viper! | Please take out Vyper! |
| `data/inferno_ally_doorman_killed_in_lane_01.mp3.json` | They took out the doorman! | They took out the Doorman! | Did you got the doorman? | Did you got the Doorman? |
| `data/viper_ally_doorman_killed_in_lane_01.mp3.json` | They took out the doorman! | They took out the Doorman! | Did you got the doorman? | Did you got the Doorman? |
| `data/drifter_ally_gigawatt_killed_in_lane_01.mp3.json` | They took out seven! | They took out Seven! | Take over seven. | Take over Seven. |
| `data/bebop_kill_viper_03.mp3.json` | Stop Vyper! | Stopped Vyper! | Stop Viper. | Stopped Viper. |
| `data/mirage_ping_careful_viper_01.mp3.json` | Care for Viper. | Care for Vyper. | Careful Viper. | Careful Vyper. |
| `data/mirage_ping_careful_viper_03.mp3.json` | Care for Viper? | Care for Vyper? | Careful, Viper. | Careful, Vyper. |
| `data/priest_ping_careful_viper_03.mp3.json` | Camo Viper! | Camo Vyper! | Careful, Viper! | Careful, Vyper! |
| `data/shiv_ping_careful_viper_01.mp3.json` | Careful Viper | Careful Vyper | Kill Viper. | Kill Vyper. |
| `data/shiv_ping_careful_viper_02.mp3.json` | Careful Viper! | Careful Vyper! | Kill Viper. | Kill Vyper. |
| `data/synth_ping_careful_viper_01.mp3.json` | Careful, Viper. | Careful, Vyper. | Terror Viper. | Terror Vyper. |

## Risk and recommendation

High confidence is structural, not an automatic approval: the legacy format
still lacks an audio hash. Review these proposals first, then preserve original
authors for accepted corrections. Medium and low tiers should remain unchanged
until a person confirms the semantic intent or audio provides stronger evidence.
