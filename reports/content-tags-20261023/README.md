# Reviewed content-tag import — 2026-10-23

Imports the supported Wrong names, Nicknames and Insults findings through the Harrow release, together with the earlier included spreadsheet and supported September discoveries. The user's authorization covers this initial content import and deployment. This is a transcript-based classification; no audio-verification claim is made.

## Result

- 4,312 transcript files / 4,345 revisions gain tags.
- 5,837 distinct recording hashes have at least one tag, including historical recordings.
- Insults: 5,070; Nicknames: 853; Wrong names: 37 recording/tag memberships. Tags overlap.
- Tags expand through the existing exact-text filename-lineage and duplicate-hash closure. Unrelated equal wording does not cause propagation.
- Text, source authority, hashes, revision grouping and other metadata are unchanged. Existing tags are preserved. Definitions retain their IDs/labels and have no descriptions.

## Selection and holdouts

Positive inputs are the workbook's included Insults rows and Include instances, nickname rows except the Grandpa exclusion, caption-supported Wrong names rows, and text-supported September/October findings. Borderline, unresolved generated wrong-name evidence, and other unreviewed retrieval inventories are not direct import seeds. Later caption/review decisions take precedence for the same recording/tag. Historical absence from the newest release does not erase a supported recording that remains in the source repository.

All accepted seed captions were checked against the current repository at `dd29f997fd5ee24e5ae974fb5289865a4c0b0bfc`. Cosmetic normalization permits only Unicode/case/punctuation/spacing differences. The remaining 43 distinct before/after caption pairs were read individually: 39 preserve the tag signal; two translation placeholders, one changed nickname and one definition/context turn remain held. See `caption-review.json`.

`editorial-exclusions.json` removes 17 conversation-context revisions that do not themselves carry the proposed tag, including corrective name replies, nickname setup/replies, and non-insult responses. The full exchange remains available in the research evidence. Grandpa and murder-grandpa nickname assignments remain excluded.

`held-out.json` preserves 531 held recording/tag entries and 7 logical groups whose positive seeds overlap a held member. Those entire group/tag combinations stay untagged. The other categories remain deferred.

## Evidence and reproduction

- `assignments.json`: exact filename, revision index, expected caption/hash set, before/after tags, reviewed seed hashes, and source reference IDs for each changed revision. Apply only against the pinned base and verify every precondition; changes are additive.
- `summary.json`: counts, source artifact SHA-256 checksums, exclusions and base commit. Sources are the frozen spreadsheet reconciliation and the October 2/22 research audits; their original uncertainty classifications are retained.
- `expected-catalog.json`: expected immutable membership URLs, byte lengths, digests and counts from the source projection. This is verification evidence, not a separately maintained production manifest.

Existing repository validation must report no assignment/group conflicts. Content sync publishes the source tags, verifies immutable membership dependencies before catalog discovery, regenerates conversation projections, and advances the successful-deployment cursor only after public verification. Use the serialized existing CI workflow; do not write memberships directly to R2. The live website compatibility is already deployed; the new filter interface is tracked separately in VLViewer #297.
