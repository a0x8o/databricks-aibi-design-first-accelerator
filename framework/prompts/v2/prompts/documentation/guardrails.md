# Documentation — Guardrails

> **Always loaded.** This file contains normative prohibitions and hard stops for `generate_documentation`. Historical incidents and fixes live only in the failure runbook.

## Prohibited Actions

1. DO NOT skip reading `documentation/instructions.md` before writing README
2. DO NOT write a flat summary instead of the structured 11-section format
3. DO NOT report an affected asset or check as successful when verified `ground_truth_validation.yaml` evidence shows failure; preserve independently verified results for unaffected fields
4. DO NOT omit NOT_IMPLEMENTED KPIs from the catalog
5. DO NOT omit reference SQL for NOT_IMPLEMENTED KPIs
6. DO NOT re-execute earlier pipeline stages (data layer, metric views, dashboards) to produce ground_truth_validation.yaml
7. DO NOT run any notebook that imports `dbldatagen` during documentation — that is exclusively a Step 2 dependency
8. DO NOT derive `deploy_root` independently — consume the exact resolved `deploy_root` from `step_handoff.yaml` under G-12; if it is missing, halt and return to the master resolver
9. DO NOT write documentation files outside `{OUTPUT_FOLDER}/documentation/` — all output stays in the versioned `generated_outputs/{version}/` folder
10. DO NOT use a manifest alone as proof that an asset currently exists, is published, or passed validation
11. DO NOT overwrite intended configuration or semantics with readback values — report differences as `DRIFT`
12. DO NOT describe a Metric View feature as unsupported from a hardcoded feature list — use the resolved capability contract and preserve its `PLATFORM` or `ACCELERATOR` scope
13. DO NOT call reference SQL validated unless an executed-query validation record confirms it
14. DO NOT accept a successful-looking ground-truth report without exact `scope_input_binding: PASS`, valid matching `scope_inputs_sha256`, inventory parity, and strategy-aware producer-checkpoint authentication
15. DO NOT locate `run_context.yaml` by scanning folders or choosing a newest version — use only the resolver-supplied `run_context_path` and G-12 bootstrap
16. DO NOT accept a Metric View plan or validation for either strategy unless both artifacts' top-level `run_id`, `asset_suffix`, and `metric_view_strategy` exactly match current run context and handoff
17. DO NOT document a Genie threshold, benchmark action, or stage status from prompt prose, a
    request-time default, or an artifact whose quality tuple/effective-policy hash does not match

---
