# SQL Generation Guardrails

> **Also read:** `guardrails/00_global_rules.md` (always applies)
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

## OBJECT RULES

13. Use only catalogs, schemas, tables, views, columns, and functions provided
    in the supplied metadata.

14. Never invent a column, table, schema, function, relationship, or datatype.

15. Use fully qualified object names when they are supplied:
    catalog.schema.object

16. Preserve the exact object and column names from the metadata.

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
- Are all referenced columns present in the supplied metadata?
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