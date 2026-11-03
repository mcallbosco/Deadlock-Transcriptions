# Spoken Ixian — reviewed assignments, 2026-11-03

Adds `spoken-ixian` / **Spoken Ixian** for recordings containing actual Ixian
speech, including mixed English/Ixian dialogue. This is a transcript-based
classification corroborated by public voice-line references, not an independent
audio transcription or a claim that every unidentified utterance has been found.

## Coverage

17 recording hashes in 17 revisions across 16 transcript files: Apollo (11),
Abrams (3), Grey Talon (1), Rem (1), and Seven (1). Counts include historical and
unused recordings; they are not the number of results in any one game version.

The scope includes the six-turn Apollo/Abrams exchange, Apollo's greeting to
Infernus, his mixed-language nickname for Vindicta, his ability phrases and
alternate delivery, and the three other heroes' phrases directed at Apollo.
The existing `nicknames` assignment on the Vindicta line remains intact.

## Evidence and resolved candidates

- [Apollo's voice-line entries](https://deadlock.wiki/Apollo/Voice_lines) identify
  the relevant conversation and ability recordings as Ixian. Both the old and
  replacement revisions of `fencer_use_power1_03.mp3` qualify: the former is in
  Removed/Unused Voice Lines, the replacement in Disengaging Sigil.
- The ability section identifies both deliveries of `Virachi` as Ixian, with an
  [explicit alternate filename](https://cdn.deadlock.wiki/Fencer_use_power4_start_03_alt_01.mp3).
  Its existing generated transcript authority is preserved.
- [Abrams' conversation entries](https://deadlock.wiki/Abrams/Voice_lines) identify
  all six turns of the exchange as Ixian. The wiki and repository use different
  spellings for Apollo's question; the matching conversation/recording establishes
  the classification without changing the official transcript.
- [Grey Talon's enemy lines](https://deadlock.wiki/Grey_Talon/Voice_lines) explicitly
  identify his Apollo kill line as Ixian. No inferred translation is needed.
- [Rem's voice-line entries](https://deadlock.wiki/Rem/Voice_lines) and
  [Seven's voice-line entries](https://deadlock.wiki/Seven/Voice_lines) identify
  the corresponding taunt and kill line. Rem's unused status does not disqualify
  a recording already present in the historical transcript library.
- [Ixia's language reference](https://deadlock.wiki/Ixia#Language) corroborates the
  speakers and phrase families. The
  [community phonetic study](https://www.reddit.com/r/DeadlockTheGame/comments/1xdl6fb/ixian_language_phonetic_study/)
  was a discovery aid, not authority for speculative translations.

## Exclusions and open candidates

- English mentions of Ixia, Ixians, and the language remain untagged, including
  Infernus's replies in the greeting exchange and the surrounding Vindicta
  conversation. The English explanation of the nickname is not Ixian speech.
- French fencing expressions such as `En garde` and the title `Dauphin`, proper
  names alone, and other non-English dialogue are not evidence of spoken Ixian.
- The [Cultist Sacrifice whisper](https://deadlock.wiki/Cultist_Sacrifice) is
  described as presumed Ixian. No corresponding transcript/recording entry was
  found in this repository. It remains an open candidate, without a fabricated
  filename or hash.

## Verification and reproduction

`assignments.json` records the pinned base commit, exact filename/revision index,
text, hash set, previous/new tags, and source references for each accepted seed.
Reproduction must verify those preconditions against the base before applying
only the new tag. The existing `tools.set_content_tags` helper accepts the
recorded filename, a hash, and the complete `afterTags` set.

The existing exact-text filename-lineage and duplicate-hash closure was evaluated
over the full repository. It adds no further revisions for these seeds. Full
assignment validation found no group conflicts. All non-tag transcript fields,
revision boundaries, recording hashes, and previous tags are unchanged.

`summary.json` records counts and preservation checks; `validation.json` records
the complete repository validation; `expected-catalog.json` records the expected
source projection, including the new membership's digest and count. The catalog
is evidence, not a production manifest to publish separately. Publication uses
the existing serialized content-sync workflow after merge. No deployment is
performed by preparing this change.

Validation completed:

- All 182 repository tests passed. Complete source validation: 128,522 files,
  137,202 revisions, 200,704 hashes, no errors, warnings, or ambiguities.
- The website's 12 content-tag tests passed. Chromium checked the generated
  membership against a local fixture with separate current/historical revisions:
  the label appears, filtering excludes the English language-reference control,
  mixed speech remains, reload retains selection, and clearing restores the
  control. Both ability revisions were exercised in their respective fixture
  versions; no browser page errors occurred. This is not a production-CDN check.
- Conversation projection with the actual greeting/reply hashes tags only the
  Ixian line and the containing conversation, leaving the English reply untagged.
- `git diff --check` and an independent before/after comparison confirmed that
  transcript changes add only this tag and preserve all previous metadata.

The full public-CDN synchronization plan is left to the pull request's existing
CI workflow. No website code changes are required.
