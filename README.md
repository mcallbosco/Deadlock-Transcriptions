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
Ambiguous, structural, added-file, bot-authored, fuzzy/no-match, and multi-contributor
records remain in review queues. Revisions whose `source` is `official` are always
reported with the `protected` action and are never eligible for replacement.

When Stage 2 creates migration commits, it must set the author name, email, and date
from each audit record. The migration operator remains the committer, so Git records
both who made the original correction and who performed the migration.

Run the tests with:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests -v
```
