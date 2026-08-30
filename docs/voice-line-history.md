# Voice-line history publication

Deadlock-Transcriptions CI is the sole owner of VLViewer's derived official
voice-line history. Historical Content continues to publish version catalogs
and audio, but it must not write objects below `deadlock/history/voicelines/`.

## Inputs and identity

The generator joins two authoritative inputs:

- official `voicelines.json` catalogs read directly from R2; and
- transcript states from the checked-out Git commit, resolved by audio SHA-256.

`config/deadlock/voice-line-history.json` declares the immutable official
chronology from oldest to newest. Hidden official versions participate. Entries
whose root-manifest `kind` is `custom` never participate.

History identity is the normalized full filename: trimmed, slash-normalized,
and case-folded. This matches Historical Content's adjacent-version comparison.
`voiceline_id` is retained only as display/share metadata because it is not
unique in published catalogs. A rename is therefore a removal plus an addition
unless a future explicit lineage mapping says otherwise.

Consecutive versions with the same filename and audio SHA-256 collapse into one
event range. A transcript correction replaces the text resolved for that audio
SHA; it does not create a new event or correction-history entry.

## Published contract

The mutable capability document is:

```text
deadlock/history/voicelines/manifest.json
```

It records the transcript commit, an ordered catalog fingerprint, exact
per-version voice-line JSON hashes, and a map from two-digit buckets to
immutable shard objects:

```text
deadlock/history/voicelines/shards/<sha256>.json
```

The bucket is the first byte of SHA-256 over the normalized filename. Shard
objects use one-year immutable caching. The manifest uses revalidation and is
published after all new shard objects. Unchanged shard hashes and URLs are
reused across complete logical regenerations.

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
   `voiceLineSha256`.
8. Unhide or promote the version.

The history-only mode requires the private transcript cursor to equal the
checked-out target commit. It does not advance or bypass pending transcript
deployments. Its catalog fingerprint is independent of that Git cursor, so it
detects a newly published hidden version at the same transcript commit.

Historical Content must preserve the root capability URL when rewriting the
game manifest. Its root-manifest update and transcript CI should ultimately
share conditional-write/deployment-lock semantics; until then, the operational
rule prohibiting concurrent publication is required.
