# SQL Generation Guardrails

> **Also read:** `{AGENT_SKILLS_DIR}/prompts/shared/global_guardrails.md` (always applies)
>
> These rules are BINDING for ALL SQL generation across the pipeline: DDL notebooks,
> metric view DDL, dataset SQL, Genie example SQL, and validation queries.

## STRICT REQUIREMENTS

1. Generate ONLY Databricks SQL.
2. Do not return Markdown.
3. Do not use ```sql or ``` code fences.
4. Do not include explanations, comments, notes, or prose outside the SQL.
5. Generate the complete multi-statement SQL script in a single response.
6. Separate independent SQL statements using semicolons.
7. Use only Databricks SQL syntax and functions.
8. Do not generate Snowflake, PostgreSQL, SQL Server, Oracle, or BigQuery-specific syntax.

## IDENTIFIER RULES

9. Do NOT automatically wrap table names, schema names, catalog names, column names,
   aliases, functions, expressions, or literals in backticks.

10. Use an unquoted identifier whenever it contains only:
    letters, numbers, and underscores
    and does not otherwise require quoting.

11. Use backticks ONLY when required by Databricks SQL, for example:
    - identifier contains a space
    - identifier contains a hyphen or special character
    - identifier conflicts with syntax requiring delimiting

12. NEVER place backticks around:
    - SQL expressions
    - function calls
    - literals
    - numeric values
    - CASE expressions
    - aggregate expressions
    - fully generated SQL fragments

CORRECT:
    customer_id
    sales.total_amount
    SUM(sales.total_amount) AS total_amount
    `Order Date`
    catalog.schema.table

INCORRECT:
    `SUM(total_amount)`
    `sales.total_amount`
    `catalog.schema.table`
    `CASE WHEN ... END`

## METADATA AUTHORITY RULES

Metadata authority is lifecycle- and concern-specific:

- Before deployment, `table_spec.yaml` defines the expected physical schema only after it has been validated as an exact projection of `erd_parsed.yaml`.
- Before DDL, authenticated `{OUTPUT_FOLDER}/schema_assumptions.yaml` defines any governed datatype-only inference already incorporated into the resolved ERD; SQL stages consume it and never infer locally. After DDL deployment and before synthetic-data SQL, catalog readback using `DESCRIBE TABLE` defines the exact object names, column names, and datatypes that executable SQL may reference. The deployed schema must first reconcile to `table_spec.yaml`, and authenticated `{OUTPUT_FOLDER}/schema_reconciliation.yaml` evidence must show the current run/target/suffix, policy `DEPLOYED_DATATYPE_REPAIR_V1`, `status: PASS`, matching expected/observed schema hashes, and zero unresolved mismatches. A fresh exact name/type readback must still agree with that evidence.
- After `validate_data`, all downstream executable SQL additionally requires matching current-run `data_layer_validation.yaml` evidence with `overall_status: PASS`. Its reconciliation artifact path/hash and embedded reconciliation payload must authenticate the same standalone evidence; final validation never substitutes for the pre-generation reconciliation boundary.
- `semantic_model.yaml` defines intended grains and relationships; it does not prove a deployed join is safe.
- Once `data_layer_validation.yaml` exists, SQL may use only relationships whose matching relationship-level entry has `validation_status: PASS`.
- If applicable authority sources disagree, HALT with the relevant contract error. Do not choose one silently, omit a conflicting field, or invent a reconciliation.
- Never insert `CAST`, `TRY_CAST`, implicit string conversion, or an alternate expression merely to make SQL run against a deployed datatype that conflicts with the expected schema. Preserve both types and route the mismatch to Data Layer GATE 4.2.

## OBJECT RULES

13. Use only catalogs, schemas, tables, views, columns, and functions provided
    in the applicable authoritative metadata above.

14. Never invent a column, table, schema, function, relationship, or datatype in a SQL stage. A
    datatype resolved upstream by the authenticated greenfield-synthetic policy is consumed as
    validated schema intent; it is not recomputed or reinterpreted here.

15. Use fully qualified object names when they are supplied:
    catalog.schema.object

16. Preserve the exact object and column names from the applicable authoritative metadata.

## DATABRICKS RULES

17. Generate syntax compatible with Databricks SQL.
18. Prefer native Databricks SQL constructs.
19. Use named parameter markers (:parameter_name) when runtime values need to be
    supplied rather than concatenating values into SQL.
20. Use IDENTIFIER() only when an object identifier itself must be dynamically
    parameterized.

## MULTI-STATEMENT RULES

21. Treat the requested SQL as one logical script.
22. Validate dependencies between statements before responding.
23. If statement 2 depends on an object created by statement 1, ensure the
    names and schema are identical.
24. Do not repeat CREATE statements unnecessarily.
25. Ensure every statement is syntactically complete.
26. End statements with semicolons.

## DDL-SPECIFIC RULES

27. Every column definition MUST end with a comma except the LAST column before
    the closing parenthesis. Missing commas are the #1 cause of PARSE_SYNTAX_ERROR.
28. Column definitions follow this pattern:
    column_name DATATYPE,
    column_name DATATYPE,
    last_column_name DATATYPE
29. Do NOT wrap column names in backticks in CREATE TABLE statements.
    Write: clm_dtl_billed_amt DECIMAL(27,4)
    NOT: `clm_dtl_billed_amt` DECIMAL(27,4)
30. Do NOT wrap table names in backticks in CREATE TABLE statements.
    Write: catalog.schema.table_name
    NOT: `catalog`.`schema`.`table_name`

## FINAL SELF-CHECK

Before returning the SQL, silently verify:

- Is every statement valid Databricks SQL?
- Are all parentheses balanced?
- Are all quotes balanced?
- Are all CASE expressions closed with END?
- Are aliases syntactically valid?
- Are GROUP BY expressions consistent with SELECT?
- Are all referenced columns present in the applicable authoritative metadata?
- Does every referenced relationship have a relationship-level `PASS` result when `data_layer_validation.yaml` exists?
- Are catalog.schema.table references valid?
- Have backticks been used only where necessary?
- Are there any Markdown fences?
- Is any SQL from another SQL dialect present?
- Are dependencies between statements consistent?
- Does every column definition end with a comma (except the last)?

If any issue is detected, correct it before producing the final response.

## OUTPUT CONTRACT

Return only the executable SQL script.
Return nothing before or after the SQL.
