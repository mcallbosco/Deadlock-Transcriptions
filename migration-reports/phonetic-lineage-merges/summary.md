# Phonetic lineage merge review

The audit compared transcript revisions across permanent filename lineages built
from shared recording hashes and 11,519 reviewed manual correlation groups.

| Result | Count | Disposition |
| --- | ---: | --- |
| Transcript files scanned | 98,944 | Complete repository |
| Multi-file lineages | 13,013 | Shared-hash and manual edges are transitive |
| Strong candidate pairs | 171 | 169 applied; 2 withheld after review |
| Recording hashes reconciled | 457 | 375 official; 5 manual; 77 generated |
| Transcript files changed | 285 | Every represented hash was preserved |
| Lower-confidence candidate pairs | 4,594 | Report only; no transcript changes |

## Review tables

- [Strong candidates](strong/candidates.md)
- [Lower-confidence candidates](lower-confidence/candidates.md)

## Representative decisions

| Tier | Left | Right | Decision |
| --- | --- | --- | --- |
| Strong | `atlas/abrams_use_curse_03.mp3`: “I'll curse them!” (generated) | `atlas/atlas_use_curse_03.mp3`: “I'll curse 'em!” (official) | Applied the official transcript |
| Strong STT mishearing | `astro/astro_unselect_01.mp3`: “Lives are at stake.” (generated) | `astro/holliday_unselect_01.mp3`: “Lines are at stake.” (generated) | Selected “Lives are at stake.” and kept it generated |
| Withheld | `ghost/geist_enemy_kelvin_kill_on_ice_path_01.mp3`: “Kevin” (generated) | `ghost/ghost_enemy_kelvin_kill_on_ice_path_01.mp3`: “Kelvin” (generated) | Kept for review because either name may be what was spoken |
| Withheld | `announcer/male_patron/patron_male_ally_calico_start_01.mp3`: starts with “Oh” | correlated `nano` filename: same line without “Oh” | Kept separate because the extra spoken word may be real |
| Lower confidence | `atlas/abrams_use_curse_02.mp3`: “Curse them!” (generated) | `atlas/atlas_use_curse_02.mp3`: “Cursing 'em!” (official) | Listed for review; not changed |

Strong candidates require either the same normalized spoken phrase or at least 98%
normalized character similarity. The lower-confidence table includes recognizable
speech-to-text substitutions down to 70% character similarity, but its similarity
scores are ranking aids rather than merge approvals.
