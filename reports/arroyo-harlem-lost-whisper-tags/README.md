# Arroyo family, Spanish Harlem, and Lost Whisper reference tags

This reviewed batch adds three independent subject tags. `assignments.json`
records every assigned filename, zero-based revision index, exact transcript,
recording hash, and inclusion rationale.

- **The Arroyo family** (`arroyo-family`): Ivy's family and household, including
  Carlos, Maria, and Sophia; adoption, family advice, school, employment, the
  mayoral campaign, and threats. Individual family members qualify even when a
  line is not about their relationship with Ivy. A line addressing Ivy as
  “Ms. Arroyo” explicitly invokes her family name; ordinary Ivy callouts do not.
- **Spanish Harlem** (`spanish-harlem`): the neighborhood and its community,
  including Ivy's “Savior of Spanish Harlem” title and contextual references to
  residents, territorial threats, and her efforts to protect the neighborhood.
- **Lost Whisper** (`lost-whisper`): the prison, imprisonment, escape, execution,
  and personnel. Includes Seven's contextual references to his incarceration,
  attempted execution, and prison clothing, and the conversation identifying
  Edmund Volker's connection to the prison.

## Evidence and boundaries

The review searched all stored revisions and historical aliases and read
neighboring conversation turns across speakers. The source JSON is authoritative
for the exact text and recording identities; the evidence file preserves it
without transcript edits. Shared audio hashes and exact-text filename lineages
receive consistent tags using the repository's logical grouping rules. Existing
assignments are retained.

Examples of indirect matches include Sophia falling asleep in Dynamo's class,
Rat King's reference to Carlos and “his kids”, Ivy's “my neighborhood”, Wraith
“visiting a friend” after being challenged about Spanish Harlem, and Seven's
“indignities I suffered” in the named Lost Whisper exchange.

Exclude unrelated family members (such as Holliday's sister and Graves's parents),
metaphorical adoption, generic acknowledgments, and ordinary Ivy callouts.
Carlos/Sophia references are resolved through Ivy's established household rather
than assuming that any occurrence of those first names belongs to this family.
General New York dialogue and every Mendoza reference do not automatically
qualify as Spanish Harlem. Generic prisoner spotting pings, combat escape calls,
and unrelated prisons do not automatically qualify as Lost Whisper. Seven's
historical “program” line is left out because this wording does not independently
establish which institution it refers to.

Viper's actual selection line explicitly discusses breaking out of Lost Whisper
and qualifies even though Viper is not Seven. The Nurse conversation identifies
someone stationed there; it does not establish that Nurse herself served there.

Historical generated revisions with recognizable named references remain
eligible. This is transcript-based editorial coverage, not a claim that every
untagged recording is unrelated or that all historical transcriptions have been
audio-verified.

## Validation and publication

Run the repository unit suite and full content-sync validation against the base
branch. Check a semantic diff to ensure transcript changes only add tags and
preserve all earlier tags, text, source metadata, and recording hashes.

After merge, the existing serialized content-sync deployment publishes the
catalogue and memberships. Confirm all three IDs after deployment. This PR does
not independently publish CDN data or change the website application.
