# Bear Pit, Cadenza, Eldritch Tactical Solutions, and Mendoza

This batch adds four independently assignable reference tags. `assignments.json`
is the reviewed evidence inventory: filename, zero-based revision index, exact
transcript text, every recording hash, and the reason for inclusion.

- **Bear Pit** (`bear-pit`): the fighting venue, its championship and spectators,
  and Bebop/Lash's established pit-fighting careers. Includes contextual turns
  about Bebop retiring from the pit, betting on his fights, and Familiar's visit.
- **Cadenza** (`cadenza`): the island/state, its products and corporate retreats,
  and the political episode involving Fairfax, sovereignty, and US statehood.
- **Eldritch Tactical Solutions** (`eldritch-tactical-solutions`): the Fairfax
  subsidiary, including ETS and the historical “Eldrich” spelling; recruitment,
  personnel, operations, allegations, and direct comparisons to its hit squads.
- **Mendoza** (`mendoza`): the criminal boss and his explicitly identified
  syndicate, including his employees, victims, conflict with Ivy, and continuing
  threat. This is a combined subject tag, not a claim that the person and
  organization are interchangeable.

The review searched every stored transcript revision, including historical
filenames, then inspected neighboring turns across conversation speakers. Tags
are assigned by recording identity and existing exact-text filename lineages.
Existing tags, source authority, text, and recording hashes are preserved.

## Context and exclusions

Names are not required when adjacent dialogue identifies the subject. Examples
include “He was a good client” / “He was a bad man” about Mendoza, “All goes well
today I won't need to fight in the pit anymore” from Bebop, and “a fine company”
in the ETS recruitment exchange. Haze's response “I've operated in North Ixia”
counters Deadpack's dismissal of ETS allegations as media slander; this is
included because of that specific exchange, not because all North Ixia dialogue
refers to ETS. Cadenza includes Fairfax's reaction and the value of his statehood
legacy in the same named conversation.

Generic ritual combat, acknowledgments, or neighboring lines with no substantive
subject reference are excluded. General references to Ivy's title, the Arroyos,
or Spanish Harlem do not automatically qualify for Mendoza. Fairfax equipment
does not automatically qualify for ETS. Neither every island nor every political
reference is Cadenza.

Bear Pit includes official pit-fighter descriptions of Bebop and Lash, whose
venue is established in their dialogue. Generated-only Bear Pit claims in
`krill/krill_killed_by_bebop_05.mp3` and `lash/lash_kill_bebop_06.mp3` are left
unassigned pending audio review. The generated pit-fighter text in
`lash/lash_kill_atlas_05.mp3` is likewise excluded; its separate official revision
must not inherit a tag from that wording. Other historical generated revisions
with clear named references supported by corresponding official variants remain
eligible.

This inventory represents transcript-based editorial coverage, not a guarantee
that every untagged recording is unrelated. No audio transcription changes are
included.

## Verification and publication

Run `python3 -m unittest discover -s tests -v` and
`python3 -m tools.content_sync_cli validate --repo . --base origin/main`.
Validation checks schema, preserved recording hashes, defined tags, and agreement
across shared recordings and logical groups. A semantic diff should confirm only
tag additions in transcripts, with no removal of prior assignments.

After merge, use the existing serialized content-sync deployment. Confirm all
four catalogue IDs and memberships after publication. This source-only PR does
not independently publish CDN data or change the website application.
