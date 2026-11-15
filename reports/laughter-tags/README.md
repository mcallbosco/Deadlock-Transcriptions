# Laughter

The initial selection covers explicit performed laughter in transcript text:
stage directions (laughs, laughter, chuckles, giggles, cackles) and repeated
laughter syllables, including laughter mixed with dialogue. Mocking or sarcastic
laughter qualifies. Historical and unused recordings are eligible.

The candidate review matched whole-word laugh/chuckle/giggle/cackle variants,
repeated separated ha/he/ho syllables, and joined repeated “ha” syllables.
It reviewed 101 matching revisions and selected 74 revisions in 69 files,
covering 102 unique recording hashes. No laughter-named files were found.

`assignments.json` records every changed revision, its recording hashes, source,
original text, prior tags, new tags, and whether it was selected directly or
included through shared-hash/exact-text lineage consistency. Existing tags are
preserved. `exclusions.json` records the 27 rejected candidates: mentions rather
than performed laughter, and apparent generated mishearings such as “Giggles on
the roof!” in a Gigawatt sighting or “You got laughs!” in a Lash kill callout.
A single ambiguous “Ha!” is not enough evidence for this seed batch.

This is transcript-based editorial classification, not an audio audit or an
exhaustive laughter detector. Clear generated laughter transcripts are included
with their existing source authority; no transcript text, model, source, or
recording membership is changed. Captions may omit laughter, so absence of this
tag does not establish absence of laughter in the recording.

After merge, verify Deploy content sync succeeds and the runtime catalogue has
`laughter` / `Laughter` with nonzero membership. Reload the site's tag filters and
check a representative tagged recording. Publication uses the existing pipeline.
