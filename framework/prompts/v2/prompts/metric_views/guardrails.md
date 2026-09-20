# Metric Views — Guardrails

> **Always loaded.** This file contains normative prohibitions and hard stops for `create_metric_views`. Historical incidents and fixes live only in the failure runbook.

## Prohibited Actions

0. DO NOT classify enrollment/secondary-grain KPIs as NOT_IMPLEMENTED without creating their metric view
1. DO NOT skip schema profiling
2. DO NOT skip relationship verification
3. DO NOT skip KPI enumeration completeness check (GATE 4.2)
4. DO NOT use raw SUM/COUNT/AVG instead of MEASURE() syntax
5. DO NOT create metric views with columns not in the source table
6. DO NOT modify source table data or schema
7. DO NOT skip validation of metric view queryability
8. DO NOT create metric views in a different schema than configured
9. DO NOT skip the multi-grain analysis (GATE 4.5)
10. DO NOT skip the planned-vs-created parity check (GATE 5.7)
11. DO NOT drop a secondary grain because it has "fewer than 2 KPIs"
12. DO NOT use source table column names in metric view DDL without verifying they match
13. DO NOT assume column names from spec text — use DESCRIBE TABLE
14. DO NOT create a metric view without validating its SQL against the source tables
15. DO NOT skip idempotently synchronizing `step_handoff.yaml` with all planned metric_view_fqns; upsert by normalized FQN and do not append duplicates
16. DO NOT reuse metric view names from prior versions without version suffix
17. DO NOT skip the KPI-to-metric-view mapping validation
18. DO NOT generate a capability disabled by the resolved contract. Apply its declared fallback first. A validated semantics-preserving fallback remains implemented and must be recorded. Use `NOT_IMPLEMENTED` only when no applicable fallback succeeds; missing or unknown capability evidence must HALT, never classify.
19. DO NOT skip an intermediate view explicitly required by the validated desired-state plan. Do not create one merely because a join exists when a validated direct Metric View join is sufficient.
20. DO NOT proceed to dashboards without GATE 10.1 passing
21. DO NOT reference source table columns in measure/field expressions without verifying they exist in the actual DESCRIBE TABLE output — the template's Gate 2b validates this automatically and halts with the exact missing column
22. DO NOT reconstruct or repair missing resolved identities from `run_context.yaml`, `accelerator.yaml`, folder names, or model memory; return the defect to the master resolver
23. DO NOT treat `metric_view_plan.yaml`, `metric_view_design.yaml`, `metric_view_spec.yaml`, or a deployment manifest as proof of deployed Metric View content; use current DESCRIBE/query/SHOW CREATE or approved API readback
24. DO NOT rewrite desired Metric View intent to match divergent deployed readback; record drift and fail the owning gate
