The current pattern is:
LLM
  → generates config + notebook cells
      → notebook interprets config
          → validates
          → executes
          → reads back
          → writes manifests

I think eveolving to this is a betetr pattern
LLM
  → produces declarative artifact
      → deterministic validator/compiler
          → execution adapter
              → target system
          → readback/verifier
          → immutable manifest


The key distinction is that the LLM should not really be "populating a notebook." It should be producing a versioned declarative specification. The notebook should consume that specification.

Eg. 
artifact:
  type: metric_view
  name: sales_margin

source:
  catalog: prod
  schema: platinum

measures:
  - name: gross_margin
    expression: revenue - cost

dimensions:
  - segment
  - region

deployment:
  mode: create_or_replace

validation:
  required_columns:
    - revenue
    - cost
  expected_grain:
    - month
    - segment

Then the notebook/runtime translates that into actual SQL/API calls.

That gives you several advantages: reproducibility, diffability, CI/CD support, easier rollback, deterministic validation, and much less dependence on notebook structure.

The second issue I would challenge is this:
LLM generates DDL, design YAML, Genie config


For example, instead of:LLM → CREATE OR REPLACE VIEW ...

Prefer 
LLM → structured metric definition

{
  "measure": "gross_margin",
  "formula": "revenue - cost",
  "dimensions": ["segment", "region"]
}
Then: Compiler → Databricks SQL / Metric View YAML

That is much safer because you're shrinking the LLM's executable surface area.

The third issue is your guardrail placement.
Right now you have:
Template Notebook
  - gate_checks
  - verify_before_write

That's good, but I would explicitly split these into four gates, because they solve different failure classes:
Gate 1 — Structural validation
Schema-valid YAML/JSON
Required fields
No malformed configuration

Gate 2 — Metadata validation
Catalog exists
Schema exists
Columns exist
Relationships exist
Types compatible etc

Gate 3 — Semantic validation
Grain valid
KPI references valid
Join paths valid
No ambiguous dimensions
No duplicate measure definitions etc

Gate 4 — Deployment validation
Permissions
Target object state
Naming conflicts
Environment policy
Expected readback 

Only after all four pass should execution happen.

This is particularly important because "valid SQL" is not the same as "correct architecture."

A generated view can compile perfectly and still be wrong because it joins two facts at incompatible grains.

The fourth thing I would change is your error-repair model.

I would not let the LLM directly receive an arbitrary runtime exception and regenerate the notebook.
Instead
Execution Error
     ↓
Error Classifier
     ↓
Known deterministic error?
     ├── Yes → deterministic remediation / fail
     │
     └── No
          ↓
      LLM repair request

For example:
UNRESOLVED_COLUMN
→ LLM repair may be appropriate

PARSE_SYNTAX_ERROR
→ LLM repair may be appropriate

PERMISSION_DENIED
→ NEVER LLM repair

OBJECT_ALREADY_EXISTS
→ deployment policy decides

RATE_LIMIT
→ retry logic

TIMEOUT
→ retry / circuit breaker

INVALID_KPI_GRAIN
→ semantic validation failure

That prevents the LLM from "fixing" infrastructure, authorization, or governance errors.

The fifth area I would strengthen is idempotency.
Every template notebook should be rerunnable safely.
You want:
same specification
+
same environment
=
same final state

That means each artifact should have something like:
artifact_id
artifact_version
source_hash
generated_hash
environment
deployment_id
created_by
created_at
validation_status
execution_status
readback_hash

Your manifests then become much more valuable.
The manifest should not just say:
created metric_view

It should prove:
requested state
generated state
deployed state
verified state

Conceptually:
Desired State
    ↓
Generated Artifact
    ↓
Applied Artifact
    ↓
Readback Artifact
    ↓
COMPARE

If:
desired != readback

deployment fails.

That is one of the strongest parts of your design already; I would formalize it further.
I would also be careful with the phrase "Template Notebook is single point of control."

Architecturally, that sounds attractive, but I'd rename it to something like:

Deterministic Deployment Runtime

because notebooks should be an implementation vehicle, not the architectural abstraction.

Today it may be a Databricks notebook.

Tomorrow it could be:

Databricks Workflow task
Python wheel
Asset Bundle
CI/CD pipeline
Databricks App backend

## Implementation Lesson: "Copy Verbatim" Does Not Work

Telling the LLM to "copy cells 2-7 verbatim from template" reliably fails. The LLM:
- Truncates large code blocks (Gate 2b: 57 lines of column validation stripped)
- Removes "unnecessary" comments and docstrings
- "Optimizes" control flow, dropping error handling paths
- Adds extra cells it thinks are helpful

The v3 metric view deployment notebook had every cell different from the template despite
explicit "copy VERBATIM" instructions in the prompt.

The fix is architectural: templates are FILE-COPY operations, not cell-copy instructions.
The LLM reads the template as a single string, does `str.replace()` on 4 placeholders,
and uses the result unchanged. This is codified as G-16 in global rules.

This also explains why the DDL template was always rewritten from scratch — the original
template was a SQL notebook (`-- Databricks notebook source`) containing Python code,
which was structurally impossible to execute. The LLM saw this and generated its own
Python notebook every time, introducing different syntax bugs per run.

## Implementation Lesson: Config Is the Single Source of Truth for Paths

`deploy_root` and `output_folder` must be written ONCE by Step 0 into `step_handoff.yaml`,
then read verbatim by every downstream step. Prior approach had each step re-deriving
`deploy_root` via `os.path.dirname()` chains (4 levels up from OUTPUT_FOLDER), which
failed when:
- The `/Workspace` prefix differed between notebook and execute_python contexts
- `run_context.yaml` didn't actually contain `deploy_root` (it was never written there)
- The assert on `os.path.isdir(templates_dir)` killed entire steps instead of degrading

The fix: treat paths like any other config value. Step 0 computes them once, writes to
`step_handoff.yaml`, done. No derivation, no dirname chains, no environment variables.

## Implementation Lesson: Separation of Concerns Between Steps

The documentation step (Step 6) was trying to run the cross-validation sweep itself when
`ground_truth_validation.yaml` didn't exist. This required loading `gate_checks.py` via
`shutil.copy2` from the templates dir, which failed in `execute_python` context due to
path resolution issues. Every attempt to make the path resolution more robust introduced
new failure modes.

The fix: enforce separation of concerns. The cross-validation sweep is Step 5.3's job
(master prompt orchestration). The doc step only READS the artifact — it never creates it.
If it doesn't exist, the doc step documents the gap from available manifests and moves on.

This follows the same principle as the rest of the architecture: each step produces
artifacts, downstream steps consume them. No step should reach back into framework
code to compensate for a prior step's failure.

## Design Analysis: App Restart Resilience During Agent Runs

### What's Already Working (Write-Through Persistence)

The codebase has a solid write-through pattern — every event is persisted to Lakebase
as it happens, not batched:

```
Agent emits event → event_callback() → in-memory update → Lakebase write-through
                                                          (non-blocking on failure)
```

| Event Type       | In-Memory Update           | Lakebase Write-Through          |
|------------------|----------------------------|---------------------------------|
| phase_update     | step_data[step]['phases']  | persist_phase_update()          |
| tool_started/completed/failed | step_data[step]['tool_calls'] | persist_tool_call() |
| step_started     | step_data[step] created    | upsert_step(status='running')   |
| step_completed   | step_data[step] updated    | update_step(status='completed') |
| step_failed      | step_data[step] updated    | update_step(status='failed')    |
| pipeline_completed | run status finalized     | update_run_status()             |

Recovery on restart: `get_run_status()` → `_runs.get(run_id)` returns None →
`load_run_full()` reconstructs full `step_data` from Lakebase tables.

Zombie detection: if Lakebase says 'running' but no active thread exists,
status endpoint marks it 'failed' with "Interrupted: app restarted".

### The Gap: No Graceful Shutdown Hook

When gunicorn kills a worker (restart, max_requests recycle, OOM, deploy), the
Python thread running `_run_pipeline_background` is killed instantly:

- No `finally` block executes (thread is killed, not interrupted)
- No cleanup happens
- In-memory `_runs` dict is gone
- Lakebase state = whatever was last write-through persisted (this IS correct)

The **irrecoverable loss** is the LLM agent session. The agent is mid-conversation
with the model — system prompt, tool call history, in-flight reasoning. This cannot
be serialized. On restart, the current step MUST restart from scratch.

### Fix: Gunicorn worker_exit Hook + atexit

Gunicorn sends SIGTERM to workers on restart/deploy. The worker has a grace period
(30s by default) before SIGKILL. We can use this window to flush state:

```python
# gunicorn.conf.py
def worker_exit(server, worker):
    """Called when a worker is about to exit (SIGTERM grace period)."""
    from routes.pipeline_routes import _runs, _get_state_store
    store = _get_state_store()
    if not store:
        return
    for run_id, run in _runs.items():
        if run.get('status') == 'running':
            try:
                store.update_run_status(
                    run_id, 'failed',
                    error='Worker shutdown: app restarted during execution'
                )
            except Exception:
                pass  # Best-effort
```

```python
# app.py — atexit handler (covers non-gunicorn scenarios)
import atexit
def _flush_running_state():
    from routes.pipeline_routes import _runs, _get_state_store
    store = _get_state_store()
    if not store:
        return
    for run_id, run in _runs.items():
        if run.get('status') == 'running':
            try:
                store.update_run_status(
                    run_id, 'failed',
                    error='Process exit: app restarted during execution'
                )
            except Exception:
                pass
atexit.register(_flush_running_state)
```

### What This Doesn't Solve (And What Does)

The hooks above handle SIGTERM (graceful shutdown). They DON'T handle:
- SIGKILL (OOM killer, hard kill) — no signal handler runs
- Power failure / VM preemption — no code runs at all

For those cases, the zombie detection pattern already handles recovery:
1. Lakebase shows run as 'running'
2. No active thread exists for that run_id
3. Status endpoint detects this and marks as 'failed'
4. UI shows "Resume All" button

So the full resilience model is:

```
Graceful shutdown (SIGTERM)    → worker_exit hook flushes state
Ungraceful shutdown (SIGKILL)  → zombie detection on next access
Network partition / VM death    → zombie detection on next access
```

### The Real Gap: Intra-Step Resumability

The bigger design question isn't "can we detect the failure" (we can), but
"can we resume without re-running completed work."

**Current step-level resume (working):**
1. Completed steps are marked in Lakebase `steps` table
2. `get_resume_steps()` returns only non-completed steps
3. `_detect_resume_step_from_artifacts()` checks filesystem markers
4. Rerun starts from the first incomplete step

**What happens on crash mid-step:** The entire step re-runs from scratch.
But this is NOT because the LLM session is "irrecoverably lost" in some
fundamental sense. It's because the current architecture doesn't replay
what was already done within a step.

### Why LLM Session Loss Is Actually Solvable

Key architectural fact: each step starts a FRESH agent conversation (see
`agent_step.py` line 99: `self._agent.run(prompt_content=...)`). There is
no conversation carry-over between steps. Each step gets:
1. Framework prompt (loaded from file)
2. Context variables (config, paths, output_folder)
3. System supplements (API docs)

The agent doesn't need its prior conversation to resume — it needs to know
**what artifacts already exist**. The conversation is just the vehicle for
producing artifacts. If the artifacts are durable, the conversation is
replayable by starting a new one that says "these artifacts are already done."

### The Solution: Artifact-Gated Phase Skip

The approach follows our own architecture: **artifacts are the state,
not conversations.** Each phase within a step produces specific output files.
If those files exist and are valid, the phase is done.

```
Phase starts → Check: does this phase's output artifact exist?
  ├── YES → skip (log "phase already completed, artifact exists")
  └── NO  → execute normally
```

**Implementation layers:**

1. **Phase-to-artifact mapping** (config, stored in `step_phases_config`):
   ```yaml
   # Example: create_dashboards step
   phases:
     - phase_name: load_configuration
       completion_artifact: dashboards/dashboard_design.yaml
     - phase_name: profile_metrics
       completion_artifact: dashboards/dashboard_dataset_validation.yaml
     - phase_name: create_dashboard
       completion_artifact: dashboards/dashboard_manifest.json
   ```

2. **Artifact existence check** (deterministic, in PipelineRunner):
   Before the agent runs, scan the output folder for existing phase artifacts.
   Build a `completed_phases` list. Inject this into the agent's system prompt
   as a RESUME_CONTEXT block.

3. **System prompt injection** (already partially implemented via
   `_build_resume_context`):
   ```
   RESUME_CONTEXT:
     completed_phases:
       - load_configuration (artifact: dashboard_design.yaml exists, 14KB)
       - profile_metrics (artifact: dashboard_dataset_validation.yaml exists, 8KB)
     resume_from: create_dashboard
     instruction: "Skip completed phases. Their artifacts are valid and
                   already in the output folder. Start from create_dashboard."
   ```

4. **Deterministic validation** (safety net):
   The artifact check is deterministic — no LLM compliance needed. Even if
   the agent tries to redo a completed phase, the file-write tool can detect
   the artifact already exists and return early. But the prompt injection
   is the primary mechanism.

### Why This Works

- **No serialization needed.** We don't serialize the LLM session, the model's
  internal state, or the conversation history. We serialize the OUTPUTS.
- **Idempotent by construction.** If phase N's artifact exists, phase N is done.
  The LLM doesn't get to disagree.
- **Already partially built.** `get_resume_point()` exists in state_store.py.
  `_build_resume_context()` exists in pipeline.py (line 633). `resume_from`
  is plumbed through PipelineRunner. The gap is the artifact existence check
  and the phase-to-artifact mapping.
- **Crash-safe.** On app restart:
  1. Zombie detection marks the run as failed
  2. User clicks "Resume All"
  3. Completed steps are skipped (already working)
  4. The interrupted step restarts, but now with artifact-gating:
     completed phases within that step are skipped
  5. Only the phase that was in-flight at crash time re-executes

### What This Still Doesn't Solve

- **In-flight tool execution.** If the agent was mid-way through a tool call
  (e.g., CREATE TABLE was submitted but the response wasn't received), the
  tool call may have partially succeeded. The deterministic validator at the
  start of the resumed phase needs to handle this (e.g., check if the table
  exists before creating it). This is the CREATE_OR_REPLACE pattern.
- **LLM non-determinism.** A resumed step may produce different outputs than
  the original run would have. This is acceptable because the artifacts from
  completed phases are frozen — only the in-flight phase re-executes.
- **Token cost.** The resumed conversation includes the full system prompt +
  RESUME_CONTEXT, costing tokens. This is negligible compared to re-running
  the entire step.

### Implementation Status: COMPLETE

All layers implemented across 4 files:

1. **PHASE_ARTIFACT_MAP** (`pipeline.py`) — Maps each step's phases to
   their completion artifact paths. 5 steps, 26 phase-artifact pairs.
   Phases with `None` artifact always re-execute (transient, e.g. load_config).

2. **`_check_phase_artifacts()`** (`pipeline.py`) — Scans output folder via
   `WorkspaceService.file_exists()` + `read_file()` for size. Empty files
   don't count as complete. Returns per-phase existence dict.

3. **`_build_artifact_resume_context()`** (`pipeline.py`) — Builds
   RESUME_CONTEXT dict with `completed_phases`, `resume_from_phase`,
   and `instruction` text.

4. **Injection point** (`pipeline.py`, step loop) — Before each step
   executes, runs artifact check and injects RESUME_CONTEXT into
   `self._domain_context` → flows to `AgentStep.execute()` → `AgentLoop.run()`.
   Also clears stale RESUME_CONTEXT between steps.

5. **System prompt injection** (`agent_loop.py`, `_build_system_message`) —
   Phase-level RESUME_CONTEXT block with explicit RULES:
   don't write frozen artifacts, don't re-run SQL, call report_progress
   for skipped phases, start from resume_from_phase.

6. **Frozen artifacts** (`tool_executor.py`) — `set_frozen_artifacts(paths)`
   marks completed-phase artifacts as write-protected. `_handle_write_workspace_file`
   returns SKIPPED message instead of writing. Deterministic safety net.

7. **AgentStep bridge** (`agent_step.py`) — `set_frozen_artifacts()` method
   delegates to `ToolExecutor`. Called from `_execute_step` in pipeline.py.

To test: kill app mid-dashboard-creation, resume, verify only
remaining phases execute

## Implementation Lesson: py_compile Gate Must Look Past DBTITLE Lines

The `py_compile` pre-flight gate in `tool_executor.py` checks each notebook cell
for syntax errors before submitting a job run. It skips cells that start with
magic commands like `%pip`. But Databricks notebook cells often have `# DBTITLE`
comment lines BEFORE the magic command:

```
# DBTITLE 1,Install dependencies
%pip install dbldatagen --quiet
```

The old code checked only `first_line.startswith('%pip')` — but `first_line` was
the DBTITLE comment, not the `%pip`. So `py_compile` tried to compile `%pip` as
Python, which fails as a syntax error.

Fix: skip past comment lines to find the first real code line, and also add a
fallback that skips any cell containing a bare `%pip` line anywhere.

## Implementation Lesson: TRUNCATE TABLE Is Not Supported in Databricks SQL / UC

The LLM generated `TRUNCATE TABLE catalog.schema.table` which fails with
`PARSE_SYNTAX_ERROR` in Databricks SQL on Unity Catalog. `TRUNCATE` is simply
not in the Databricks SQL grammar.

Fix: three layers of defense:
1. **Prompt guardrail (G-18):** Explicit rule in `00_global_rules.md` stating
   TRUNCATE is not supported, with the correct alternative (`DELETE FROM`).
2. **Prompt fix:** Replaced all "use TRUNCATE" advice in `00_master_prompt.md`
   and `01_create_data_layer.md` with `DELETE FROM`.
3. **Tool-level pre-flight:** `_handle_execute_sql` in `tool_executor.py` now
   blocks statements starting with TRUNCATE (and VACUUM) before they reach the
   SQL warehouse, returning an actionable error message.

## Implementation Lesson: Join Fanout From Missing pk_cols in Dimension Tables

Validation check 7.7 caught: `Join fanout detected: 9,000 detail rows joined
to 1,800,000 rows` — a 200x row multiplication.

Root cause: the LLM omitted `pk_cols` for a dimension/lookup table in
`synthetic_data_spec.yaml`. The `generate_table()` function in the dbldatagen
template only enforces PK uniqueness when `pk_cols` is provided (lines 453-468).
Without it, dbldatagen generates random values that may collide. When the fact
table's FK column joins to this non-unique dimension PK, every FK value matches
multiple dimension rows — producing cartesian-like fanout.

The math: if a dimension table has 200 rows but only ~45 distinct PK values
(due to collisions), each FK lookup returns ~4.4 rows instead of 1. For 9,000
fact rows: 9,000 × 200 = 1,800,000.

Fix: three layers:
1. **Guardrail (AP-DL-7):** New anti-pattern in `01_data_layer_guardrails.md`
   with root cause, detection pattern, and repair action.
2. **Prohibited actions #25-26:** Every dimension table MUST have `pk_cols`;
   never proceed past check 7.7 if `after_rows > before_rows`.
3. **Existing defense (validation check 7.7):** Already catches the fanout and
   prevents `overall_status: PASS`. The gap was the LLM's spec generation, not
   the validation. The guardrail tells the LLM WHY it must always specify PKs.

## Implementation Lesson: Zombie Phase Normalization After App Crash

When the app crashes mid-step, zombie detection correctly marks the **run** as
failed and the **step** as failed. But it does NOT touch **phase** records in
Lakebase. Phases that were `running` at crash time remain `running`.

The `get_run_status()` endpoint had normalization for completed steps (if step
is completed, all phases must be completed too) but NOT for failed steps. Result:
the UI shows all phases of a failed step as "In Progress" simultaneously, which
looks like parallel execution. The identical "WHAT'S HAPPENING" content across
phases confirms they are stale — the same pre-crash agent file reads displayed
in every phase panel.

Fix: added `elif step_status == 'failed':` normalization in `get_run_status()`
that changes any `running` phase to `failed`. This ensures the UI shows the
correct terminal state after app restart.

## Implementation Lesson: Resume Button Shows for Completed Versions (Stale Lakebase Runs)

The KPI Domains page showed "Resume v9 (failed)" even though v9 was `completed`
in `version_registry.yaml`. Two bugs:

**Bug 1: Stale fallback overrides authoritative source.** The `checkResumableRun()`
function had three layers: version-status endpoint (primary), Lakebase runs API
(fallback), and localStorage (last resort). When the primary source correctly said
`is_resumable: false` (v9 completed), the function fell through to the Lakebase
fallback which found an earlier FAILED run for the same domain and showed the
resume button anyway.

Fix: when version-status endpoint responds successfully and says `is_resumable: false`
for an existing version, trust it and return immediately. Only fall through to
Lakebase when the version-status endpoint is unreachable.

**Bug 2: "Run Pipeline" reused failed version instead of creating fresh.** The
`launchPipeline()` function sent `version_mode: 'auto'` (the default). In auto
mode, the resolver only resumes `running` versions, but if there's a zombie entry
still marked `running` in the registry (from a crash that wasn't cleaned up), it
resumes that instead of creating a new version.

Fix: `launchPipeline()` now explicitly sends `version_mode: 'fresh'`, which always
creates a new version. The Resume button retains `version_mode: 'retry'` for
intentional failure recovery. Clean separation of concerns:

| Button | version_mode | Behavior |
|--------|-------------|----------|
| Run Pipeline | `fresh` | Always creates v(N+1) |
| Resume vN (failed) | `retry` | Resumes the latest failed version |

## Implementation Lesson: Asset Counts Showing 0 on Domain Card (G-15 Again)

The KPI Domains card showed `0 tables, 0 views, 0 dashboards` despite v9 having
12 tables, 4 views, 2 dashboards, and 1 genie space. Three bugs in
`_get_latest_version_info()` in `domain_routes.py`:

1. **`SHOW TABLES LIKE '%_v9'`** — uses SQL `%` wildcard but `SHOW TABLES LIKE`
   expects glob `*`. Returns 0 rows. This is AP-DL-4 / G-15 striking in the
   app's own code, not just in LLM-generated SQL.
   Fix: `LIKE '*_v9'`.

2. **`ObjectType.DASHBOARD_V3`** — the SDK returns `ObjectType.DASHBOARD` for
   Lakeview dashboards (`.lvdash.json` files), not `DASHBOARD_V3`.
   Fix: check for both `ObjectType.DASHBOARD` and `.lvdash.json` extension.

3. **Genie counting worked** — `_manifest.json` pattern matched correctly.
   No fix needed.

## File Preview UX Overhaul (Fix 7 Continuation)

Three changes to the file preview feature in `domains.html`:

1. **Full-screen view replaces modal overlay.** Clicking "View" hides the entire
   `.domains-page` div and shows a sibling `.file-preview-page` div that fills the
   viewport. Back button / ESC restores the domains page. No popup, no dialog —
   works naturally on phones and iPads.

2. **ERD zoom controls.** Toolbar shows −/+/Fit buttons when previewing images.
   Zoom levels: 25% → 50% → 75% → 100% → 125% → 150% → 200% → 300% → 400%.
   CSS `transform: scale()` on the image with `transform-origin: top center`.

3. **Proper markdown rendering.** Multi-pass block-aware renderer replacing the
   regex-chain approach. Phase 1 extracts fenced code blocks into placeholders,
   Phase 2 escapes HTML, Phase 3 does inline formatting (bold, italic, code,
   links, images), Phase 4 does block-level line-by-line parsing (headers,
   blockquotes, tables, lists, paragraphs). GitHub-style CSS: dark code blocks
   (#1e1e2e), bordered h1/h2 underlines, striped table rows, tinted blockquotes.

4. **YAML file preview with syntax highlighting.** `.yaml`/`.yml` files now
   viewable. Backend already served them as text (fallthrough in `get_input_file`).
   Frontend `highlightYaml()` does line-by-line tokenization with 7 token types:
   keys (blue), string values (green), numbers (orange), booleans/null (red),
   comments (gray italic), list dashes (yellow), anchors/aliases (purple).
   Dark theme matching the markdown code blocks.

## Pipeline Monitor Timer/Duration Fixes

Three bugs in `pipeline_monitor.html`:

1. **Duration showed during run.** `updateTimer()` was continuously writing elapsed
   time to the Duration field. Duration should only appear once the run reaches a
   terminal state (completed/failed/cancelled). Fix: Duration `<div>` starts with
   `display:none`, becomes visible only in the terminal-state handler.

2. **Negative elapsed time (`-4:xx:xx`).** Backend stores `started_at` as
   `datetime.utcnow().isoformat()` — bare ISO without timezone suffix. Browser's
   `new Date('2025-01-15T12:00:00')` parses this as **local time**, not UTC. If
   the user's timezone is behind UTC (e.g. US Pacific = UTC-7), the parsed time
   is ~7 hours in the future relative to the actual start, producing negative
   elapsed seconds. Fix: append `'Z'` before parsing to force UTC interpretation.
   Also added `Math.max(0, ...)` as a safety floor.

3. **Duplicate elapsed timer.** Elapsed was shown in both the top-bar header and
   the bottom status bar. Removed the header copy (`elapsed-timer`) — one display
   in the status bar is sufficient.

## Implementation Lesson: Gate Assertion Failures Must Be LLM-Repairable, Not Critical Halt

**Error:** `Gate 2b FAILED: column references not found in source table:
member_claims_enrollment_metric_view_v10`

**Root cause:** The LLM hallucinated a column `mbr_enr_product_id` in the enrollment
metric view spec. The actual `fact_member_enrollment_v10` table has 25 columns but
`mbr_enr_product_id` is not one of them. Gate 2b correctly caught this.

**Why the pipeline halted instead of self-correcting:** The error classifier
(`classify_error()` in `agent_loop.py`) didn't match any known pattern for
`AssertionError: Gate 2b FAILED...`. It fell through to `UNKNOWN`. The UNKNOWN
handler checks if the tool is in `CRITICAL_TOOLS` — and `execute_notebook` IS
critical — so `is_critical = True` → immediate pipeline halt.

But gate assertion failures ARE LLM-repairable: the LLM can read the error
("column 'source.mbr_enr_product_id' not in source"), remove the hallucinated
column from the metric view spec, regenerate the notebook, and retry.

**Fix:** Added gate failure patterns to `ERROR_CLASSIFICATION['LLM_REPAIRABLE']`:
- `"Gate 2b FAILED"` — column reference validation
- `"Gate 2 FAILED"` — source table accessibility
- `"Gate 3 FAILED"` — semantic validation (duplicate measures, grain)
- `"AssertionError: Gate"` — catch-all for any gate assertion

With this fix, the error classifier returns `LLM_REPAIRABLE` before reaching
the UNKNOWN handler. The LLM gets the error as tool output and can self-correct.

**Key principle (from the error repair model in this doc):**
```
Gate assertion failures (hallucinated columns, spec errors)
    → LLM repair IS appropriate

Permission/infrastructure errors
    → NEVER LLM repair (correctly classified as DETERMINISTIC_FAIL)
```

### Root Cause: ERD → table_spec Column Drop + Greenfield Fast Path

The hallucination is NOT the LLM inventing a column from nothing. The column
`mbr_enr_product_id` has a legitimate provenance chain with a gap in the middle:

```
1. ERD image (user input)      → mbr_enr_product_id ✅ (32 observed columns)
2. table_spec (Step 1 LLM)     → mbr_enr_product_id ❌ DROPPED (only 25 of 32 kept)
3. Actual table (CREATE TABLE) → mbr_enr_product_id ❌ (never created — follows spec)
4. schema_profile (Step 2 LLM) → mbr_enr_product_id ✅ RE-INTRODUCED
5. metric_view_spec            → source.mbr_enr_product_id in "Product Id" field
6. Gate 2b                     → ❌ CAUGHT — column not in actual table
```

The column existed in the ERD image (the vision model correctly read it from the
diagram). Step 1 dropped 7 of 32 ERD columns when generating `table_spec.yaml`
(including `mbr_enr_product_id`, plus 6 others like `mbr_enr_group_ck`,
`mbr_enr_subgroup_code`, etc.). The actual table was created from table_spec,
so it has 25 columns.

The critical failure is at Step 4: the **Greenfield Fast Path** in
`02_create_metric_views.md` (lines 257-267) tells the LLM:

> "Read contracts directly (DO NOT run DESCRIBE TABLE individually)"
> "Write schema_profile.yaml from contracts"

But which contracts? The prompt says "erd_parsed.yaml + semantic_model.yaml".
The LLM read the ERD (which has 32 columns including `mbr_enr_product_id`) and
wrote it into `schema_profile.yaml` as a dimension — even though the actual
table only has 25 columns.

The schema_profile is SUPPOSED to reflect reality (what's actually in the catalog).
The Greenfield Fast Path optimization short-circuits reality-checking by reading
contracts instead of running DESCRIBE. This creates a trust gap:

```
ERD (32 cols) → table_spec (25 cols) → Actual table (25 cols)
                                            │
ERD (32 cols) → schema_profile (includes the 7 dropped cols!)
                    │
                    └─→ metric_view_spec (references the phantom column)
```

The schema_profile should have been derived from table_spec (which matches the
actual table) or from DESCRIBE TABLE — NOT from the ERD directly.

**Systemic impact:** 3 of 8 tables had hallucinated columns in the profile:
- `dim_member_v10`: 4 phantom columns (mbr_current_pcp_eff_date, mbr_deceased_date,
  mbr_extract_date, mbr_line_of_business_name)
- `fact_member_enrollment_v10`: 1 phantom column (mbr_enr_product_id)
- `fact_claim_detail_v10`: 3 phantom columns (clm_dtl_apl_posting_date,
  clm_dtl_check_date, clm_dtl_last_update_date)

**Fix applied (3 changes to `02_create_metric_views.md`):**

1. **Input Authority table** — Changed column authority from
   `Physical schema (DESCRIBE TABLE / erd_parsed.yaml)` to
   `table_spec.yaml (Step 1 output)`. Added explicit note that
   `erd_parsed.yaml` is for semantic context only, NOT column lists.

2. **Greenfield Fast Path rewrite** — Step 1 now reads `table_spec.yaml`
   for columns (not ERD). Added CRITICAL warning block explaining why
   ERD columns must not be used (they include columns dropped during DDL
   generation). Added column authority chain diagram:
   ```
   erd_parsed.yaml (N cols) → table_spec.yaml (≤N cols) → CREATE TABLE
                                     ↑
                              USE THIS for schema_profile
   ```

3. **Prohibited action #2 strengthened** — "DO NOT invent columns" now
   explicitly says to use `table_spec.yaml` and NOT to trust `erd_parsed.yaml`
   for column names.

**Defense in depth (already in place):**
- **Gate 2b** catches phantom columns at metric view deployment time
- **LLM_REPAIRABLE classification** (added this session) lets the pipeline
  self-correct instead of halting on Gate 2b failures
- The prompt fix prevents the hallucination from entering the pipeline at all
- **GATE 2.2** (added): post-profile DESCRIBE cross-check runs immediately
  after `schema_profile.yaml` is written. DESCRIBEs every source table and
  compares actual catalog columns against the profile's dimension/key/measure/
  temporal lists. Phantom columns are self-healed (dropped from profile, logged)
  without halting. Registered in `06_state_contract.md` as `cross_check_profile`
  phase and in `pipeline.py` PHASE_ARTIFACT_MAP with `None` artifact (always
  re-runs since it's a cheap single-SQL verification step)

## Error Classifier: Broadened AssertionError to LLM_REPAIRABLE

**Error:** `AssertionError: Unbalanced datatype: DECIMAL(28` in the DDL notebook.

The vision model truncated `DECIMAL(28,4)` to `DECIMAL(28` in `erd_parsed.yaml`.
The DDL template has an auto-repair gate (lines 70-93) that fixes unbalanced
parentheses before the assertion fires. But the LLM generated the notebook from
scratch instead of using the template (AP-DL-5 / G-16 violation), so the repair
code was absent and the raw assertion fired.

The error classifier had `"AssertionError: Gate"` as the LLM_REPAIRABLE pattern,
but this error doesn't contain "Gate" — it says "Unbalanced datatype". So it
fell through to UNKNOWN → critical halt.

**Fix:** Replaced the four specific gate patterns (`Gate 2 FAILED`,
`Gate 2b FAILED`, `Gate 3 FAILED`, `AssertionError: Gate`) with a single
broad pattern: `"AssertionError"`. Rationale: ALL AssertionErrors from template
notebooks are validation gates — structural, metadata, semantic, or deployment
checks. They always catch LLM spec errors (hallucinated columns, bad types,
missing fields). Infrastructure errors use different exception types
(`PermissionDenied`, `RuntimeError`, etc.) and are classified separately as
`DETERMINISTIC_FAIL`. The broad pattern eliminates whack-a-mole on individual
gate message strings.

## Tool Enforcement: `deploy_from_template` Replaces Manual File-Copy

**Problem:** G-16 said "file-copy the DDL template" but relied on the LLM to:
1. `read_workspace_file(template)` → get template content
2. Do `str.replace()` on placeholders
3. `import_notebook(path, result)` → import the result

The LLM consistently skipped step 1 and generated notebooks from scratch (AP-DL-5).
The `import_notebook` tool accepted any content — no enforcement that it came from
a template. The DECIMAL(28 error happened because the from-scratch notebook lacked
the template's auto-repair gate (lines 70-93).

**Fix: New `deploy_from_template` tool** (`tool_executor.py`):
```
LLM calls:
  deploy_from_template(
    template_path = ".../framework/templates/ddl_notebook.py.template",
    output_path   = ".../generated_outputs/v1/notebooks/ddl_member_claims.py",
    placeholders  = {"DOMAIN_NAME": "member_claims", "OUTPUT_FOLDER": "...", ...}
  )

Tool does:
  1. read_file(template_path)           ← verbatim read
  2. str.replace() for each placeholder ← deterministic
  3. check for unreplaced {{...}}       ← validation
  4. import_notebook(output_path, ...)  ← guaranteed template content
```

**Three layers of enforcement:**
1. `deploy_from_template` tool does the copy — LLM never touches template content
2. `import_notebook` rejects paths containing template stems (ddl\_, metric\_view\_, etc.)
3. Tool validates no unreplaced placeholders remain — catches missing values

Templates with per-table custom cells (dbldatagen) still use `import_notebook`
since the LLM must add generation cells on top of the template base. Those paths
don't contain the blocked stems.

**Files changed:**
- `tool_executor.py`: `_handle_deploy_from_template()`, `_TEMPLATE_STEMS` guard in
  `_handle_import_notebook()`
- `tools.py`: `deploy_from_template` tool definition with full parameter schema
- `01_create_data_layer.md`: Step 4 now calls `deploy_from_template` with placeholder dict
- `02_create_metric_views.md`: Deploy section now calls `deploy_from_template`
- `00_global_rules.md`: G-16 rewritten from "File-Copy" to "Use `deploy_from_template`"

## dbldatagen Template: OUTPUT_FOLDER Was os.environ, Not a Placeholder

**Error:** Empty tables after DDL. Notebook ran but generated no data.

**Root cause chain:**
1. The DDL template uses `{{OUTPUT_FOLDER}}` as a **placeholder** (line 30:
   `SPEC_PATH = "{{OUTPUT_FOLDER}}/table_spec.yaml"`). At deploy time,
   `deploy_from_template` replaces `{{OUTPUT_FOLDER}}` with the actual path.
2. The dbldatagen template used `os.environ.get("OUTPUT_FOLDER", "")` as a
   **runtime env var** (line 500). But `execute_notebook` (Jobs API) doesn't
   set this env var → resolves to `""` → `SPEC_PATH = "synthetic_data_spec.yaml"`
   (relative path) → `os.path.exists()` = False → template falls back to
   "LLM-populated cells" (which are commented-out examples) → no data generated.

**Fix:** Replaced `os.environ.get("OUTPUT_FOLDER", "")` with `{{OUTPUT_FOLDER}}`
placeholder in `dbldatgen_notebook.py.template`. Both references (spec path at
line 500 and manifest path at line 595) now use the placeholder. The template
now has 5 placeholders: `DOMAIN_NAME`, `OUTPUT_FOLDER`, `SOURCE_CATALOG`,
`SOURCE_SCHEMA`, `VERSION_SUFFIX`.

Also updated `01_create_data_layer.md` Step 5 (synthetic data) to include
explicit `deploy_from_template` call with all 5 placeholder names.

## DELTA_EXCEED_CHAR_VARCHAR_LIMIT Added to LLM_REPAIRABLE

**Error:** `[DELTA_EXCEED_CHAR_VARCHAR_LIMIT] Value "FME-00000001" exceeds
char/varchar type length limitation`

Generated data value is longer than the `CHAR(8)` / `VARCHAR(n)` column type.
The LLM can fix by widening the column in `table_spec.yaml` or adjusting the
spec to generate shorter values. Added `DELTA_EXCEED_CHAR_VARCHAR_LIMIT`,
`DELTA_CONSTRAINT_VIOLATION`, and `CHECK_CONSTRAINT_VIOLATED` to
`ERROR_CLASSIFICATION['LLM_REPAIRABLE']` in `agent_loop.py`.

Also added AP-DL-8 to `01_data_layer_guardrails.md`: prefer `STRING` over
`CHAR(n)`/`VARCHAR(n)` unless a specific length is required by the ERD.

## step_handoff.yaml: sql_fqn Backtick Normalization

Error: Dashboard step halted because step_handoff.yaml had unquoted sql_fqn
values (catalog.schema.view instead of backtick-quoted 3-part names) and was
missing warehouse_id and parent_path.

Root cause: Metric view step wrote sql_fqn without backticks. Dashboard prompt
had strict rule: "If values look wrong, HALT." LLM correctly followed the halt
instruction instead of normalizing.

Fix: Added normalization section to both 03_create_dashboards.md and
04_create_genie_space.md. Three normalizations applied before use:
1. sql_fqn: split on dot, wrap each segment in backticks
2. warehouse_id: fallback to accelerator.yaml
3. parent_path: derive from output_folder + /dashboards
Removed the "HALT if wrong" rule for format issues. Now: normalize and proceed.

## lakeview_dashboard_helpers Stored as Notebook, Not File

**Error:** `ModuleNotFoundError: No module named 'lakeview_dashboard_helpers'`

**Root cause:** `lakeview_dashboard_helpers.py` was stored as `ObjectType.NOTEBOOK`
in the workspace (Databricks auto-detects `# Databricks notebook source` header
and stores as notebook). The dashboard template does
`sys.path.insert(0, templates_dir)` then `from lakeview_dashboard_helpers import ...`.
Python's import system looks for `.py` files on `sys.path`, but notebook objects
don't appear as `.py` files on the filesystem — they're stored without extension
as notebook objects. So `import` fails.

**Fix:** Deleted the notebook object, stripped the `# Databricks notebook source`
header, and recreated as `ObjectType.FILE` at `lakeview_dashboard_helpers.py`.
All 811 lines, valid Python, all 6 key functions verified present. The other
helper files (`gate_checks.py`, `erd_validation_utils.py`) were already plain files.

**Why it was never hit before:** The LLM previously generated dashboard notebooks
from scratch (AP-DL-5 pattern), bypassing the template entirely. The template's
import mechanism was never exercised until `deploy_from_template` enforcement.

## Dashboard Template: Missing warehouse_id Arguments

**Error 1:** `TypeError: describe_metric_view() missing 1 required positional argument: 'warehouse_id'`

**Error 2:** `RuntimeError: Dataset 'ds_...' SQL FAILED: is not a valid endpoint id.`

**Root cause:** Two function calls in `dashboard_notebook.py.template` omitted
the `warehouse_id` argument, despite `WAREHOUSE_ID` being defined at line 44:

| Call site | Before | After |
| --- | --- | --- |
| Line 124 | `describe_metric_view(fqn)` | `describe_metric_view(fqn, WAREHOUSE_ID)` |
| Line 202 | `build_validated_dataset(name, sql)` | `build_validated_dataset(name, sql, warehouse_id=WAREHOUSE_ID)` |
| Line 433 | `deploy_dashboard(..., warehouse_id=WAREHOUSE_ID)` | Already correct |

**Fix:** Added `WAREHOUSE_ID` to both calls. Also made `warehouse_id` a
keyword-only required argument in `build_validated_dataset` (`*, warehouse_id: str`)
so future callers that omit it get a clear `TypeError` instead of a runtime
"not a valid endpoint id" error.

## Dashboard Template: is_measure Detection Wrong for Metric Views

**Error:** `[METRIC_VIEW_MISSING_MEASURE_FUNCTION]` — measure columns selected
without `MEASURE()` wrapping.

**Root cause chain:**
1. `describe_metric_view()` detects measures by checking if `data_type` is in
   `('bigint', 'double', 'decimal', ...)` — exact string match.
2. But `DESCRIBE TABLE` on a metric view returns `'bigint measure'`,
   `'decimal(38,2) measure'` — with a `" measure"` suffix.
3. Exact match failed → all 20 measure columns classified as dimensions →
   `is_measure=False` for everything → `COLUMN_REGISTRY` has 30 "dimensions", 0 measures.

**Fix in `lakeview_dashboard_helpers.py`:**
```
# Old: is_measure = data_type.lower() in ('bigint', 'double', ...)
# New: is_measure = ' measure' in data_type.lower()
```
Now correctly identifies 10 dimensions and 20 measures.

## Dashboard Template: Metric View Dataset SQL Requires MEASURE() + GROUP BY

**Error:** Dashboards show "unable to render" after successful deployment.

**Root cause:** The dataset SQL was `SELECT * FROM metric_view`. Lakeview
executes dataset SQL as-is. For metric views, `SELECT *` fails with
`METRIC_VIEW_MISSING_MEASURE_FUNCTION` because measure columns require
`MEASURE()` wrapping. Lakeview displays this as "unable to render."

The template's `build_mv_dataset` originally did:
```
sql = f"SELECT * FROM {mv_fqn}"  # ← FAILS for metric views
```

**Fix:** `build_mv_dataset` now uses `COLUMN_REGISTRY` (from `describe_metric_view`)
to build correct SQL — dimensions selected directly, measures wrapped in
`MEASURE()`, with `GROUP BY` on all dimensions:
```
SELECT `dim1`, `dim2`, ...,
       MEASURE(`measure1`) AS `measure1`, MEASURE(`measure2`) AS `measure2`, ...
FROM `catalog`.`schema`.`metric_view`
GROUP BY `dim1`, `dim2`, ...
```

Also fixed backtick pollution: `mv_fqn.split(".")[-1]` left backticks in dataset
names when `sql_fqn` was backtick-quoted. Fixed with `mv_fqn.replace("\`", "").split(".")[-1]`.

**All four dashboard template bugs were dormant** because the LLM previously
generated dashboard notebooks from scratch. Enforcing `deploy_from_template`
surfaced them. Once fixed, the templates are more reliable than LLM-from-scratch
because the logic is tested and deterministic.

**Files changed:**
- `lakeview_dashboard_helpers.py`: Converted NOTEBOOK→FILE; fixed `is_measure`
  detection; made `warehouse_id` required in `build_validated_dataset`
- `dashboard_notebook.py.template`: Added `WAREHOUSE_ID` to `describe_metric_view`
  and `build_validated_dataset` calls; rewrote `build_mv_dataset` to produce
  correct metric view SQL with `MEASURE()` + `GROUP BY`; fixed backtick-strip
  in `mv_short` derivation

## Dashboard Template: Widget/Page Names Must Be Alphanumeric

**Error:** `InvalidParameterValue: validation failed: [resource names should only
contain alphanumeric characters (a-z, A-Z, 0-9), hyphens (-), or underscores (_)
[widget-0-Total Claims]`

**Root cause:** The `build_widget_from_spec` function in the dashboard template
constructed widget names as `widget-{idx}-{measure.replace('_', '-')}`. When the
LLM-generated `dashboard_design.yaml` used display-style measure names with spaces
(e.g., `"Total Claims"` instead of `"total_claims"`), the spaces passed through
to the Lakeview API which rejects them.

Same issue for page names: `page_title.lower().replace(' ', '_')` didn't strip
other special characters (parentheses, ampersands, quotes, etc.).

**Fix:** Both widget names and page names now use `re.sub(r'[^a-zA-Z0-9_-]', '', ...)`
to strip all characters not in the Lakeview-allowed set. This is defensive —
whatever the LLM puts in the design spec, the template produces valid resource names.

**Files changed:**
- `dashboard_notebook.py.template`: Added `import re` to imports; widget name uses
  `re.sub` sanitization; page name uses `re.sub` sanitization

So this is how it will look finally 
                  GENERATION PLANE
┌─────────────────────────────────────────────┐
│                    LLM                      │
│                                             │
│ Prompt + architecture standards             │
│ ERD / KPI specification / step handoff      │
│                                             │
│ Produces                                    │
│ ────────                                    │
│ Declarative artifact specification          │
│ + rationale / metadata                      │
└────────────────────┬────────────────────────┘
                     │
                     ▼
                 CONTRACT
         JSON / YAML / typed schema
                     │
                     ▼
                  CONTROL PLANE
┌─────────────────────────────────────────────┐
│ Deterministic Validator / Compiler          │
│                                             │
│ 1. Schema validation                        │
│ 2. Metadata validation                      │
│ 3. Semantic validation                      │
│ 4. Security / policy validation             │
│ 5. Generate executable artifacts            │
└────────────────────┬────────────────────────┘
                     │
                     ▼
                 EXECUTION PLANE
┌─────────────────────────────────────────────┐
│ Deployment Runtime                          │
│                                             │
│ Statement Execution API                     │
│ Genie API                                   │
│ Lakeview API                                │
│ UC APIs                                     │
│ Other Databricks APIs                       │
└────────────────────┬────────────────────────┘
                     │
                     ▼
                 VERIFICATION
┌─────────────────────────────────────────────┐
│ API Readback + Runtime Validation            │
│                                             │
│ Desired state vs deployed state              │
│ Smoke tests                                  │
│ Benchmark/evaluation tests                   │
│ Security checks                              │
└────────────────────┬────────────────────────┘
                     │
                     ▼
                  MANIFEST
         immutable deployment evidence


## Fix 26: Genie Space serialized_space Uses Wrong data_sources Key

**Error:** `BadRequest: The zip archive contains no items`

**Root cause:** The LLM rewrote the `build_serialized_space` helper function
instead of copying it verbatim from the template. It used `"data_sources": {"tables": ...}`
instead of `"data_sources": {"metric_views": ...}`. The Genie API v2 expects the
`"metric_views"` key. Using `"tables"` causes the API to try to package file-based
table attachments into a zip archive, but UC metric views are not files — the zip
is empty.

**Fix:**
1. Fixed generated v9 notebook Cell 9: `"tables"` -> `"metric_views"`, removed `column_configs`
2. Added format validation guard in Cell 10 (Create/Update Space) that asserts
   `data_sources` contains `"metric_views"` (not `"tables"`) before the API call
3. Added same guard to the template `genie_space_notebook.py.template`
4. Documented as AP-GN-4 in `04_genie_guardrails.md` plus prohibited actions #18-20

**Lesson:** The LLM continues to rewrite helper functions instead of copying
them verbatim. Adding runtime assertions in the API call cell (which the LLM
is less likely to rewrite) catches these deviations before they reach the API.
