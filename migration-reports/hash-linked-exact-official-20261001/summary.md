# Exact official transcript hash links

Base commit: `168cb091607ca97f641607b1818eff62943c5711`.

Links 3,403 editable transcript groups (5,631 distinct recording hashes) to existing official revisions within confirmed Deadlock filename lineages. Matching uses the existing `transcript_match_key` case, punctuation, and spacing normalization. No fuzzy or phonetic matches are included. Every pre-existing official text and source stays unchanged.

The official revision gains the older recording hash in its `sha256` array. The original transcript file retains that hash and adopts the matching official text/source. Every existing alias for the hash receives the same state. No original hash membership is removed.

For example, `astro/ping/holliday_ping_gigawatt_in_mid.mp3` keeps recording `ad297323b1ae4b0b8726dd68011ce91a957a271cdb40b76e3e2bca81de3f3f86`. The same hash is added alongside `5cba48276f366266eb68eedc5aba22dc3765e21795abc8ec4012429c88b567d5` in the existing official revision of `astro/ping/astro_ping_gigawatt_in_mid.mp3`. Both copies contain the original official wording, “Seven's in mid!”. A later official correction can therefore reach both recordings and their retained files.

## Counts

- 114,367 transcript files scanned; 5,995 changed.
- 5,642 official hash memberships added for 5,631 distinct recordings.
- 5,710 generated and 1,146 manual recording occurrences adopt official state.
- 9,876 original recording occurrences retained across changed files.
- All 2,819 pre-existing official recording occurrences in changed files preserve their exact state.
- Zero ambiguous groups and zero conflicting hashes in this batch.

## Validation

The full repository content validator passes, including published-state consistency for hashes present in multiple files. All 146 Python tests pass. An independent comparison against the Git base confirms original memberships and official states are preserved, and that each added membership joins an existing official revision with equivalent text. A second audit proposes zero changes.

The machine-readable audit records each editable group, its previous state, retained recording hashes, exact official wording, and original official destination locations. Destination indices refer to the base documents.

## Import dependency

Use [VLViewer-DL-Organizer #18](https://github.com/mcallbosco/VLViewer-DL-Organizer/pull/18) (the DLSoundProjectUtilities importer update) before regenerating or publishing this data. It propagates incoming official corrections across linked hashes and all persisted copies, and rejects contradictory official input for a linked group before writes. The existing importer only updates the directly resolved document and can leave retained copies stale.

## Reproduction

Run from the repository root:

```sh
python3 -m tools.link_exact_official_transcripts --report /tmp/exact-official-audit.json
python3 -m tools.link_exact_official_transcripts --apply --report /tmp/exact-official-apply.json
python3 -m unittest discover -s tests
```

The first command audits without writing transcripts; the second applies the guarded plan and runs repository validation.
