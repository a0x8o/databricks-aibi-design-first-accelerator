# Databricks notebook source
# DBTITLE 1,DDL Compiler — member_claims
# Generated from table_spec.yaml. Edit catalog/schema in accelerator.yaml only.
# This is a SQL notebook — each cell is plain SQL separated by:
# "-- COMMAND ----------"
#
# THREE-PLANE ARCHitecture:
# Generation Plane: LLM produces table_spec.yaml (declarative: tables, columns, types)
# Control Plane: This notebook reads table_spec.yaml, validates via 4-gate model, compiles to SQL
# Execution Plane: spark.sql() executes each CREATE TABLE IF NOT EXISTS statement
# Verification: SHOW TABLES + DESCRIBE TABLE validates schema reconciliation
#
# This template IS the Deterministic Deployment Runtime for DDL.
# The LLM NEVER writes SQL. It writes table_spec.yaml. This notebook compiles it.

spark.sql("CREATE SCHEMA IF NOT EXISTS aw_serverless_stable_catalog.aibi_member_claims")

# COMMAND ----------

# DBTITLE 1,Load Table Spec and Compile to DDL
# =============================================================================
# READ table_spec.yaml (declarative spec from LLM) and compile to CREATE TABLE SQL
# This cell IS the compiler — it translates declarative spec to executable SQL
# =============================================================================

import yaml
import json

# Read table_spec.yaml from output folder
SPEC_PATH = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v10/table_spec.yaml"

# Load and parse the declarative spec
with open(SPEC_PATH) as f:
    spec = yaml.safe_load(f)

CATALOG = spec["catalog"]
SCHEMA = spec["schema"]
VERSION_SUFFIX = spec.get("version_suffix", "")
TABLES = spec["tables"]

# GATE 1: Structural validation
assert TABLES and len(TABLES) > 0, "table_spec.yaml has no tables"
for t in TABLES:
    assert "name" in t, f"Table missing 'name' field"
    assert "columns" in t and len(t["columns"]) > 0, f"Table {t['name']} has no columns"
    for col in t["columns"]:
        assert "name" in col, f"Column missing 'name' in table {t['name']}"
        assert "type" in col, f"Column {col['name']} missing 'type' in table {t['name']}"
print(f"Gate 1 PASSED: {len(TABLES)} tables, all structurally valid")

# GATE 2: Metadata validation (types are valid Spark SQL types)
VALID_TYPES = {"BIGINT", "INT", "INTEGER", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE",
               "DECIMAL", "STRING", "VARCHAR", "CHAR", "BOOLEAN", "DATE",
               "TIMESTAMP", "TIMESTAMP_NTZ", "BINARY"}
for t in TABLES:
    for col in t["columns"]:
        base_type = col["type"].split("(")[0].upper().strip()
        assert base_type in VALID_TYPES, f"Invalid type '{col['type']}' for column {col['name']} in table {t['name']}"
print(f"Gate 2 PASSED: all column types valid")

# ── Gate 2b: Fix truncated data types (deterministic repair) ──
# Vision models frequently truncate types: decimal(28 instead of decimal(28,2).
# This repair runs BEFORE SQL compilation to prevent PARSE_SYNTAX_ERROR.
import re
type_fixes = []
for t in TABLES:
    for col in t["columns"]:
        dtype = col["type"].strip()
        original = dtype
        # Fix 1: Unclosed parenthesis — e.g., decimal(28 or varchar(255
        if "(" in dtype and ")" not in dtype:
            lower = dtype.lower()
            m = re.match(r"(decimal|numeric)\((\d+),?\s*$", lower)
            if m:
                prec = int(m.group(2))
                scale = 2 if prec > 10 else 0
                dtype = f"{m.group(1).upper()}({prec},{scale})"
            else:
                dtype = dtype + ")"
        # Fix 2: Decimal with precision but no scale — e.g., decimal(28)
        m = re.match(r"^(decimal|numeric)\((\d+)\)$", dtype, re.IGNORECASE)
        if m:
            prec = int(m.group(2))
            if prec > 10:
                dtype = f"{m.group(1).upper()}({prec},2)"
        # Fix 3: Mismatched parentheses count
        opens = dtype.count("(")
        closes = dtype.count(")")
        if opens > closes:
            dtype = dtype + ")" * (opens - closes)
        elif closes > opens:
            dtype = dtype.rstrip(")")
            dtype = dtype + ")" * opens
        if dtype != original:
            type_fixes.append(f"  {t['name']}.{col['name']}: '{original}' → '{dtype}'")
            col["type"] = dtype
if type_fixes:
    print(f"Gate 2b: Fixed {len(type_fixes)} truncated data types:")
    for fix in type_fixes:
        print(fix)
else:
    print(f"Gate 2b PASSED: all data types have balanced parentheses")

# Compile declarative spec to CREATE TABLE IF NOT EXISTS statements
DDL_STATEMENTS = []
for table in TABLES:
    table_name = f"{table['name']}{VERSION_SUFFIX}"
    col_defs = []
    for col in table["columns"]:
        nullable = "" if col.get("nullable", True) else " NOT NULL"
        col_defs.append(f"  {col['name']} {col['type']}{nullable}")
    columns_sql = ",\n".join(col_defs)
    comment = table.get("comment", "")
    ddl = f"""CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.{table_name} (
{columns_sql}
) USING DELTA COMMENT '{comment}'"""
    DDL_STATEMENTS.append(ddl)

print(f"Compiled {len(DDL_STATEMENTS)} CREATE TABLE statements from table_spec.yaml")

# COMMAND ----------

# DBTITLE 1,Execute DDL
# =============================================================================
# Execute each compiled DDL statement
# =============================================================================

for stmt in DDL_STATEMENTS:
    spark.sql(stmt)
    table_name = stmt.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
    print(f"Created: {table_name}")

print(f"Executed {len(DDL_STATEMENTS)} CREATE TABLE IF NOT EXISTS statements")

# COMMAND ----------

# DBTITLE 1,Schema Reconciliation (GATE 4.1 + 4.2)
# =============================================================================
# Verify tables exist and schema matches spec
# =============================================================================

# GATE 4.1: Table count verification
# NOTE: SHOW TABLES LIKE uses GLOB syntax (* = wildcard), NOT SQL LIKE (% = wildcard) — see G-15
tables_result = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA} LIKE '*{VERSION_SUFFIX}'")
actual_tables = [row.tableName for row in tables_result.collect()]
expected_tables = [f"{t['name']}{VERSION_SUFFIX}" for t in TABLES]
assert len(actual_tables) >= len(expected_tables), \
    f"GATE 4.1 FAILED: expected {len(expected_tables)} tables, found {len(actual_tables)}"
print(f"Gate 4.1 PASSED: {len(actual_tables)} tables exist")

# GATE 4.2: Schema reconciliation
for table in TABLES:
    full_name = f"{CATALOG}.{SCHEMA}.{table['name']}{VERSION_SUFFIX}"
    desc = spark.sql(f"DESCRIBE TABLE {full_name}").collect()
    actual_cols = [row.col_name for row in desc if not row.col_name.startswith("#")]
    expected_cols = [col["name"] for col in table["columns"]]
    if set(actual_cols) != set(expected_cols):
        print(f"SCHEMA MISMATCH: {table['name']}")
        print(f"  Expected: {expected_cols}")
        print(f"  Actual:   {actual_cols}")
        raise AssertionError(f"Schema mismatch for {table['name']}")
    print(f"  {table['name']}: {len(actual_cols)} columns verified")
print("Gate 4.2 PASSED: all schemas reconciled")

# COMMAND ----------

# DBTITLE 1,Write Manifest with Hash Chain
# =============================================================================
# MANIFEST: Immutable deployment evidence with hash chain
# source_hash (declarative spec) -> generated_hash (compiled DDL) -> readback_hash (deployed state)
# =============================================================================

import json
import hashlib

# Compute source_hash (hash of the declarative spec file)
with open(SPEC_PATH) as f:
    spec_raw = f.read()
SOURCE_HASH = hashlib.sha256(spec_raw.encode()).hexdigest()

# Compute generated_hash (hash of all compiled DDL statements)
combined_ddl = "\n\n---\n\n".join(DDL_STATEMENTS)
GENERATED_HASH = hashlib.sha256(combined_ddl.encode()).hexdigest()

# Compute readback_hash (hash of deployed schema from DESCRIBE TABLE readback)
readback_data = []
for table in TABLES:
    full_name = f"{CATALOG}.{SCHEMA}.{table['name']}{VERSION_SUFFIX}"
    desc = spark.sql(f"DESCRIBE TABLE {full_name}").collect()
    actual_cols = sorted([row.col_name for row in desc if not row.col_name.startswith("#")])
    readback_data.append({"table": table['name'], "columns": json.dumps(actual_cols)})
readback_combined = json.dumps(readback_data, sort_keys=True)
READBACK_HASH = hashlib.sha256(readback_combined.encode()).hexdigest()

# State comparison
STATE_COMPARISON = "match" if len(actual_tables) >= len(expected_tables) else "mismatch"

manifest = {
    "artifact_type": "ddl",
    "domain": "member_claims",
    "version_suffix": VERSION_SUFFIX,
    "validation_source": "api_readback",
    "source_hash": SOURCE_HASH,
    "generated_hash": GENERATED_HASH,
    "readback_hash": READBACK_HASH,
    "state_comparison": STATE_COMPARISON,
    "catalog": CATALOG,
    "schema": SCHEMA,
    "tables": [
        {
            "name": f"{t['name']}{VERSION_SUFFIX}",
            "fqn": f"{CATALOG}.{SCHEMA}.{t['name']}{VERSION_SUFFIX}",
            "column_count": len(t["columns"]),
            "comment": t.get("comment", ""),
        }
        for t in TABLES
    ],
    "total_tables": len(TABLES),
    "total_tables_deployed": len(actual_tables),
}

manifest_path = f"/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v10/ddl_manifest.json"
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)

print(f"Manifest written: {manifest_path}")
print(f"  Source hash:     {SOURCE_HASH[:16]}...")
print(f"  Generated hash:  {GENERATED_HASH[:16]}...")
print(f"  Readback hash:   {READBACK_HASH[:16]}...")
print(f"  State:           {STATE_COMPARISON}")
print(f"  Tables deployed: {len(actual_tables)}/{len(TABLES)}")
print(f"\nDDL deployment complete.")
