# Site-wide voice-line search index prototype

This generator publishes a single lazy-loaded index for a future VLViewer
`/search/` route as part of transcript content-sync.

The generator reads the same oldest-to-newest official version list used by
voice-line history, excludes custom versions, and downloads each version's
voice-line and conversation catalogs. Normal voice lines and individual
conversation lines are combined. Filename aliases are grouped using the exact
transitive audio-SHA lineage function used by history.

Catalog transcript fields are not authoritative because older catalogs can
contain text that was later corrected. Like voice-line history, the generator
resolves every recording's current transcript and official status from the
checked-out transcript repository by audio SHA-256. Correction history is
therefore never exposed as a game-version search state.

Each lineage contains consecutive version states. A search client examines the
states newest-to-oldest and returns the first state matching the query and
filters. Therefore:

- if both an older and newer state match, only the newer state is returned;
- if only an older state matches, that older state is returned; and
- a line present in both normal and conversation catalogs is one recording
  variant with multiple destinations, rather than duplicate search results.

Audio-only re-encoding and duration changes do not create a new searchable
state. The period retains the newest recording so playback still uses the
latest applicable asset.

The JSON uses a global string table and positional arrays to reduce transfer
and parsed-memory overhead. The `layout` object in the artifact documents every
array position. Audio SHA-256 values use unpadded base64url instead of the much
longer `sha256/xx/<hex>.mp3` key; the client can losslessly reconstruct that
key. States store inclusive version indexes into the root `versions` array. The
state `throughVersionIndex` is the newest version on which that unchanged state
applies and is the version a search result should link to.

Generate and measure the current public catalogs with:

```powershell
python -m tools.voiceline_search_cli
```

The command writes ignored local measurement artifacts below `.cache/search-index/`
and reports minified JSON and gzip sizes. Its catalog cache makes repeat runs
local and deterministic. The mutable root manifest is always refreshed and
catalog caches are partitioned by content revision, so an updated official
version cannot reuse stale input.

On every qualifying push to `main`, content-sync generates the same value from
its in-memory desired catalogs, writes compact JSON to the immutable,
content-addressed location
`deadlock/search/voicelines/<sha256>.json`, and then advertises that exact URL
as `voiceLineSearchIndexUrl` in `deadlock/manifest.json`. The immutable object
is published before the mutable root manifest. Cloudflare can negotiate gzip
or Brotli for the JSON response; VLViewer should request the advertised URL
normally rather than fetching a `.gz` object. The VLViewer search UI remains a
separate application change.

## September 1, 2026 measurement

The 17 current official versions produced 94,448 lineages, 106,404 searchable
states, 107,542 recording variants, and 112,866 destinations. The minified JSON
was 24,279,929 bytes. It compressed to 7,572,306 bytes with gzip level 9 and
5,956,013 bytes with Brotli quality 11. On the development desktop, Node parsed
the artifact in roughly 145 ms and a simple newest-applicable scan for one text
query took roughly 32 ms; browser and mobile performance still need to be
measured in the eventual UI.
