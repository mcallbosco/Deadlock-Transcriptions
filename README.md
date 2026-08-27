# Deadlock Transcripts

Human-readable transcript and content configuration used to generate VLViewer data.

Audio transcripts are stored below `transcripts/` at paths that mirror the audio files.
Each schema-v3 revision shares one subtitle across an array of audio SHA-256 values.
Grouping ignores case, Unicode punctuation, and whitespace; stored text is selected by
source authority (`official`, then `manual`, then `generated`).

Edit a revision's `text`, set `source` to `manual`, remove `model`, preview locally,
then commit. Split a hash into a separate revision when one recording needs different text.

To audit the remaining revision groups for near-matching text without modifying any
transcripts, run:

```powershell
python tools/audit_fuzzy_transcript_matches.py
```

The audit compares groups only within the same transcript file and writes complete
JSON plus a compact Markdown review report under `migration-reports/`. Confidence
levels are advisory; even high-confidence candidates require human review.

After reviewing the generated/official candidates, merge them with the official group
as the survivor using:

```powershell
python tools/apply_fuzzy_generated_official_matches.py
python tools/apply_fuzzy_generated_official_matches.py --apply
```

The first command is a dry run. The apply command preserves all hashes and excludes
official text mentioning Hidden King or Archmother, recording every exclusion in JSON
and Markdown under `migration-reports/`. It also propagates each promoted official
state to alias filenames that contain the same audio hash, splitting revision groups
when necessary so unrelated hashes retain their existing transcript state.

## Legacy contribution audit

Stage 1 of the legacy migration is an audit only. It reads the legacy and v3 layouts
from pinned Git objects, identifies legacy text changes that still survive on the old
branch, and reports whether each one has an exact target revision match. It does not
edit `transcripts/` or `config/`.

Run the checked-in audit with the commits used for the initial inventory:

```powershell
python tools/audit_legacy_contributions.py `
  --legacy-ref 2baf749298f6efdec6b2fb7c6b3ac08d2dfb6a64 `
  --target-ref ce36237ac4b165f57eba15edef4c752cebc48160
```

The command writes:

- `migration-reports/manual-contribution-audit.json`: machine-readable evidence,
  including the original author name, email, date, commit, before/after text, target
  revision hash, decision, and proposed action.
- `migration-reports/manual-contribution-audit.md`: a short inventory summary.

Only `candidate_manual` records are eligible for automatic replay in Stage 2.
A candidate must resolve to exactly one mirrored transcript path and one non-official
audio SHA-256 revision. Ambiguous paths/revisions, structural changes, added files,
bot-authored changes, fuzzy/no-match results, and multi-contributor records remain in
review queues. Revisions whose `source` is `official` are always reported with the
`protected` action and are never eligible for replacement.

Stage 1B audits corrections on deleted files and older transcript states:

```powershell
python tools/audit_historical_contributions.py `
  --legacy-ref 2baf749298f6efdec6b2fb7c6b3ac08d2dfb6a64 `
  --target-ref ce36237ac4b165f57eba15edef4c752cebc48160
```

Its JSON and Markdown reports are written below `migration-reports/`. Historical
candidates have stricter requirements: one path, one generated audio-SHA revision,
one correction epoch, and one exact matching state within that epoch. Deleted legacy
files are evidence only; the migration never recreates them. Official and skipped
target revisions are review-only in this historical pass.

To validate the current-correction application without writing files:

```powershell
python tools/apply_current_contributions.py
```

Pass `--apply` only when the transcript tree is clean and the pinned audit has been
reviewed. The tool changes only selected non-official revisions, removes their model,
sets their source to `manual`, and deliberately does not stage or commit anything.

### Targeting a released game version

The legacy format has no audio hash, so array position cannot identify the active
revision. A VLViewer version manifest provides the missing `filename` to `audioKey`
mapping. Audit corrections against the manifest before applying them:

```powershell
python tools/audit_latest_version_contributions.py `
  --manifest-url "https://cdn.vlviewer.com/deadlock/versions/ognb/voicelines.json?_v=1786504895450-82710"

python tools/apply_latest_version_contributions.py
```

The first command records the manifest URL, ETag, last-modified time, and content
SHA-256 in the report. A latest-hash correction is eligible only when that revision
contains either the exact legacy pre-correction text or the exact corrected text.
This prevents an old correction from overwriting a divergent re-recording. The apply
command is a dry run unless `--apply` is passed, and it never stages or commits files.

### Historical corrections for a released version

CDN `publishedAt` timestamps describe when data was imported into VLViewer, not when
the game update shipped. `config/deadlock/version-releases.json` therefore records
reviewed release-date boundaries and the official sources supporting them. The root
CDN manifest remains the authority for each version ID's live voice-line manifest.

The first implemented historical window is the Six Hero Update:

```powershell
python tools/audit_versioned_historical_contributions.py `
  --version-id six-hero-update

python tools/apply_versioned_historical_contributions.py
```

The audit selects only correction epochs wholly inside the configured release
window, resolves their filenames through that version's audio SHA-256 manifest, and
requires one exact historical text state. The apply command is a dry run unless
`--apply` is passed. It verifies the transcript worktree is clean, refuses any
official or non-generated revision, and does not stage or commit its changes.

The current OGNB window can be audited separately without applying anything:

```powershell
python tools/audit_versioned_historical_contributions.py `
  --version-id ognb `
  --output-json migration-reports/ognb-historical-contribution-audit.json `
  --output-markdown migration-reports/ognb-historical-contribution-audit.md
```

After released-version candidates and official revisions are excluded, search every
version in the live root manifest for exact anchors among the unresolved epochs:

```powershell
python tools/audit_cross_version_historical_contributions.py
```

Cross-version matches are report-only because their recording was not active in the
version assigned from the correction date. They must have unique path, SHA, text
state, and history evidence and must still be unchanged and generated on `HEAD`.
After explicit review, validate or apply the selected report candidates with:

```powershell
python tools/apply_cross_version_historical_contributions.py
python tools/apply_cross_version_historical_contributions.py `
  --apply --approve-temporal-mismatch
```

Current corrections that diverge on the OGNB SHA can likewise be checked for exact
states on older recordings:

```powershell
python tools/audit_cross_version_current_contributions.py
python tools/apply_cross_version_current_contributions.py
python tools/apply_cross_version_current_contributions.py `
  --apply --approve-reviewed-temporal-mismatch
```

The apply command is pinned to an explicit review decision and audit content hash. It
requires one exact older audio revision, verifies the current generated text, and never
changes the divergent active OGNB recording or an official revision.

For Six Hero epochs with no exact state on any published SHA, generate a conservative
semantic-delta review. This ranks already-correct lexical equivalents and uniquely
transferable edit spans. Application is a separate, explicitly reviewed step pinned
to the audit's content hash:

```powershell
python tools/audit_semantic_delta_contributions.py
python tools/apply_semantic_delta_contributions.py
python tools/apply_semantic_delta_contributions.py `
  --apply --approve-reviewed-high-confidence
```

The apply tool accepts only the two high-confidence statuses recorded in the review
decisions file. It verifies the selected SHA still has its audited generated text,
refuses official revisions, and leaves all resulting changes unstaged and uncommitted.

Low-confidence records remain ineligible by default. When an explicitly filtered list
has been manually reviewed, record that selection and its text overrides in a pinned
decisions file, then validate and apply it separately:

```powershell
python tools/apply_reviewed_low_confidence_contributions.py
python tools/apply_reviewed_low_confidence_contributions.py `
  --apply --approve-reviewed-low-confidence
```

This tool still requires the audited generated text at the exact selected SHA and never
modifies official revisions. Its checked-in decision set includes external and mixed
external/user correction epochs only; user-only and Copilot-authored epochs are excluded.

Reviewed medium-confidence records use a separate pinned decision set so suspicious
transfers remain excluded and reviewer-supplied text overrides are explicit:

```powershell
python tools/apply_reviewed_medium_confidence_contributions.py
python tools/apply_reviewed_medium_confidence_contributions.py `
  --apply --approve-reviewed-medium-confidence
```

When Stage 2 creates migration commits, it must set the author name, email, and date
from each audit record. The migration operator remains the committer, so Git records
both who made the original correction and who performed the migration.

Run the tests with:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests -v
```

## Double-blank audio review

Start the local reviewer for recordings that returned blank from both
`gpt-transcribe` passes:

```powershell
python tools/double_blank_review_server.py --open
```

The interface loads both CDN encodes for every held recording, shows earlier transcript
candidates, and supports transcript, nonspeech, and hold decisions. Decisions are saved
after every action to
`migration-reports/gpt-transcribe-double-blank-decisions.json`; they can also be exported
from the interface. The server listens only on `127.0.0.1` by default and has no external
package dependencies.

Keyboard shortcuts are available outside text fields: `A` and `B` play either encode,
`Space` toggles playback, `J`/`K` navigate, and `T`, `N`, or `H` save a transcript,
nonspeech, or hold decision respectively.

Once every recording has a decision, validate and apply the review with:

```powershell
python tools/apply_double_blank_review.py
python tools/apply_double_blank_review.py --apply
```

Accepted speech becomes `manual`, confirmed nonspeech becomes `skippednonspeech`, and a
held decision can be merged into a unique current official revision by mentioning
`official` in its review note. The applier updates every current occurrence of every
recording hash and refuses incomplete reviews, unknown hashes, or unresolved holds.

## CDN synchronization

Pull requests targeting `main` validate the complete repository and build a
credential-free plan against the public VLViewer CDN. Changes to transcript revisions,
categories, and character display names are deployable in Phase 1. Changes to mapping,
alias, grouping, conversation-override, or per-version audio-override inputs fail with
`regeneration required` until the deterministic generator is available.

CI also requires every recording SHA-256 to resolve to one published transcript state.
Duplicate states are reconciled by `official` > `manual` > `generated`, with the most
recent Git edit breaking ties at the same authority.

After the one-time baseline is initialized, qualifying pushes to protected `main`
automatically recalculate from the private deployment cursor and conditionally update R2.
The workflow publishes version content and metadata first, the public game manifest last,
verifies the changed public URLs, and only then advances the private cursor.

Repository/environment setup and baseline instructions are documented in
[`docs/content-sync-operations.md`](docs/content-sync-operations.md).

The Phase 1 planner and R2 synchronizer are checked in under `tools/` and are tested in
the same pull request as transcript and configuration changes. CI therefore does not
fetch executable publisher code from another repository.
