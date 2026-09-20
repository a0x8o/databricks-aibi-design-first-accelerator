# Terminal Cross-Validation — Validation Contract

> **Always loaded.** Owns successful report, binding, inventory-parity, and output evidence.

## Success Gate

A successful sweep requires exact current-run identity, `source: cross_validation_sweep`, `overall_status: PASS`, scope and workspace-host bindings `PASS`, exact expected/observed inventory parity, and one authenticated current-readback result per expected asset. Dashboard quality `WARN` remains non-structural and preserves Dashboard `PARTIAL_SUCCESS`.

## Output Contract

| Output | Required condition |
|---|---|
| `ground_truth_validation.yaml` | Written and re-read for both `PASS` and diagnosed `FAIL` outcomes |
| `scope_inputs_sha256` | Lowercase 64-hex digest of the exact frozen scope object |
| `ground_truth_validation_sha256` | Lowercase 64-hex digest of the exact persisted report bytes, held by orchestration |
| stage status | `PASS` only for an authenticated successful report; otherwise `FAIL` |
| failure owner | `null` on success; one allowed owner on failure |

There is no `SKIPPED` outcome for this stage. `SWEEP_UNAVAILABLE` is a documentation fallback label,
not a successful or skipped terminal-sweep result.
