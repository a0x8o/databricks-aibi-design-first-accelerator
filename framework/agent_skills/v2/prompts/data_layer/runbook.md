# Data Layer — Failure Runbook

> **FAILURE-ONLY — DO NOT LOAD ON A SUCCESSFUL PATH.** Authenticate this file's exact frozen path/version/raw SHA-256 after the stage has emitted a classified error. Load only the matching section needed for diagnosis. A runbook never changes authority, weakens a gate, or authorizes an unclassified retry. Record the selected section and digest in the failure evidence.

## Anti-Patterns

### AP-DL-1: Vision Model Truncation
Vision model returns a partial table (for example, 5 of 12 columns). Re-invoke with a targeted crop.
Missing table/column identity is structural loss and MUST NOT be synthesized by the datatype resolver;
halt if the complete inventory cannot be recovered.

### AP-DL-2: Mixed-Type YAML Lists
`synthetic_data_spec.yaml` has `[99213, "99214", 99215]` — YAML parses unquoted numbers as integers. Fix: quote ALL string column values.

### AP-DL-3: dbldatagen Boolean/Timestamp Bugs
`dbldatagen` raises DATATYPE_MISMATCH for BooleanType with values/weights, and ValueError for TimestampType with date-only begin/end. Fix: `_safe_withColumn` patch in template handles both.

### AP-DL-6: Truncated Data Types from Vision Model (decimal(28)
**Pattern:** The vision model returns an incomplete value such as `decimal(28`, `decimal(28,)`, or `varchar(`. Note that `decimal` and `decimal(28)` are valid Databricks syntax and canonicalize to `decimal(10,0)` and `decimal(28,0)`.
**Root cause:** Precision, scale, or length was not legible, the model truncated the ERD text, or a new output/asset version reused an older invalid `erd_parsed.yaml` based only on matching image hash and non-empty tables.
**Fix:** Reject an invalid cached candidate as a cache miss, invalidate `parse_erd` and dependents,
and perform up to two targeted high-resolution reparses. If the defect remains datatype-only and the
run is ERD-driven with `greenfield.enabled: true` and `greenfield.synthetic_data: true`, invoke the
attested `GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1` resolver. It preserves visible components,
prefers strict-majority semantic peers, applies release-pinned scale policies (monetary 4, rate/ratio
6, measurement 4, count 0, generic decimal 18), and uses `STRING` when character width or type
family cannot be recovered safely. Atomically persist `schema_assumptions.yaml`, the resolved ERD,
and raw/resolved hashes; rerun strict validation and GATE 4.0. This is an accelerator policy, not a
claimed Databricks default. HALT only for structural loss, ineligible source/live or
synthetic-disabled scope, broken provenance, or a non-convergent resolver.

### AP-DL-5: LLM Generates DDL Notebook From Scratch Instead of Using Template
**Pattern:** DDL notebook has syntax bugs (wrong SHOW TABLES wildcard, SQL comment style in Python notebook, missing commas in column defs) that vary between runs.
**Root cause:** The DDL template (`ddl_notebook.py.template`) was originally a SQL notebook format with Python code — structurally unusable. The LLM saw this and generated its own Python notebook from scratch, introducing different bugs each run.
**Fix:** Template rewritten as valid Python `.py` notebook format. Prompt updated to prohibit from-scratch generation (Prohibited Action #24). The LLM produces `table_spec.yaml` and uses the template with placeholders resolved.

### AP-DL-4: SHOW TABLES LIKE Uses Wrong Wildcard
**Pattern:** GATE 4.1 fails with `missing tables [...]` even though CREATE TABLE succeeded.
**Root cause:** `SHOW TABLES LIKE '%{ASSET_SUFFIX}'` uses SQL LIKE wildcard (`%`) but `SHOW TABLES LIKE` expects glob syntax (`*`). The query returns 0 rows.
**Fix:** Use `SHOW TABLES LIKE '*{ASSET_SUFFIX}'` (glob `*`, not SQL `%`) with the exact frozen asset suffix. See **G-15** in `{AGENT_SKILLS_DIR}/prompts/shared/global_guardrails.md`.

### AP-DL-7: Join Fanout From Missing pk_cols in Dimension Tables
**Pattern:** Validation check 7.7 fails: `Join fanout detected: 9,000 detail rows joined to 1,800,000 rows` (200x multiplication).
**Root cause:** The LLM omitted `pk_cols` for a dimension/lookup table in `synthetic_data_spec.yaml`. Without `pk_cols`, `generate_table()` does NOT enforce PK uniqueness (lines 453-468 of the template are skipped). The dimension table ends up with duplicate values in the join key. When the fact table's FK joins to the non-unique dimension PK, every FK value matches multiple dimension rows → cartesian-like fanout.
**Detection:** Check 7.7 in the validation matrix catches this:
```sql
SELECT '{join_name}' j,
  (SELECT COUNT(*) FROM {child}) before_rows,
  (SELECT COUNT(*) FROM {child} f JOIN {parent} d ON f.{fk} = d.{pk}) after_rows
```
If `after_rows > before_rows`, fanout is occurring.
**Fix:** Every table in `synthetic_data_spec.yaml` MUST have `pk_cols` specified — especially dimension/lookup tables. The primary key column(s) listed in the ERD MUST appear in `pk_cols` so `generate_table()` enforces uniqueness.
**Repair action:** If fanout is detected at validation time:
1. Identify the parent (dimension) table in the failing join
2. Verify its `pk_cols` were specified in the spec
3. If missing: add `pk_cols`, regenerate that table ONLY, re-validate
4. If present but still failing: the PK column has collisions from `dbldatagen` — increase `uniqueValues` or reduce row count

**CRITICAL**: Do NOT mark `overall_status: PASS` if ANY join produces fanout. Fanout poisons ALL downstream metric views and dashboards.

### AP-DL-8: DELTA_EXCEED_CHAR_VARCHAR_LIMIT from dbldatagen Generated Values
**Pattern:** `[DELTA_EXCEED_CHAR_VARCHAR_LIMIT] Value "FME-00000001" exceeds char/varchar type length limitation` at data write.
**Root cause:** The `table_spec.yaml` defines a column as `CHAR(n)` or `VARCHAR(n)` with a length too short for the values dbldatagen generates. The `generate_table()` function in the template applies `enforce_varchar_limits()` post-build (line ~420), but only if the column type metadata is correctly propagated. Common triggers:
  - ERD has `CHAR(8)` but generated values like "FME-00000001" are 12 chars
  - `template=` patterns produce variable-length strings that exceed the declared max
  - FK replacement inserts parent key values that are longer than the child column allows
**Authority handling:** Record the declared width, failing value, and affected relationship. Do not mutate `table_spec.yaml` to make generation pass. HALT with `SCHEMA_CONTRACT_ERROR` and repair the generated value/domain logic. GATE 4.2's deployed-schema repair policy does not apply because the deployed datatype already matches the intended datatype; this is a data-value generation defect, not deployed schema drift.

### AP-DL-9: Populated Current-Version Schema Drift
**Pattern:** `schema_reconciliation.yaml` reports `DATATYPE_MISMATCH_UNSAFE_TO_REPAIR`, the expected and observed precision/scale differ, and `row_count_before > 0`.
**Root cause:** `CREATE TABLE IF NOT EXISTS` reused a populated table created under an older schema, or an earlier executor bypassed the `reconcile_schema` boundary. Compare the table's Delta history with the current run phase timestamps and authenticate the frozen template/helper hashes to distinguish them.
**Required action:** Preserve the table and HALT with no mutation. Do not `ALTER`, cast, overwrite, change `table_spec.yaml`, or mark the gate PASS. For disposable synthetic assets, use a fresh asset version after correcting the runtime, or perform explicitly approved exact-inventory cleanup outside the automatic pipeline. For retained data, use an operator-owned migration outside this accelerator.
**Prevention:** `generate_ddl → reconcile_schema → generate_synthetic_data` is mandatory. The dbldatagen runtime authenticates the persisted PASS artifact and a fresh name/type readback before its first append.

# Validated Learnings (from production runs)

These are confirmed failures from actual runs. Treat as mandatory guardrails.

**1. `monotonically_increasing_id()` is NOT sequential on serverless**

On 200-partition serverless, 3000 rows produce ~195 distinct values with modulo. ALWAYS use `F.row_number().over(Window.orderBy(F.monotonically_increasing_id()))` for sequential/uniform distribution.

**2. Large `F.array([F.lit(v) for v in list])` fails with EXECUTION_ERROR**

When parent PK lists exceed ~500 values, the literal array expression overflows. Use broadcast join pattern instead:

```python
parent_df = spark.table(parent).select("pk_col").distinct()
df = df.join(parent_df.withColumn("_rn", F.row_number().over(w)), ...)
```

**3. `DecimalType(p,s)` bounds generators**

`DecimalType(5,2)` max is 999.99. Bound `minValue`/`maxValue` accordingly or generation overflows.

**4. Generic `val_xx` values are the #1 data quality failure**

Prior runs produced `val_1`...`val_5` for ALL categorical columns because the LLM skipped domain inference. GATE 5.1 now catches this BEFORE data generation executes. The fix is the Domain Value Inference Protocol in §5.3.

**5. dbldatagen `template=r"PREFIX\\d{N}"` is literal on Spark Connect**

Backslash-digit sequences don't generate random digits on serverless. Use native Spark expressions for all PK/FK generation.

---


### GENERATED_IDENTIFIER_ERROR: Invalid or colliding generated table name

An object name such as `dim.provider_v14` contains a period inside one target
component. Quoting does not legalize it. Follow this step's DL-G1 and validation
GATE 2.1a: inspect the source label and its mapping, then return the defect to the
parse owner through the master. Do not patch SQL or rename live/source objects.
Use preflight mutation evidence to determine whether regeneration is safe; existing
partial mutations require the master's recovery decision, not a blind notebook retry.

### SYNTHETIC_SPEC_ERROR / KeyError parent_pk

The generated spec does not satisfy the notebook's executable interface. Apply
DL-G2 and GATE 5.0 to the whole spec. Correct the producer's artifact using actual
schema/relationship evidence, not aliases or guessed parent keys. For an older
notebook that failed after starting writes, inspect every target's row count before
any retry; append execution cannot safely resume over partially populated targets.

### Multiple data-layer phases displayed as running

Apply DL-G3 and shared G-19. Check notebook run status and persisted checkpoints;
a UI label alone does not establish concurrent execution or completion. Missing
completion events remain unverified; a halted active phase must not remain running.


### TEMPLATE_BINDING_ERROR / Missing template fields (including ASSET_SUFFIX)

Follow DL-G4 and shared G-16. Inspect the frozen template's placeholder names rather
than reusing another stage's map. Bind exact target coordinates from the authenticated
handoff. The failed deployment cannot authorize Metric Views; inspect whether a later
successful retry and all producer gates exist before interpreting historical UI logs.

For `ASSET_SUFFIX`, distinguish an omitted tool argument from a bad handoff. Read
current `step_handoff.asset_suffix` and `run_context.version.asset_suffix`; both
must be nonempty and identical. Never use optional `short_name_suffix` or reconstruct
the value from a folder. If valid, the master may admit a retry of the failed owning
phase using GATE TEMPLATE-BINDING's complete map. If absent or inconsistent, return
`HANDOFF_AUTHORITY_ERROR` to the master without importing or executing a notebook.
The failed call imported nothing; an older notebook at the output path is not proof
of a successful current deployment. Preserve existing reconciliation and empty-target
checks before any synthetic execution on retry.


### SCHEMA_CONTRACT_ERROR / Empty table-spec datatype across columns

Read the actual current-run ERD and table-spec artifacts. Distinguish missing
`type` from a populated but wrong field such as `datatype`. Under DL-G5, validated
ERD `observed.columns[].datatype` projects to table-spec `columns[].type`. A widespread
empty-type report does not by itself mean the ERD image lacks datatypes.

On master-admitted retry, run GATE 4.0's bounded projection from the authenticated
resolved ERD, persist only a passing candidate with replacement evidence, and validate
readback before deployment. Do not reparse a valid ERD, invent datatypes, disable the
gate, or blindly rerun an earlier script that might have performed other mutations.


### Scalar parent reference rejected as a composite primary key

Under DL-G2, distinguish the semantic primary key from the synthetic runtime's
legacy `pk_columns` list of independently unique generation columns. Multiple entries
in that list do not prove a composite relationship. Authenticate the exact parent
reference from the semantic relationship and reconciled schema, retain its column,
and ensure it has an independent unique-value strategy. Do not switch it to the
surrogate primary key or remove valid alternate-key generation. Genuine tuple
relationships still require a tuple-aware generator and cannot use this scalar spec.

Use the corrected release template only after frozen path/digest admission. Never
bypass the hash for an existing run. Authenticate prior execution and empty-target
checks before any master-admitted retry; runtime key-domain failures can occur after
parent tables have been written and must not trigger a blind append rerun.
