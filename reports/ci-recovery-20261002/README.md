# October 2 content-sync recovery

The last successful transcript cursor was `22cde42fad75cf5619822a3a84690bfde0a17f16`.
The October 2 import introduced 32 conflicting recording hashes across filename
aliases. `duplicate-hash-reconciliation.json` records all candidates and the chosen
state. All candidates are official transcripts; in every decision the most recently
edited file supplies the state. The correction updates 34 files and splits 28 revision
groups so unrelated recordings keep their original state. No recording hashes are removed.

The owner confirmed that structural content regeneration is already complete.
The CDN release metadata confirms `cns-rat` was published at
`2026-10-02T21:20:35.062831Z` and `cns` reached content revision 21 at
`2026-10-02T21:41:01.094138+00:00`.
`regeneration-approvals.json` acknowledges only the exact current character mapping
and the two version-specific audio filename overrides. Planning checks canonical JSON
SHA-256 and the corresponding published release identity/revision before acknowledging
a generator input. Unknown paths and future configuration changes still block.

Both CI planning and deployment pass this acknowledgement file explicitly. It does
not update structural content; that is handled by Historical Content regeneration.
It lets the transcript updater catch up from the old cursor against the regenerated
catalogs, including rebuilding history/lineage metadata for the transcript editor.
