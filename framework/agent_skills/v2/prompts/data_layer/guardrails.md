# Data Layer — Guardrails

> **Always loaded.** This file contains normative prohibitions and hard stops for `create_data_layer`. Historical incidents and fixes live only in the failure runbook.

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
27. DO NOT silently accept schema drift after DDL — `DESCRIBE TABLE` must match `table_spec.yaml`; never skip an expected column or generate an unexpected deployed column with defaults
28. DO NOT treat a relationship in `semantic_model.yaml` as validated — downstream use requires its matching relationship-level `data_layer_validation.yaml` entry to be `PASS`
29. DO NOT recompute catalog, schema, asset/version suffixes, output folder, or paths from `accelerator.yaml`; use the current-run resolved configuration/handoff and halt on conflict

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
