# Databricks notebook source
# DBTITLE 1,Step 1: Delete Versioned Genie Spaces
"""Delete all versioned Genie spaces for member_claims."""
import requests
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
host = w.config.host.rstrip('/')
headers = {"Authorization": f"Bearer {w.config.token}"}

# Get versioned Genie spaces
resp = requests.get(f"{host}/api/2.0/genie/spaces", headers=headers)
spaces = resp.json().get('spaces', [])
versioned = [s for s in spaces if '_v' in s.get('title', '') and 'member_claims' in s.get('title', '')]

print(f"Found {len(versioned)} versioned Genie spaces to delete:")
for s in versioned:
    print(f"  {s['title']} (id={s['space_id']})")

# Delete each one
deleted = 0
for s in versioned:
    try:
        del_resp = requests.delete(f"{host}/api/2.0/genie/spaces/{s['space_id']}", headers=headers)
        if del_resp.ok or del_resp.status_code == 404:
            print(f"  ✓ Deleted: {s['title']}")
            deleted += 1
        else:
            print(f"  ✗ {s['title']}: {del_resp.status_code}")
    except Exception as e:
        print(f"  ✗ {s['title']}: {e}")

print(f"\nDeleted {deleted}/{len(versioned)} Genie spaces")

# COMMAND ----------

# DBTITLE 1,Step 2: Purge Lakebase Pipeline State
"""Purge ALL pipeline run records from Lakebase (runs, steps, phases, events, step_logs, tool_calls)."""
import psycopg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Get Lakebase endpoint
project_id = "aibi-studio"
branch_id = "production"
endpoint_name = f"projects/{project_id}/branches/{branch_id}/endpoints/primary"

ep = w.postgres.get_endpoint(name=endpoint_name)
host = ep.status.hosts.host
print(f"Endpoint: {host} (state: {ep.status.current_state})")

# Auth
me = w.current_user.me()
username = getattr(me, 'application_id', None) or me.user_name
token = w.postgres.generate_database_credential(endpoint=endpoint_name).token

# Connect
conn = psycopg.connect(host=host, dbname="databricks_postgres",
                        user=username, password=token, sslmode="require")
cur = conn.cursor()

# Delete in FK order (children first)
tables = ["tool_calls", "events", "step_logs", "phases", "steps", "runs"]
for t in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM public.{t}")
        before = cur.fetchone()[0]
        cur.execute(f"DELETE FROM public.{t}")
        conn.commit()
        print(f"  ✓ {t}: {before} rows purged")
    except Exception as e:
        print(f"  ✗ {t}: {e}")
        conn.rollback()

conn.close()
print("\nLakebase state purged. Next pipeline run starts fresh.")

# COMMAND ----------

# DBTITLE 1,Step 3: Verify Clean State
"""Verify everything is clean."""
import os

print("=== UC Tables ===")
remaining = spark.sql("SHOW TABLES IN aw_serverless_stable_catalog.aibi_member_claims LIKE '*_v*'").count()
print(f"  Versioned tables remaining: {remaining}")

print("\n=== Output Folders ===")
base = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs"
if os.path.exists(base):
    contents = os.listdir(base)
    print(f"  Contents of generated_outputs/: {contents or '(empty)'}")
else:
    print("  generated_outputs/ directory does not exist")

print("\n=== Version Registry ===")
registry = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/version_registry.yaml"
if os.path.exists(registry):
    print("  version_registry.yaml: EXISTS (should be gone)")
else:
    print("  version_registry.yaml: DELETED ✓")

print("\n=== Genie Spaces ===")
import requests
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
host = w.config.host.rstrip('/')
headers = {"Authorization": f"Bearer {w.config.token}"}
resp = requests.get(f"{host}/api/2.0/genie/spaces", headers=headers)
spaces = resp.json().get('spaces', [])
versioned = [s for s in spaces if '_v' in s.get('title', '') and 'member_claims' in s.get('title', '')]
print(f"  Versioned Genie spaces remaining: {len(versioned)}")

print("\n" + "="*50)
if remaining == 0 and len(versioned) == 0:
    print("✅ FULL RESET COMPLETE — next pipeline run will start at v1")
else:
    print("⚠️ Some items remain — check above")
