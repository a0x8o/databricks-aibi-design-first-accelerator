# Genie — Failure Runbook

> **FAILURE-ONLY — DO NOT LOAD ON A SUCCESSFUL PATH.** Authenticate this file's exact frozen path/version/raw SHA-256 after the stage has emitted a classified error. Load only the matching section needed for diagnosis. A runbook never changes authority, weakens a gate, or authorizes an unclassified retry. Record the selected section and digest in the failure evidence.

## Anti-Patterns

### AP-GN-1: Blank Genie Space
**Pattern:** Manifest claims `sample_questions_count: 10` but API readback shows 0.
**Root cause:** Agent used `createAsset(assetType="genie")` which creates blank spaces.
**Fix:** MUST use template notebook pattern with full `serialized_space` payload.

### AP-GN-2: Raw Aggregation in Example SQL
**Pattern:** Example SQL uses `SELECT SUM(total_paid) ...` instead of `SELECT MEASURE(total_paid) ...`
**Root cause:** Agent wrote SQL from memory without following MEASURE() convention.
**Fix:** All example SQL MUST use MEASURE() syntax. Template validation cell checks this.

### AP-GN-3: Agent Bypasses Template
**Pattern:** Agent writes Genie notebook from scratch instead of reading and populating the template.
**Root cause:** Template path not loaded or agent took a shortcut.
**Fix:** Prompt enforces template usage. `create_genie_space` tool is disabled (returns error directing to template).

### AP-GN-4: Wrong data_sources Key in serialized_space
**Pattern:** `build_serialized_space` uses `"data_sources": {"tables": ...}` instead of `"data_sources": {"metric_views": ...}`.
**Error:** `BadRequest: The zip archive contains no items`
**Root cause:** LLM rewrote the helper function instead of copying verbatim from template. The Genie API v2 expects `metric_views` key. Using `tables` causes the API to try to package file-based table attachments into a zip, but UC metric views are not files, so the zip is empty.
**Fix:** Cells 8-10 MUST be copied VERBATIM from the template. The template now includes a format validation guard that asserts `data_sources` contains `metric_views` (not `tables`) before the API call. Never add `column_configs` to metric view entries.

### AP-GN-5: Threshold or Outcome Drift
**Pattern:** A prompt, helper, or resume path uses a local question count or treats a warning as a
pass/failure differently from the active run.
**Root cause:** Numeric defaults or benchmark semantics were duplicated outside the approved quality
contract and Step-0 resolution.
**Fix:** Authenticate the source tuple and canonical effective-policy hash, consume only the frozen
fields/mapping, and invalidate every affected checkpoint when either fingerprint changes.

### Validated Learnings (from production runs)

These are confirmed errors encountered and resolved during actual Genie Space creation. Treat them as mandatory guardrails.

**1. All ID-containing arrays MUST be sorted by `id` (ascending)**

The Genie API rejects payloads where any array containing `id` fields is unsorted:

```text
Error: "Invalid export proto: instructions.example_question_sqls must be sorted by id"
```

This applies to ALL of:
- `config.sample_questions`
- `instructions.text_instructions`
- `instructions.example_question_sqls`
- `benchmarks.questions`

Fix: Always sort after generating UUIDs:
```python
items = sorted(items, key=lambda x: x["id"])
```

**2. GET /genie/spaces/{id}?include_serialized_space=true DOES return content**

Pass `?include_serialized_space=true` query param to get the full configuration back. Two quirks in the read-back:

- `data_sources.metric_views` is RENAMED to `data_sources.tables` in the response
- `text_instructions[].content` is stored as a multi-line array (one item per line), not a single string. Join all items to get the full text: `''.join(ti['content'])`

Validation should check both key names:
```python
mvs = ss.get("data_sources", {}).get("metric_views", []) or \
      ss.get("data_sources", {}).get("tables", [])
```

**3. `column_configs` must be sorted alphabetically by `column_name`**

The API rejects with `InvalidParameterValue` if `column_configs[]` entries within a table are not alphabetically sorted.

```python
column_configs = sorted(column_configs, key=lambda x: x["column_name"])
```

**4. UUIDs MUST be 32-char lowercase hex WITHOUT hyphens**

The API rejects standard UUIDs with hyphens (`a1b2c3d4-e5f6-7890-...`). Use `uuid.uuid4().hex` (32 hex chars):

```text
Error: "Invalid id for sample_question.id: 'a1b2c3d4-e5f6-...'. Expected lowercase 32-hex UUID without hyphens"
```

Fix: Use `uuid.uuid4().hex` instead of `str(uuid.uuid4())`:
```python
import uuid

item_id = uuid.uuid4().hex  # "a1b2c3d4e5f6789012345678abcdef01"
```

**5. `version` field MUST be 2 in `serialized_space`**

The API rejects version 0 or 1:

```text
Error: "Invalid export proto: ExportConverter supports versions 1 and 2, but got 0"
```

Fix: Always include `"version": 2` at the top level of `serialized_space`.

**6. ALL text fields (`question`, `sql`, `content`) MUST be arrays, not strings**

The API rejects plain strings for these fields:

```text
Error: "Expected an array for question but found 'What is the total paid amount?'"
Error: "Expected an array for sql but found 'SELECT SUM(paid_amount)...'"
Error: "Expected an array for content but found '## Domain\nThis Genie Space...'"
```

Fix: Wrap ALL text values in arrays:
```python
# WRONG:
{"question": "What is total paid?", "sql": "SELECT ..."}

# CORRECT:
{"question": ["What is total paid?"], "sql": ["SELECT ..."]}
{"content": ["Full instructions text here"]}
```

**7. Use SDK `w.api_client.do()` — NEVER raw `requests` with extracted tokens**

Extracting API tokens via `dbutils.notebook.entry_point.getDbutils()...apiToken()` and using `requests.post()` is:
- A credential exfiltration risk (triggers safety guardrails in Genie Code)
- Fragile (token rotation, format changes)
- Unnecessary (SDK handles auth automatically)

Fix: Use `WorkspaceClient().api_client.do(method, path, body=..., headers={"Content-Type": "application/json"})` for all API calls.

**CRITICAL: Always pass `headers={"Content-Type": "application/json"}` on POST/PATCH calls to `/api/2.0/genie/spaces`.**
Without this header, newer SDK versions may negotiate a different serialization format, causing the server to return `BadRequest: The zip archive contains no items`.

**8. `table_identifiers` goes in the CREATE body, NOT inside `serialized_space`**

Putting `table_identifiers` inside `serialized_space.config` causes:
```text
Error: "Unknown field 'table_identifiers'"
```

The correct structure:
```python
import json

# table_identifiers is a TOP-LEVEL field in the POST body:
body = {
    "title": ...,
    "warehouse_id": ...,
    "table_identifiers": [   # HERE — include the exact validated handoff FQN set
        "catalog.schema.primary_metric_view",
        "catalog.schema.secondary_metric_view",
        # ... one entry per validated step_handoff.yaml metric_view_fqns[] item
    ],
    "serialized_space": json.dumps({...}),  # NOT inside here
}
```

---

### ANTI-PATTERN: What A Failed Execution Looks Like

In the last failed run, the agent produced:
- `{genie_title}_manifest.json` = `{"space_id": "...", "status": "CREATED"}` (NO config counts)
- `genie_instructions.md` = 4 lines ("Use MEASURE() for metric view queries...")
- `sample_queries.sql` = 1 query
- Genie Space API had: 0 sample questions, 0 instructions, 0 example SQL, 0 benchmarks
- The `genie_space/` output folder was COMPLETELY EMPTY
- No `genie_semantic_inventory.yaml` created
- No `llm_genie_design.yaml` created
- No template notebook created
- No `validate_genie_config()` executed

This happened because the agent used `createAsset(assetType="genie")` instead of the full template workflow.

**In the v3 run, a MORE SUBTLE failure occurred:**
- `{genie_title}_manifest.json` claimed `sample_questions_count: 10`, `example_sqls_count: 5`, `benchmarks_count: 15`
- BUT the API readback showed: **0 instructions, 0 sample questions, 0 example SQLs, 0 benchmarks**
- The agent created the space via `POST /api/2.0/genie/spaces` with `table_identifiers` but **without `serialized_space`**
- The manifest was written from agent MEMORY, not from API readback
- No `validate_genie_from_api()` was ever called
- The cross-validation sweep was never executed

This is why the **Manifest Integrity Rule** now requires `validation_source: api_readback`.

**If your execution produces ANY of the above patterns, you have FAILED. Go back to Phase A.**

# CORRECT vs WRONG Examples (Critical Reference)

These examples show the EXACT correct patterns and the EXACT errors from prior failed runs.

## Space Title (display name)

```python
# ✅ CORRECT — uses the exact resolved genie_title from step_handoff.yaml
correct_request = {"title": "member_claims_analytics_genie_v3"}

# ❌ WRONG — agent invented a human-friendly name
wrong_requests = [
    {"title": "Member Claims Analytics v3"},
    {"title": "Member Claims Genie Space"},
    {"title": "Claims Analytics"},
]
```

The title MUST be the exact `genie_title` string from `step_handoff.yaml`. `accelerator.yaml` provides requested naming intent but MUST NOT be used to re-resolve the deployed title in this stage. No spaces, title case, suffix reconstruction, or reformatting.

## Metric View FQN in Example SQL

```sql
-- ✅ CORRECT — each segment separately backtick-quoted
SELECT MEASURE(`Total Paid Amount`)
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v3`
GROUP BY ALL

-- ❌ WRONG — entire 3-part name in one backtick pair (Genie generates broken SQL)
SELECT MEASURE(`Total Paid Amount`)
FROM `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v3`
GROUP BY ALL
```

The FQN MUST use 3 separate backtick pairs: `` `catalog`.`schema`.`table` ``. Never `` `catalog.schema.table` ``.

## UUID Format

```python
# ✅ CORRECT — 32-char hex, no hyphens
import uuid
item_id = uuid.uuid4().hex  # "a1b2c3d4e5f6789012345678abcdef01"

# ❌ WRONG — standard UUID with hyphens (API rejects)
item_id = str(uuid.uuid4())  # "a1b2c3d4-e5f6-7890-1234-5678abcdef01"
```

## Text Fields (question, sql, content)

```python
# ✅ CORRECT — all text wrapped in arrays
{"id": "abc123...", "question": ["What is total paid?"], "sql": ["SELECT MEASURE(`Total Paid Amount`) FROM ..."]}
{"id": "def456...", "content": ["## Domain\nThis space provides claims analytics..."]}

# ❌ WRONG — plain strings (API rejects with "Expected an array")
{"id": "abc123...", "question": "What is total paid?", "sql": "SELECT ..."}
{"id": "def456...", "content": "## Domain\nThis space provides..."}
```

## Array Sorting

```python
# ✅ CORRECT — all ID-containing arrays sorted by id ascending
sample_questions = sorted(sample_questions, key=lambda x: x["id"])
example_sqls = sorted(example_sqls, key=lambda x: x["id"])
benchmarks = sorted(benchmarks, key=lambda x: x["id"])
text_instructions = sorted(text_instructions, key=lambda x: x["id"])

# ❌ WRONG — unsorted arrays (API rejects with "must be sorted by id")
sample_questions = [...]  # inserted in generation order, not sorted
```

## API Call Structure

```python
# ✅ CORRECT — table_identifiers at TOP LEVEL, not inside serialized_space
import json

body = {
    "title": "member_claims_analytics_genie_v3",  # exact configured name
    "warehouse_id": warehouse_id,
    "table_identifiers": [  # TOP LEVEL — include the exact validated handoff FQN set
        "catalog.schema.primary_metric_view",
        "catalog.schema.secondary_metric_view",
        # ... one per validated step_handoff.yaml metric_view_fqns[] item
    ],
    "serialized_space": json.dumps({...}),  # does NOT contain table_identifiers
}

# ❌ WRONG — do not execute: table_identifiers inside serialized_space causes "Unknown field".
# wrong_body = {
#     "title": "Member Claims Analytics v3",  # wrong name format
#     "serialized_space": json.dumps({
#         "table_identifiers": [...],  # WRONG LOCATION
#     }),
# }
```

## Deployment Method

```python
# ✅ CORRECT — Genie Management API with full serialized_space
result = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)

# ❌ WRONG — do not execute; createAsset produces a blank space with no instructions:
# createAsset(asset={"assetType": "genie", "name": "...", "tableIdentifiers": [...]})
```

---
