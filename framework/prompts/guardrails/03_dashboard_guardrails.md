# Dashboard Guardrails — Step 4 (Create Dashboards)

> **Also read:** `guardrails/00_global_rules.md` (always applies)

---

## Enforcement Architecture

Dashboard deployment uses the **template notebook pattern** (`dashboard_notebook.py.template`).
The LLM's job is to produce `dashboard_design.yaml` (a structured spec). The template notebook
compiles the spec into deployed dashboards with all guardrails in the code path.

**The template enforces these rules automatically:**
- Always uses `build_filter_widget()` → queryName always present
- Always runs DESCRIBE before building datasets → column names always correct
- Always uses `build_bar_chart()`, `build_counter()`, etc. → no hand-rolled builders
- Always calls `deploy_dashboard()` → pre-deploy gates + API readback

---

## Gates

### GATE 3.1: Page Count Validation (MANDATORY)
After writing `dashboard_design.yaml`, count canvas pages per dashboard. If any dashboard has fewer canvas pages than its KPI spec mapping defines → HALT.

### GATE 3.2: Design Contract Validation
`dashboard_design.yaml` must be written and validated BEFORE any dashboard construction. No dashboard JSON may be built without this contract.

### HARD GATE: lakeview_dashboard_api.md Must Be Loaded
The agent must read the Lakeview API reference before building dashboards. This is non-negotiable.

### HARD GATE: No Dashboard Construction Without Design Contract
If `dashboard_design.yaml` does not exist → HALT. Do NOT construct dashboards from memory.

### GATE 19.1: Ground-Truth Validation Required
After all dashboards deployed, `ground_truth_validation.yaml` must be written via cross-validation sweep.

---

## Dashboard Design Spec Schema

The LLM produces `dashboard_design.yaml` with this structure:

```yaml
dashboards:
  - name: my_dashboard_v1
    metric_view: catalog.schema.my_metric_view_v1     # single MV
    # OR for multi-MV dashboards:
    metric_views:                                       # list of MVs
      - catalog.schema.claims_mv_v1
      - catalog.schema.enrollment_mv_v1
    pages:
      - title: Overview
        widgets:
          - type: counter          # counter, bar, line, or text
            measure: total_claims  # column name from DESCRIBE output
            title: Total Claims
            display_name: Claims   # optional: counter label
            agg: SUM               # optional: SUM (default) or AVG
          - type: bar
            measure: total_paid_amount
            dimension: claim_type  # x-axis for bar/line charts
            title: Paid Amount by Type
          - type: line
            measure: total_paid_amount
            dimension: service_date
            title: Paid Amount Trend
          - type: text
            content: "## Section Header"
    filter_dimensions:
      - claim_type               # simple string → auto-detects widget type
      - field_name: service_date # OR dict with explicit config
        display_name: Service Date
        widget_type: filter-date-range-picker
```

---

## Prohibited Actions

1. DO NOT use `execute_python` for dashboard creation or publishing — the subprocess has NO WorkspaceClient
2. DO NOT use the `create_dashboard` or `publish_dashboard` tools — these are DISABLED. Use the template notebook pattern instead.
3. DO NOT bypass the dashboard_design.yaml contract — build from spec, not from memory
4. DO NOT create dashboards with 0 filter pages
5. DO NOT create dashboards with 0 canvas widgets
6. DO NOT publish dashboards without API readback validation
7. DO NOT write manifests without `validation_source: api_readback`
8. DO NOT skip DESCRIBE on the metric view before building datasets
9. DO NOT use column names from spec text or agent memory — only from DESCRIBE
10. DO NOT mix filter and canvas widgets on the same page
11. DO NOT use `spec.version: 1` for filter widgets (must be 2)
12. DO NOT omit `queryName` from filter widget `encodings.fields[]`
13. DO NOT use a separate filter dataset — filters MUST share the same dataset as canvas widgets
14. DO NOT reference measure columns directly in dataset SQL — ALWAYS use `MEASURE()` (causes `METRIC_VIEW_MISSING_MEASURE_FUNCTION` error)
15. DO NOT fall back to `execute_python` when SQL fails — fix the SQL
16. DO NOT skip the pre-deploy gate checks
17. DO NOT hand-write filter widget JSON inline — ALWAYS use `build_filter_widget()` from helpers
18. DO NOT define your own widget builder functions (e.g., `def bar(...)`, `def counter(...)`)
19. DO NOT skip DESCRIBE on the metric view before building datasets
20. DO NOT use `spark.sql()` — see **G-13** in `guardrails/00_global_rules.md`
22. DO NOT add `%pip install` cells to the dashboard deployment notebook — the template does not include them and all required packages (`pyyaml`, `databricks-sdk`) are pre-installed on serverless. Adding a `%pip` + `restartPython()` cell causes preflight syntax errors that abort the notebook before the helpers import cell runs (see G-17)
23. DO NOT add `import dbldatagen` or other synthetic-data imports to the dashboard notebook — dashboard deployment has no dependency on dbldatagen
21. DO NOT set `PARENT_PATH` to user home root — see **G-14** in `guardrails/00_global_rules.md`

---

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
**Fix:** `PARENT_PATH` must always be a subfolder within the project's output directory (e.g., `/Users/{username}/databricks-aibi-design-first-accelerator/kpi_domains/{domain}/generated_outputs/{version}/dashboards`). The `step_handoff.yaml` now includes `parent_path` to prevent the LLM from guessing. The prompt's recovery logic (PROHIBITED ACTION #19) explicitly requires deriving `parent_path` from `{OUTPUT_FOLDER}` by stripping the `/Workspace` prefix and appending `/dashboards`.

---

## Hard Stop Rules

Any of these invalidate the dashboard and require re-execution:

- Hand-writes filter widget JSON without using `build_filter_widget()`
- Builds dataset SQL without first running `DESCRIBE TABLE {metric_view_fqn}`
- Defines its own `bar()`, `counter()`, `line()` builder functions
- Reports `published: true` without API readback
- Creates a dashboard with 0 filter pages
- Creates a dashboard with canvas pages missing widgets
- Uses `spark.sql()` for any SQL execution (violation of G-13)
- Sets `PARENT_PATH` to the user's home root (violation of G-14)
