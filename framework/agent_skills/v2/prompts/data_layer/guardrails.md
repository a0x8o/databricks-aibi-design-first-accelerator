# Data Layer — Guardrails

> **Always loaded.** This file contains normative prohibitions and hard stops for `create_data_layer`. Historical incidents and fixes live only in the failure runbook.

## Shared rules

Use `../shared/global_guardrails.md` G-0 for prompt/runtime ownership, G-8 for
workspace transport, G-12 for bootstrap acknowledgement, and G-19 for checkpoint
and progress integrity. Data-layer-specific policies remain in this file below.

## Prohibited Actions

1. DO NOT skip ERD parsing by using a cached/assumed schema
2. DO NOT modify column names or constraints from the ERD; datatype-only resolution is permitted solely by `GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1` in its eligible scope and must be disclosed in `schema_assumptions.yaml`
3. DO NOT create tables outside the configured catalog.schema
4. DO NOT use `DROP TABLE` on source tables
5. DO NOT proceed past a GATE without verifying the condition
6. DO NOT use generic column names (`col1`, `col2`, `value`)
7. DO NOT skip validation of generated synthetic data
8. DO NOT use `CTAS` (CREATE TABLE AS SELECT) for DDL — use explicit `CREATE TABLE` with column definitions
9. DO NOT invent new tables not in the ERD
10. DO NOT add columns beyond what the ERD specifies
11. DO NOT skip the vision model step if an ERD image is provided
12. DO NOT assume column types from names ad hoc — exact ERD evidence and semantic-peer evidence take precedence; column-name semantics may be used only by the pinned greenfield-synthetic resolver and must be labeled `INFERRED_POLICY`
13. DO NOT skip schema reconciliation (GATE 4.2)
14. DO NOT use unquoted numeric values for STRING/VARCHAR columns in synthetic_data_spec.yaml
15. DO NOT generate data without calling `validate_domain_cols()` first (DETERMINISM GATE)
16. DO NOT generate data without calling `validate_fk_replacements()` for FK columns (DETERMINISM GATE)
17. DO NOT use generic placeholder values (`val_1` through `val_5`) for categorical columns
18. DO NOT skip the Domain Value Inference Protocol for categorical columns
19. DO NOT write the data generation notebook without the safety utilities from `dbldatagen_notebook.py.template`
20. DO NOT execute data generation without `verify_before_write()` pre-write validation
21. DO NOT skip the `enforce_varchar_limits()` truncation safety net
22. Use the pinned DDL compiler for identifier quoting and comma placement. Quoting cannot legalize an invalid Unity Catalog object name; apply DL-G1 below.
23. DO NOT omit commas between column definitions
25. DO NOT omit `pk_columns` for ANY dimension/lookup table in `synthetic_data_spec.yaml` — this causes join fanout (AP-DL-7)
26. DO NOT proceed past validation check 7.7 (join cardinality) if `after_rows > before_rows` — dimension PK uniqueness must be fixed first
24. DO NOT generate the DDL notebook from scratch — always use `ddl_notebook.py.template` with resolved placeholders. The template is a tested Python notebook; the LLM writing its own version introduces syntax bugs (wrong SHOW TABLES wildcards, SQL/Python format mismatches, missing commas) that the template eliminates — every column definition MUST end with a comma except the LAST column before the closing parenthesis. Missing commas are the #1 cause of DDL PARSE_SYNTAX_ERROR
27. DO NOT silently accept schema drift after DDL — `DESCRIBE TABLE` must match `table_spec.yaml`; never skip an expected column or generate an unexpected deployed column with defaults
28. DO NOT treat a relationship in `semantic_model.yaml` as validated — downstream use requires its matching relationship-level `data_layer_validation.yaml` entry to be `PASS`
29. DO NOT recompute catalog, schema, asset/version suffixes, output folder, or paths from `accelerator.yaml`; use the current-run resolved configuration/handoff and halt on conflict
30. DO NOT make unrecorded datatype repairs. Perform up to two authoritative reparses first. Only an ERD-driven target with `greenfield.enabled: true` and `greenfield.synthetic_data: true` may use `GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1`; source/live schemas, retained data, and structural loss remain hard stops
31. DO NOT generate or insert synthetic data unless the current-run `reconcile_schema` phase is VALID, `{OUTPUT_FOLDER}/schema_reconciliation.yaml` authenticates with `status: PASS` and zero unresolved mismatches, and a fresh exact name/type readback still matches `table_spec.yaml`
32. DO NOT treat final `data_layer_validation.yaml` as a substitute for the pre-generation reconciliation artifact; final validation must authenticate and preserve the same reconciliation evidence
33. DO NOT accept or copy a prior-version `erd_parsed.yaml` using only image-hash equality and non-empty tables. Revalidate it with the current digest-attested helper. If legacy assumptions evidence is absent, create a new current-run `schema_assumptions.yaml` from the validated/resolved in-memory candidate rather than treating the missing generated output as input-authority failure. Existing current-contract assumptions, when present, must authenticate
34. DO NOT deploy or execute the DDL notebook until programmatic GATE 4.0 authenticates `schema_assumptions.yaml` and proves that `table_spec.yaml` is an exact projection of the resolved `erd_parsed.yaml`
35. DO NOT treat governed pre-DDL resolution as permission to widen, cast, or adopt a catalog datatype; catalog state is never inference evidence. Record policy decisions in `schema_assumptions.yaml`, derived type replacements in `ddl_preflight.yaml`, and rerun exact projection validation
36. DO NOT retry a failed DDL notebook unless authenticated `ddl_preflight.yaml` proves the failure occurred before any catalog mutation and selects the exact bounded ERD-reparse or table-spec-regeneration route

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


## DL-G1: Source labels and generated target identifiers

For greenfield generated targets, `tables[].name` is one unqualified physical
table-name component, not a source-schema-qualified label or SQL FQN. Catalog and
schema come separately from the frozen handoff. Unity Catalog forbids periods
inside an object name, even when quoted.

The agent interprets source labels using the ERD and domain context, preserves the
original label as `source_name`, and resolves a legal target name before completing
the parse. Preserve namespace information in provenance; choose a collision-free,
descriptive unqualified name. Do not blindly strip prefixes or globally replace
punctuation. For example, `dim_provider` is a possible mapping for `dim.provider`,
not a mandated name or domain default. Record source→target mappings and rationale
in the parse artifact. Ask for clarification if evidence cannot distinguish entities.

Apply this mapping to every relationship endpoint and downstream semantic, table,
synthetic-data, and KPI reference, before datatype-assumption hashes and checkpoints
are created. `table_spec.yaml` remains an exact projection of the resolved parse.
Never rename only inside DDL or silently repair frozen inputs. Existing live-source
objects remain unchanged; represent their catalog/schema/table components separately.

Reject period, space, slash, ASCII control characters, DEL, and embedded backticks
in generated table-name components. Validate final names including the asset suffix
against the 255-character limit and detect collisions ignoring case. Execute the
pinned DDL template's pure `validate_uc_target_names(catalog, schema, tables,
asset_suffix)` before deployment. The notebook repeats it before catalog mutation.
`GENERATED_IDENTIFIER_ERROR` belongs to parse/name resolution, not datatype repair.
Return it to that owning phase; invalidate dependent fingerprints and regenerate
the consistent contracts before retrying. If prior catalog mutations or frozen
contracts prevent safe regeneration, use a fresh version rather than renaming
deployed objects or substituting names inside executable SQL.

## DL-G2: Executable synthetic-data specification

The following column-level strategy notes are planning metadata. They are **not**
the executable notebook input schema. Write `synthetic_data_spec.yaml` using this
exact table-level structure (logical table names without the asset suffix):

```yaml
tables:
  - name: dim_member
    rows: 100
    pk_columns: [member_id]
    date_range: ["2020-01-01", "2024-12-31"]
    domain_columns:
      status:
        values: ["Active", "Inactive"]
        weights: [0.8, 0.2]
    fk_columns: {}
  - name: fact_claim
    rows: 500
    pk_columns: [claim_id]
    domain_columns: {}
    fk_columns:
      member_id:
        parent_table: dim_member
        parent_pk: member_id
```

Use the actual authenticated names, rows, domains, and relationships for this run.
`parent_pk` is mandatory; do not substitute `parent_column`, `referenced_column`, or
other aliases, and never infer a missing key from the child column's name. Both
columns must match the reconciled deployed schema. Parents precede children. The
current sampler supports single-column parent primary keys; composite keys and
cycles must halt with an explicit unsupported-generation diagnostic.

Before notebook deployment, run the exact frozen template's
`validate_synthetic_spec(spec, table_spec_tables)` against the **entire** spec using
the attested template bytes (extract that pure function with Python AST after
excluding notebook `%` magic lines).
The notebook repeats this check before the first data write. A preflight failure
returns to this spec-generation phase; fix the owned spec before execution.
Never blindly retry an append notebook after a partial write: inspect target row
counts and use a fresh version when existing rows prevent safe execution.

## DL-G3: Data-layer phase ordering

The phases are sequential: `generate_ddl` → `reconcile_schema` →
`generate_synthetic_data`. Wait for each notebook's terminal success, complete its
readback and workspace checkpoint commit, and emit its completed event before
starting the next phase. Never submit these notebooks concurrently. A missing
completion event is not proof of success and must not be bypassed.

Apply shared G-19 for checkpoint and progress-event integrity. On premature
synthetic-data admission, return control to the master and authenticate the DDL and
reconciliation checkpoints before any generation. UI labels alone never permit reuse.
