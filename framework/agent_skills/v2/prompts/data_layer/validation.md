# Data Layer — Validation Contract

> **Always loaded.** This file owns executable gates and evidence requirements for `create_data_layer`. Operational history is intentionally excluded.

## Gates

### GATE 2.1b: Data Type Validation (MANDATORY post-parse)
After parsing the ERD, verify every column has a Databricks-valid datatype. `DECIMAL`, `DECIMAL(p)`,
and `DECIMAL(p,s)` are complete platform syntax and canonicalize using documented defaults `p=10`,
`s=0`; enforce `1 <= p <= 38` and `0 <= s <= p`. For NULL, UNKNOWN, truncated, unbalanced, or
unsupported types, re-invoke the vision model with a targeted crop up to two times. If a datatype-only
defect remains and the run is ERD-driven with both `greenfield.enabled` and
`greenfield.synthetic_data` true, invoke `GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1`, persist every
decision in `schema_assumptions.yaml`, and rerun strict validation. This resolver is total for
datatype defects: recover visible components, prefer strict-majority semantic peers, apply the
release-pinned semantic policy, then use non-truncating `STRING`. Source/live, retained-data, and
structural defects remain `ERD_EXTRACTION_ERROR` hard stops.

This gate applies equally to a fresh vision response, a prior-version ERD cache candidate, and a
resume candidate. Matching ERD image hash, parseable YAML, non-empty tables, or an old phase status
cannot pass this gate. Run the current digest-attested validator before accepting or writing the
candidate. A cached candidate that fails becomes a cache miss; invalidate `parse_erd` and all
dependents and perform a fresh parse. Cache/resume PASS additionally requires a current authenticated
`schema_assumptions.yaml`, even when its resolution count is zero.

### GATE 4.0: Expected Schema Contract (MANDATORY before DDL execution)
`table_spec.yaml` must be an exact physical projection of the resolved `erd_parsed.yaml`. Before notebook
deployment or execution, invoke the digest-attested `validate_table_spec_projection(erd_tables,
table_spec)` function and require `PASS`. Normalize and compare every ordered table, column, and
datatype; reject duplicates and malformed parameterized types. Authenticate the assumptions artifact's
run/target/suffix, policy ID, raw/resolved ERD hashes, and ordered rows first. An eligible invalid ERD
datatype routes through bounded targeted reparse and governed resolution; a table-spec projection
difference routes to regeneration as `SCHEMA_CONTRACT_ERROR`. Neither rejected artifact may reach
`execute_notebook`.

Defense in depth inside the DDL runtime occurs before the first Spark SQL statement and writes
`ddl_preflight.yaml`. For an eligible datatype-only defect, the runtime independently applies the
same pinned resolver, atomically writes the resolved ERD and `schema_assumptions.yaml`, proves
idempotence, and then regenerates only table-spec type fields from the resolved ERD. Record every
old/new value, raw/resolved ERD hashes, assumptions digest, and both table-spec hashes; require a
second exact projection PASS. This never authorizes adopting catalog drift as intent. Structural
differences remain hard failures.

### GATE 4.1: Table Count Verification
`SHOW TABLES IN {catalog}.{schema} LIKE '*{ASSET_SUFFIX}'` must return expected count, using the exact frozen `step_handoff.yaml.asset_suffix`. HALT if fewer.
**CRITICAL:** `SHOW TABLES LIKE` uses **glob syntax** (`*` = wildcard), NOT SQL LIKE syntax (`%` = wildcard). See **G-15** in `{AGENT_SKILLS_DIR}/prompts/shared/global_guardrails.md`. Using `%` returns zero results.

### GATE 4.2 / `reconcile_schema`: Schema Reconciliation (MANDATORY after DDL execution)
After GATE 4.1, verify each table's **actual deployed schema** from `DESCRIBE TABLE` matches the **expected generated schema** in `table_spec.yaml`, including normalized column names and datatypes. GATE 4.0 already proves that `table_spec.yaml` matches `erd_parsed.yaml`.

The canonical policy identifier is `DEPLOYED_DATATYPE_REPAIR_V1`.

Use only the release-approved deterministic datatype canonicalizer. Canonicalization may normalize case, insignificant whitespace, and aliases explicitly encoded by that canonicalizer; it MUST NOT infer widening compatibility, add a cast, change precision/scale/length, or treat two merely coercible types as equal. Preserve the exact expected and observed type strings as evidence.

For any real deployed datatype mismatch, the Data Layer is the sole repair owner. Automatic repair is permitted exactly once per table only when **all** of these checks pass:

1. the FQN is the exact current-run generated target from `table_spec.yaml`, in the frozen target catalog/schema, with the exact frozen `asset_suffix`;
2. the table is a greenfield accelerator-owned target, not a live/source table, unversioned object, or object discovered by a wildcard;
3. `SELECT COUNT(*)` succeeds and returns exactly zero;
4. the repair uses the pinned DDL compiler and unchanged `table_spec.yaml`; and
5. no earlier datatype repair attempt was made for that table in this run.

The only allowed **post-deployment drift** action is: record the mismatch, drop the exact empty table,
rerun its compiler-generated CREATE statement, rerun `DESCRIBE TABLE`, and require exact canonical
schema equality. `ALTER COLUMN`, casts, `TRY_CAST`, CTAS, overwrite, post-freeze mutation of
`erd_parsed.yaml`/`table_spec.yaml`, and adoption of the observed type are prohibited drift-repair
mechanisms. This does not prohibit the authenticated pre-DDL datatype-resolution phase above.

If ownership is ambiguous, the table is non-empty, row count cannot be proven, the object is source/live/unversioned, the operation lacks permission, or post-repair readback still differs, write failure evidence and HALT with `DATATYPE_MISMATCH_UNSAFE_TO_REPAIR`. Do not delete or coerce data. Missing/unexpected/renamed-column mismatches use the same empty-current-version-table eligibility gate and otherwise halt with `SCHEMA_CONTRACT_ERROR`.

Before any synthetic specification or write, atomically record every decision in `{OUTPUT_FOLDER}/schema_reconciliation.yaml`: current run/target/suffix binding, raw `table_spec.yaml` digest, expected/observed schema fingerprints, policy identifier, expected/observed schemas, canonical comparison, ownership checks, row count, action, attempt count, post-repair readback, unresolved mismatches, and terminal status. Persist both PASS and FAIL outcomes. Only PASS with zero unresolved mismatches creates a `VALID` `reconcile_schema` checkpoint. FAIL halts immediately and must not run later data-quality checks.

Steps 5 and 6 must re-authenticate this artifact and freshly recompute catalog name/type equality before work. The final `data_layer_validation.yaml` records the reconciliation artifact's exact path/raw digest and embeds the same outcome; it does not first create or reinterpret reconciliation evidence.

### GATE 5.1: Domain Value Validation
Every categorical column MUST have domain-specific values (not `val_1`...`val_5`). Run the Domain Value Inference Protocol for any column with generic values.

### GATE 5.2: YAML Type Safety Validation (MANDATORY before writing spec)
All values for VARCHAR/STRING columns MUST be quoted strings in `synthetic_data_spec.yaml`. YAML parses `99213` as integer, creating mixed-type lists.

### GATE 6.1: Row Count Verification
ALL tables must have rows > 0 after synthetic data generation. HALT with `SYNTHETIC_GENERATION_ERROR` if any table is empty.

### GATE 7.1: Data Layer Validation
`data_layer_validation.yaml` must exist with `overall_status: PASS`; its recorded path/raw digest must authenticate the current `schema_reconciliation.yaml` and `schema_assumptions.yaml`; the embedded reconciliation payload must match and have policy `DEPLOYED_DATATYPE_REPAIR_V1`, status `PASS`, and zero unresolved mismatches; the assumptions payload must have policy `GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1`, matching raw/resolved ERD hashes, and zero unresolved datatypes. Every relationship in `semantic_model.yaml` must have exactly one relationship-level validation entry with `validation_status: PASS`. HALT otherwise. `semantic_model.yaml` is relationship intent; this relationship-level result is the authority for downstream use of the deployed relationship.

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
| `AP-DL-9` | Populated Current-Version Schema Drift / `DATATYPE_MISMATCH_UNSAFE_TO_REPAIR` |

Classify the failure from current evidence before loading a runbook section. The index is a routing aid, not authority to bypass the stage owner or retry policy.
