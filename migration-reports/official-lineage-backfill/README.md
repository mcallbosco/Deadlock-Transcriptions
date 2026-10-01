# Historical official transcript lineage backfill

Older merge tools updated inherited transcript wording without consistently retaining the older recording hash in the actual official destination. The September 29 content imports corrected official wording, and the subsequent alias repair left some historical recordings on separate older revisions. This backfill restores documented historical relationships so the official importer can propagate subsequent corrections.

The base is `e0a1cbdc504621b5204b49d13b512810f746235c` (including #291). This change covers 4,050 reviewed historical groups, adds 9,518 hash memberships to official destinations, and updates 3,678 orphaned recording hashes in all existing aliases. Of those corrections, 3,615 concern capitalization, punctuation, or spacing, and 63 are reviewed typo repairs. It also restores documented links whose current wording already agrees. There are 6,580 changed transcript files.

Every original recording hash remains in every original file. Existing official destination wording is retained. Only explicitly reviewed inherited copies receive the already established official correction. Six entity substitutions (Fathom/Slork and Paradox/Chrono) and 171 matches without adequate historical proof are excluded.

For example, the older Haze recording `80f9f7122c817f7e4dca80899688d1dfb930be3627685650d343f4e896d8eca7` remains in `haze/haze_kill_holliday_04.mp3` and is restored to the official revision in `haze/haze_kill_astro_04.mp3`. Its inherited “Troubador” wording follows the existing official “Troubadour” correction. The current authoritative wording is unchanged.

## Review artifacts

- `plan.json`: explicit hashes, old and corrected text, original aliases, unchanged official destination references, original official provenance, historical merge receipts, and exclusions. Destination provenance uses the authoritative snapshot before fuzzy merges (`defc2288844010601e307cf72c0efebc5492af1d`), receipt evidence, and published canonical destinations in the confirmed filename lineage.
- `typo-corrections.json`: the 39 distinct before/after spelling and wording pairs affecting 63 hashes. Capitalization variants can produce separate pairs for the same typo.
- `apply-result.json`: application counts and repository validation.
- `verification.json`: independent comparison against the base tree, including original memberships, unrelated state preservation, explicit official destinations, and restored graph connectivity.

The importer synchronization in VLViewer-DL-Organizer #18 is already merged. This PR changes transcript data and supplies guarded reproduction tooling; it does not change the older merge tools or deploy content.

## Reproduction and verification

From the base commit, run:

```sh
python3 -m tools.backfill_official_lineage \
  --plan migration-reports/official-lineage-backfill/plan.json \
  --apply --report migration-reports/official-lineage-backfill/apply-result.json
python3 -m unittest discover -s tests -q
python3 -m tools.content_sync_cli validate --base e0a1cbdc504621b5204b49d13b512810f746235c
```

The manifest and tool must be available in that checkout. The planner rejects unknown recordings, conflicting targets, changed aliases, unexpected source/text drift, and modified official destinations before writing. A rerun on the backfilled dataset produces zero changed files and zero added memberships. The regression suite passes all 151 tests.
