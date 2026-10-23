# October 23 official-caption conflict recovery

The official-caption update at `ba720f29b7d736b45d904caac8365c91a3921538`
exposed one pre-existing published/source mismatch. The [first failed deployment](https://github.com/mcallbosco/Deadlock-Transcriptions/actions/runs/39884834533)
and the [deployment after the tag publisher merge](https://github.com/mcallbosco/Deadlock-Transcriptions/actions/runs/39956846135)
both stopped before publishing. The latter plan reports no validation errors,
995 ordinary record updates, 777 no-ops, and one conflict. Its base is the last
successful transcript commit, `3feec55ce461a039b6aa04862dbff830a4e29c91`.

The conflict is in `deadlock/versions/cns-deadman/voicelines.json`, at
`$/deadman danny/Self/Emotions/Pain/Pain death/9`, for recording
`8382362c6a01e25bae5a228baca21794c27e75923651437193d223eb271642ad`.
Its source is `transcripts/deadpack/emote/deadpack_pain_death_05.mp3.json`.

| State | Text | Official |
| --- | --- | --- |
| Deployed Git base | empty (`skippednonspeech`) | false |
| Current CDN | `(include all the lines that he says after each scream)` | true |
| Intended source | `Agh!` | true |

The CDN contains a production note instead of the intended caption. The publisher
correctly rejects this third state; no transcript rollback or relaxation of conflict
detection is needed. The supplied approval authorizes only the exact record location,
hash, current text/status, and desired text/status above.

On October 23, a fresh public download was JSON-equivalent to the failed run's
pre-change R2 backup. Its body SHA-256 was
`eb0aaa8f22ce60bc0f0a7afcbbace9b18cc6876d7c0716cbbb7ba47d0a18974e`.
The release identified `cns-deadman`, content revision 7, updated at
`2026-10-23T01:30:19.009621Z`. The approval was generated from the saved blocked
deployment plan with `tools.create_content_sync_conflict_approvals --expected-count 1`.

## Recovery after merge

1. Run **Deploy content sync** on `main` in **incremental-dry-run** mode. Set
   `conflict_approvals` to `reports/ci-recovery-20261023/conflict-approvals.json`;
   leave `base_commit` empty and `approve_baseline` false.
2. Inspect the new plan: it must have zero conflicts/errors and exactly this one
   approved overwrite. The run also includes the official-caption and tag-publisher
   changes pending since the deployment cursor.
3. Run **incremental-deploy** with the same approval input. Conditional writes,
   backups, public verification, and cursor advancement remain in effect.
4. Confirm the published caption is `Agh!`, then use ordinary deployments with no
   approval input. Repeating the recovery after success is harmless: the desired
   record is already a no-op.

The manual input is opt-in and restricted to tracked JSON files under `reports/`.
Normal pushes never load this approval. Merging this recovery PR alone does not
repair the published record; the manual recovery run is required.
