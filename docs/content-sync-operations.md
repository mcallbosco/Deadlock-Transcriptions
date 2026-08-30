# Content sync operations

The `Content sync plan` workflow is read-only and uses no production credentials. The
`Deploy content sync` workflow uses the protected `production-cdn` environment.

## Optional repository variable

- `CDN_BASE_URL` (defaults to `https://cdn.vlviewer.com`)

## Required production environment

Create a GitHub environment named `production-cdn`, restrict deployment branches to
protected `main`, and add:

- Secret `R2_ACCESS_KEY_ID`
- Secret `R2_SECRET_ACCESS_KEY`
- Variable `R2_BUCKET` (normally `vlviewer-content`)
- Variable `R2_ENDPOINT_URL` (the account R2 S3 endpoint)

For targeted cache purges, also add variable `CLOUDFLARE_ZONE_ID` and secret
`CLOUDFLARE_API_TOKEN`. They may be omitted; public verification still runs.

The R2 credentials should be limited to this bucket. The cache token should be limited
to cache purge for the VLViewer zone.

## One-time cutover and baseline

1. Deploy the updated content Worker so `<game>/_internal/**` returns `404` before the
   private cursor is created.
2. Preserve the former repository history on `legacy-main` and make the replacement
   history protected `main` without merging the unrelated histories.
3. Configure the `production-cdn` environment and secrets above.
4. Run `Deploy content sync` on `main` with mode `baseline-dry-run`.
5. Download and review the plan artifact. Resolve every reported ambiguous transcript
   SHA or other conflict.
6. Run it again with mode `initialize` and check `approve_baseline`.
7. Require `Validate and plan CDN changes` in branch protection. Later qualifying
   merges to `main` deploy automatically.

The sync implementation lives in this repository under `tools/content_sync.py`, so the
workflow always runs the exact code reviewed with the transcript/config commit. No
cross-repository publisher reference is required.

For a local validation or credential-free incremental plan:

```powershell
python -m pip install --requirement requirements-ci.txt
python -m tools.content_sync_cli validate --repo .
python -m tools.content_sync_cli plan `
  --repo . `
  --base <ancestor-commit> `
  --output-json plan.json `
  --output-markdown plan.md
```

Planning requires the transcript/config tree to be committed and clean so the reported
target commit always identifies the exact content that was evaluated.

Repository validation treats conflicting published states for the same recording SHA-256
as a hard error. Resolve duplicate hashes before merge using this authority order:
`official`, then `manual`, then `generated`; when candidates have the same authority, use
the file version most recently edited in Git. The pull-request workflow runs this invariant
check explicitly before contacting the public CDN, and the planner validates it again.

## Exact conflict approvals

An incremental plan normally blocks when a live CDN record matches neither the Git base
nor the desired target. A reviewed approval file may authorize an individual overwrite by
pinning all of its identity and state fields: version, object key, JSON path, recording
SHA-256, current published text/status, and desired published text/status. Any change to
one of those fields remains a conflict; this is not a global force switch.

Both pull-request planning and production deployment use
`migration-reports/fuzzy-cdn-conflict-approvals.json` for the reviewed fuzzy-transcript
migration. Once those records hold the desired state, the entries are harmless no-ops.
Generate a reviewed set from a saved blocked plan with:

```powershell
python -m tools.create_content_sync_conflict_approvals `
  plan.json `
  migration-reports/fuzzy-cdn-conflict-approvals.json `
  --expected-count <reviewed-count> `
  --source-run-url <github-actions-run-url>
```

Initialization refuses to run if the cursor already exists. A failed initialization is
safe to rerun: desired-state objects become no-ops, metadata retains the target deployment
identity, and the cursor is written only after public verification.

## Manual modes

- `incremental-dry-run`: plan from the cursor without writes.
- `incremental-deploy`: retry/recover the cursor-to-HEAD range. An optional ancestor
  `base_commit` can override the cursor for reviewed recovery.
- `baseline-dry-run`: compare the complete current tree with R2 without writes.
- `baseline-deploy`: full reconciliation; requires `approve_baseline`.
- `initialize`: first full reconciliation and cursor creation; requires
  `approve_baseline` and an absent cursor.
- `history-dry-run`: rebuild history against current R2 catalogs without writes;
  requires the private cursor to equal the target transcript commit.
- `history-reconcile`: publish and verify history after a hidden official version is
  added; requires the same cursor equality and does not bypass transcript changes.

Do not use an old-history commit as an incremental base. Non-ancestor ranges are rejected
and must go through a reviewed baseline operation.

For a new official game version, update `config/deadlock/voice-line-history.json`
first, publish the version as hidden, run the two history modes, verify the exact
voice-line and conversation catalog hashes in the public history manifest, and only
then promote the version. Do not
run the Historical Content desktop publisher concurrently with this workflow.
