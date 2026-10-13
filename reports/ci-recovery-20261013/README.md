# October 13 structural regeneration acknowledgment

Owner Miles Calloway authorized this narrowly scoped acknowledgment after reviewing
the already-published content, and subsequently authorized merging the fix and
checking normal merged-main CI. No new structural generation is required.

The [blocked deployment](https://github.com/mcallbosco/Deadlock-Transcriptions/actions/runs/38474885335)
at `7281bbb94bc74d480b9231dd1c8e33729b1b4ff3` reports only
`config/deadlock/voiceline-groups.json` as requiring regeneration. Relative to its
base `dfd6c3b661c12fd34da899de3ac7e0c87a44bc05`, that configuration only adds
`hero_debut` to Hero Selection. The run's result is `blocked`.

On October 13, a fresh public-CDN inspection checked all 22 official catalogs and
`ognb-russian-voice-mod`. Only `cns-deadman` contains affected records, all already
under `Self / Hero Selection / Hero debut`:

- `baba/baba_hero_debut_01.mp3`
- `chessmaster/chessmaster_hero_debut_01.mp3`
- `deadpack/deadpack_hero_debut_01.mp3`
- `ratking/ratking_hero_debut_01.mp3`

The [published catalog](https://cdn.vlviewer.com/deadlock/versions/cns-deadman/voicelines.json)
is JSON-equivalent to the failed run's pre-change R2 backup. Its downloaded body
SHA-256 is `faa1b7ab83c06b05cf11070ebe99d264d75d0ff7faf6c68971c3c88007bef901`.
The [release metadata](https://cdn.vlviewer.com/deadlock/versions/cns-deadman/release.json)
identifies `cns-deadman`, published at `2026-10-13T21:29:20.583520Z`, revision 2,
updated at `2026-10-13T21:54:35.371256Z`.

The existing approval file now binds the groups configuration's canonical JSON
SHA-256 `24314c290c3daa9b428dfe9ac160e018e51bc38b20b2ed3a883fdc6b7dd9ecc2`
to that exact release identity and minimum revision. The guard remains unchanged:
different configuration bytes after canonicalization, a different release identity,
or an older release still block. Existing approvals are preserved.

The existing acknowledgment regression test now also covers the groups path,
including rejecting changed configurations, wrong release identities, and older
revisions. This test change triggers the existing credential-free PR plan workflow.
Normal deployment after merge may apply the pending transcript and history changes
from the existing cursor; this approval does not itself generate or edit those records.
