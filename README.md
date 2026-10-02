# Deadlock Transcripts

Transcripts and content configuration used to generate VLViewer data.

Audio transcripts are stored below `transcripts/` at paths that mirror the audio files.
Each schema-v3 revision shares one subtitle across an array of audio SHA-256 values.
Grouping ignores case, Unicode punctuation, and whitespace; stored text is selected by
source authority (`official`, then `manual`, then `generated`).

Edit a revision's `text`, set `source` to `manual`, remove `model`, preview locally,
then commit. Split a hash into a separate revision when one recording needs different text.

## Cross-file phonetic lineage review

To find cross-file transcript variants inside the permanent voice-line lineages, run:

```powershell
python tools/audit_phonetic_lineage_merges.py
```

The audit follows both shared-audio-hash edges and reviewed manual filename
correlations. It writes separate strong and lower-confidence JSON/Markdown tables
below `migration-reports/phonetic-lineage-merges/`. Strong candidates are limited to
normalized spoken equivalents or near-identical wording. The lower-confidence table
retains recognizable speech-to-text mishearings and wording variants for review.

Strong same-authority pairs require an explicit decision; generated-only decisions
remain `generated` with their transcription model. Different-authority pairs use `official`, then `manual`, then
`generated`. Validate the reviewed batch first, then apply it with:

```powershell
python tools/apply_phonetic_lineage_merges.py
python tools/apply_phonetic_lineage_merges.py `
  --apply --approve-reviewed-phonetic-merges
```

The application preserves every represented recording hash, propagates the selected
state to every filename containing a targeted hash, and leaves lower-confidence
candidates unchanged.

## Acknowledging completed structural regeneration

The transcript updater blocks changes to generator inputs until Historical Content
has regenerated and published the affected content. After that operation, pass
`--regeneration-approvals <report.json>` to `tools.content_sync_cli plan` or `deploy`.
Each approval names an exact generator configuration path, its canonical JSON SHA-256,
and published release evidence (`version`, `publishedAt`, and minimum `contentRevision`).
Changed configurations and missing or older releases remain blocked. Record the operator's
confirmation and evidence alongside the approval; release metadata confirms publication,
while the operator confirms which configuration was used for regeneration.

The October 2 recovery is documented in `reports/ci-recovery-20261002/README.md`.
