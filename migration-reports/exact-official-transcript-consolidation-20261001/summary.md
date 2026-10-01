# Exact matches to official transcripts

Scanned 114,367 transcript files from main at `168cb09160` and matched manual/generated revisions to existing official text within the same filename or confirmed shared-hash/reviewed filename lineages.

Updated **5,631 unique recordings** across **3,403 transcript files**. Including aliases, this changes 6,856 recording occurrences: 5,710 generated and 1,146 manual. The 1,658 distinct wording pairs match exactly using `tools.transcript_schema.transcript_match_key`, which ignores capitalization, Unicode punctuation, and whitespace. Identical stored text also qualifies for official source consolidation.

Existing official text, source, metadata, and original recording membership remain unchanged. Matched hashes join an existing official revision where available; aliases without that revision receive its exact official text. Transcription model metadata is removed from promoted generated revisions. Every audio hash remains in its original file.

Ten spacing cases received individual sentence-context review: missing spaces around ellipses, `afterall`/`after all`, `out run`/`outrun`, `Shadowweave`/`Shadow Weave`, `setup`/`set up`, `everyone`/`every one`, and `anytime`/`any time`. Each preserves the spoken words in its sentence.

**All fuzzy wording candidates remain unchanged**: 1,467 unambiguous candidate groups and another 25 ambiguous groups are deferred. Rewritten patron dialogue is outside this exact-match batch.

Verification:

- Full repository validation passes, including consistency across aliases of each recording hash.
- All 140 existing tests pass.
- Independent comparison against Git main verifies each changed file's complete hash multiset, all existing official states, and exact normalized equivalence for every changed recording.
- Every target wording has an official source in the base commit.
- Reapplying the same exact decisions changes zero files.
- `git diff --check` passes.

[Review and recording-level audit](review-and-apply.json) records the base commit, policy, reviewed pairs, prior states, official origins, and recording hashes for each change.
