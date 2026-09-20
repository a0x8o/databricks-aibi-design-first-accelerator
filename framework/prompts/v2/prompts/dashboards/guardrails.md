# Dashboards — Guardrails

> **Always loaded.** This file contains normative prohibitions and hard stops for `create_dashboards`. Historical incidents and fixes live only in the failure runbook.

## Prohibited Actions

1. DO NOT use `execute_python` for dashboard creation or publishing — the subprocess has NO WorkspaceClient
2. DO NOT use the `create_dashboard` or `publish_dashboard` tools — these are DISABLED. Use the template notebook pattern instead.
3. DO NOT bypass the dashboard_design.yaml contract — build from spec, not from memory
4. DO NOT create dashboards with fewer filter pages than frozen `run_context.quality_gates.min_filter_pages_per_dashboard`
5. DO NOT treat a widget-density, visualization-diversity, filter-count, fallback-page-count, or KPI-context target miss as a structural deployment failure
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
20. DO NOT use `spark.sql()` — see **G-13** in `shared/global_guardrails.md`
22. DO NOT add `%pip install` cells to the dashboard deployment notebook — the template does not include them and all required packages (`pyyaml`, `databricks-sdk`) are pre-installed on serverless. Adding a `%pip` + `restartPython()` cell causes preflight syntax errors that abort the notebook before the helpers import cell runs (see G-17)
23. DO NOT add `import dbldatagen` or other synthetic-data imports to the dashboard notebook — dashboard deployment has no dependency on dbldatagen
21. DO NOT set `PARENT_PATH` to user home root — see **G-14** in `shared/global_guardrails.md`
24. DO NOT normalize, reconstruct, or overwrite `step_handoff.yaml` in the dashboard stage
25. DO NOT use `metric_view_plan.yaml`, `metric_view_design.yaml`, stored DDL, or agent memory in place of live `DESCRIBE TABLE` and `SHOW CREATE TABLE`
26. DO NOT treat an LLM design proposal as authority over KPI eligibility, handoff identity, or deployed Metric View readback
27. DO NOT treat a dashboard manifest as proof of current deployed state — it is locator and deployment-attempt evidence only
28. DO NOT rewrite `dashboard_design.yaml` merely to make a divergent Lakeview API GET response appear correct
29. DO NOT import `gate_checks` or Dashboard helpers from a fixed/ambient `sys.path`, a shared non-digest-qualified temp directory, or an unattested output-folder copy
30. DO NOT manually reproduce or fall back around the canonical pinned `validate_dashboard_from_api` validator
31. DO NOT consume auto-produced Metric View handoff entries unless the complete G-3 producer checkpoint, capability tuple, raw handoff hash, canonical plan hash, full entry tuples, and separate `VALID` fingerprinted producer phase authenticate them
32. DO NOT accept a Metric View plan or validation for either strategy unless its top-level `run_id`, `asset_suffix`, and `metric_view_strategy` exactly match the other artifact, current run context, and handoff
33. DO NOT serialize, wrap, reshape, or patch a text widget outside the exact digest-attested `build_text_widget()` helper
34. DO NOT add, drop, merge, split, rename, or reorder mapped pages to satisfy a numeric quality target

---

## Hard Stop Rules

Any of these invalidate the dashboard and require re-execution:

- Hand-writes filter widget JSON without using `build_filter_widget()`
- Builds dataset SQL without first running live `DESCRIBE TABLE` and `SHOW CREATE TABLE` for every exact handoff FQN
- Defines its own `bar()`, `counter()`, `line()` builder functions
- Serializes or patches a text widget outside the digest-attested `build_text_widget()` helper
- Reports `published: true` without API readback
- Creates a dashboard with fewer filter pages than frozen `run_context.quality_gates.min_filter_pages_per_dashboard`
- Violates the exact mapped-page inventory, or produces an empty fallback canvas inventory
- Converts a Dashboard quality-target miss into a structural failure or suppresses its `WARN`
- Uses `spark.sql()` for any SQL execution (violation of G-13)
- Sets `PARENT_PATH` to the user's home root (violation of G-14)
- Mutates or reconstructs `step_handoff.yaml` in this downstream stage
- Builds field inventory without live DESCRIBE and SHOW CREATE for every handoff FQN
- Treats a dashboard manifest as proof of deployed state without Lakeview API GET/readback
- Silently changes desired dashboard design to match a divergent deployed response
- Loads a fixed-name/unpinned helper, accepts a stale cached module, or performs manual Dashboard validation because the canonical helper is unavailable
- Consumes auto-planned Metric View identities without exact strategy-aware producer-checkpoint authentication
