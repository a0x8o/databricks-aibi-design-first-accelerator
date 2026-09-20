# Data Layer — Validation Contract

> **Always loaded.** This file owns executable gates and evidence requirements for `create_data_layer`. Operational history is intentionally excluded.

## Gates

### GATE 2.1b: Data Type Validation (MANDATORY post-parse)
After parsing ERD, verify every column has a concrete data type. If ANY column has NULL/UNKNOWN type, re-invoke vision model with a targeted crop. HALT if still unresolved after 2 retries.

### GATE 4.0: Expected Schema Contract (MANDATORY before DDL execution)
`table_spec.yaml` must be an exact physical projection of `erd_parsed.yaml`. Normalize and compare every table, column, and datatype. HALT with `SCHEMA_CONTRACT_ERROR` on any missing, unexpected, renamed, or retyped object.

### GATE 4.1: Table Count Verification
`SHOW TABLES IN {catalog}.{schema} LIKE '*{ASSET_SUFFIX}'` must return expected count, using the exact frozen `step_handoff.yaml.asset_suffix`. HALT if fewer.
**CRITICAL:** `SHOW TABLES LIKE` uses **glob syntax** (`*` = wildcard), NOT SQL LIKE syntax (`%` = wildcard). See **G-15** in `shared/global_guardrails.md`. Using `%` returns zero results.

### GATE 4.2: Schema Reconciliation (MANDATORY after DDL execution)
After GATE 4.1, verify each table's **actual deployed schema** from `DESCRIBE TABLE` matches the **expected generated schema** in `table_spec.yaml`, including normalized column names and datatypes. GATE 4.0 already proves that `table_spec.yaml` matches `erd_parsed.yaml`.

The canonical policy identifier is `DEPLOYED_DATATYPE_REPAIR_V1`.

Use only the release-approved deterministic datatype canonicalizer. Canonicalization may normalize case, insignificant whitespace, and aliases explicitly encoded by that canonicalizer; it MUST NOT infer widening compatibility, add a cast, change precision/scale/length, or treat two merely coercible types as equal. Preserve the exact expected and observed type strings as evidence.

For any real deployed datatype mismatch, the Data Layer is the sole repair owner. Automatic repair is permitted exactly once per table only when **all** of these checks pass:

1. the FQN is the exact current-run generated target from `table_spec.yaml`, in the frozen target catalog/schema, with the exact frozen `asset_suffix`;
2. the table is a greenfield accelerator-owned target, not a live/source table, unversioned object, or object discovered by a wildcard;
3. `SELECT COUNT(*)` succeeds and returns exactly zero;
4. the repair uses the pinned DDL compiler and unchanged `table_spec.yaml`; and
5. no earlier datatype repair attempt was made for that table in this run.

The only allowed automatic action is: record the mismatch, drop the exact empty table, rerun its compiler-generated CREATE statement, rerun `DESCRIBE TABLE`, and require exact canonical schema equality. `ALTER COLUMN`, casts, `TRY_CAST`, CTAS, overwrite, mutation of `erd_parsed.yaml`/`table_spec.yaml`, and adoption of the observed type are prohibited repair mechanisms.

If ownership is ambiguous, the table is non-empty, row count cannot be proven, the object is source/live/unversioned, the operation lacks permission, or post-repair readback still differs, write failure evidence and HALT with `DATATYPE_MISMATCH_UNSAFE_TO_REPAIR`. Do not delete or coerce data. Missing/unexpected/renamed-column mismatches use the same empty-current-version-table eligibility gate and otherwise halt with `SCHEMA_CONTRACT_ERROR`.

Record every decision in `data_layer_validation.yaml.schema_reconciliation`: policy identifier, expected/observed schema, canonical comparison, ownership checks, row count, action, attempt count, post-repair readback, and terminal status. A failure may write a partial validation artifact with `overall_status: FAIL`; downstream and resume gates accept only `overall_status: PASS`, `schema_reconciliation.policy_id: DEPLOYED_DATATYPE_REPAIR_V1`, `schema_reconciliation.status: PASS`, and zero unresolved mismatches.

### GATE 5.1: Domain Value Validation
Every categorical column MUST have domain-specific values (not `val_1`...`val_5`). Run the Domain Value Inference Protocol for any column with generic values.

### GATE 5.2: YAML Type Safety Validation (MANDATORY before writing spec)
All values for VARCHAR/STRING columns MUST be quoted strings in `synthetic_data_spec.yaml`. YAML parses `99213` as integer, creating mixed-type lists.

### GATE 6.1: Row Count Verification
ALL tables must have rows > 0 after synthetic data generation. HALT with `SYNTHETIC_GENERATION_ERROR` if any table is empty.

### GATE 7.1: Data Layer Validation
`data_layer_validation.yaml` must exist with `overall_status: PASS`, `schema_reconciliation.policy_id: DEPLOYED_DATATYPE_REPAIR_V1`, `schema_reconciliation.status: PASS`, and zero unresolved schema mismatches. Every relationship in `semantic_model.yaml` must have exactly one relationship-level validation entry with `validation_status: PASS`. HALT otherwise. `semantic_model.yaml` is relationship intent; this relationship-level result is the authority for downstream use of the deployed relationship.

---

## Failure-Only Runbook Routing Index

| Runbook section | Load only when observed evidence matches |
|---|---|
| `AP-DL-1` | Vision Model Truncation |
| `AP-DL-2` | Mixed-Type YAML Lists |
| `AP-DL-3` | dbldatagen Boolean/Timestamp Bugs |
| `AP-DL-6` | Truncated Data Types from Vision Model (decimal(28) |
| `AP-DL-5` | LLM Generates DDL Notebook From Scratch Instead of Using Template |
| `AP-DL-4` | SHOW TABLES LIKE Uses Wrong Wildcard |
| `AP-DL-7` | Join Fanout From Missing pk_cols in Dimension Tables |
| `AP-DL-8` | DELTA_EXCEED_CHAR_VARCHAR_LIMIT from dbldatagen Generated Values |

Classify the failure from current evidence before loading a runbook section. The index is a routing aid, not authority to bypass the stage owner or retry policy.
