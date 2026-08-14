# Fuzzy transcript candidate audit

This report is advisory only. Candidates are possible equivalents, not approved merges.
Comparison is limited to revision groups in the same transcript file. Exact schema-v3
matches are excluded because they are already grouped.

## Confidence bands

| Confidence | Similarity | Candidates |
| --- | ---: | ---: |
| High | ≥ 95% | 688 |
| Medium | ≥ 90% | 1,828 |
| Low | ≥ 80% | 4,050 |

Similarity is the `difflib.SequenceMatcher` ratio after ignoring case, Unicode
punctuation, and whitespace. Even high-confidence pairs require human review because
small changes can alter names, subjects, negation, or gameplay meaning.

## Coverage

- Transcript files: 98,944
- Revision groups: 122,103
- Within-file pairs: 29,702
- Nonblank, non-exact pairs compared: 29,522
- Candidates: 6,566

The complete candidate set, including hashes and normalized lengths, is in
`fuzzy-transcript-candidates.json`.

## Source combinations

| Sources | High | Medium | Low | Total |
| --- | ---: | ---: | ---: | ---: |
| generated + generated | 675 | 1,759 | 3,964 | 6,398 |
| generated + manual | 7 | 25 | 30 | 62 |
| generated + official | 4 | 44 | 51 | 99 |
| manual + official | 2 | 0 | 1 | 3 |
| official + official | 0 | 0 | 4 | 4 |

## High confidence

Showing 100 of 688 candidates.

| Similarity | Path | Sources | Left text | Right text |
| ---: | --- | --- | --- | --- |
| 99.59% | `transcripts/kali/rr_test_19_ping_see_dynamo_on_roof.mp3.json` | generated / generated | ChatGPT: context: ### Transcribe this Deadlock voice line in English exactly. Preserve all spoken words. Do not add commentary or quotation marks. The following JSON contains authoritative Deadlock spellings, terminology, and transcription guidelines. Follow it when applicable: {"Characters":["Holliday","Shelly Fisher","Geist","Marla","Marlowe","Troubadour","Nashala Dion","Viscous","John Hathorne","Edrick","Captain Murphy","Holliday","Infernus","Kelvin","Abrams","Vindicta","Operative","Bebop","Cadence","Paradox","Dynamo","McGinnis","Lady Geist","Seven","Haze","Krill","Lash","Magician","Mirage","Nano","Grey Talon","Shiv","Slork","Pocket","Ivy","Trapper","Vyper","Viscous","Warden","Wraith","Wrecker","Yamato","Fern","Mina Ha","Doorman","Paige","Rem","Apollo","Graves","Pepper","Silver","Venator"],"Groups":["Djinn"],"Places":["Ixia","Blackmore"],"Abilities":["Ping"],"Game Terms":["Mid","Mid-Boss","Gank","Payload","Capture","Control","Escort"],"Transcription Guidelines":["Use sentence case for all transcriptions.","Use standard punctuation.","Follow the above spelling for ambiguous names.","Do not include extra whitespace at the beginning or end of transcriptions."]} ### | context: ### Transcribe this Deadlock voice line in English exactly. Preserve all spoken words. Do not add commentary or quotation marks. The following JSON contains authoritative Deadlock spellings, terminology, and transcription guidelines. Follow it when applicable: {"Characters":["Holliday","Shelly Fisher","Geist","Marla","Marlowe","Troubadour","Nashala Dion","Viscous","John Hathorne","Edrick","Captain Murphy","Holliday","Infernus","Kelvin","Abrams","Vindicta","Operative","Bebop","Cadence","Paradox","Dynamo","McGinnis","Lady Geist","Seven","Haze","Krill","Lash","Magician","Mirage","Nano","Grey Talon","Shiv","Slork","Pocket","Ivy","Trapper","Vyper","Viscous","Warden","Wraith","Wrecker","Yamato","Fern","Mina Ha","Doorman","Paige","Rem","Apollo","Graves","Pepper","Silver","Venator"],"Groups":["Djinn"],"Places":["Ixia","Blackmore"],"Abilities":["Ping"],"Game Terms":["Mid","Mid-Boss","Gank","Payload","Capture","Control","Escort"],"Transcription Guidelines":["Use sentence case for all transcriptions.","Use standard punctuation.","Follow the above spelling for ambiguous names.","Do not include extra whitespace at the beginning or end of transcriptions."]} ### |
| 99.53% | `transcripts/book/oathkeeper/vn_geist_scene04d_12.mp3.json` | generated / generated | No, the point was to save my life. We've already established that you're incapable of repairing the walls, so where does that leave me? | No, the point was to save my life. We've already established that you're incapable of repairing the wall, so where does that leave me? |
| 99.52% | `transcripts/newscaster/newscaster_headline_53.mp3.json` | generated / generated | Is Trinity Church an undead time bomb waiting to explode? We talked with premier necromancer Frederick Toten to get his take. | Is Trinity Church an undead time bomb waiting to explode? We talked with premier necromancer Frederick Totten to get his take. |
| 99.51% | `transcripts/dynamo/prof_monologue_01.mp3.json` | generated / generated | Welcome. Forgive the mess. I just finished lecturing on metaphysics, astral gates, and the intersection between the two. I swear, I could talk about the intricacies of quantum entanglement and the intertwining of consciousness, cosmic vibrations, and esoteric mysteries forever, but sorry, I can't help but notice you have the exact expression my students made during class. | Welcome! Forgive the mess, I just finished lecturing on metaphysics, astral gates, and the intersection between the two. I swear, I could talk about the intricacies of quantum entanglement and the intertwining of consciousness and cosmic vibrations and esoteric mysteries forever, but, sorry, I can't help but notice you have the exact expression my students made during class. |
| 99.50% | `transcripts/announcer/male_patron/patron_male_ally_shiv_start_03.mp3.json` | generated / generated | Many men would kill for the gift you are looking to purge. Nonetheless, complete the ritual, and I will give you what you seek. | Many men would kill for the gift you're looking to purge. Nonetheless, complete the ritual, and I will give you what you seek. |
| 99.47% | `transcripts/announcer/male_patron/patron_male_ally_atlas_start_04.mp3.json` | generated / generated | Trust doesn't come easy for you, Abrams, but know this: when you complete the ritual, I will hold up my end of the bargain. | Trust does not come easy for you, Abrams, but know this: when you complete the ritual, I will hold up my end of the bargain. |
| 99.40% | `transcripts/newscaster/newscaster_headline_81.mp3.json` | generated / generated | The international bestseller for queen and coven, highlighting the daring exploits of the queen's own 13th airborne assault coven, is under fire as representatives of the crown claim that some of the operations detailed in the tell-all violate the nation's scrying laws and pose a national security risk. | The international bestseller for Queen & Coven, highlighting the daring exploits of the queen's own 13th airborne assault coven, is under fire as representatives of the crown claim that some of the operations detailed in the tell-all violate the nation's scrying laws and pose a national security risk. |
| 99.35% | `transcripts/synth/pocket_select_04.mp3.json` | generated / generated | My father's gift for my 18th birthday was a bullet to the chest. Today's my chance to say thank you. | My father's gift for my 18th birthday was a bullet to the chest. Today is my chance to say thank you. |
| 99.34% | `transcripts/dynamo/prof_kill_haze_02.mp3.json` | generated / generated | I should probably stop telling my students that OSIC Sandman was just a conspiracy theory. | I should probably stop telling my students that OSIC's Sandman was just a conspiracy theory. |
| 99.32% | `transcripts/shopkeeper/guide_the_map_core.mp3.json` | generated / generated | There's a shrine at the back of each team's base, destroying the enemy's shrine wins the game. | There is a shrine at the back of each team's base. Destroying the enemy's shrine wins the game. |
| 99.26% | `transcripts/lash/lash_upgrade_power1_05.mp3.json` | generated / generated | Every time I hear someone scream in frustration, I just get a big ol' smile on my face. | Every time I hear someone screaming frustration, I just get a big ol' smile on my face. |
| 99.26% | `transcripts/lash/lash_upgrade_power1_05.mp3.json` | generated / generated | Every time I hear someone scream in frustration, I just get a big ol' smile on my face. | Every time I hear someone scream in frustration, I just get a big old smile on my face. |
| 99.25% | `transcripts/t1_guardians/guardian_test_04/rr_guardian_test_04_greeting_05.mp3.json` | generated / generated | The training manual said that taking out the troopers should be our top priority. | The training manual said that taking out the trooper should be our top priority. |
| 99.24% | `transcripts/lash/lash_select_10_02.mp3.json` | generated / generated | I'm not dumb. I know a lot of people hate me. It's a... I mean, it's a curse, really. You know, I've ruled so hard that, uh, you know, every mediocre soul in the city just has to resent me. | I'm not dumb. I know a lot of people hate me. It's a... I mean, it's a curse, really. You know, I've ruled so hard that, you know, every mediocre soul in the city just has to resent me. |
| 99.21% | `transcripts/inferno/inferno_select_09.mp3.json` | generated / generated | It is so nice to know that my years of antisocial behavior can be put to good use. | It's so nice to know that my years of antisocial behavior can be put to good use. |
| 99.15% | `transcripts/wraith/wraith_select_07.mp3.json` | generated / generated | Blackmail sounds so sleazy. I prefer information retention services. | Blackmail sounds so sleazy. I'd prefer information retention services. |
| 99.13% | `transcripts/gigawatt/gigawatt_select_10.mp3.json` | generated / generated | I free myself from the shackles of the past, and my future looks bright. | I freed myself from the shackles of the past, and my future looks bright. |
| 99.08% | `transcripts/announcer/male_patron/patron_male_ally_lash_start_05.mp3.json` | generated / generated | You have proven yourself time and again, Lash, but the world still doubts you. But once you release me, your greatness will be undeniable. | You've proven yourself time and again, Lash, but the world still doubts you. But once you release me, your greatness will be undeniable. |
| 98.99% | `transcripts/shopkeeper/guide_the_map_welcome.mp3.json` | generated / generated | Shadowline is a 6v6 strategic shooter where gunplay, fast-paced movement, tower progression, and unique heroes collide. | Shadowline is a 6v6 strategic shooter where gunplay, fast-paced movement, power progression, and unique heroes collide. |
| 98.97% | `transcripts/krill/krill_start_match_10.mp3.json` | generated / generated | Well, we will know in a couple minutes how this day is gonna go. | Well, we will know in a couple minutes how this day's gonna go. |
| 98.94% | `transcripts/shopkeeper/guide_the_map_core_2.mp3.json` | generated / generated | There is a shrine at the back of each team's base. Destroying the enemy's shrine completes the ritual and wins the game. | There's a shrine at the back of each team's base. Destroying the enemy shrine completes the ritual and wins the game. |
| 98.86% | `transcripts/lash/lash_select_10_02.mp3.json` | generated / generated | I'm not dumb. I know a lot of people hate me. It's a... I mean, it's a curse, really. You know, I rule so hard that, uh, you know, every mediocre soul in the city just has to resent me. | I'm not dumb. I know a lot of people hate me. It's a... I mean, it's a curse, really. You know, I've ruled so hard that, uh, you know, every mediocre soul in the city just has to resent me. |
| 98.85% | `transcripts/kali/rr_test_19_angry_10.mp3.json` | generated / generated | How do I do my job? How do I resolve this problem anyways? | How do I do my job? How do I resolve this problem, anyway? |
| 98.81% | `transcripts/newscaster/newscaster_headline_20.mp3.json` | generated / generated | The Supreme Court today upheld Cindermar vs. the State of Alabama, paving the way for the spirits' congressional bid. Read all about it in the New York Oracle. | The Supreme Court today upheld Cindermaw v. the State of Alabama, paving the way for the spirit's congressional bid. Read all about it in the New York Oracle. |
| 98.77% | `transcripts/lash/lash_select_10.mp3.json` | generated / generated | I'm not dumb. I know a lot of people hate me. It's a... it's a curse, really. You know, it's just rules so hard that, uh, every mediocre soul in the city has to resent you. | I'm not dumb. I know a lot of people hate me. It's a... it's cursed, really. You know, it's just rule so hard that, uh, every mediocre soul in the city has to resent you. |
| 98.73% | `transcripts/haze/haze_kill_paradox_03.mp3.json` | generated / generated | You're not as clever as you think you are, Paradox. | You are not as clever as you think you are, Paradox. |
| 98.70% | `transcripts/krill/krill_killed_by_chrono_03.mp3.json` | generated / generated | Stupid beef with our stupid time manipulation! | Stupid bee with our stupid time manipulation! |
| 98.67% | `transcripts/announcer/female_patron/patron_female_ally_orion_start_01.mp3.json` | generated / generated | You've lived quite the life, Rime, but you still have time for one last adventure. Complete the ritual and transform from a man into a legend. | You've lived quite the life, Riven, but you still have time for one last adventure. Complete the ritual and transform from a man into a legend. |
| 98.63% | `transcripts/atlas/abrams_unselect_08.mp3.json` | generated / generated | I got better things to do than getting shot at. | I got better things to do than gettin' shot at. |
| 98.63% | `transcripts/book/oathkeeper/vn_geist_scene03c_17.mp3.json` | generated / generated | You're binding of me. Ensure favorable terms. | You're binding of me. Ensured favorable terms. |
| 98.59% | `transcripts/haze/haze_idol_drop_05.mp3.json` | generated / generated | The last soul will be waiting on the bridge. | The last souls will be waiting on the bridge. |
| 98.58% | `transcripts/shopkeeper/guide_power_ap.mp3.json` | generated / generated | Destroying enemy objectives earns everyone on your team ability points. You also earn ability points as you accumulate souls. | Destroying an enemy objective earns everyone on your team ability points. You also earn ability points as you accumulate souls. |
| 98.57% | `transcripts/newscaster/newscaster_headline_27.mp3.json` | generated / generated | Have love potions ruined dating? See what relationship expert Madame LaPree thinks. | Have love potions ruined dating? See what relationship expert Madame LePree thinks. |
| 98.55% | `transcripts/gigawatt/gigawatt_lose_late_05.mp3.json` | generated / generated | We are defined by the quality of our rivals. | We're defined by the quality of our rivals. |
| 98.55% | `transcripts/nano/calico_upgrade_power3_02.mp3.json` | generated / generated | I'm going to put my fists through this skull. | I'm going to put my fist through this skull. |
| 98.54% | `transcripts/announcer/female_patron/patron_female_tutorial_combat_neutrals_info.mp3.json` | generated / generated | These neutrals won't attack you unless you attack them, but if you're looking to pick a fight, it's a great way to earn extra coins. | These neutrals won't attack you unless you attack them, but if you're looking to pick a fight, it's a great way to earn an extra coin. |
| 98.53% | `transcripts/lash/lash_upgrade_power1_05.mp3.json` | generated / generated | Every time I hear someone screaming frustration, I just get a big ol' smile on my face. | Every time I hear someone scream in frustration, I just get a big old smile on my face. |
| 98.51% | `transcripts/inferno/inferno_win_late_05.mp3.json` | generated / generated | History's gonna remember that we struggled. History's gonna remember that we won. | History is gonna remember that we struggled. History is gonna remember that we won. |
| 98.51% | `transcripts/krill/krill_kill_forge_04.mp3.json` | generated / generated | Looks like your turrets couldn't save you. | Looks like your turret couldn't save you. |
| 98.46% | `transcripts/announcer/female_patron/patron_female_enemy_walker_destroyed_03_alt_02.mp3.json` | generated / generated | We are so close to completing the ritual. | We're so close to completing the ritual. |
| 98.46% | `transcripts/atlas/abrams_enemy_bebop_kill_mid_laser_03.mp3.json` | generated / generated | That laser is supposed to be impressive. | That laser's supposed to be impressive. |
| 98.46% | `transcripts/lash/lash_use_power5_06.mp3.json` | generated / generated | They're just begging to get killed by me. | They are just begging to get killed by me. |
| 98.45% | `transcripts/lash/lash_unselect_03.mp3.json` | generated / generated | Fine. The Lash doesn't crash parties he's not invited to, because no party worth going to would ever not invite The Lash. | It's fine. The Lash doesn't crash parties he's not invited to, because no party worth going to would ever not invite The Lash. |
| 98.44% | `transcripts/slork/slork_select_05.mp3.json` | generated / generated | The sailors called me Fathom, but the denizens of the deep know me by my true name. | The sailors call me Fathom, but the denizens of the deep know me by my true name. |
| 98.43% | `transcripts/announcer/female_patron/patron_female_tutorial_lane_info.mp3.json` | generated / generated | First things first, you need to take out that Guardian at the end of this lane. By destroying it, we don't just get closer to the final objective, we earn money and ability points for the entire team. | First things first, you need to take out that Guardian that's at the end of this lane. By destroying it, we don't just get closer to the final objective, we earn money and ability points for the entire team. |
| 98.43% | `transcripts/newscaster/newscaster_headline_34.mp3.json` | generated / generated | The Gray Coven leaves audiences spellbound. Read the New York Oracle's review of the latest off-Broadway sensation. | The Great Coven leaves audiences spellbound. Read the New York Oracles review of the latest Off-Broadway sensation. |
| 98.43% | `transcripts/shopkeeper/hero_training_shopping_alt.mp3.json` | generated / generated | Time to go shopping. Hover over an item to see what it does. Then, buy something. Buy lots of somethings. Give me your money. | Time to go shopping. Hover over an item to see what it does. Then, buy something. Buy lots of somethings. Gimme your money. |
| 98.41% | `transcripts/announcer/male_patron/patron_male_enemy_doorman_killing_streak_low_01.mp3.json` | generated / generated | Stop the Dorman before he kills us all! | Stop the doorman before he kills us all! |
| 98.41% | `transcripts/krill/krill_kill_cadence_06.mp3.json` | generated / generated | Sorry, Momo. She did not leave us a choice. | Sorry, Momo. He did not leave us a choice. |
| 98.41% | `transcripts/nano/calico_use_power4_09.mp3.json` | generated / generated | Let me introduce you to my best friends. | Let me introduce you to my best friend. |
| 98.41% | `transcripts/shopkeeper/shopkeeper_hotdog_open_spirit_05.mp3.json` | generated / generated | In the mood for something magical, I see. | In the mood for somethin' magical, I see. |
| 98.40% | `transcripts/announcer/female_patron/patron_female_tutorial_tasks_complete.mp3.json` | generated / generated | Well done. Use the transit line to return to the base. Once you're there, I'll give you resources to spend so you can power up for a final push on that guardian. | Well done. Use the transit line to return to the base. Once you're there, I'll give you resources to spend so you can power up for the final push on that Guardian. |
| 98.39% | `transcripts/announcer/female_patron/patron_female_tutorial_single_lane_walker_intro.mp3.json` | generated / generated | Be careful taking out that walker. If you get too close, it'll try to crush you. | Be careful taking out that walker. If you get too close, it will try to crush you. |
| 98.39% | `transcripts/newscaster/newscaster_headline_19.mp3.json` | generated / generated | Funko! Party game or a ritual component. To the Soho coven, it's a little of both. | Bunko: party game or a ritual component. To the Soho coven, it's a little of both. |
| 98.36% | `transcripts/butcher/rr_test_21_upgrade_power1_09.mp3.json` | generated / generated | They'll be runnin' like hell in no time. | They'll be running like hell in no time. |
| 98.36% | `transcripts/slork/rr_test_26_close_call_05.mp3.json` | generated / generated | I got a heal before I go back out there. | I gotta heal before I go back out there. |
| 98.34% | `transcripts/newscaster/newscaster_headline_65.mp3.json` | generated / generated | Eldritch Tactical Solutions, a subsidiary of Fairfax Industries, comes under fire as new allegations are made by former employees. Are these soldiers of fortune committing war crimes? The New York Oracle investigates. | Eldridge Tactical Solutions, a subsidiary of Fairfax Industries, comes under fire as new allegations are made by former employees. Are these soldiers of fortune committing war crimes? The New York Oracle investigates. |
| 98.33% | `transcripts/announcer/male_patron/patron_male_ally_chrono_start_01.mp3.json` | generated / generated | You will show the other members of Paradox why you are fit to lead. Summon me. | You'll show the other members of Paradox why you are fit to lead. Summon me. |
| 98.33% | `transcripts/book/oathkeeper/vn_geist_scene02a_18.mp3.json` | generated / generated | Do I imagine I could drum up some interest? When next year were you thinking? | I imagine I could drum up some interest. When next year were you thinking? |
| 98.31% | `transcripts/atlas/abrams_happy_07.mp3.json` | generated / generated | After we take their shrine, I'm buyin'. | After we take their shrine, I'm buying. |
| 98.31% | `transcripts/book/oathkeeper/vn_geist_scene05i_02.mp3.json` | generated / generated | Peace. This dance with Urdkeeper needs to end. Free me of his influence, and let us all walk away prosperously. | Peace. This dance with Urthkeeper needs to end. Free me of his influence, and let us all walk away prosperously. |
| 98.31% | `transcripts/krill/krill_kill_gigawatt_02.mp3.json` | generated / generated | Oh, my hair is a static mess now, isn't it? | Oh, my hair's a static mess now, isn't it? |
| 98.31% | `transcripts/shopkeeper/shopkeeper_hotdog_t4_nano_02.mp3.json` | generated / generated | You ask me, the Oracle was way too harsh when they called you a warmonger. | If you ask me, the Oracle was way too harsh when they called you a warmonger. |
| 98.31% | `transcripts/tengu/tengu_ally_kelvin_pass_on_zipline_02.mp3.json` | generated / generated | Hey, Kelvin! Kelvin! Your name's Kelvin! | Hey, Kevin! Kelvin! Your name's Kelvin! |
| 98.28% | `transcripts/lash/lash_select_12_02.mp3.json` | generated / generated | Oh, I'll summon the patrons, and when I do, I know exactly what I'm wishing for. | I'll summon the patrons, and when I do, I know exactly what I'm wishing for. |
| 98.25% | `transcripts/book/oathkeeper/vn_geist_scene03b_17.mp3.json` | generated / generated | What good is eternal life if I spend it in an Ursyse oubliette? As we both know, that's exactly where I would end up if I gave in to your every whim. | What good is eternal life if I spend it in an Urassi oubliette? As we both know, that's exactly where I would end up if I gave in to your every whim. |
| 98.25% | `transcripts/haze/haze_enemy_wraith_lifts_03.mp3.json` | generated / generated | I'll make you suffer for this wreath. | I'll make you suffer for this wrath. |
| 98.25% | `transcripts/krill/krill_killed_by_ghost_04.mp3.json` | generated / generated | It would seem the powers of the eighth son aren't an overexaggeration. | It would seem the powers of the eighth sun aren't an overexaggeration. |
| 98.25% | `transcripts/lash/lash_angry_01.mp3.json` | generated / generated | They're not gonna get the best of us. | They are not gonna get the best of us. |
| 98.18% | `transcripts/atlas/abrams_use_tech_defender_02.mp3.json` | generated / generated | I'm not worried about their power. | I'm not worried about their powers. |
| 98.18% | `transcripts/shiv/shiv_sad_05.mp3.json` | generated / generated | Never should have taken this job. | I never should have taken this job. |
| 98.18% | `transcripts/warden/warden_ally_shiv_unkillable_02.mp3.json` | generated / generated | Looks like he's not a fop after all. | Looks like he's not a flop after all. |
| 98.18% | `transcripts/wraith/wraith_ally_shiv_unkillable_01.mp3.json` | generated / generated | They don't have an answer for Shiv. | They don't have any answer for Shiv. |
| 98.11% | `transcripts/haze/haze_idol_drop_06.mp3.json` | generated / generated | Who is going to get the spirit jar? | Who's going to get the spirit jar? |
| 98.11% | `transcripts/haze/haze_unselect_09.mp3.json` | generated / generated | More time to find my next target. | More time to find my next targets. |
| 98.11% | `transcripts/lash/lash_select_03.mp3.json` | generated / generated | Oh, I'll summon the patrons, but just so I can tell them, you're welcome. | Oh, I'll summon the patrons, but just so I can tell 'em, you're welcome. |
| 98.11% | `transcripts/nano/calico_sad_01.mp3.json` | generated / generated | I am surrounded by incompetence. | I'm surrounded by incompetence. |
| 98.11% | `transcripts/nano/calico_use_silencer_03.mp3.json` | generated / generated | Hm, their powers will be useless. | Hmm, their powers will be useless. |
| 98.11% | `transcripts/paradox/ping/paradox_ping_mcginnis_under_garage.mp3.json` | generated / generated | The guiness is under the garage. | The guinness is under the garage. |
| 98.11% | `transcripts/wraith/ping/wraith_ping_orion_check_items.mp3.json` | generated / generated | Check out what great talent bots! | Check out what great talent bot! |
| 98.09% | `transcripts/announcer/female_patron/patron_female_ally_vampirebat_start_05.mp3.json` | manual / official | Once you complete the ritual, Arin will realize their folly, and the other vampires you are worth. | Once you complete the ritual, Arin will realize their folley.  And the other vampires, your worth. |
| 98.08% | `transcripts/lash/lash_select_10_02.mp3.json` | generated / generated | I'm not dumb. I know a lot of people hate me. It's a... I mean, it's a curse, really. You know, I rule so hard that, uh, you know, every mediocre soul in the city just has to resent me. | I'm not dumb. I know a lot of people hate me. It's a... I mean, it's a curse, really. You know, I've ruled so hard that, you know, every mediocre soul in the city just has to resent me. |
| 98.08% | `transcripts/lash/ping/lash_ping_post_game_04.mp3.json` | generated / generated | Ah, no need to thank me. Being amazing is a burden I'm happy to bear. | Ah-ah, no need to thank me. Being amazing is a burden I'm happy to bear. |
| 98.08% | `transcripts/paradox/paradox_upgrade_power4_02.mp3.json` | generated / generated | If someone's by themselves, I'll drag 'em to where I want them to be. | If someone's by themselves, I'll drag them to where I want them to be. |
| 98.07% | `transcripts/book/oathkeeper/vn_geist_scene05h_12.mp3.json` | generated / generated | I don't really know if flowers are the appropriate thing to bring someone who endangered your life before saving it, but I just... I don't know, just had to see you. | I don't really know if flowers are the appropriate thing to bring someone who endangered your life before saving it, but I just, I just... I don't know, just had to see you. |
| 98.06% | `transcripts/newscaster/newscaster_headline_48.mp3.json` | generated / generated | Looking to take your kids to the Bleet Carnival? Pick up your copy of the New York Oracle to find out how to keep your family safe. | Looking to take your kids to the Bleak Carnival? Pick up your copy of the New York Oracle to find out how to keep your family safe. |
| 98.04% | `transcripts/atlas/abrams_select_08.mp3.json` | generated / generated | No one's takin' this book from me. | No one's taking this book from me. |
| 98.04% | `transcripts/atlas/ping/abrams_ping_grey_talon_under_garage.mp3.json` | generated / generated | Great talents under the garage. | Great talent under the garage. |
| 98.04% | `transcripts/atlas/ping/abrams_ping_grey_talon_under_garage_1.mp3.json` | generated / generated | Great talents under the garage. | Great talent under the garage. |
| 98.04% | `transcripts/atlas/ping/abrams_ping_orion_under_garage_1.mp3.json` | generated / generated | Great talents under the garage. | Great talent under the garage. |
| 98.04% | `transcripts/forge/ping/mcginnis_ping_viscous_check_items.mp3.json` | generated / generated | Check out what Biscuit bought. | Check out what Biscuit's bought. |
| 98.04% | `transcripts/ghost/geist_enemy_astro_bounce_escape_02.mp3.json` | generated / generated | He can't keep bouncing forever. | She can't keep bouncing forever. |
| 98.04% | `transcripts/ghost/ping/geist_ping_grey_talon_on_top_of_garage.mp3.json` | generated / generated | Great ammo on top of the garage! | Great ammo's on top of the garage. |
| 98.04% | `transcripts/ghost/ping/geist_ping_grey_talon_under_garage.mp3.json` | generated / generated | Great talent under the garage. | Great talent's under the garage. |
| 98.04% | `transcripts/ghost/ping/geist_ping_orion_on_top_of_garage.mp3.json` | generated / generated | Great ammo on top of the garage! | Great ammo's on top of the garage. |
| 98.04% | `transcripts/ghost/ping/geist_ping_orion_under_garage.mp3.json` | generated / generated | Great talent under the garage. | Great talent's under the garage. |
| 98.04% | `transcripts/gigawatt/gigawatt_outnumbered_03.mp3.json` | generated / generated | It's not wise to engage on my own. | It is not wise to engage on my own. |
| 98.04% | `transcripts/paradox/ping/paradox_ping_yamato_on_top_of_garage.mp3.json` | generated / generated | Yamato's on top of the carriage! | Yamato is on top of the carriage! |
| 98.01% | `transcripts/newscaster/newscaster_headline_47.mp3.json` | generated / generated | The median line continues to be closed this week. While the mayor has not spoken publicly on the nature of the closure, inside sources suspect it may have something to do with a sewer spirit. | The line continues to be closed this week. While the mayor has not spoken publicly on the nature of the closure, inside sources suspect it may have something to do with a sewer spirit. |
| 98.00% | `transcripts/lash/lash_ally_orion_pass_on_zipline_01.mp3.json` | generated / generated | Don't worry, old man. The last will be back to help carry you soon. | Don't worry, old man, The Lash will be back to help carry you soon. |

## Medium confidence

Showing 100 of 1,828 candidates.

| Similarity | Path | Sources | Left text | Right text |
| ---: | --- | --- | --- | --- |
| 94.95% | `transcripts/haze/haze_enemy_forge_destroy_turrets_02.mp3.json` | generated / generated | Build as many of those machines as you want, they won't help you. | Fill as many of those machines as you want, they won't help you. |
| 94.92% | `transcripts/atlas/abrams_enemy_inferno_killed_mid_ult_01.mp3.json` | generated / generated | You never had what it takes, Inferno. | You never had what it takes, Infernus. |
| 94.92% | `transcripts/dynamo/prof_kill_forge_05.mp3.json` | generated / generated | Did T-rex put you up to this, McGinnis? | Did Tivex put you up to this, McGinnis? |
| 94.92% | `transcripts/forge/mcginnis_kill_shiv_04.mp3.json` | generated / generated | Could get a fight the wrong way, Shiv. | Could get to fight the wrong way, Shiv. |
| 94.92% | `transcripts/ghost/geist_ally_haze_interrupt_with_finesse_01.mp3.json` | generated / generated | Your precision is impeccable, Haze. | Your precision is impeccable, Hades. |
| 94.92% | `transcripts/gigawatt/gigawatt_ally_orion_missile_stops_ult_01.mp3.json` | generated / generated | the Ryan knows how to make an entrance. | Ryan knows how to make an entrance. |
| 94.92% | `transcripts/haze/haze_idol_drop_08.mp3.json` | generated / generated | We can't forget about the spirit charm. | We can't forget about SpiritCharm. |
| 94.92% | `transcripts/mirage/mirage_upgrade_power2_02_alt.mp3.json` | generated / generated | I'll let the beasts do the work for me. | I'll let the Beatles do the work for me. |
| 94.92% | `transcripts/nano/calico_concerned_06.mp3.json` | generated / generated | We can't give them the satisfaction. | We can't give them this satisfaction. |
| 94.92% | `transcripts/shopkeeper/guide_the_map_walkers.mp3.json` | generated / generated | Walkers lie deeper in the lanes and have an arsenal of defensive moves. | Walkers lie deeper in the lengths and have an arsenal of defensive moves. |
| 94.92% | `transcripts/t1_guardians/guardian_test_02/rr_guardian_test_02_thanks_05.mp3.json` | generated / generated | Ha! Knew you wouldn't leave me hanging! | Ah, knew you wouldn't leave me hangin'. |
| 94.92% | `transcripts/viscous/viscous_sad_01.mp3.json` | generated / generated | Coming to this surface was a mistake. | Coming to the surface was a mistake. |
| 94.92% | `transcripts/wraith/wraith_idol_drop_04.mp3.json` | generated / generated | Do we want to collect the spirit urn? | Do we want to collect this spirit urn? |
| 94.87% | `transcripts/forge/mcginnis_killstreak_start_03.mp3.json` | generated / generated | You know any my jersey, yeah, you're gonna real soon. | You know any myters, yeah, you're gonna real soon. |
| 94.87% | `transcripts/inferno/inferno_win_late_04.mp3.json` | generated / generated | It doesn't matter if it was a fast win or a long win. At the end of the day, all that matters is that you win. | It doesn't matter if it was a fast win or a long win. At the end of the day, all that matters is the W. |
| 94.85% | `transcripts/announcer/female_patron/patron_female_lose_objective_while_ahead_01.mp3.json` | generated / generated | They've taken the objective, but we still hold the advantage. | They've taken an objective, but we still hold the advantage. |
| 94.85% | `transcripts/lash/lash_unselect_03.mp3.json` | generated / generated | Define the last dozen crash parties he's not invited to, because no party worth going to would ever not invite the Lash. | It's fine. The Lash doesn't crash parties he's not invited to, because no party worth going to would ever not invite The Lash. |
| 94.83% | `transcripts/shopkeeper/guide_power_secure.mp3.json` | generated / generated | When you light a killing blow, exit soul's pop out. You can secure these souls by shooting the green orb, tanking them, or letting them float away. | When you land a killing blow, exit souls pop out! You can secure these souls by shooting the green orb containing them, or letting them float away. |
| 94.74% | `transcripts/announcer/female_patron/patron_female_ally_sandeep_start_01.mp3.json` | generated / generated | You seek to change the world, Saint, but doing that will come at a price. | You seek to change the world, Sandlip, but doing that will come at a price. |
| 94.74% | `transcripts/announcer/female_patron/patron_female_grant_boon_general_06.mp3.json` | generated / generated | The patrons give free. | The patrons give freely. |
| 94.74% | `transcripts/announcer/female_patron/patron_female_tutorial_farm_reminder_alt_01.mp3.json` | generated / generated | Remember, you only earn souls off a dying trooper if you were an ally at the last hit. | Remember, you only earn souls off a dying trooper if you or an ally get the last hit. |
| 94.74% | `transcripts/atlas/abrams_ally_yamato_kills_with_hook_03.mp3.json` | generated / generated | No one runs from Yamano. | No one runs from Yamato. |
| 94.74% | `transcripts/atlas/ping/abrams_ping_attack_hornet.mp3.json` | generated / generated | Let's take out Vindicta. | Let's take our vindicta. |
| 94.74% | `transcripts/atlas/ping/abrams_ping_rupture_almost_ready.mp3.json` | generated / generated | Rupture's almost ready. | Rapture's almost ready. |
| 94.74% | `transcripts/atlas/ping/abrams_ping_stun_atlas_01.mp3.json` | generated / generated | So netless. | Sonnetless. |
| 94.74% | `transcripts/atlas/ping/abrams_ping_stun_calico_01.mp3.json` | generated / generated | Stun, Calico. | Sun Calico. |
| 94.74% | `transcripts/bebop/bebop_unselect_07.mp3.json` | generated / generated | Michelle is having one of her good days, so I'm gonna spend time with her while I can. | Miss Shelly's having one of her good days, so I'm gonna spend time with her while I can. |
| 94.74% | `transcripts/book/oathkeeper/vn_geist_scene05g_03.mp3.json` | generated / generated | oma, please! | Omar, please! |
| 94.74% | `transcripts/bookworm/ping/bookworm_ping_stun_dynamo_01.mp3.json` | generated / generated | Stun Dynamo. | Sun Dynamo. |
| 94.74% | `transcripts/bookworm/ping/bookworm_ping_stun_slork_01.mp3.json` | generated / generated | Stun fathom. | Sunfathom. |
| 94.74% | `transcripts/bookworm/ping/bookworm_ping_viscous_almost_respawn.mp3.json` | generated / generated | This gets almost back. | This gets us almost back. |
| 94.74% | `transcripts/butcher/rr_test_21_ping_archer_headed_to_orange.mp3.json` | generated / generated | R's is headed to orange. | Ours is headed to orange. |
| 94.74% | `transcripts/butcher/rr_test_21_ping_attack_engineer.mp3.json` | generated / generated | Let's take out Engineer. | Let's take our engineer. |
| 94.74% | `transcripts/butcher/rr_test_21_ping_bull_headed_to_purple.mp3.json` | generated / generated | Pulls headed to purple. | Pulse headed to purple! |
| 94.74% | `transcripts/butcher/rr_test_21_ping_hornet_headed_to_blue.mp3.json` | generated / generated | Point it headed to blue! | Point is headed to blue! |
| 94.74% | `transcripts/butcher/rr_test_21_ping_see_ghost.mp3.json` | generated / generated | I see ghosts. | I see Ghost. |
| 94.74% | `transcripts/butcher/rr_test_21_ping_stun_chrono_01.mp3.json` | generated / generated | Stun chrono! | Sun Chrono. |
| 94.74% | `transcripts/butcher/rr_test_21_ping_wraith_headed_to_orange.mp3.json` | generated / generated | Grey's headed to Orange! | Gray's headed to orange! |
| 94.74% | `transcripts/dynamo/ping/prof_ping_hornet_on_top_of_mid.mp3.json` | generated / generated | Vindicta's on top of mid! | Vendicta's on top of mid! |
| 94.74% | `transcripts/dynamo/ping/prof_ping_lash_under_garage.mp3.json` | generated / generated | Clash under the garage! | Crash under the garage! |
| 94.74% | `transcripts/dynamo/prof_enemy_astro_bounce_escape_02.mp3.json` | generated / generated | She got away. | He got away! |
| 94.74% | `transcripts/forge/mcginnis_idol_drop_03.mp3.json` | generated / generated | The spell I'll be my son. | The spell I will be my son. |
| 94.74% | `transcripts/forge/ping/mcginnis_ping_see_fairfax_on_bridge.mp3.json` | generated / generated | Krebak's is on the bridge! | Krebak's on the bridge! |
| 94.74% | `transcripts/ghost/geist_enemy_haze_kill_when_invisible_02.mp3.json` | generated / generated | There's no escape, Hanes. | There's no escape, Hayes. |
| 94.74% | `transcripts/ghost/geist_kill_seven_04.mp3.json` | generated / generated | The convoy has stopped. | The convoy was stopped. |
| 94.74% | `transcripts/ghost/geist_upgrade_power4_06.mp3.json` | generated / generated | Today we'll keep our receipts payment in space. | Today we'll keep our receipts payment in Spain. |
| 94.74% | `transcripts/ghost/ping/geist_ping_krill_under_garage.mp3.json` | generated / generated | Please under that rush. | Please under that rash. |
| 94.74% | `transcripts/gigawatt/gigawatt_ally_orion_missile_stops_ult_01.mp3.json` | generated / generated | Ryan knows how to make an entrance. | Brian knows how to make an entrance. |
| 94.74% | `transcripts/gigawatt/gigawatt_ally_warden_pass_on_zipline_01.mp3.json` | generated / generated | I'll be back soon, Warren. | I'll be back soon, Warden. |
| 94.74% | `transcripts/gigawatt/gigawatt_kill_kelvin_02.mp3.json` | generated / generated | Die, killin'! | DIE, KILLING! |
| 94.74% | `transcripts/gigawatt/gigawatt_kill_nano_04.mp3.json` | generated / generated | Nano is down. | Nano's down! |
| 94.74% | `transcripts/gigawatt/ping/gigawatt_ping_attack_gigawatt.mp3.json` | generated / generated | Let's take out Gigawatt. | Let's take out Digawatt. |
| 94.74% | `transcripts/gigawatt/ping/gigawatt_ping_can_heal_astro.mp3.json` | generated / manual | Holliday, I can hear you. | Holliday, I can heal you! |
| 94.74% | `transcripts/gigawatt/ping/gigawatt_ping_can_heal_mirage.mp3.json` | generated / generated | All right, I can hear you. | All right, I can heal you. |
| 94.74% | `transcripts/haze/ping/haze_ping_heal_ready.mp3.json` | generated / generated | Heal's ready. | Heal ready. |
| 94.74% | `transcripts/haze/ping/haze_ping_wrecker_almost_respawn.mp3.json` | generated / generated | Wrecker is almost back. | Grecker is almost back. |
| 94.74% | `transcripts/hornet/ping/vindicta_ping_can_heal_mcginnis.mp3.json` | generated / generated | McGinnis, I can heal you. | McGinnis, I can hear you. |
| 94.74% | `transcripts/hornet/vindicta_idol_drop_02.mp3.json` | generated / generated | We collect spirits on the bridge. | We can collect spirits on the bridge. |
| 94.74% | `transcripts/inferno/inferno_ally_chrono_steals_rejuv_02.mp3.json` | generated / generated | Paradox stole the Reju! | Paradox stole the Riju! |
| 94.74% | `transcripts/inferno/inferno_kill_forge_05_02.mp3.json` | generated / generated | You may be a genius, but you weren't smart enough to stay home. | You may be a genius, but you wasn't smart enough to stay home. |
| 94.74% | `transcripts/inferno/ping/inferno_ping_krill_dead.mp3.json` | generated / generated | Crew is dead. | Crew's dead. |
| 94.74% | `transcripts/inferno/ping/inferno_ping_krill_was_here.mp3.json` | generated / generated | Crew's here! | Crew is here! |
| 94.74% | `transcripts/inferno/ping/inferno_ping_orion_check_items.mp3.json` | generated / generated | Check out what great talent bought. | Check out what Great Talon bought. |
| 94.74% | `transcripts/inferno/ping/inferno_ping_stun_mirage_01.mp3.json` | generated / generated | Stun Mirage. | Sun Mirage. |
| 94.74% | `transcripts/kali/rr_test_19_ping_stun_hornet_01.mp3.json` | generated / generated | Stun Hornet! | Sunhornet! |
| 94.74% | `transcripts/kali/rr_test_19_use_power1_10.mp3.json` | generated / generated | There we are. | Here we are. |
| 94.74% | `transcripts/kelvin/kelvin_enemy_lash_mid_air_kill_03.mp3.json` | generated / generated | I'll style no substance. | All style, no substance. |
| 94.74% | `transcripts/krill/krill_killed_by_chrono_03.mp3.json` | generated / generated | Stupid bee with her stupid time manipulation! | Stupid bee with our stupid time manipulation! |
| 94.74% | `transcripts/krill/krill_killed_by_ghost_04.mp3.json` | generated / generated | It would seem the powers of the eighth son aren't an overexaggeration. | It would seem the powers of the Aether Son aren't an overexaggeration. |
| 94.74% | `transcripts/krill/krill_killed_by_gigawatt_01.mp3.json` | generated / generated | Gigawatts cunning! We must be cutting too much. | Gigawatts cutting! We must be cutting too much. |
| 94.74% | `transcripts/krill/ping/krill_ping_stun_dynamo_01.mp3.json` | generated / generated | stun Dynamo! | Sun Dynamo. |
| 94.74% | `transcripts/krill/ping/krill_ping_stun_mirage_01.mp3.json` | generated / generated | Stun Mirage! | Sun Mirage! |
| 94.74% | `transcripts/lash/lash_upgrade_power5_08.mp3.json` | generated / generated | Ready to take them apart. | Ready to take 'em apart. |
| 94.74% | `transcripts/lash/lash_use_power1_02.mp3.json` | generated / generated | Dice Strike! | Die strike! |
| 94.74% | `transcripts/lash/ping/lash_ping_haze_was_here.mp3.json` | generated / generated | Haze is here. | Hazes here. |
| 94.74% | `transcripts/lash/ping/lash_ping_headed_blue_01.mp3.json` | generated / generated | Heads blue. | Head is blue. |
| 94.74% | `transcripts/lash/ping/lash_ping_saw_ghost.mp3.json` | generated / generated | I saw a Geist. | I saw Geist. |
| 94.74% | `transcripts/lash/ping/lash_ping_stun_kelvin_01.mp3.json` | generated / generated | Sun Kelvin. | Stun Kelvin! |
| 94.74% | `transcripts/lash/ping/lash_ping_stun_warden_01.mp3.json` | generated / generated | Sunwarden. | Stun Warden. |
| 94.74% | `transcripts/mirage/ping/mirage_ping_atlas_dead.mp3.json` | generated / generated | If I'm stead. | If I'm steady. |
| 94.74% | `transcripts/mirage/ping/mirage_ping_with_orion.mp3.json` | generated / generated | I'm with you, Great Talon. | I'm with you, Great Taron. |
| 94.74% | `transcripts/nano/ping/calico_ping_attack_sandeep.mp3.json` | generated / generated | Let's take out Sandeep. | Let's take it out, Sandeep. |
| 94.74% | `transcripts/nano/ping/calico_ping_bebop_under_garage.mp3.json` | generated / generated | E-bots under the garage. | E-bops under the garage. |
| 94.74% | `transcripts/nano/ping/calico_ping_careful_gigawatt_01.mp3.json` | generated / generated | Carefully get the watch. | Careful, get the watch. |
| 94.74% | `transcripts/nano/ping/calico_ping_see_abrams_on_roof.mp3.json` | generated / generated | Gave of this on the roof. | Game of this on the roof. |
| 94.74% | `transcripts/paradox/ping/paradox_ping_saw_wrecker.mp3.json` | generated / generated | I saw Raker! | I saw Racker! |
| 94.74% | `transcripts/pocket/ping/pocket_ping_stun_calico_01.mp3.json` | generated / generated | Stun Calico. | Sun Calico. |
| 94.74% | `transcripts/pocket/ping/pocket_ping_wraith_in_mid.mp3.json` | generated / generated | Grace in mid. | Race in mid. |
| 94.74% | `transcripts/priest/ping/priest_ping_saw_ghost.mp3.json` | generated / generated | I saw a Geist! | I saw Geist. |
| 94.74% | `transcripts/synth/ping/pocket_ping_stun_calico_01.mp3.json` | generated / generated | Stun Calico. | Sun Calico. |
| 94.74% | `transcripts/synth/ping/pocket_ping_wraith_in_mid.mp3.json` | generated / generated | Grace in mid. | Race in mid. |
| 94.74% | `transcripts/t1_guardians/guardian_test_02/rr_guardian_test_02_under_attack_07.mp3.json` | generated / generated | Some help on orange would be nice! | Some help on the Orange would be nice! |
| 94.74% | `transcripts/tengu/ivy_enemy_ghost_ping_with_swap_02.mp3.json` | generated / generated | Guys is looking to steal your life! | Guys, he's looking to steal your life! |
| 94.74% | `transcripts/tengu/ivy_enemy_inferno_killed_mid_ult_03.mp3.json` | generated / generated | That could have gone by real quick! | That could have gone bad real quick. |
| 94.74% | `transcripts/tengu/ivy_tower_got_denied_05.mp3.json` | generated / generated | They can keep the money! We've got what we came for. | We can keep the money. We've got what we came for. |
| 94.74% | `transcripts/tengu/ivy_unselect_08.mp3.json` | generated / generated | Can I at least have a hug? | Can I at least have a hog? |
| 94.74% | `transcripts/tengu/ping/ivy_ping_see_kelvin_01.mp3.json` | generated / generated | I see Kelvin! | I see Kevin. |
| 94.74% | `transcripts/tengu/ping/tengu_ping_ignore_lash.mp3.json` | generated / generated | Ignorelash! | Ignore las |
| 94.74% | `transcripts/tengu/tengu_unselect_08.mp3.json` | generated / generated | Can I at least have a hug? | Can I at least have a hog? |
| 94.74% | `transcripts/vampirebat/ping/vampirebat_ping_stun_warden_01.mp3.json` | generated / generated | Stun Warden! | Sunwarden! |

## Low confidence

Showing 100 of 4,050 candidates.

| Similarity | Path | Sources | Left text | Right text |
| ---: | --- | --- | --- | --- |
| 89.94% | `transcripts/gigawatt/gigawatt_unselect_09.mp3.json` | generated / generated | One day you will fail, and when you do, remember this moment. The moment you could have shared in victory. | One day you will save us all, and when you do, remember this moment. The moment you could have chosen victory. |
| 89.92% | `transcripts/announcer/male_patron/patron_male_ally_ghost_start_02.mp3.json` | generated / official | Time is running out, Lady Geist. Summon me before Oathkeeper breaks free. | Time is running out Lady Geist.  Summon The Hidden King before Oathkeeper breaks free. |
| 89.86% | `transcripts/announcer/female_patron/patron_female_ally_viscous_start_10.mp3.json` | generated / generated | Don't discount what you bring to the table, Viscous, but I see you for what you are. | Only a fool would discount what you bring to the table, Viscous, but I see you for what you are. |
| 89.86% | `transcripts/bebop/bebop_killed_by_akimbo_04.mp3.json` | generated / generated | Kemba has become a stooge of the organics. | The Kenba's become a stooge of the organics! |
| 89.86% | `transcripts/gigawatt/gigawatt_enemy_hornet_killed_mid_air_03.mp3.json` | generated / generated | Indeed, I learned a valuable lesson today. | Vindicta learned a valuable lesson today. |
| 89.86% | `transcripts/orion/orion_outnumbered_03.mp3.json` | generated / generated | I couldn't help anyone if I threw my life away. | I can't help anyone if I throw my life away. |
| 89.86% | `transcripts/shiv/shiv_ally_geist_killed_in_lane_02_02.mp3.json` | generated / generated | This is it. That's me, but probably next time. | That's it, that's me, but probably next time we |
| 89.86% | `transcripts/tengu/ivy_kill_forge_03.mp3.json` | generated / generated | I thought you were supposed to be some genius. | But you were supposed to be some genius! |
| 89.86% | `transcripts/tengu/tengu_unselect_01.mp3.json` | generated / generated | Hey, maybe I'll make that interview after all! | Hey, maybe I'll make that dinner after all! |
| 89.83% | `transcripts/forge/mcginnis_unselect_04.mp3.json` | generated / generated | Great, I've got a new way to weaponize souls in my shower. I need to go to the lab. | Great, I've got a new way to weaponize soul machawa. I need to go to the lab. |
| 89.82% | `transcripts/gigawatt/gigawatt_unselect_09.mp3.json` | generated / generated | One day you will fail, and when you do, remember this moment. The moment you could have shared in victory. | One day you will save her, and when you do, remember this moment. The moment you could have chosen victory. |
| 89.80% | `transcripts/forge/ping/mcginnis_ping_warden_on_top_of_garage.mp3.json` | generated / generated | The one is on top of the garage. | The word is on top of the garage. |
| 89.80% | `transcripts/ghost/geist_idol_drop_12.mp3.json` | generated / generated | There's a spear on the bridge. | There's a spew turn on the bridge. |
| 89.80% | `transcripts/gigawatt/gigawatt_concerned_10.mp3.json` | generated / generated | Time for the good shopping now. | Time for the get shopping now. |
| 89.80% | `transcripts/haze/haze_enemy_chrono_kill_post_swap_03.mp3.json` | generated / generated | Did she think that would work? | Does she think that would work? |
| 89.80% | `transcripts/haze/haze_enemy_orion_see_missile_02.mp3.json` | generated / generated | Get away from that missile. | Gotta get away from that missile. |
| 89.80% | `transcripts/haze/haze_enemy_wraith_lifts_02.mp3.json` | generated / generated | Pray I don't survive this race. | Pray I don't survive this waste. |
| 89.80% | `transcripts/haze/haze_enemy_wraith_lifts_02.mp3.json` | generated / generated | Pray I don't survive this week. | Pray I don't survive this waste. |
| 89.80% | `transcripts/haze/haze_enemy_wraith_lifts_02.mp3.json` | generated / generated | Pray I don't survive this waste. | Pray I don't survive this wish. |
| 89.80% | `transcripts/haze/ping/haze_ping_wrecker_check_items.mp3.json` | generated / generated | Check out what Wrecker bought. | Check out what Record bought. |
| 89.80% | `transcripts/inferno/inferno_enemy_chrono_steals_rejuv_03.mp3.json` | generated / generated | Of course she stole the rune. | Of course she stole the Rejuvin. |
| 89.80% | `transcripts/krill/krill_killed_by_lash_02.mp3.json` | generated / generated | You can come in from anywhere. | They can come in from anywhere. |
| 89.80% | `transcripts/krill/krill_sad_09.mp3.json` | generated / generated | Oh, I don't know how we win this. | Oh, I don't know how we ruined this. |
| 89.80% | `transcripts/tengu/ivy_idol_drop_02.mp3.json` | generated / generated | There's a Spitter on the bridge. | There's a skater on the bridge. |
| 89.80% | `transcripts/tengu/ivy_kill_orion_01.mp3.json` | generated / generated | I wanted to respect my elders, but you gotta give me no choice! | I wanted to respect my elders, but you kinda gave me no choice! |
| 89.80% | `transcripts/wraith/ping/wraith_ping_sandeep_under_garage.mp3.json` | generated / generated | Sand deep is under the garage. | Send deepest under the garage. |
| 89.80% | `transcripts/wraith/ping/wraith_ping_wrecker_check_items.mp3.json` | generated / generated | Check out what Record bought! | Check out what Wrecker bought. |
| 89.80% | `transcripts/wraith/wraith_enemy_ghost_ping_with_swap_01.mp3.json` | generated / generated | Guys are looking to drain life. | Guys is looking to drain life. |
| 89.80% | `transcripts/wraith/wraith_select_01.mp3.json` | generated / generated | If you think crime doesn't pay, you are outrageously bad at crime. | If you think crime doesn't pay, you are really bad at crime. |
| 89.74% | `transcripts/announcer/female_patron/patron_female_ally_gigawatt_start_05.mp3.json` | generated / generated | Your destiny awaits, Egwot. Complete the ritual. | Your destiny awaits, Seven. Complete the ritual. |
| 89.74% | `transcripts/announcer/male_patron/patron_male_ally_orion_start_02.mp3.json` | generated / official | Your heart is burdened by the horrors you've seen. Summon me, and I will help you find peace. | Your heart is burdened by the horrors you've seen… summon The Hidden King and he will help you find peace. |
| 89.74% | `transcripts/shiv/shiv_upgrade_power3_06.mp3.json` | generated / generated | Take one out, this way here. Take out another one. | Take one out, this right here, take out another one. |
| 89.70% | `transcripts/announcer/female_patron/patron_female_ally_shiv_start_04.mp3.json` | generated / generated | The monster inside is not a beast. He's ambitious. Complete the ritual, and you will finally be saved. | The monster inside you is not the beast. It is ambition. Complete the ritual, and you will finally be sated. |
| 89.70% | `transcripts/announcer/male_patron/patron_male_ally_viper_start_02.mp3.json` | generated / official | I see into your heart fiber. I know what you want, and you can have it. All you need to do is summon me. | I see into your heart Viper.  I know what you want.  And you can have it… all you need to do is summon The Hidden King. |
| 89.66% | `transcripts/announcer/female_patron/patron_female_tutorial_combat_companion_need_help_05.mp3.json` | generated / generated | And I need your help. | I need your help. |
| 89.66% | `transcripts/atlas/abrams_ally_holliday_pass_on_zipline_01.mp3.json` | generated / generated | Go get 'em, sheriff! | Go get him, Sheriff! |
| 89.66% | `transcripts/atlas/ping/abrams_ping_kali_missing_01.mp3.json` | generated / generated | Holliday's missing. | Holly's missing. |
| 89.66% | `transcripts/atlas/ping/abrams_ping_see_ghost_on_bridge.mp3.json` | generated / generated | guys on the bridge. | Gas on the bridge. |
| 89.66% | `transcripts/bebop/bebop_unselect_02.mp3.json` | generated / generated | Great. More time for me to work out new ways to hurt Nash. | Good. More time for me to work out new ways to hurt Lash. |
| 89.66% | `transcripts/bebop/bebop_use_hook_03.mp3.json` | generated / generated | I'm gonna grab him! | I'm gonna grab them! |
| 89.66% | `transcripts/bebop/ping/bebop_ping_calico_was_here.mp3.json` | generated / generated | Gotta go, who's here! | Gotta go was here! |
| 89.66% | `transcripts/bookworm/ping/bookworm_ping_haze_almost_respawn.mp3.json` | generated / generated | Haze is almost back. | He's almost back. |
| 89.66% | `transcripts/bookworm/ping/bookworm_ping_skyrunner_missing_01.mp3.json` | generated / generated | Skyron is missing. | Skyrim's missing. |
| 89.66% | `transcripts/bookworm/ping/bookworm_ping_with_dynamo.mp3.json` | generated / generated | I'm with you, Dynamo. | I'm with you, Daimo. |
| 89.66% | `transcripts/butcher/rr_test_21_pick_up_rejuv_02.mp3.json` | generated / generated | We got the rejuice. | We got the rejuke! |
| 89.66% | `transcripts/butcher/rr_test_21_pick_up_rejuv_02.mp3.json` | generated / generated | We got the rejuice. | We got the rejuve! |
| 89.66% | `transcripts/butcher/rr_test_21_ping_attack_archer.mp3.json` | generated / generated | Let's take out Ork. | Let's take out Rock. |
| 89.66% | `transcripts/butcher/rr_test_21_ping_attack_kali.mp3.json` | generated / generated | That's it, Chatalee! | That's it, Chatali! |
| 89.66% | `transcripts/butcher/rr_test_21_ping_need_help_yellow.mp3.json` | generated / generated | We help on yellow! | Get help on yellow! |
| 89.66% | `transcripts/dynamo/ping/prof_ping_wrecker_on_top_of_mid.mp3.json` | generated / generated | Ray's on top of mid! | Ready on top of mid! |
| 89.66% | `transcripts/forge/mcginnis_desperation_power4_04.mp3.json` | generated / generated | See you in class. | See you in the class! |
| 89.66% | `transcripts/forge/mcginnis_kill_anyhero_06.mp3.json` | generated / generated | Just take that plan. | Just take a plan. |
| 89.66% | `transcripts/forge/mcginnis_kill_geist_01.mp3.json` | generated / generated | I stopped the leash. | I stop the leash. |
| 89.66% | `transcripts/forge/mcginnis_kill_geist_05.mp3.json` | generated / generated | I got that like that. | Gotta like that. |
| 89.66% | `transcripts/forge/mcginnis_pick_up_rejuv_01.mp3.json` | generated / generated | We got the rejuve. | We got the rejuice. |
| 89.66% | `transcripts/forge/mcginnis_use_power4_06.mp3.json` | generated / generated | I'll give him hell. | I'll give them hell. |
| 89.66% | `transcripts/forge/ping/mcginnis_ping_astro_missing_01.mp3.json` | generated / generated | Holly's missing. | Holliday's missing. |
| 89.66% | `transcripts/forge/ping/mcginnis_ping_holliday_missing_01.mp3.json` | generated / generated | Holly's missing. | Holliday's missing. |
| 89.66% | `transcripts/forge/ping/mcginnis_ping_saw_grey_talon.mp3.json` | generated / generated | I saw a great talon! | I saw a Grey Talon! |
| 89.66% | `transcripts/forge/ping/mcginnis_ping_saw_orion.mp3.json` | generated / generated | I saw a great talon! | I saw a Grey Talon! |
| 89.66% | `transcripts/ghost/geist_ally_yamato_kills_with_hook_01.mp3.json` | generated / generated | Yamato was subdued. | Yamato was sued. |
| 89.66% | `transcripts/ghost/geist_t3_shop_reminder_02.mp3.json` | generated / generated | Someone you won't help me in my pocket. | Somebody won't help me in my pocket. |
| 89.66% | `transcripts/gigawatt/gigawatt_ally_chrono_killed_in_lane_01.mp3.json` | generated / generated | Take out Paradox! | I talk out Paradox. |
| 89.66% | `transcripts/gigawatt/ping/gigawatt_ping_attack_wrecker.mp3.json` | generated / generated | Let's take a breath. | Let's take a break. |
| 89.66% | `transcripts/gigawatt/ping/gigawatt_ping_dynamo_was_here.mp3.json` | generated / generated | Dynamo, what is here? | Dynamo was here! |
| 89.66% | `transcripts/gigawatt/ping/gigawatt_ping_tengu_missing_01.mp3.json` | generated / generated | I've been missing. | I've eaten missing. |
| 89.66% | `transcripts/gigawatt/ping/gigawatt_ping_with_dynamo.mp3.json` | generated / generated | I'm with you, Dynamo. | I wish you dynamo. |
| 89.66% | `transcripts/gigawatt/ping/gigawatt_ping_with_lash.mp3.json` | generated / generated | Time with you lasts. | I'm with you, lass. |
| 89.66% | `transcripts/haze/ping/haze_ping_fairfax_in_mid.mp3.json` | generated / generated | Fairfax is in mid. | Fairfax is in Mitt. |
| 89.66% | `transcripts/haze/ping/haze_ping_sandeep_in_mid.mp3.json` | generated / generated | Send deep and mid. | Send deep, send mid. |
| 89.66% | `transcripts/hornet/ping/vindicta_ping_attack_tengu.mp3.json` | generated / generated | Let's see that item. | Let's see that ice! |
| 89.66% | `transcripts/hornet/ping/vindicta_ping_push_orange_01.mp3.json` | generated / generated | Let's push Orange! | Let's crush orange. |
| 89.66% | `transcripts/hornet/ping/vindicta_ping_seven_on_top_of_mid.mp3.json` | generated / generated | Sends on top of me! | Seton's on top of me! |
| 89.66% | `transcripts/hornet/ping/vindicta_ping_shiv_on_top_of_mid.mp3.json` | generated / generated | She was on top of me! | She is on top of me! |
| 89.66% | `transcripts/inferno/ping/inferno_ping_careful_inferno_02.mp3.json` | generated / generated | Careful, Infernal. | Careful, Inferno. |
| 89.66% | `transcripts/inferno/ping/inferno_ping_defend_blue_02.mp3.json` | generated / generated | Tofen Broadway. | To defend Broadway. |
| 89.66% | `transcripts/inferno/ping/inferno_ping_hornet_dead.mp3.json` | generated / generated | Vendicta is dead. | Vendictus is dead. |
| 89.66% | `transcripts/kali/rr_test_19_idol_grab_03.mp3.json` | generated / generated | Hands off the idol! | Hands on the idol! |
| 89.66% | `transcripts/kali/rr_test_19_kill_anyhero_10.mp3.json` | generated / generated | Come on, multiply. | Come out, multiply. |
| 89.66% | `transcripts/kali/rr_test_19_ping_careful_inferno_01.mp3.json` | generated / generated | Careful, Inferno. | Careful, Infernal. |
| 89.66% | `transcripts/kali/rr_test_19_ping_driller_back_01.mp3.json` | generated / generated | Griller, get back! | Thriller, get back! |
| 89.66% | `transcripts/kali/rr_test_19_ping_stun_pestilence_01.mp3.json` | generated / generated | Stun pestilence! | Stand pestilence! |
| 89.66% | `transcripts/kali/rr_test_19_sell_upgrade_06.mp3.json` | generated / generated | This game is money. | This game is mine. |
| 89.66% | `transcripts/kelvin/ping/kelvin_ping_enemy_take_mid.mp3.json` | generated / generated | They're taking me! | They're taking mid! |
| 89.66% | `transcripts/krill/krill_killed_by_kali_01.mp3.json` | generated / generated | Caly still got it. | Cali's still got it. |
| 89.66% | `transcripts/lash/ping/lash_ping_hornet_in_mid.mp3.json` | generated / generated | Predict is in mid. | Predictors in mid. |
| 89.66% | `transcripts/lash/ping/lash_ping_see_lash_on_bridge.mp3.json` | generated / generated | Flash is on bridge. | Last is on bridge. |
| 89.66% | `transcripts/lash/ping/lash_ping_stun_orion_01.mp3.json` | generated / generated | Stun, Great Talon! | Stun, great talent! |
| 89.66% | `transcripts/lash/ping/lash_ping_take_shrine.mp3.json` | generated / generated | It's time to end this. | Time to end this. |
| 89.66% | `transcripts/mirage/ping/mirage_ping_with_warden.mp3.json` | generated / generated | I'm with you, Orden. | I'm with you, Warden. |
| 89.66% | `transcripts/nano/ping/calico_ping_lash_on_top_of_mid.mp3.json` | generated / generated | Flash on top of mid. | Last on top of mid. |
| 89.66% | `transcripts/orion/ping/orion_ping_inferno_was_here.mp3.json` | generated / generated | Inferno was here. | Infernus was here. |
| 89.66% | `transcripts/orion/ping/orion_ping_saw_hornet.mp3.json` | generated / generated | I shall vindicate. | I shall vindicta. |
| 89.66% | `transcripts/orion/ping/orion_ping_wraith_on_top_of_mid.mp3.json` | generated / generated | Grace on top of it. | Grace on top of mid. |
| 89.66% | `transcripts/paradox/ping/paradox_ping_can_heal_haze.mp3.json` | generated / generated | Haze, I can heal you! | Hey, I can heal you! |
| 89.66% | `transcripts/paradox/ping/paradox_ping_sandeep_in_mid.mp3.json` | generated / generated | Sound DPS in mid. | Sounds deeps in mid. |
| 89.66% | `transcripts/paradox/ping/paradox_ping_see_enemy_on_roof.mp3.json` | generated / generated | Damn is on the roof! | Demi's on the roof! |
| 89.66% | `transcripts/paradox/ping/paradox_ping_with_pocket.mp3.json` | generated / generated | I'm with you, Pocket. | I wish you pocket. |
| 89.66% | `transcripts/pocket/ping/pocket_ping_jar_call_01.mp3.json` | generated / generated | Spirit urn is here. | Spirit on is here. |
| 89.66% | `transcripts/priest/ping/priest_ping_haze_almost_respawn.mp3.json` | generated / generated | He's almost back! | Haze is almost back! |
