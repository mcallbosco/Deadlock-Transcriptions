# Transcript content tags

Transcript revisions may include `tags`, a set of category IDs from
`config/deadlock/content-tags.json`. Schema version remains 3. Missing tags and
`[]` both mean untagged. The initial vocabulary is `wrong-names`, `nicknames`,
and `insults`; definitions can be extended without changing publisher code.

`spoken-ixian` (Spoken Ixian) identifies recordings that contain speech in the
Ixian language, including phrases within otherwise English dialogue. References
to Ixia or Ixians, English translations, and dialogue in other languages do not
qualify on their own. Supported historical and unused recordings remain eligible.

`swears` (Swears) identifies spoken profanity, including mild swearing such as
“ass” and emphatic “bloody”, alongside stronger profanity and
compound forms such as “bullshit” and “jackass”. “Damn” and its variants
(including “goddamn”, “damned”, and “damnation”) do not qualify on their own;
“hell” and “helluva” also do not qualify on their own. A line containing another
qualifying swear still receives the tag. Literal blood descriptions,
place names such as Hell’s Kitchen, and unrelated words such as “Dickens” or
“cocktail” do not qualify. Tags can overlap with `insults`; a swear need not be
directed at someone. Historical and unused recordings remain eligible.
Assignments follow transcript evidence; obvious or uncertain generated
mishearings (for example, “Shiv” transcribed as “shit” in a spotting ping)
require audio review before tagging. This is editorial metadata, not an
automatic profanity detector or a guarantee that untagged audio is swear-free.
Use the existing group helper for future additions and corrections.

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

Maintenance reconciliation and phonetic-review tools check the resulting groups
across aliases before writing files. Equivalent tag orderings and missing versus
empty arrays compare as the same assignment; official linking preserves the
existing official metadata representation when it combines those groups.

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

## Adding Swears: deployment checks

Merge the transcript PR into this repository's `main`. Changes to both
`transcripts/**` and `config/deadlock/**` trigger **Deploy content sync** in
`.github/workflows/content-sync-deploy.yml`, using `incremental-deploy`.
No manual importer run, database migration, Worker deploy, or website rebuild
is required for this vocabulary/assignment-only change with the currently
tag-compatible services and website. The website's filter and recording-tag
panel read definitions from the runtime catalogue, including unfamiliar IDs.

After merging:

1. Confirm **Deploy content sync** finishes successfully (approve the
   `production-cdn` environment if GitHub requests an approval).
2. Follow `contentTagsCatalogUrl` from the live Deadlock manifest and confirm
   the catalogue contains `swears` / `Swears` with a nonzero membership count.
3. Reload the website, open **Filter by Tags**, and select **Swears**. Check a
   matching recording's tag panel and verify existing tags still appear.
   Open pages may retain the previous manifest until reloaded.

If publication fails, inspect its Actions summary and retry the serialized
workflow from `main` using `incremental-deploy`; retain the successful cursor
and avoid concurrent independent publishers or an unnecessary baseline reset.
A successful merge alone is not proof that the CDN publication succeeded.
