# Deadlock Transcripts

Human-readable transcript and content configuration used to generate VLViewer data.

Audio transcripts are stored below `transcripts/` at paths that mirror the audio files.
Each JSON file retains one revision for each distinct audio SHA-256 value.

Edit a revision's `text`, set `source` to `manual`, remove `model`, preview locally, then commit.

## Legacy contribution audit

Stage 1 of the legacy migration is an audit only. It reads the legacy and v2 layouts
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

When Stage 2 creates migration commits, it must set the author name, email, and date
from each audit record. The migration operator remains the committer, so Git records
both who made the original correction and who performed the migration.

Run the tests with:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests -v
```
