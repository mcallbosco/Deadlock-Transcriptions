# Hank, The 7th Moon, The Troubadour, and The Baroness

This batch adds four separate reference tags. `assignments.json` records each
assigned filename, zero-based revision index, exact text, full recording hashes,
and inclusion rationale.

- **Hank** (`hank`): Infernus's friend and the bar owner, including his worries,
  the effort to save his business, and his proposed deal in the historical
  Oathkeeper scenes. Individual business references qualify when the dialogue
  clearly identifies Hank; generic bartending is not sufficient.
- **The 7th Moon** (`seventh-moon`): the organization, including written-number
  variants and Haze's contextual description of Yamato's operation growing from
  a gang into a cartel. Yamato's identity or presence alone is insufficient.
- **The Troubadour** (`troubadour`): the killer, Holliday's pursuit, related
  warnings, and dialogue asking about his identity. Speculation and denials
  remain statements made by the speakers, not assertions of a confirmed identity.
- **The Baroness** (`baroness`): the hotel, its guests, staff, events, services,
  supernatural hospitality, and clearly contextual Hotel Guest ability dialogue
  concerning rooms or stays. Doorman's unrelated combat chatter is excluded.

## Evidence and boundaries

Research searched every stored revision and historical filename, followed by
source verification and reading neighboring conversation turns across speakers.
The inventory preserves actual JSON text, including historical wording; it does
not edit transcripts or silently replace generated text with an interpretation.
Existing tags, source authority, recording hashes, and text remain unchanged.
Shared-hash and exact-text filename-lineage groups receive consistent assignments
using the repository's logical grouping rules.

Examples of indirect references include Infernus saying “He's nervous” after
being asked about Hank, Haze describing “your operation” before Yamato names the
7th Moon, Drifter denying that he is the Troubadour, and Geist complaining about
“that hotel” after asking whether Doorman works at The Baroness.

The Troubadour-labeled historical conversation sets also contain unrelated
reporter, romance, and receptionist dialogue. Those filenames alone do not
justify a tag. Historical direct mentions and clearly grounded pursuit references
remain eligible without presenting an old story state as current canon.
Generic crows, murders, and every Holliday/Drifter line are not automatically
Troubadour references.

For The 7th Moon, ambiguous generated alternatives such as “Sandmoon”,
“sevensmith”, “seven rules”, and “heaven's move” remain unassigned pending further
review. The generated “The seventh moon, wounded” fragment is also excluded.
Distinct official revisions in the same files remain eligible. Generic moons,
Yamato's brother, and her personal history are not automatically group references.

Holliday's cheap Hell's Kitchen hotel is explicitly a different accommodation
from the Baroness invitation, so it is excluded. A news report about an unnamed
haunted Chelsea hotel is not enough to establish the Baroness. The hotel tag does
include substantive references to its guests, management, brunch bans, employment,
rooms, and amenities resolved from Doorman's established workplace or adjacent
named dialogue.

This is transcript-based editorial coverage, not a guarantee that every untagged
recording is unrelated or every historical transcript has been audio-verified.

## Validation and publication

Run the repository unit suite and full content-sync validation against the base
branch. Verify a semantic diff confirms transcript changes only add tags and
preserve prior tags and all other revision fields.

After merge, the existing serialized content-sync deployment publishes the tag
catalogue and memberships. Verify the four IDs after deployment. This source-only
PR does not independently publish CDN data or change the website application.
