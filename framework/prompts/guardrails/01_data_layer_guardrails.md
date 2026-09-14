# Data Layer Guardrails — Step 2 (Create Data Layer)

> **Also read:** `guardrails/00_global_rules.md` (always applies)

---

## Gates

### GATE 2.1b: Data Type Validation (MANDATORY post-parse)
After parsing ERD, verify every column has a concrete data type. If ANY column has NULL/UNKNOWN type, re-invoke vision model with a targeted crop. HALT if still unresolved after 2 retries.

### GATE 4.1: Table Count Verification
`SHOW TABLES IN {catalog}.{schema} LIKE '*{VERSION_SUFFIX}'` must return expected count. HALT if fewer.
**CRITICAL:** `SHOW TABLES LIKE` uses **glob syntax** (`*` = wildcard), NOT SQL LIKE syntax (`%` = wildcard). See **G-15** in `guardrails/00_global_rules.md`. Using `%` returns zero results.

### GATE 4.2: Schema Reconciliation (MANDATORY after DDL execution)
After GATE 4.1, verify each table's **actual schema** matches the **ERD-parsed schema**. `CREATE TABLE IF NOT EXISTS` is a no-op on tables that already exist with a different schema from a prior interrupted run.

### GATE 5.1: Domain Value Validation
Every categorical column MUST have domain-specific values (not `val_1`...`val_5`). Run the Domain Value Inference Protocol for any column with generic values.

### GATE 5.2: YAML Type Safety Validation (MANDATORY before writing spec)
All values for VARCHAR/STRING columns MUST be quoted strings in `synthetic_data_spec.yaml`. YAML parses `99213` as integer, creating mixed-type lists.

### GATE 6.1: Row Count Verification
ALL tables must have rows > 0 after synthetic data generation. HALT with `SYNTHETIC_GENERATION_ERROR` if any table is empty.

### GATE 7.1: Data Layer Validation
`data_layer_validation.yaml` must exist with `overall_status: PASS`. HALT if FAIL.

---

## Prohibited Actions

1. DO NOT skip ERD parsing by using a cached/assumed schema
2. DO NOT modify column names, types, or constraints from the ERD
3. DO NOT create tables outside the configured catalog.schema
4. DO NOT use `DROP TABLE` on source tables
5. DO NOT proceed past a GATE without verifying the condition
6. DO NOT use generic column names (`col1`, `col2`, `value`)
7. DO NOT skip validation of generated synthetic data
8. DO NOT use `CTAS` (CREATE TABLE AS SELECT) for DDL — use explicit `CREATE TABLE` with column definitions
9. DO NOT invent new tables not in the ERD
10. DO NOT add columns beyond what the ERD specifies
11. DO NOT skip the vision model step if an ERD image is provided
12. DO NOT assume column types from names — always verify with the parsed ERD
13. DO NOT skip schema reconciliation (GATE 4.2)
14. DO NOT use unquoted numeric values for STRING/VARCHAR columns in synthetic_data_spec.yaml
15. DO NOT generate data without calling `validate_domain_cols()` first (DETERMINISM GATE)
16. DO NOT generate data without calling `validate_fk_replacements()` for FK columns (DETERMINISM GATE)
17. DO NOT use generic placeholder values (`val_1` through `val_5`) for categorical columns
18. DO NOT skip the Domain Value Inference Protocol for categorical columns
19. DO NOT write the data generation notebook without the safety utilities from `dbldatagen_notebook.py.template`
20. DO NOT execute data generation without `verify_before_write()` pre-write validation
21. DO NOT skip the `enforce_varchar_limits()` truncation safety net
22. DO NOT use backtick-quoted column names in DDL — write `clm_dtl_billed_amt DECIMAL(27,4)` NOT `` `clm_dtl_billed_amt` DECIMAL(27,4) ``. Backticks in DDL column definitions cause PARSE_SYNTAX_ERROR when a comma is missing between columns, and the error message is misleading because it shows the backtick-quoted name as the problem token
23. DO NOT omit commas between column definitions
25. DO NOT omit `pk_cols` for ANY dimension/lookup table in `synthetic_data_spec.yaml` — this causes join fanout (AP-DL-7)
26. DO NOT proceed past validation check 7.7 (join cardinality) if `after_rows > before_rows` — dimension PK uniqueness must be fixed first
24. DO NOT generate the DDL notebook from scratch — always use `ddl_notebook.py.template` with resolved placeholders. The template is a tested Python notebook; the LLM writing its own version introduces syntax bugs (wrong SHOW TABLES wildcards, SQL/Python format mismatches, missing commas) that the template eliminates — every column definition MUST end with a comma except the LAST column before the closing parenthesis. Missing commas are the #1 cause of DDL PARSE_SYNTAX_ERROR

---

## Prohibited Value Patterns (GATE 5.1 rejects these)

```text
val_1, val_2, val_3, val_4, val_5           — generic placeholders
type_1, type_2, type_3                       — generic type names
category_a, category_b                       — generic categories
status_1, active, inactive (for non-status)  — wrong domain
```

## Prohibited Column Name Patterns

```text
table_name_column_name   — concatenated table+column
original_source_column   — source system prefix
any column not in ERD    — invented columns
```

---

## Anti-Patterns

### AP-DL-1: Vision Model Truncation
Vision model returns partial table (e.g., 5 of 12 columns). GATE 2.1b catches this by checking for NULL types. Fix: re-invoke with targeted crop.

### AP-DL-2: Mixed-Type YAML Lists
`synthetic_data_spec.yaml` has `[99213, "99214", 99215]` — YAML parses unquoted numbers as integers. Fix: quote ALL string column values.

### AP-DL-3: dbldatagen Boolean/Timestamp Bugs
`dbldatagen` raises DATATYPE_MISMATCH for BooleanType with values/weights, and ValueError for TimestampType with date-only begin/end. Fix: `_safe_withColumn` patch in template handles both.

### AP-DL-6: Truncated Data Types from Vision Model (decimal(28)
**Pattern:** `AssertionError: Unbalanced datatype: decimal(28` at DDL execution. The vision model truncates `decimal(28,4)` to `decimal(28` when parsing ERD images.
**Root cause:** Two-layer defense existed but had a gap. Layer 1 (ERD validation utility) catches truncated types before `erd_parsed.yaml` is written, but the LLM sometimes skips calling it or re-derives types from memory. Layer 2 (DDL template Gate 2) only validated the base type name (`DECIMAL` is valid), never checked balanced parentheses.
**Fix:** Added Gate 2b to DDL template: deterministic type-balancing repair that detects unbalanced parentheses, missing decimal scales, and truncated types BEFORE SQL compilation. Repairs `decimal(28` → `decimal(28,2)`, `varchar(255` → `varchar(255)`, etc. This catches the error even if the ERD validation was skipped.

### AP-DL-5: LLM Generates DDL Notebook From Scratch Instead of Using Template
**Pattern:** DDL notebook has syntax bugs (wrong SHOW TABLES wildcard, SQL comment style in Python notebook, missing commas in column defs) that vary between runs.
**Root cause:** The DDL template (`ddl_notebook.py.template`) was originally a SQL notebook format with Python code — structurally unusable. The LLM saw this and generated its own Python notebook from scratch, introducing different bugs each run.
**Fix:** Template rewritten as valid Python `.py` notebook format. Prompt updated to prohibit from-scratch generation (Prohibited Action #24). The LLM produces `table_spec.yaml` and uses the template with placeholders resolved.

### AP-DL-4: SHOW TABLES LIKE Uses Wrong Wildcard
**Pattern:** GATE 4.1 fails with `missing tables [...]` even though CREATE TABLE succeeded.
**Root cause:** `SHOW TABLES LIKE '%{VERSION_SUFFIX}'` uses SQL LIKE wildcard (`%`) but `SHOW TABLES LIKE` expects glob syntax (`*`). The query returns 0 rows.
**Fix:** Use `SHOW TABLES LIKE '*{VERSION_SUFFIX}'` (glob `*`, not SQL `%`). See **G-15** in `guardrails/00_global_rules.md`.

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
**Fix:** In `table_spec.yaml`, use generous column widths. Prefer `STRING` over `CHAR(n)` / `VARCHAR(n)` unless a specific length constraint is required. If the ERD specifies a short CHAR/VARCHAR, widen it to at least 2x the longest expected value (e.g., `CHAR(8)` → `VARCHAR(50)`).
**Repair action:** If this error occurs at runtime:
  1. Identify the column from the error message
  2. Widen the type in `table_spec.yaml` (e.g., `CHAR(8)` → `VARCHAR(50)`)
  3. Re-deploy and re-execute the DDL notebook to recreate the table with the wider type
  4. Re-execute the dbldatagen notebook
