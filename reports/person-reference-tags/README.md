# Shelly and Fairfax reference tags

This reviewed batch adds three independently assignable tags:

- `ms-shelly` / **Miss Shelly**: Shelly Fisher, including Miss Shelly, Bebop's mother, creator, maker, or sick charge and contextual references to her care, health, and relationships.
- `maximilian-fairfax` / **Maximilian Fairfax**: named spelling variants, Pocket's father (including references to both parents), and personal references resolved by surrounding dialogue.
- `fairfax-industries` / **Fairfax Industries**: the company, FI, its named subsidiaries, employment, operations, and branded products. A line can also carry the Maximilian tag when it refers to both.

`assignments.json` records every assigned revision's filename, zero-based revision index, exact transcript, complete recording hashes, and rationale. This is a snapshot of the reviewed source, not an automatic keyword classifier. Existing transcript text, source authority, recording hashes, and tags are preserved. Shared-hash and exact-text filename lineage groups receive consistent assignments using the repository's logical grouping rules.

The corpus-wide search covered all stored revisions and historical aliases, not only the latest character names. Direct-name searches were followed by reading surrounding turns across speakers, Bebop/Pocket dialogue, corporate dialogue, patron lines, newscasts, and the Oathkeeper book scenes. Context identifiers embedded in filenames allow the neighboring conversation turns to be inspected alongside each assignment.

## Editorial boundaries

- A mention need not use a name: “My creator needs my help,” “Dad would be proud,” and “You're gonna take over your dad's company” qualify.
- Shelly includes Lash's mistaken “Miss Cheri” followed by Bebop's correction, and the unnamed sick woman in Oathkeeper scene 04c after Shelly Fisher is proposed as a host.
- Maximilian includes Walter's son taking over the company and the personal conversation about Cadenza. “He's dead” in the Walter exchange refers to Walter and is excluded.
- Pocket telling Apollo “You don't have to be your father” and “Stop living your father's life” refer to Apollo's father, so are excluded. Generic family-name references alone and assassination exchanges without a reference to the person who commissioned them are excluded.
- Company references include Eldritch Tactical Solutions / ETS, explicitly identified as a subsidiary in the news and Haze conversation. An investment by “Mr. Fairfax” alone does not establish a corporate investment.
- Historical combat pings addressing Pocket as “Fairfax” do not identify Maximilian or the company. Surname-only references with no clear personal or corporate referent remain excluded.
- Brief generic acknowledgments and unrelated turns are not tagged merely because they occur in a relevant conversation. Conversation-level tags are derived by the publisher from tagged constituent recordings.

This is transcript-based editorial coverage. Untranscribed audio and ambiguous references may require further review; absence of a tag is not proof that a recording is unrelated.

## Verification and publication

Run the repository unit suite and `python3 -m tools.content_sync_cli validate --repo . --base origin/main`. Validation checks recording preservation, transcript schema, definitions, shared hashes, and logical-group tag consistency.

After merge, the serialized content-sync deployment publishes the definitions and memberships to the CDN. Verify all three IDs in the runtime catalogue and their filters after publication. This PR changes source metadata only; it does not publish the CDN or change application code.
