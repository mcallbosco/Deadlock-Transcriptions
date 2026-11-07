# Unique Pings

`unique-pings` identifies bespoke character dialogue in in-game ping recordings. Pre-game, post-game, and ability callouts are excluded, regardless of their wording. It covers
jokes, relationships, lore, and expressive calls that add meaning beyond the
shared ping templates. It is an editorial tag, not a claim that a string appears
only once in the corpus.

## Comparison and selection

The comparison scanned 77,093 nonempty revisions in filenames containing
`_ping_`, including historical files outside the usual `ping/` directory.
It grouped 7,328 normalized phrasings after replacing known character aliases,
normalizing punctuation, and normalizing common contractions. Event families
remove target aliases and revision suffixes, allowing comparisons between
characters doing the same kind of ping.

Groups shared by more than two character folders were removed from the candidate
pool. The remaining 6,672 groups were split into targeted, social, and other
calls. Pre-game, post-game, and ability groups were excluded from selection. Rarity was only a way to find candidates. The authoritative wording lists
were reviewed for meaning; generated-only candidates were screened separately.
Unclear generated text was not treated as a new joke or unique phrase. The explicitly selected generated-only phrasing is a coherent historical variant
of the independently confirmed Silver/Shiv line.

Examples included:

- Pocket: “I see my ex.”
- Rem's deliberate McGinnis mispronunciations and McGinnis's Kevin joke.
- Lash's self-praise and Viscous noticing that Sinclair's callout rhymes.

Examples excluded:

- Ability use, readiness, cooldown, ultimate-status, and targeted ability-request
  callouts, including bespoke jokes and lore in those lines. Enemy sightings
  remain eligible even when they warn about an enemy's abilities.

- All pre-game and post-game pings, including their jokes and lore references.

- Standard sightings, locations, healing, readiness, and cooldown templates.
- An ordinary template with a prototype hero or ability name substituted.
- Ordinary role descriptions such as “I see the robot”.
- A simple ability action or companion-readiness statement without additional
  characterization.
- Transcription errors, spelling differences, and unverified generated-only
  outtakes. The “Speaks Japanese” placeholder supplies no usable dialogue.

This is a conservative text-based selection. Audio-only delivery differences and
unverified historical transcriptions are not classified by this pass. A selected
recording's historical revisions may inherit membership through the repository's
required shared-hash and logical-text-group consistency rules.

## Review artifacts

- `comparison-evidence.json`: selected normalized groups, event families, common
  comparison phrases, and selection reasons.
- `candidates.json`: exact filename, revision index, text, and reason before
  propagation.
- `assignments.json`: final assignments, prior tags, hashes, and source evidence.
- `build_comparison.py` and `select_candidates.py`: reproducible discovery and
  editorial selection against the PR base corpus. From the repository root,
  create `.scratch`, run the comparison script, then the selection script.
  These scripts only write scratch research output and do not edit transcripts.

Final membership: **148 revisions, 199 unique recording hashes**, across 148
transcript files. Existing text, hashes, sources, and tags are preserved.
