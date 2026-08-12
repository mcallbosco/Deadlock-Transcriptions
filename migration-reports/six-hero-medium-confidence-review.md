# Six Hero medium-confidence contribution review decisions

The review approved 56 exact selected-SHA corrections and excluded the suspicious Spanish
transfer. "Review-time text" is the generated text observed before application; "reviewed
result" is the committed manual text, or the unchanged generated text for the exclusion.

## Summary

- Approved and applied: **56**
- Explicit reviewer overrides: **8**
- Suspicious transfers excluded: **1**
- Official revisions changed: **0**

| Author | Medium records |
| --- | ---: |
| Mcall (`26465212+mcallbosco@users.noreply.github.com`) | 40 |
| Gunseeker (`gunseekergaming@gmail.com`) | 7 |
| Archer (`92534692+ArcherOfLegend@users.noreply.github.com`) | 4 |
| Sloan (`vekterfs@protonmail.com`) | 3 |
| Miles Calloway (`26465212+mcallbosco@users.noreply.github.com`) | 1 |
| youremother23 (`youremother23@gmail.com`) | 1 |
| retrogradual (`vekterfs@protonmail.com`) | 1 |

## Exact edit, differing context (21)

| Legacy path | Review-time text | Reviewed result | Legacy edit | Author / commit | Decision |
| --- | --- | --- | --- | --- | --- |
| `data/bebop_kill_viper_03.mp3.json` | Stop Viper. | Stopped Vyper! | Stop Vyper! -> Stopped Vyper! | Archer `a760cb0977da` | Applied |
| `data/bebop_ping_stun_gigawatt_01.mp3.json` | Countdown seven. | Stun Seven! | Stan seven! -> Stan Seven! | Mcall `718e4db5e385` | Applied |
| `data/chrono_kill_doorman_05.mp3.json` | I took down the doorman. | I took down the Doorman. | I tip down the doorman. -> I tip down the Doorman. | Mcall `6fa7de717b3d` | Applied |
| `data/drifter_ally_gigawatt_killed_in_lane_01.mp3.json` | Take over seven. | Take over Seven. | They took out seven! -> They took out Seven! | Mcall `718e4db5e385` | Applied |
| `data/drifter_ally_shiv_killed_in_lane_01.mp3.json` | They took our ship! | They took out ship! | They took our Shiv! -> They took out Shiv! | Gunseeker `fc0b6965e2dc` | Applied |
| `data/frank_kill_doorman_03.mp3.json` | If that was a normal doorman, I'd have too much a hand. | If that was a normal Doorman, I'd have too much a hand. | If that was a normal doorman, I have two matching hands. -> If that was a normal Doorman, I have two matching hands. | Mcall `6fa7de717b3d` | Applied |
| `data/gigawatt_ping_atlas_on_top_of_mid.mp3.json` | Keep it on top of me! | Keep it on top of mid! | Abrams on top of me! -> Abrams' on top of mid! | Sloan `35263eac6703` | Applied |
| `data/hornet_kill_doorman_04.mp3.json` | Your mind game and here, doorman. | Your mind game and here, Doorman. | Your mind games end here, doorman. -> Your mind games end here, Doorman. | Mcall `6fa7de717b3d` | Applied |
| `data/inferno_ally_doorman_killed_in_lane_01.mp3.json` | Did you got the doorman? | Did you got the Doorman? | They took out the doorman! -> They took out the Doorman! | Mcall `6fa7de717b3d` | Applied |
| `data/mirage_ping_careful_viper_01.mp3.json` | Careful Viper. | Careful Vyper. | Care for Viper. -> Care for Vyper. | Mcall `2ebce15260ef` | Applied |
| `data/mirage_ping_careful_viper_03.mp3.json` | Careful, Viper. | Careful Vyper. | Care for Viper? -> Care for Vyper? | Mcall `2ebce15260ef` | Applied |
| `data/priest_ping_careful_gigawatt_03.mp3.json` | Kettle seven! | Kettle Seven! | Careful seven! -> Careful Seven! | Mcall `718e4db5e385` | Applied |
| `data/priest_ping_careful_viper_03.mp3.json` | Careful, Viper! | Careful Vyper. | Camo Viper! -> Camo Vyper! | Mcall `2ebce15260ef` | Applied |
| `data/shiv_ping_careful_viper_01.mp3.json` | Kill Viper. | Careful Vyper. | Careful Viper -> Careful Vyper | Mcall `2ebce15260ef` | Applied |
| `data/shiv_ping_careful_viper_02.mp3.json` | Kill Viper. | Careful Vyper. | Careful Viper! -> Careful Vyper! | Mcall `2ebce15260ef` | Applied |
| `data/synth_ping_careful_viper_01.mp3.json` | Terror Viper. | Terror Vyper. | Careful, Viper. -> Careful, Vyper. | Mcall `2ebce15260ef` | Applied |
| `data/vampirebat_ally_gigawatt_killed_in_lane_01.mp3.json` | They got seven! | They got Seven! | They took out seven! -> They took out Seven! | Mcall `718e4db5e385` | Applied |
| `data/vampirebat_kill_hornet_04.mp3.json` | You tried to assassinate me? Who do I look like, Aaron Fairfax? | You tried to assassinate me? Who do I look like, Arin Fairfax? | You tried to assassinate me? Who'd I look like, Aaron Fairfax? -> You tried to assassinate me? Who'd I look like, Arin Fairfax? | Mcall `718e4db5e385` | Applied |
| `data/vampirebat_ping_attack_viper.mp3.json` | Please take out Viper! | Please take out Vyper! | Let's take out Viper! -> Let's take out Vyper! | Mcall `2ebce15260ef` | Applied |
| `data/viper_ally_doorman_killed_in_lane_01.mp3.json` | Did you got the doorman? | Did you got the Doorman? | They took out the doorman! -> They took out the Doorman! | Mcall `6fa7de717b3d` | Applied |
| `data/wraith_ally_doorman_killed_in_lane_01.mp3.json` | Did you check out the doorman? | Did you check out the Doorman? | They took out the doorman! -> They took out the Doorman! | Mcall `6fa7de717b3d` | Applied |

## Near semantic match (35)

| Legacy path | Review-time text | Reviewed result | Legacy edit | Author / commit | Decision |
| --- | --- | --- | --- | --- | --- |
| `data/chrono_kill_astro_03.mp3.json` | She's never fought someone like me, Holliday! | You've never fought someone like me, Holliday! | You've never fought someone like me, holliday! -> You've never fought someone like me, Holliday! | Mcall `718e4db5e385` | Applied |
| `data/chrono_kill_synth_05.mp3.json` | You can change your name, Iron, but I know who you really are. | You can change your name, Arin, but I know who you really are. | You can change your name, Aaron, but I know who you really are. -> You can change your name, Arin, but I know who you really are. | Mcall `718e4db5e385` | Applied |
| `data/drifter_ally_orion_killed_in_lane_01.mp3.json` | They took out Great Talon! | They took out Grey Talon! | They took our Grey Talon! -> They took out Grey Talon! | Gunseeker `fc0b6965e2dc` | Applied |
| `data/drifter_kill_doorman_01.mp3.json` | You tricks aren't gonna be enough to stop me, Doorman. | Cute tricks aren't gonna be enough to stop me, Doorman. | Cute tricks aren't gonna be enough to stop me, Dorman. -> Cute tricks aren't gonna be enough to stop me, Doorman. | Archer `d74b40c49a60` | Applied |
| `data/drifter_kill_doorman_02.mp3.json` | Why don't you scurry back to the Barrenlands, doorman? | Why don't you scurry back to the baroness, Doorman? | Why don't you story back to the baroness, doorman? -> Why don't you scurry back to the baroness, Doorman? | Archer `3102de59f827` | Applied |
| `data/drifter_kill_viper_02.mp3.json` | I always feel bad killing someone so pathetic. | I almost feel bad killing someone so pathetic. | I once feel bad killing someone so pathetic. -> I almost feel bad killing someone so pathetic. | Archer `eafadacf7edd` | Applied |
| `data/drifter_ping_bookworm_on_top_of_mid_alt.mp3.json` | Graves is on top of mid! | Paige is on top of mid! | Spades is on top of mid! -> Paige is on top of mid! | Gunseeker `fc0b6965e2dc` | Applied |
| `data/drifter_ping_punkgoat_on_top_of_garage.mp3.json` | Pinned on top of the garage. | Billy's on top of the garage! | It is on top of the garage! -> Billy's on top of the garage! | Gunseeker `fc0b6965e2dc` | Applied |
| `data/gigawatt_ally_orion_killed_in_lane_01.mp3.json` | They took out Gray Talon! | They took out Grey Talon! | They took out grey talon! -> They took out Grey Talon! | Mcall `718e4db5e385` | Applied |
| `data/gigawatt_kill_viscous_01.mp3.json` | Return to the deep, mistress. | Return to the deep, Viscous! | Return to the deep, viscus! -> Return to the deep, Viscous! | retrogradual `b957d463ce8a` | Applied |
| `data/gigawatt_ping_astro_on_top_of_mid.mp3.json` | Harmony's on top of mid! | Holliday's on top of mid! | Holidays on top of med! -> Holliday's on top of mid! | Sloan `0d07c0b2492e` | Applied |
| `data/gigawatt_ping_can_heal_astro.mp3.json` | Holiday, I can heal you. | Holliday, I can heal you! | Holiday, I can hear you! -> Holliday, I can heal you! | Sloan `0d07c0b2492e` | Applied |
| `data/gigawatt_ping_see_synth.mp3.json` | I see | I see Pocket! | Icy Pocket! -> I see Pocket! | Mcall `de6734de55bf` | Applied |
| `data/kelvin_ally_doorman_killed_in_lane_01.mp3.json` | Then took out the doorman. | They took out the Doorman! | And took out the doorman! -> They took out the Doorman! | Gunseeker `646946c1cad1` | Applied |
| `data/kelvin_kill_yamato_04.mp3.json` | Yamato is a menace. | Yamato is a menace! | Yamato is a menace! -> Yamato is a menace! | Mcall `7f06b4f71e5e` | Applied |
| `data/kelvin_ping_can_heal_haze.mp3.json` | Hey, I can heal you! | Haze, I can heal you! | Haze, I can hear you! -> Haze, I can heal you! | Gunseeker `646946c1cad1` | Applied |
| `data/kelvin_ping_wraith_on_top_of_mid.mp3.json` | Raise on top of mid! | Wraith's on top of mid! | Wraiths on top of mid! -> Wraith's on top of mid! | Gunseeker `646946c1cad1` | Applied |
| `data/lash_ping_can_heal_vampirebat.mp3.json` | Mean I can heal you. | Mina, I can heal you! | Meena, I can heal you! -> Mina, I can heal you! | Mcall `24e30d241201` | Applied |
| `data/magician_henry_ping_viper_on_top_of_garage.mp3.json` | Viper's on top of the garage! | Vypers on top of the garage! | Vipers on top of the garage! -> Vypers on top of the garage! | Mcall `2ebce15260ef` | Applied |
| `data/magician_savannah_ping_can_heal_viper.mp3.json` | Kyper, I can heal you! | Vyper, I can heal you! | Viper, I can heal you! -> Vyper, I can heal you! | Mcall `2ebce15260ef` | Applied |
| `data/magician_savannah_ping_viper_on_top_of_garage.mp3.json` | Viper's on top of the garage! | Vypers on top of the garage! | Vipers on top of the garage! -> Vypers on top of the garage! | Mcall `2ebce15260ef` | Applied |
| `data/magician_savannah_ping_viper_on_top_of_mid.mp3.json` | Viper's on top of mid! | Vypers on top of mid! | Vipers on top of mid! -> Vypers on top of mid! | Mcall `2ebce15260ef` | Applied |
| `data/mirage_ping_viper_on_top_of_garage.mp3.json` | Viper's on top of the garage. | Vypers on top of the garage! | Vipers on top of the garage! -> Vypers on top of the garage! | Mcall `2ebce15260ef` | Applied |
| `data/mirage_ping_viper_on_top_of_mid.mp3.json` | Viper's on top of mid. | Vypers on top of mid! | Vipers on top of mid! -> Vypers on top of mid! | Mcall `2ebce15260ef` | Applied |
| `data/patron_female_ally_vampirebat_killing_streak_02.mp3.json` | Mean and darts amongst them, a perpetual thorn in their side. | Mina darts amongst them, a perpetual thorn in their side. | Mena darts amongst them, a perpetual thorn in their side. -> Mina darts amongst them, a perpetual thorn in their side. | Mcall `24e30d241201` | Applied |
| `data/patron_female_ally_vampirebat_start_05.mp3.json` | Once you complete the ritual, everyone will realize their folly, and the other vampires you all were... | Once you complete the ritual, Arin will realize their folly, and the other vampires you are worth. | Once you complete the ritual, Aaron will realize their folly, and the other vampires you are worth. -> Once you complete the ritual, Arin will realize their folly, and the other vampires you are worth. | Mcall `718e4db5e385` | Applied |
| `data/patron_male_ally_vampirebat_killing_streak_03.mp3.json` | Oh, how mean as Crimson children make them scream! | Oh, how Mina's crimson children make them scream! | Oh, how mean his crimson children make them scream! -> Oh, how Mina's crimson children make them scream! | youremother23 `b3717819a54f` | Applied |
| `data/shiv_ping_viper_on_top_of_mid.mp3.json` | Viper's on top of mid. | Vypers on top of mid! | Vipers on top of mid! -> Vypers on top of mid! | Mcall `2ebce15260ef` | Applied |
| `data/shopkeeper_hotdog_t4_doorman_01.mp3.json` | Hey, buddy, don't suppose you can get me into Mitch's brunch reservations for Sunday? | Hey, buddy, don't suppose you can get me into Mrs. Brunch reservations for Sunday? | Hey, buddy, don't suppose you can get me into Mrs. Brunch Reservations for Sunday? -> Hey, buddy, don't suppose you can get me into Mrs. Brunch reservations for Sunday? | Miles Calloway `e3e7733fbca9` | Applied |
| `data/synth_ping_can_heal_viper.mp3.json` | Tiger, I can heal you. | Vyper, I can heal you. | Viper, I can heal you. -> Vyper, I can heal you. | Mcall `2ebce15260ef` | Applied |
| `data/synth_ping_viper_on_top_of_garage.mp3.json` | Climbers on top of the garage. | Vypers on top of the garage! | Vipers on top of the garage! -> Vypers on top of the garage! | Mcall `2ebce15260ef` | Applied |
| `data/synth_ping_viper_on_top_of_mid.mp3.json` | Viper's on top of mid. | Vypers on top of mid. | Vipers on top of mid. -> Vypers on top of mid. | Mcall `2ebce15260ef` | Applied |
| `data/tengu_ally_orion_killed_in_lane_01.mp3.json` | They took out Great Talon! | They took out Grey Talon! | They took out grey talon! -> They took out Grey Talon! | Mcall `718e4db5e385` | Applied |
| `data/vampirebat_ping_viper_on_top_of_mid.mp3.json` | Viper's on top of mid! | Vypers on top of mid! | Vipers on top of mid! -> Vypers on top of mid! | Mcall `2ebce15260ef` | Applied |
| `data/viper_ping_can_heal_vampirebat.mp3.json` | Then I can heal you! | Mina, I can heal you! | Meena, I can heal you! -> Mina, I can heal you! | Mcall `24e30d241201` | Applied |

## Suspicious transfer (1)

| Legacy path | Review-time text | Reviewed result | Legacy edit | Author / commit | Decision |
| --- | --- | --- | --- | --- | --- |
| `data/tengu_kill_anyhero_03.mp3.json` | Nadie amenaza a mis amigos. | Nadie amenaza a mis amigos. | ¡Nadie amenaza a mis amigos! -> ¡Nadie aMinaza a mis amigos! | Mcall `e6a1eaa4468c` | Excluded; left generated |
