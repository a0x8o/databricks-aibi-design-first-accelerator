# Dashboards — Failure Runbook

> **FAILURE-ONLY — DO NOT LOAD ON A SUCCESSFUL PATH.** Authenticate this file's exact frozen path/version/raw SHA-256 after the stage has emitted a classified error. Load only the matching section needed for diagnosis. A runbook never changes authority, weakens a gate, or authorizes an unclassified retry. Record the selected section and digest in the failure evidence.

## Anti-Patterns

### AP-DB-1: Missing queryName in Filter Widgets
**Pattern:** Filter shows "no fields or parameters selected" in Lakeview UI.
**Root cause:** Hand-written filter JSON omits `queryName: "main_query"` from `encodings.fields[]`.
**Fix:** Template `build_filter_widget()` always includes `queryName`. NEVER hand-write filter JSON.

**Working (correct):**
```json
"encodings": {"fields": [{"fieldName": "claim_type", "displayName": "Claim Type", "queryName": "main_query"}]}
```

**Broken (incorrect):**
```json
"encodings": {"fields": [{"fieldName": "claim_type", "displayName": "Claim Type"}]}
```

### AP-DB-2: bar() TypeError from Hand-Rolled Builders
**Pattern:** `TypeError: bar() missing 1 required positional argument: 'p'`
**Root cause:** Agent defined `def bar(n, d, x, y, t):` (5 params) then called with 6 params.
**Fix:** ALWAYS import `build_bar_chart` from template. NEVER define custom builder functions.

### AP-DB-3: Column Name Mismatch in Dataset SQL
**Pattern:** Dashboard dataset SQL references `clm_dtl_claim_type` but metric view alias is `claim_type`.
**Root cause:** Agent used source table column names instead of metric view aliases.
**Fix:** DESCRIBE the metric view (not source table). Template Cell 3 does this automatically.

### AP-DB-4: f-string Backslash SyntaxError
**Pattern:** `SyntaxError: f-string expression part cannot include a backslash` in gate_checks.py
**Root cause:** `f"{'\u2500' * 40}"` — backslash inside f-string `{}` on Python <3.12.
**Fix:** Extract to variable: `sep = '\u2500' * 40; f"{sep}"`. Already fixed in gate_checks.py.

### AP-DB-5: Agent Bypasses Template Helpers
**Pattern:** Agent builds entire dashboard JSON inline via `execute_python` instead of importing the template.
**Root cause:** Prompt told agent to use helpers but didn't show HOW to import them in subprocess context.
**Fix:** `dashboard_notebook.py.template` imports are in Cell 2 (VERBATIM). Agent copies template, not builds from scratch.

### AP-DB-6: METRIC_VIEW_MISSING_MEASURE_FUNCTION
**Pattern:** Dataset SQL references measure columns directly (e.g., `SELECT \`Total Claims\` FROM metric_view`) instead of wrapping them in `MEASURE()`.
**Root cause:** Metric view measures are computed expressions, not regular columns. Accessing them without `MEASURE()` causes `[METRIC_VIEW_MISSING_MEASURE_FUNCTION]` error. The prompt examples used simple lowercase names (e.g., `total_paid`) but actual measure names often have spaces (e.g., `Total Paid Amount`) requiring backtick-quoting inside `MEASURE()`.
**Fix:** Step 7 now includes explicit wrong/correct examples and backtick-quoting rules. ALL measure references in dataset SQL MUST use `MEASURE(\`Measure Name\`)` — never direct column access.

### AP-DB-7: create_dashboard Tool Is Disabled
**Pattern:** LLM calls `create_dashboard` tool and gets `ERROR: create_dashboard tool is disabled. Use the template notebook pattern instead`.
**Root cause:** The prompt header and guardrails were updated to reference the template notebook pattern (`dashboard_notebook.py.template`), but Steps 13/15 and PROHIBITED ACTIONS #13 still instructed the LLM to use the `create_dashboard` and `publish_dashboard` tools directly. The execution environment has disabled these tools — dashboards must be deployed via the template notebook pattern (same as metric views and Genie spaces).
**Fix:** Steps 13/15 and all tool references updated to use the template notebook pattern. The LLM produces `dashboard_design.yaml`; the template handles compilation, deployment, readback, and manifest writing.

### AP-DB-8: NameError spark is not defined
**Pattern:** Pipeline fails with `NameError: name 'spark' is not defined` during dashboard notebook execution.
**Root cause:** The LLM generated notebook code using `spark.sql()` for dataset validation or DESCRIBE queries. The `spark` variable is NOT available in the notebook execution context on serverless compute or job tasks. The metric view deployment notebook already uses the Statement Execution API (`w.statement_execution.execute_statement()`), but the dashboard helpers and prompt did not enforce the same pattern.
**Fix:** `lakeview_dashboard_helpers.py.template` now provides `_execute_sql_via_api(stmt, warehouse_id)` using the Statement Execution API. `describe_metric_view()`, `validate_dataset_sql()`, and `build_validated_dataset()` now accept `warehouse_id` and use the API internally. The prompt PROHIBITS `spark.sql()` (PROHIBITED ACTION #18) and requires the Statement Execution API or template helpers.

### AP-DB-9: PermissionDenied on Dashboard Creation
**Pattern:** Pipeline fails with `PermissionDenied: User ... does not have create permission for tree node with aclPath /workspace/...`.
**Root cause:** `PARENT_PATH` was set to the user's home root (e.g., `/Users/{username}`), but the service principal running the pipeline does NOT have create permission there. The Lakeview API `parent_path` parameter determines where the dashboard appears in the workspace browser — it must be a directory where the SP has write access.
**Fix:** The upstream resolver must write `parent_path` in `step_handoff.yaml` as a writable subfolder within the project's output directory (e.g., `/Users/{username}/databricks-aibi-design-first-accelerator/kpi_domains/{domain}/generated_outputs/{version}/dashboards`). The dashboard stage validates and consumes that value verbatim. If it is missing or points to the home root, halt with `DASHBOARD_INPUT_AUTHORITY_ERROR`; do not derive or rewrite it locally.

### AP-DB-10: Planned Metric View State Overrides Deployment
**Pattern:** Dataset SQL uses a field found in `metric_view_design.yaml` or stored DDL but absent from the deployed Metric View.
**Root cause:** Desired-state artifacts were treated as deployed truth and live readback was skipped.
**Fix:** Always run `DESCRIBE TABLE` and `SHOW CREATE TABLE` against every exact handoff FQN. Preserve the desired-versus-actual mismatch and return it to the Metric View stage; do not substitute or invent a field.

### AP-DB-11: Manifest Treated as Dashboard Ground Truth
**Pattern:** A dashboard is reported complete because its manifest says `published: true`, although the Lakeview API returns missing pages, widgets, filters, or a different published state.
**Root cause:** Locator/attempt metadata was treated as deployed-state authority.
**Fix:** Use the manifest to locate the dashboard, then use Lakeview API GET/readback to establish actual state. Compare that response with `dashboard_design.yaml`; a material mismatch fails validation.

### AP-DB-12: Second Text-Widget Serializer
**Pattern:** Titles or narrative widgets fail after orchestration code emits or patches its own text-widget dictionary.
**Root cause:** Wire-format knowledge was duplicated outside the pinned helper.
**Fix:** Keep semantic `content` in the design and pass it only to the digest-attested `build_text_widget()`; append its opaque return value unchanged.

### AP-DB-13: Quality Target Used as a Structural Gate
**Pattern:** A valid mapped dashboard is rejected or padded with filler pages/widgets solely to meet a numeric design target.
**Root cause:** Preferred quality thresholds were interpreted as mandatory structure.
**Fix:** Preserve the exact mapped-page inventory, apply structural gates separately, and record unmet quality targets as `WARN` with Dashboard `PARTIAL_SUCCESS`.

---

# Validated Learnings (from production runs)

**1. Use `build_text_widget()` for every text/title widget**

Prior runs failed when orchestration code copied or guessed the Lakeview text-widget wire format.
The design records semantic `content`; the digest-attested `build_text_widget(name, markdown,
position)` helper is the sole serializer, and its returned object is opaque. Never embed a text
widget JSON example in generated code or patch the helper output.

**2. `uiSettings` format must include `theme` and `applyModeEnabled`**

Using `{"themeColors": {}}` causes `failed to parse serialized dashboard`.

Correct format:
```json
"uiSettings": {"theme": {"widgetHeaderAlignment": "ALIGNMENT_UNSPECIFIED"}, "applyModeEnabled": false}
```

**3. Separate filter datasets break cross-filtering**

Creating a dedicated `ds_filter_values` dataset for filters causes filters to populate but NOT bind to canvas widgets. The API does not auto-bind across datasets.

Fix: Filter widgets and canvas widgets MUST reference the SAME `datasetName`.

**4. `publish_dashboard` requires `warehouse_id` + `embed_credentials`**

Calling publish without a body (or with empty body) may succeed but the published dashboard won't render. Always pass:
```json
{"warehouse_id": "<id>", "embed_credentials": true}
```

**5. Counter aggregation MUST follow validated KPI/Metric View semantics**

When a shared dataset includes filter dimensions, the counter may change the roll-up grain. Do not choose `SUM`, `AVG`, or another reducer from the measure's label. Resolve the exact behavior from validated semantics or halt with `AGGREGATION_SEMANTICS_UNRESOLVED`.

**6. Widget `name` must be alphanumeric/hyphens/underscores only**

Spaces, special characters, or dots in widget names cause silent failures.

**7. `queryLines` concatenation uses NO separator**

Array elements join with no space between them. Either use a single-element array (one long SQL string) or end each element with a space character.

---

# CORRECT vs WRONG Examples (Critical Reference)

These examples show the EXACT correct patterns and the EXACT errors from prior failed runs.

## Display Name

```python
# ✅ CORRECT — uses the resolved display_name from step_handoff.yaml
correct_request = {"display_name": "member_claims_kpis_dashboard_v3"}

# ❌ WRONG — agent invented a human-friendly name
wrong_requests = [
    {"display_name": "Member Claims KPIs v3"},
    {"display_name": "Member Claims KPIs Dashboard v3"},
    {"display_name": "KPIs Dashboard"},
]
```

The `display_name` MUST be the exact matching `dashboard_display_names[].display_name` string from `step_handoff.yaml`. No suffix reconstruction, spaces, title case, or reformatting.

## Metric View FQN in SQL

```sql
-- ✅ CORRECT — each segment separately backtick-quoted
SELECT MEASURE(`Total Paid Amount`)
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v3`
GROUP BY ALL

-- ❌ WRONG — entire 3-part name in one backtick pair (causes rendering failure)
SELECT MEASURE(`Total Paid Amount`)
FROM `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v3`
GROUP BY ALL
```

The FQN MUST use 3 separate backtick pairs: `` `catalog`.`schema`.`table` ``. Never `` `catalog.schema.table` ``.

## Tool Usage (MANDATORY)

```text
# CORRECT — use deploy_from_template (create_dashboard tool is DISABLED)
1. Produce dashboard_design.yaml (declarative spec)
   → Write to {OUTPUT_FOLDER}/dashboards/dashboard_design.yaml
2. Call deploy_from_template to create the dashboard notebook:
   → template_path: exact frozen run_context.templates.dashboard_notebook
   → output_path: {OUTPUT_FOLDER}/dashboards/dashboard_deployment.ipynb
   → placeholders: {"DOMAIN_NAME": "<run_context.domain.name>",
      "CATALOG": "<handoff target catalog>", "SCHEMA": "<handoff target schema>",
      "VERSION_SUFFIX": "<handoff.version_suffix>", "ASSET_SUFFIX": "<handoff.asset_suffix>",
      "WAREHOUSE_ID": "<handoff.warehouse_id>", "PARENT_PATH": "<handoff.parent_path>",
      "OUTPUT_FOLDER": "<handoff.output_folder>", "DEPLOY_ROOT": "<handoff.deploy_root>",
      "METRIC_VIEW_FQNS": [<exact handoff sql_fqn values>],
      "QUALITY_GATES": <run_context.quality_gates>}
   The tool reads the template verbatim and performs ONLY placeholder substitution.
   Cells 2-N are guaranteed VERBATIM from the template — the LLM never touches them.
   DO NOT use write_workspace_file or import_notebook for dashboard_ notebook paths — they are blocked by G-16.
3. Execute the notebook
# The template handles: Lakeview API create + publish + readback + manifest

# WRONG — these tools are DISABLED and will fail:
Tool: create_dashboard   # DISABLED
Tool: publish_dashboard   # DISABLED
execute_python with code: w.lakeview.create(...)   # no WorkspaceClient in subprocess
execute_python with code: w.api_client.do("POST", ...)   # no SDK access
execute_python with code: requests.post(...)   # no tokens
```

---
