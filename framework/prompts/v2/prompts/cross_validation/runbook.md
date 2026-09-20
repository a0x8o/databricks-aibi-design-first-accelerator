# Terminal Cross-Validation — Failure Runbook

> **FAILURE-ONLY — DO NOT LOAD ON A SUCCESSFUL PATH.** Authenticate the frozen tuple and load only the section matching the classified failure owner.

## Failure Contract and Ownership

Allowed owners are exactly:

```text
MASTER_RESOLVER
DATA_LAYER_STAGE
METRIC_VIEW_STAGE
DASHBOARD_STAGE
GENIE_STAGE
CROSS_VALIDATION_SWEEP
```

Route a mismatch by the field's G-3 owner, not by whichever manifest or file was read last.

On failure:

1. Persist a diagnostic report at the same canonical path with
   `source: cross_validation_sweep`, `overall_status: FAIL`, exact current identity/scope fields,
   `failure_owner`, and a non-empty classified error.
2. Re-read and hash the exact diagnostic bytes for terminal evidence.
3. Return `FAIL` to the master. Never write or imply a completed/partial terminal lifecycle state.
4. Do not repair or redeploy assets from this stage. The master may route a targeted correction to
   `DATA_LAYER_STAGE`, `METRIC_VIEW_STAGE`, `DASHBOARD_STAGE`, or `GENIE_STAGE`, then must re-run the
   entire terminal sweep.
5. `MASTER_RESOLVER` and `CROSS_VALIDATION_SWEEP` failures require contract/helper correction and
   halt rather than asset mutation.
6. Never re-run data generation merely to repair or repeat cross-validation.

Documentation may run afterward only in authenticated failure-reporting mode. It must label the
failed sweep as failed evidence, must not call this stage or helper itself, and must not claim ground
truth from a fallback.
