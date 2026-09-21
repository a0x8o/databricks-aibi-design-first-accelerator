# Data Layer — Failure Runbook

> **FAILURE-ONLY — DO NOT LOAD ON A SUCCESSFUL PATH.** Authenticate this file's exact frozen path/version/raw SHA-256 after the stage has emitted a classified error. Load only the matching section needed for diagnosis. A runbook never changes authority, weakens a gate, or authorizes an unclassified retry. Record the selected section and digest in the failure evidence.

## Anti-Patterns

### AP-DL-1: Vision Model Truncation
Vision model returns partial table (e.g., 5 of 12 columns). GATE 2.1b catches this by checking for NULL types. Fix: re-invoke with targeted crop.

### AP-DL-2: Mixed-Type YAML Lists
`synthetic_data_spec.yaml` has `[99213, "99214", 99215]` — YAML parses unquoted numbers as integers. Fix: quote ALL string column values.

### AP-DL-3: dbldatagen Boolean/Timestamp Bugs
`dbldatagen` raises DATATYPE_MISMATCH for BooleanType with values/weights, and ValueError for TimestampType with date-only begin/end. Fix: `_safe_withColumn` patch in template handles both.

### AP-DL-6: Truncated Data Types from Vision Model (decimal(28)
**Pattern:** The vision model returns an incomplete value such as `decimal(28`, `decimal(28)`, `decimal(28,)`, or `varchar(`.
**Root cause:** Precision, scale, or length was not legible or the model truncated the ERD text.
**Fix:** Never close the parenthesis or supply a default scale/length. The strict ERD utility and DDL compiler reject incomplete parameterized types. Re-invoke the vision model with a targeted high-resolution crop and preserve the authoritative value. If it remains unresolved after the allowed retries, HALT with `ERD_EXTRACTION_ERROR`.

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
