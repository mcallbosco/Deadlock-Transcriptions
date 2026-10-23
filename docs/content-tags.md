# Transcript content tags

Transcript revisions may include `tags`, a set of category IDs from
`config/deadlock/content-tags.json`. Schema version remains 3. Missing tags and
`[]` both mean untagged. The initial vocabulary is `wrong-names`, `nicknames`,
and `insults`; definitions can be extended without changing publisher code.

```json
{"sha256":["<recording hash>"],"text":"Example dialogue.","source":"official","tags":["nicknames"]}
```

Tags are editorial metadata independent of text authority. Every hash in a
revision inherits its tags. Corrections preserve tags, splits copy them, and
merges with different sets fail until a maintainer resolves the assignments.
Duplicate hashes and logical groups across filename aliases must agree. Logical
groups use existing filename lineages and exact trimmed text, including the
special non-speech group; unrelated matching text and blank effort recordings
do not gain assignments.

Use the maintainer helper to update all entries in a group. It follows both
logical aliases and duplicate-hash memberships, validates the resulting
repository assignments, and prints the complete before/after changes. It does
not write unless `--apply` is present:

```sh
python -m tools.set_content_tags --repo . --filename hero/example.mp3 \
  --sha256 <recording-hash> --tags nicknames insults
# Repeat with --apply after reviewing the dry run. Use --tags with no values to clear.
```

Public correction operations cannot author tags. A tag assignment can be made
on official text without changing its source or making that text editable.
The research import and website filter controls ship separately.

## CDN contract

The optional `contentTagsCatalogUrl` in `deadlock/manifest.json` identifies an
immutable catalogue at `deadlock/tags/content/catalog/<sha256>.json`:

```json
{
  "schemaVersion": 1,
  "game": "deadlock",
  "identity": "audio-sha256",
  "tags": [{
    "id": "nicknames",
    "label": "Nicknames",
    "description": "Intentional alternative names, short forms, or distinctive aliases.",
    "membership": {
      "url": "https://cdn.vlviewer.com/deadlock/tags/content/memberships/<sha256>.json",
      "bytes": 123,
      "sha256": "<payload digest>",
      "recordingCount": 1
    }
  }]
}
```

Each membership payload has `schemaVersion`, `game`, `identity: "audio-sha256"`,
`tagId`, and `hashes`, a sorted unique array of lowercase audio SHA-256 values.
Paths and descriptor digests hash the exact compact UTF-8 JSON bytes. Catalogue
entries are sorted by ID. Counts describe the entire transcript repository,
including historical and conversation-only recordings, and are not page counts.
Publication provenance belongs to the sync report, not these immutable payloads.

Every generated conversation and its lines/variations receive a sorted
`contentTags` array. Untagged objects explicitly receive `[]`. The conversation
array is the union of its constituent lines; existing `tags.setting` and
`tags.content` stay intact. Recordings resolve by `audioKey`, never by matching
text or filenames. Older exports without the fields remain readable by existing
clients. Inline fields describe the loaded conversation export; consumers must
not replace them with memberships from another publication generation.

Historical search compression retains separate version states when the same
searchable text/destination has different tag memberships, without changing the
search wire format or embedding a full tag index in it.

## Publication and recovery

The existing serialized content-sync workflow validates definitions, assignments,
and alias consistency; builds memberships and catalogue; updates every affected
conversation export, inventory, and content revision; and advances discovery.
Tag-only changes and removals participate in change detection. Running against
unchanged output does not upload identical immutable objects again.

Memberships are uploaded and publicly verified before a new catalogue is
uploaded. Every catalogue dependency, including objects reused after an
interrupted upload, is publicly verified before the game manifest is written.
Conditional ETag writes and the existing final CDN verification remain in place;
the successful-deployment cursor advances only after verification. Immutable
objects with unexpected bytes block deployment. Old artifacts are retained.
Existing mutable conversation URLs retain the publisher's normal cache
purge/revalidation behavior; these objects are not an atomic multi-object snapshot.

The first deployment with the definitions file publishes empty memberships and
adds explicit empty arrays to existing conversations. No research assignments
are bundled with the compatibility release. Deploy tag-compatible correction
Worker, Manager, website draft logic, and Historical Content importer before
introducing tagged transcript data. After importing/publishing a new version,
run the serialized content sync/history reconciliation to update discovery and
membership projections. Keep using the existing publication coordination; do
not run independent publishers concurrently.

Remove a definition only after removing its source assignments. Retain an empty
definitions file if removing the entire vocabulary after publication. To recover
a partial run, recalculate its plan from the unchanged successful cursor and
retry; inventory checks reconcile already-uploaded conversation bytes.
