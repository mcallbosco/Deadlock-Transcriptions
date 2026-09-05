# Phonetic lineage merge review

The refreshed audit compared transcript revisions across permanent filename
lineages built from shared recording hashes and 11,519 reviewed manual
correlation groups.

| Result | Count | Disposition |
| --- | ---: | --- |
| Transcript files scanned | 98,944 | Complete repository |
| Multi-file lineages | 13,013 | Shared-hash and manual edges are transitive |
| Strong candidate pairs | 2 | Review snapshot |
| Lower-confidence candidate pairs | 4,275 | Review snapshot |
| Imported judgments still applicable | 424 | Four additional reviewed pairs were already resolved upstream |
| Approved candidate pairs | 291 | Applied across 247 transitive components |
| Keep-separate candidate pairs | 133 | Not changed |
| Recording hashes reconciled | 505 | 361 official; 144 generated |
| Transcript files changed | 347 | Every represented hash was preserved |
| Incorrect transcript flags | 50 | Archived with the source export; intentionally not applied |

## Review artifacts

- [Strong candidates](strong/candidates.md)
- [Lower-confidence candidates](lower-confidence/candidates.md)
- [Source review export](reviews/2026-09-05.json)
- [Applicable decisions](reviews/2026-09-05-applicable.json)
- [Apply result](reviews/2026-09-05-apply-result.json)

The candidate tables are the refreshed pre-apply snapshot used to validate the
review. When approved pairs formed a transitive component, the latest explicit
judgment in that component selected the transcript. Generated-only selections
remain generated; official selections retain official provenance.
