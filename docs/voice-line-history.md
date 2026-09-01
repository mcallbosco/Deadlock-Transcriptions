# Voice-line history publication

Deadlock-Transcriptions CI is the sole owner of VLViewer's derived official
voice-line history. Historical Content continues to publish version catalogs
and audio, but it must not write objects below `deadlock/history/voicelines/`.

## Inputs and identity

The generator joins three authoritative inputs:

- official `voicelines.json` catalogs read directly from R2;
- official `conversations.json` catalogs read directly from R2; and
- transcript states from the checked-out Git commit, resolved by audio SHA-256.

`config/deadlock/voice-line-history.json` declares the immutable official
chronology from oldest to newest. Hidden official versions participate. Entries
whose root-manifest `kind` is `custom` never participate.

History lookup identity remains the normalized full filename: trimmed,
slash-normalized, and case-folded. History itself uses permanent, transitive
recording lineages. If two filenames contain the same audio SHA-256 in any
official version, they are aliases in one lineage forever. If A shares a hash
with B and B later shares another hash with C, all three filenames belong to the
same lineage. The complete lineage is published below every alias lookup key.

Each lineage has a deterministic `lineageId`, an earliest-observed
`canonicalFilename`, and a sorted `aliases` array. The canonical filename is a
technical identity; clients should display the alias active in the selected
version, or the newest active alias by default. `voiceline_id` values remain
display/share metadata because they are not unique in published catalogs.

Schema-v2 history is expressed as consecutive version periods. A period lists
one or more recording variants, and every variant lists the filenames that use
it. A filename change therefore remains visible even when the audio SHA does
not change. If aliases that once shared a recording later diverge, the lineage
remains intact and the period contains parallel variants. Absence from an
official version breaks a period.

`hasTranscriptDifferences` compares exact transcription text across the whole
lineage. Filename-only renames, audio changes with identical text, and changes
only to `officialtranscription` do not qualify. A separate schema-v1 filename
index using criterion `transcription-text-differences` can therefore retain its
existing shape: qualifying lineage results are expanded to every alias before
the filename list is deduplicated and sorted.

## Published contract

The mutable capability document is:

```text
deadlock/history/voicelines/manifest.json
```

It records the transcript commit, an ordered catalog fingerprint, exact
per-version voice-line and conversation JSON hashes, and a map from two-digit
buckets to immutable shard objects:

```text
deadlock/history/voicelines/shards/<sha256>.json
```

The bucket is the first byte of SHA-256 over the normalized filename. Shard
objects use one-year immutable caching. The manifest uses revalidation and is
published after all new shard objects. Unchanged shard hashes and URLs are
reused across complete logical regenerations.

The schema-v2 manifest declares `identity` as
`transitive-audio-sha256-lineage` and `lookupIdentity` as
`normalized-filename`. `historyLines` continues to count filename lookup
entries. `lineageCount` counts unique published lineages and
`branchedLineageCount` counts lineages with parallel variants in at least one
version. `transcriptDifferenceLines` is the required `lineCount` of the
alias-expanded schema-v1 `transcription-text-differences` filename index; its
compiler should fail rather than publish an index with a different count.

The manifest continues to reference the two schema-v1, content-addressed
filename indexes used for cheap frontend eligibility checks:

```text
deadlock/history/voicelines/presence/<sha256>.json
deadlock/history/voicelines/transcript-differences/<sha256>.json
```

The `presence` index contains every alias of a lineage with more than one
rendered period. The `transcriptDifferences` index contains every alias of a
lineage with more than one exact transcription string. Both retain
`identity: normalized-filename`, sorted unique `filenames`, and a `lineCount`
equal to the array length. Rename-only lineages can enter `presence` but do not
enter `transcriptDifferences`, so a frontend that gates its history button on
transcript differences retains its current behavior.

Both indexes are published as immutable objects before the mutable history
manifest. Empty indexes are still published so consumers always receive the
same schema-v1 contract.

The game manifest advertises the optional capability through:

```json
{
  "voiceLineHistoryManifestUrl":
    "https://cdn.vlviewer.com/deadlock/history/voicelines/manifest.json"
}
```

## Transcript correction deployment

Every qualifying push to protected `main` performs a complete deterministic
history calculation from the in-memory desired version catalogs. Only new
content-addressed shards are written. The history manifest changes only when
the represented catalogs, transcript-derived shard content, or provenance
changes.

History uses the existing conditional R2 writer. A failed run can be retried:
an immutable create that receives a precondition failure succeeds only after
the existing object is read back and proven byte-equivalent as JSON.

## New official game version

1. Add the new version ID to `officialVersions` in chronological order and
   merge the transcript/config commit.
2. Let normal transcript content sync advance its private Git cursor.
3. Publish the new official version as hidden through Historical Content.
4. Do not run the desktop publisher concurrently with content-sync CI.
5. Run **Deploy content sync** with `history-dry-run` and review the plan.
6. Run it again with `history-reconcile`.
7. Verify that the history manifest contains the hidden version's exact
   `voiceLineSha256` and `conversationSha256`.
8. Unhide or promote the version.

The history-only mode requires the private transcript cursor to equal the
checked-out target commit. It does not advance or bypass pending transcript
deployments. Its catalog fingerprint is independent of that Git cursor, so it
detects a newly published hidden version at the same transcript commit.

Historical Content must preserve the root capability URL when rewriting the
game manifest. Its root-manifest update and transcript CI should ultimately
share conditional-write/deployment-lock semantics; until then, the operational
rule prohibiting concurrent publication is required.
