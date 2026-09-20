# Documentation — Failure Runbook

> **FAILURE-ONLY — DO NOT LOAD ON A SUCCESSFUL PATH.** Authenticate this file's exact frozen path/version/raw SHA-256 after the stage has emitted a classified error. Load only the matching section needed for diagnosis. A runbook never changes authority, weakens a gate, or authorizes an unclassified retry. Record the selected section and digest in the failure evidence.

## Anti-Patterns

### AP-DOC-1: Flat README Instead of Structured Documentation
**Pattern:** Agent writes a 90-line flat summary with no artifact inventory, no architecture diagram, no per-KPI status table.
**Root cause:** Agent skipped reading `{AGENT_SKILLS_DIR}/prompts/documentation/instructions.md` entirely.
**Fix:** Enforcement checklist in master prompt requires all 11 sections. Compare against structured 107-line v3 README.

### AP-DOC-2: dbldatagen Import in Documentation Stage
**Pattern:** `ModuleNotFoundError: No module named 'dbldatagen'` during documentation or cross-validation.
**Root cause:** Agent tried to "re-execute failed stages" and went all the way back to data layer.
**Fix:** G-6 (no stage re-execution). Cross-validation reads EXISTING manifests — it creates nothing new.

### AP-DOC-3: Missing Ground-Truth Reference
**Pattern:** README says "All dashboards deployed" but doesn't reference `ground_truth_validation.yaml`.
**Root cause:** Agent self-reported dashboard status instead of citing the validation artifact.
**Fix:** Section 10 (Validation Summary) MUST reference ground_truth_validation.yaml.

### AP-DOC-4: shutil.copy2 FileNotFoundError from Placeholder Path
**Pattern:** Pipeline fails with `FileNotFoundError` in `shutil.copy2` during documentation step.
**Root cause:** The prompt used `os.environ.get("DEPLOY_ROOT", "/Workspace/Users/{username}/...")` — the `DEPLOY_ROOT` env var is NOT set in the `execute_python` subprocess context, and `{username}` is a literal string (not a Python variable), producing an invalid path.
**Fix:** Use the exact `deploy_root` from `step_handoff.yaml` under G-12. Never invent a step-local dirname or environment fallback. If the value or target file is missing, halt with the authority error and rerun the master resolver.

### AP-DOC-5: Documentation Written Outside generated_outputs
**Pattern:** Documentation files (README.md, etc.) appear in the project root or user home instead of the versioned output folder.
**Root cause:** The prompt did not specify the output path, so the LLM wrote to the current working directory.
**Fix:** All documentation MUST be written to `{OUTPUT_FOLDER}/documentation/`. Prohibited Action #9 enforces this.

### AP-DOC-6: Manifest Treated as Deployed Truth
**Pattern:** README reports a dashboard as published or a Genie space as deployed because its manifest contains an ID or requested publication flag.
**Root cause:** A deployment record was mistaken for current API-observed state.
**Fix:** Require API readback or terminal cross-validation for deployed-state claims. Otherwise label the manifest value `RECORDED_UNVERIFIED`.

### AP-DOC-7: Intent Overwritten by Readback
**Pattern:** Documentation replaces the KPI definition, expected grain, or planned source with the deployed value and hides the difference.
**Root cause:** A global artifact hierarchy was applied instead of field-scoped authority.
**Fix:** Preserve expected and observed values, cite both sources, and record `DRIFT`; observed truth governs deployment claims while the specification/design remains the authority for intent.

### AP-DOC-8: Hardcoded Metric View Support Claim
**Pattern:** README says a window, nested join, or other Metric View feature is unsupported based on prompt text rather than the run's approved contract.
**Root cause:** Platform capability and accelerator policy were conflated.
**Fix:** Source the decision from `{OUTPUT_FOLDER}/metric_views/resolved_metric_view_capabilities.yaml`, record its version/hash and policy scope, and reconcile it with verified generation/readback results.

### AP-DOC-9: Unbound Sweep Report Treated as Ground Truth
**Pattern:** Documentation reports every asset as verified because
`ground_truth_validation.yaml` says PASS, although the file lacks
`scope_input_binding: PASS`, has no valid `scope_inputs_sha256`, or was produced for a
different expected inventory.
**Root cause:** Terminal status was checked without authenticating the immutable sweep
inputs.
**Fix:** Require the scope binding, matching lowercase 64-hex scope digest, exact inventory
parity, and the strategy-aware producer authentication above. Otherwise treat the sweep as
unavailable/drifted and preserve any independently readback-verified facts.

### AP-DOC-10: Auto Handoff Trusted Without Producer Authentication
**Pattern:** Documentation trusts auto-generated Metric View FQNs because they appear in
`step_handoff.yaml`, even though the raw handoff hash, canonical plan hash, full entry
tuples, capability tuple, or `VALID` fingerprinted producer phase does not authenticate them.
**Root cause:** The one permitted producer mutation was confused with Step-0 identity.
**Fix:** Apply the exact G-3 checkpoint checks. Route failure to `METRIC_VIEW_STAGE`; do not
repair or recreate authority during documentation.

### AP-DOC-11: Genie Quality Policy Reinterpreted
**Pattern:** The README recomputes PASS/WARN/FAIL from duplicated numbers or describes a warning as
stage PASS even though the authenticated policy assigns another status.
**Root cause:** Documentation treated prose as policy instead of authenticating the source contract,
effective snapshot, benchmark evidence, validation, and manifest tuple.
**Fix:** Report the exact frozen thresholds and selected outcome/action/stage status; preserve any
tuple or effective-hash mismatch as `DRIFT` and do not repair upstream evidence.
