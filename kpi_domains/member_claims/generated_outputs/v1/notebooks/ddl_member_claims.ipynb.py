# Databricks notebook source
# DBTITLE 1,Install dependencies
%pip install dbldatagen pyyaml --quiet

# COMMAND ----------

# DBTITLE 1,Restart Python
dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Import dbldatagen
import dbldatagen

# COMMAND ----------

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
import yaml
import json
import re

SPEC_PATH = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v1/table_spec.yaml"
with open(SPEC_PATH) as f:
    spec = yaml.safe_load(f)
CATALOG = spec["catalog"]
SCHEMA = spec["schema"]
VERSION_SUFFIX = spec.get("version_suffix", "")
TABLES = spec["tables"]
assert TABLES and len(TABLES) > 0, "table_spec.yaml has no tables"
VALID_TYPES = {"BIGINT", "INT", "INTEGER", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE", "DECIMAL", "STRING", "VARCHAR", "CHAR", "BOOLEAN", "DATE", "TIMESTAMP", "TIMESTAMP_NTZ", "BINARY"}
for t in TABLES:
    assert "name" in t and "columns" in t and len(t["columns"]) > 0
    for col in t["columns"]:
        assert "name" in col and "type" in col
        base_type = col["type"].split("(")[0].upper().strip()
        assert base_type in VALID_TYPES, f"Invalid type '{col['type']}' for column {col['name']} in table {t['name']}"
        assert col["type"].count("(") == col["type"].count(")"), f"Unbalanced datatype: {col['type']}"
print(f"Gates 1/2/2b PASSED: {len(TABLES)} tables structurally valid")
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
for stmt in DDL_STATEMENTS:
    spark.sql(stmt)
    table_name = stmt.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
    print(f"Created: {table_name}")
print(f"Executed {len(DDL_STATEMENTS)} CREATE TABLE IF NOT EXISTS statements")

# COMMAND ----------

# DBTITLE 1,Schema Reconciliation (GATE 4.1 + 4.2)
tables_result = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA} LIKE '*{VERSION_SUFFIX}'")
actual_tables = [row.tableName for row in tables_result.collect()]
expected_tables = [f"{t['name']}{VERSION_SUFFIX}" for t in TABLES]
missing = [t for t in expected_tables if t not in actual_tables]
assert not missing, f"GATE 4.1 FAILED missing tables: {missing}"
print(f"Gate 4.1 PASSED: {len(expected_tables)} expected tables exist")
for table in TABLES:
    full_name = f"{CATALOG}.{SCHEMA}.{table['name']}{VERSION_SUFFIX}"
    desc = spark.sql(f"DESCRIBE TABLE {full_name}").collect()
    actual_cols = [row.col_name for row in desc if row.col_name and not row.col_name.startswith("#")]
    expected_cols = [col["name"] for col in table["columns"]]
    if set(actual_cols) != set(expected_cols):
        row_count = spark.sql(f"SELECT COUNT(*) AS c FROM {full_name}").collect()[0].c
        if row_count == 0:
            spark.sql(f"DROP TABLE {full_name}")
            stmt = DDL_STATEMENTS[[t['name'] for t in TABLES].index(table)]
            spark.sql(stmt)
            desc = spark.sql(f"DESCRIBE TABLE {full_name}").collect()
            actual_cols = [row.col_name for row in desc if row.col_name and not row.col_name.startswith("#")]
        assert set(actual_cols) == set(expected_cols), f"Schema mismatch for {table['name']}"
    print(f"  {table['name']}: {len(actual_cols)} columns verified")
print("Gate 4.2 PASSED: all schemas reconciled")

# COMMAND ----------

# DBTITLE 1,Write Manifest with Hash Chain
import json
import hashlib
with open(SPEC_PATH) as f:
    spec_raw = f.read()
SOURCE_HASH = hashlib.sha256(spec_raw.encode()).hexdigest()
combined_ddl = "\n\n---\n\n".join(DDL_STATEMENTS)
GENERATED_HASH = hashlib.sha256(combined_ddl.encode()).hexdigest()
readback_data = []
for table in TABLES:
    full_name = f"{CATALOG}.{SCHEMA}.{table['name']}{VERSION_SUFFIX}"
    desc = spark.sql(f"DESCRIBE TABLE {full_name}").collect()
    actual_cols = sorted([row.col_name for row in desc if row.col_name and not row.col_name.startswith("#")])
    readback_data.append({"table": table['name'], "columns": json.dumps(actual_cols)})
READBACK_HASH = hashlib.sha256(json.dumps(readback_data, sort_keys=True).encode()).hexdigest()
manifest = {"artifact_type":"ddl","domain":"member_claims","version_suffix":VERSION_SUFFIX,"validation_source":"api_readback","source_hash":SOURCE_HASH,"generated_hash":GENERATED_HASH,"readback_hash":READBACK_HASH,"state_comparison":"match","catalog":CATALOG,"schema":SCHEMA,"tables":[{"name":f"{t['name']}{VERSION_SUFFIX}","fqn":f"{CATALOG}.{SCHEMA}.{t['name']}{VERSION_SUFFIX}","column_count":len(t["columns"]),"comment":t.get("comment","")} for t in TABLES],"total_tables":len(TABLES),"total_tables_deployed":len(expected_tables)}
manifest_path = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v1/ddl_manifest.json"
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest written: {manifest_path}")
print("DDL deployment complete.")
