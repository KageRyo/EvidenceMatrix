# EntityLinkage to EvidenceMatrix

This fully synthetic example links fictional external catalog records to a small entity list, preserves the decisions that need review, and turns only resolved links into EvidenceMatrix coverage. It uses no TAG data or network source.

## Run the complete flow

Install the two standalone tools:

```bash
python -m pip install -r examples/entitylinkage-coverage/requirements.txt 'evidencematrix==0.1.1'
bash examples/entitylinkage-coverage/run-example.sh
```

The script creates a temporary output directory and prints its path when it finishes. Pass a path to choose the output location:

```bash
bash examples/entitylinkage-coverage/run-example.sh ./entitylinkage-coverage-output
```

For each case, the script validates and links the records with EntityLinkage, adapts its versioned `linkage.json` output, then validates, builds, summarizes, and audits the generated EvidenceMatrix manifest. The audit returns exit code 1 because the example intentionally retains unresolved coverage findings; the script checks that expected CI-gate result.

## Review before changing coverage

`entitylinkage.yaml` produces these record decisions:

| Record | EntityLinkage result | Meaning |
| --- | --- | --- |
| `record-a-001` | resolved to `entity-1` | Exact fictional catalog name. |
| `record-a-002` | ambiguous between `entity-2` and `entity-4` | Shared alias; it remains in `review.csv`. |
| `record-a-003` | unresolved | No declared identity candidate; it remains in `review.csv`. |
| `record-b-001` | resolved to `entity-3` | Exact fictional archive name. |
| `record-b-002` | not applicable | The record is outside the archive's declared scope. |

The explicit coverage context is separate from the matching configuration. It declares the source inventory, two known mapping gaps, and one entity-source relationship that is outside scope. Pairs with no declaration or resolved record stay `unknown` when their source is available. A source marked `unavailable` or `not_in_release` keeps that meaning across all entities.

`review.csv` retains ambiguous, unresolved, and record-level not-applicable decisions, including the normalized name, candidate IDs, reason codes, and rule evidence. The adapter never promotes ambiguous or unresolved candidates into coverage. `resolved-records.csv` preserves each source record behind a supported relationship. When several records resolve to the same entity and source, the manifest has one supported relationship while the sidecar keeps every record.

## Apply a reviewed decision

`entitylinkage-reviewed.yaml` adds a manual override for `record-a-002`, after a human review selects `entity-4`. The adapter promotes only the already-declared `entity-4` / `catalog-a` `mapping_gap` to `supported`. The `entity-2` / `catalog-a` gap remains, and the unresolved record is still unresolved.

| EvidenceMatrix status | Before review | After review |
| --- | ---: | ---: |
| `supported` | 2 | 3 |
| `mapping_gap` | 2 | 1 |
| `not_applicable` | 1 | 1 |
| `unknown` | 3 | 3 |
| `source_unavailable` | 4 | 4 |
| `source_not_in_release` | 4 | 4 |

Both cases contain 16 entity-source relationships. The adapter is a standalone Python standard-library script and accepts the `entitylinkage-results-v1` JSON contract; it does not add a runtime dependency between either package.
