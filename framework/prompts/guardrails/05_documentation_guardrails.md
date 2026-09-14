# Documentation Guardrails — Step 6 (Generate Documentation)

> **Also read:** `guardrails/00_global_rules.md` (always applies)

---

## Gates

### Ground-Truth Validation Prerequisite
`ground_truth_validation.yaml` SHOULD exist before documentation is written. It is produced by Step 5.3 (cross-validation sweep) in the master prompt orchestration, NOT by the documentation step.

**If `ground_truth_validation.yaml` exists:** Use it as the primary data source for asset status reporting.

**If `ground_truth_validation.yaml` does NOT exist:** The documentation step does NOT re-run the sweep. Instead, use available step manifests (`ddl_manifest.json`, `metric_view_manifest.json`, dashboard manifests, etc.) and note the gap in the README. DO NOT execute Python code to load `gate_checks.py` or run `run_cross_validation()` — that is Step 5.3's responsibility.

**DO NOT halt the documentation step because `ground_truth_validation.yaml` is missing.** Produce documentation from available artifacts and clearly state the limitation.

**Documentation output path:** All documentation files (README.md, architecture diagrams, etc.) MUST be written to `{OUTPUT_FOLDER}/documentation/` (i.e. `generated_outputs/{version}/documentation/`). NEVER write documentation to the project root, the user's home directory, or any location outside `generated_outputs/{version}/`.

**Directory creation:** The `documentation/` subdirectory should be created by Step 0, but if it does not exist at documentation time, create it and proceed. In Genie Code context, `os.makedirs(f"{OUTPUT_FOLDER}/documentation", exist_ok=True)` is acceptable. In App context, use the Workspace API `mkdirs` tool. Do NOT halt the documentation step because the directory is missing.

---

## Required README Sections (ALL 11 MANDATORY)

The README MUST have ALL of these sections from `05_generate_documentation.md`:

1. **Solution Overview** — domain, version, status, generation date
2. **Architecture / Asset Flow** — text diagram: ERD → Tables → MVs → Dashboards → Genie
3. **Source Schema Summary** — table listing with roles, grains, relationships
4. **Data Layer** — table/row counts, validation status
5. **Metric Views** — MV listing with source, measures, dimensions, status
6. **KPI Catalog** — EVERY KPI from spec with status and notes
7. **Not Implemented KPIs** — reference SQL for each, reason, manual implementation guide
8. **Dashboards** — ID, page count, widget count, filter count, validation status
9. **Genie Space** — ID, instruction length, question counts, status
10. **Validation Summary** — per-layer pass/fail table
11. **Generated Artifacts** — complete inventory of all output files

---

## Prohibited Actions

1. DO NOT skip reading `05_generate_documentation.md` before writing README
2. DO NOT write a flat summary instead of the structured 11-section format
3. DO NOT report assets as successfully deployed if `ground_truth_validation.yaml` shows failures
4. DO NOT omit NOT_IMPLEMENTED KPIs from the catalog
5. DO NOT omit reference SQL for NOT_IMPLEMENTED KPIs
6. DO NOT re-execute earlier pipeline stages (data layer, metric views, dashboards) to produce ground_truth_validation.yaml
7. DO NOT run any notebook that imports `dbldatagen` during documentation — that is exclusively a Step 2 dependency
8. DO NOT derive `deploy_root` independently — use the G-12 canonical path derivation from `guardrails/00_global_rules.md` (primary: read from `run_context.yaml`; fallback: 4-level `os.path.dirname` from `OUTPUT_FOLDER`)
9. DO NOT write documentation files outside `{OUTPUT_FOLDER}/documentation/` — all output stays in the versioned `generated_outputs/{version}/` folder

---

## Anti-Patterns

### AP-DOC-1: Flat README Instead of Structured Documentation
**Pattern:** Agent writes a 90-line flat summary with no artifact inventory, no architecture diagram, no per-KPI status table.
**Root cause:** Agent skipped reading `05_generate_documentation.md` entirely.
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
**Fix:** Use the G-12 canonical path derivation from `guardrails/00_global_rules.md` (primary: read from `run_context.yaml`; fallback: 4-level `os.path.dirname` from `OUTPUT_FOLDER`). Never invent step-local path derivation. Add an `assert os.path.isfile()` check before `shutil.copy2` to fail fast with a clear message.

### AP-DOC-5: Documentation Written Outside generated_outputs
**Pattern:** Documentation files (README.md, etc.) appear in the project root or user home instead of the versioned output folder.
**Root cause:** The prompt did not specify the output path, so the LLM wrote to the current working directory.
**Fix:** All documentation MUST be written to `{OUTPUT_FOLDER}/documentation/`. Prohibited Action #9 enforces this.
