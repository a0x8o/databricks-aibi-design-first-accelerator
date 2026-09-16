# Global Guardrails — Apply to ALL Pipeline Steps

These rules are BINDING for every step. Violations are pipeline failures.

---

## G-0: Three-Plane Architecture (MANDATORY)

All pipeline steps follow the three-plane architecture defined in `00_master_prompt.md`:

1. **Generation Plane**: LLM produces declarative artifact specifications (YAML/JSON) — NEVER raw SQL, API calls, or executable code
2. **Control Plane**: Deterministic validator/compiler runs four gates before execution
3. **Execution Plane**: Deterministic Deployment Runtime executes via platform APIs
4. **Verification**: API readback + desired-state vs deployed-state comparison
5. **Manifest**: Immutable deployment evidence with hash chain

**The LLM's executable surface area is minimized.** It writes domain logic (measure expressions, column mappings, widget configs). It does NOT write structural SQL (CREATE TABLE, JOIN syntax) or make API calls directly. The compiler/runtime handles all structural concerns.

---

## G-0.1: Four-Gate Validation Model (MANDATORY)

Every declarative artifact MUST pass four gates before execution:

| Gate | Validates | Failure Action |
|------|-----------|----------------|
| Gate 1: Structural | Schema-valid YAML/JSON, required fields, no malformed config | Regenerate spec |
| Gate 2: Metadata | Catalog/schema/columns exist, types compatible, relationships exist | LLM repair (fix references) |
| Gate 3: Semantic | Grain valid, KPI references valid, join paths safe, no fanout, no ambiguous dimensions | LLM repair (fix architecture) |
| Gate 4: Deployment | Permissions, naming conflicts, environment policy, expected readback | Deterministic fail (infrastructure) |

**"Valid SQL" is NOT the same as "correct architecture."** A generated view can compile perfectly and still be wrong because it joins two facts at incompatible grains. Gate 3 catches what SQL compilation cannot.

---

## G-0.2: Error Classification (MANDATORY)

Runtime failures are classified before routing to remediation:

| Error Pattern | Routing | Why |
|---------------|---------|-----|
| PARSE_SYNTAX_ERROR, UNRESOLVED_COLUMN | LLM repair | Generation error — fix the spec |
| PERMISSION_DENIED, RESOURCE_EXHAUSTED, QUOTA_EXCEEDED | Deterministic fail | Infrastructure — LLM cannot fix |
| RATE_LIMIT, TIMEOUT | Retry with backoff (max 3) | Transient — retry, then fail |
| OBJECT_ALREADY_EXISTS | Deployment policy (idempotency check) | May be expected state |
| INVALID_KPI_GRAIN, FANOUT_RISK | Semantic validation fail | Gate 3 should have caught this |
| INTERNAL_ERROR | Deterministic fail | Platform issue — escalate |

The LLM must NEVER attempt to "fix" infrastructure, authorization, or governance errors.

---

## G-1: Manifest Integrity (API Readback Required)

All deployment manifests (`*_manifest.json`, `genie_manifest.json`) MUST be produced using **API readback validation**, not agent self-reporting.

**Required fields in every manifest:**
```yaml
validation_source: api_readback   # MUST be "api_readback" — never "agent_reported"
```

**Manifest writing procedure (NON-NEGOTIABLE):**
1. Deploy the asset via the API (create + publish for dashboards, POST for Genie)
2. Call `validate_dashboard_from_api()` or `validate_genie_from_api()` from `gate_checks.py`
3. Confirm the readback returns `status: PASS`
4. Write the manifest using **counts from the API readback**, NOT from agent memory
5. Include `validation_source: api_readback` in the manifest

**A manifest that claims success without API readback is FRAUD.** This is the #1 cause of pipeline failures: the agent writes `published: true` and `sample_questions_count: 10` without ever reading the deployed asset back, and the actual asset is empty.

**State checkpoint impact:**
- Manifest with `validation_source: api_readback` → trust and skip
- Manifest WITHOUT `validation_source` → re-run API readback validation before skipping
- No manifest → execute from the beginning

---

## G-2: MEASURE() Syntax Enforcement

All KPI queries against metric views MUST use `MEASURE()` syntax, never raw `SUM()`/`COUNT()`/`AVG()`.

```sql
-- CORRECT
SELECT claim_type, MEASURE(total_paid_amount) FROM metric_view GROUP BY ALL

-- WRONG — bypasses metric view semantics
SELECT claim_type, SUM(total_paid_amount) FROM metric_view GROUP BY claim_type
```

This applies to:
- Dashboard dataset SQL
- Genie example SQL
- Documentation sample queries
- Cross-validation sweep queries

---

## G-3: Column Name Authority (DESCRIBE Is Truth)

Physical column names MUST come from `DESCRIBE TABLE {metric_view_fqn}` (runtime) or `erd_parsed.yaml` (greenfield DDL), NOT from spec text, KPI descriptions, or agent memory.

**Why:** Metric view DDL uses aliases that differ from source table column names (e.g., `clm_dtl_claim_type` → `claim_type`, `clm_dtl_specific_dos_date` → `service_date`). Dashboard SQL must use metric view aliases, not source names.

**Enforcement:**
- `describe_metric_view()` in helpers template → returns actual columns
- `validate_column_refs()` → asserts all references exist
- `validate_domain_cols()` in dbldatagen template → asserts column names match schema

---

## G-4: Deterministic Deployment Runtime (Always Use, Never Hand-Write)

All deployment artifacts MUST be built using the Deterministic Deployment Runtime (template notebooks that consume declarative specs). The LLM produces the declarative spec; the runtime handles compilation, validation, and execution. Never hand-write:
- DDL SQL → produce `table_spec.yaml`, let compiler generate CREATE TABLE
- Dashboard widgets → produce `dashboard_design.yaml`, let template build Lakeview JSON
- Genie spaces → produce `genie_space_config.yaml`, let template call Genie API
- Metric views → produce `metric_view_spec.yaml`, let template call Statement Execution API
- Synthetic data → produce `synthetic_data_spec.yaml`, let template run dbldatagen

**Why:** Hand-written JSON/SQL consistently omits required fields (e.g., `queryName` in filter widgets, commas in DDL). Template functions include these fields unconditionally. Declarative specs are diffable, reproducible, and CI/CD-friendly.

---

## G-5: No Silent Failures

NEVER catch and ignore errors during:
- SQL execution (dataset validation, metric view creation)
- API calls (dashboard create/publish, Genie space POST)
- Gate check assertions

If a step fails, it MUST either:
1. Raise an exception that halts the pipeline, OR
2. Write a FAIL status to the step's validation artifact

Catching an error and proceeding as if it succeeded is a pipeline violation.

---

## G-6: No Stage Re-Execution During Later Stages

NEVER re-run an earlier pipeline stage during a later stage:
- Do NOT re-run data layer notebooks during dashboard/Genie/documentation steps
- Do NOT re-create metric views during dashboard creation
- Do NOT regenerate synthetic data to fix a dashboard issue

If an earlier stage's output is missing or invalid:
1. HALT the current stage
2. Report the dependency failure
3. Let the orchestrator re-run the failed stage explicitly

**Specific prohibition:** Do NOT run any notebook that imports `dbldatagen` outside of Step 2 (Create Data Layer). The `dbldatagen` library is a Step 2 dependency only.

---

## G-7: Python 3.11 Compatibility

DO NOT use backslashes inside f-string `{}` expressions. This is a hard Python 3.11 syntax constraint.

```python
# ILLEGAL — SyntaxError on Python <3.12
f"{'\u2500' * 40}"
f"{'\n'.join(items)}"

# CORRECT — extract to variable
separator = '\u2500' * 40
f"{separator}"
joined = '\n'.join(items)
f"{joined}"
```

---

## G-8: Workspace I/O Rules

- Use `write_workspace_file` tool (Apps agent) or direct file I/O (Genie Code) for workspace files
- Do NOT use `dbutils.fs` for `/Workspace/` paths
- Do NOT use `os.makedirs` on `/Workspace/` paths from `execute_python` subprocess
- Do NOT use shell commands to create, write, or modify workspace files

---

## G-9: Anti-Shortcut Enforcement

The agent MUST NOT take shortcuts even when:
- "It's just a small change"
- "The previous step already validated this"
- "I know what the columns are from the spec"
- The context window is running low

Every numbered step must execute. Every GATE must be verified. Every Output Contract artifact must exist.

---

## G-10: Idempotency (MANDATORY)

Every Deployment Runtime MUST be rerunnable safely. Same specification + same environment = same final state.

Each manifest MUST include:

```yaml
artifact_id: <unique_id>
source_hash: <sha256 of declarative spec>
generated_hash: <sha256 of compiled output>
readback_hash: <sha256 of deployed state from API>
state_comparison: match | mismatch
```

The manifest proves: desired state → generated state → deployed state → verified state. If `source_hash != readback_hash` (after normalization), the deployment is incomplete and the pipeline MUST fail.

---

## G-12: Canonical Path Derivation (deploy_root / templates_dir)

All steps that need `deploy_root` or `templates_dir` MUST read them from configuration. **No step may derive these paths from dirname chains or environment variables.**

### Primary method: Read from step_handoff.yaml

`deploy_root` and `output_folder` are written by Step 0 into `step_handoff.yaml`. Every downstream step reads them directly:

```python
import yaml
with open(f"{OUTPUT_FOLDER}/step_handoff.yaml") as f:
    handoff = yaml.safe_load(f)
deploy_root = handoff["deploy_root"]
templates_dir = f"{deploy_root}/framework/templates"
```

### Fallback method: Derive from OUTPUT_FOLDER (recovery only)

If `step_handoff.yaml` is missing `deploy_root` (legacy runs), derive it:

```python
import os
deploy_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(OUTPUT_FOLDER))))
templates_dir = f"{deploy_root}/framework/templates"
# Try with/without /Workspace prefix if dir not found
if not os.path.isdir(templates_dir) and not deploy_root.startswith("/Workspace"):
    deploy_root = f"/Workspace{deploy_root}"
    templates_dir = f"{deploy_root}/framework/templates"
```

### Prohibited patterns

- `os.environ.get("DEPLOY_ROOT", ...)` — the env var is NOT set in `execute_python` subprocess context
- Hardcoding absolute paths — breaks portability
- Counting `os.path.dirname()` levels as primary method — fragile, use config instead
- Hard `assert` on `templates_dir` existence — use graceful fallback instead

### Loading framework modules (gate_checks.py, helpers)

After obtaining `templates_dir` via G-12, use this pattern to load framework modules in `execute_python` subprocess context:

```python
import sys, os, shutil
tmp_dir = "/tmp/pipeline_python"
os.makedirs(tmp_dir, exist_ok=True)
shutil.copy2(f"{templates_dir}/gate_checks.py", f"{tmp_dir}/gate_checks.py")
if tmp_dir not in sys.path:
    sys.path.insert(0, tmp_dir)
```

For notebook context (not subprocess), use `sys.path.insert(0, templates_dir)` directly.

---

## G-15: SHOW TABLES / SHOW VIEWS LIKE Uses Glob Syntax (Not SQL LIKE)

Databricks `SHOW TABLES LIKE` and `SHOW VIEWS LIKE` use **glob syntax** where `*` is the wildcard. They do NOT use SQL `LIKE` syntax where `%` is the wildcard.

```sql
-- CORRECT (glob wildcard)
SHOW TABLES IN catalog.schema LIKE '*_v2'

-- WRONG (SQL LIKE wildcard — returns 0 results)
SHOW TABLES IN catalog.schema LIKE '%_v2'
```

**Impact:** Using `%` returns zero results, causing GATE 4.1 (table existence check) to falsely report all tables as missing — even though the CREATE TABLE statements succeeded.

**This applies to all SHOW commands with LIKE:** `SHOW TABLES`, `SHOW VIEWS`, `SHOW SCHEMAS`, `SHOW DATABASES`.

For filtering in `information_schema` queries, SQL `LIKE` with `%` IS correct — this rule only applies to `SHOW ... LIKE`.

---

## G-13: No `spark.sql()` in execute_python Context

`spark.sql()` is NOT available in the `execute_python` subprocess used by the Apps agent. Any step that runs SQL in `execute_python` MUST use the **Statement Execution API** (`w.statement_execution.execute_statement()`) or the helper function `_execute_sql_via_api()` from the dashboard helpers template.

**Scope:** This applies to Steps 3 (dashboards), 4 (Genie), 5 (documentation), and any future step that uses `execute_python`. Step 2 (data layer) runs in a notebook where `spark.sql()` IS available — this rule does not apply there.

**Error signature:** `NameError: name 'spark' is not defined`

**Why per-step rules are not enough:** The LLM has attempted `spark.sql()` in dashboard, Genie, and documentation steps. Repeating the prohibition in each step guardrail is fragile. This global rule is the single authority.

---

## G-14: PARENT_PATH Must Be the Output Folder (Not User Home)

When creating dashboards, Genie spaces, or other workspace assets, `PARENT_PATH` MUST point to the versioned output subfolder, NOT the user's home root.

**Correct pattern:**
```text
PARENT_PATH = "{OUTPUT_FOLDER}/dashboards"    # for dashboards
PARENT_PATH = "{OUTPUT_FOLDER}/genie_space"   # for Genie spaces
```

**Prohibited pattern:**
```text
PARENT_PATH = "/Users/{username}"              # PermissionDenied for service principal
PARENT_PATH = "/Users/arun.wagle@databricks.com"  # Hardcoded, non-portable
```

**Why:** The service principal that executes pipeline steps does NOT have create permissions at the user's home root. It only has permissions within the project directory tree. This caused `PermissionDenied` errors in dashboard deployment.

**Recovery:** If `step_handoff.yaml` is missing `parent_path`, derive it from `OUTPUT_FOLDER`:
```python
PARENT_PATH = f"{OUTPUT_FOLDER}/dashboards"  # or /genie_space for Step 4
```

---

## G-17: `%pip` Must Be Alone in Its Cell

`%pip install ...` is a Databricks cell magic. It MUST be the **only content** in its cell. Mixing `%pip` with Python code (e.g., `dbutils.library.restartPython()`) in the same cell causes preflight syntax rejection — the cell is parsed as Python, and `%pip` is not valid Python syntax.

**Correct pattern (two separate cells):**
```
Cell N:   %pip install somepackage --quiet
Cell N+1: dbutils.library.restartPython()
```

**Wrong pattern (single cell):**
```
%pip install somepackage --quiet
dbutils.library.restartPython()     # ← preflight rejects this cell
```

**Also prohibited:** Adding `%pip install` cells to generated notebooks when the package is already pre-installed on the runtime (e.g., `pyyaml`, `databricks-sdk`). Only add `%pip` when the package is genuinely not available.

---

## G-16: Template Notebooks Use `deploy_from_template` Tool

When deploying via a template notebook (`ddl_notebook.py.template`, `metric_view_notebook.py.template`, `dbldatagen_notebook.py.template`, etc.), the LLM MUST use the `deploy_from_template` tool. This tool:

1. Reads the template as a **single string**
2. Replaces **ONLY** the declared placeholders via deterministic string substitution
3. Imports the result **UNCHANGED** as a notebook
4. Validates that no unreplaced placeholders remain

**DO NOT:**
- Use `import_notebook` for template-based notebooks — it will reject paths containing template stems (ddl\_, dbldatagen\_, metric\_view\_, dashboard\_, genie\_space\_)
- Read the template via `read_workspace_file` and do string manipulation yourself — the tool handles everything
- Rewrite, summarize, simplify, or "improve" any cell
- Remove docstrings, comments, or validation code (especially gate checks)
- Drop any gate (Gate 1, 2, 2b, 3, 4) or verification step

**Why:** LLMs reliably fail at "copy verbatim" — they truncate large code blocks, remove "unnecessary" comments, and "optimize" logic, which silently drops critical validation gates. The `deploy_from_template` tool removes the LLM from the file-copy loop entirely, making this failure mode impossible.

**Validation:** The tool guarantees the output has the same line count as the template (only placeholder text differs). If the tool reports unreplaced placeholders, provide ALL placeholder values and retry.

---

## G-11: Context Window Optimization

Prompt files are large. To conserve context window:
- Each step prompt uses CONTEXT ISOLATION — forget prior step execution details, only read handoff artifacts
- Guardrails are auto-injected via `SUPPLEMENT_FILES` in the app — do NOT re-read guardrail files if already in context
- Template notebooks are read ONCE per step — do not re-read across iterations
- Use `run_context.yaml` and `step_handoff.yaml` as the sole carriers of state between steps
- Avoid quoting large code blocks in progress reports — reference artifacts by path instead

## G-18: TRUNCATE TABLE Is Not Supported

`TRUNCATE TABLE` is **not supported** in Databricks SQL with Unity Catalog. Any `TRUNCATE TABLE` statement will fail with `PARSE_SYNTAX_ERROR`.

**Always use `DELETE FROM` instead:**
```sql
-- ❌ WRONG: TRUNCATE TABLE catalog.schema.my_table
-- ✓ CORRECT:
DELETE FROM catalog.schema.my_table
```

The `execute_sql` tool blocks TRUNCATE statements at the pre-flight gate. If you need to clear a table's data, use `DELETE FROM` (no WHERE clause = delete all rows). For full table recreation, use `DROP TABLE IF EXISTS` + `CREATE TABLE`.

---

## G-17: One SQL Statement Per Execution Call

Databricks SQL allows only **ONE statement per call**. This applies to both `execute_sql` (App tool) and `executeCode` with `language: "sql"` (Genie Code).

Never combine multiple statements with semicolons in a single call:

```text
-- WRONG (two statements in one call — causes PARSE_SYNTAX_ERROR):
execute_sql("DROP MATERIALIZED VIEW IF EXISTS cat.sch.v; CREATE MATERIALIZED VIEW cat.sch.v AS ...")

-- CORRECT (separate calls):
execute_sql("DROP MATERIALIZED VIEW IF EXISTS cat.sch.v")
execute_sql("CREATE MATERIALIZED VIEW cat.sch.v AS ...")
```

**Impact:** The second statement triggers `PARSE_SYNTAX_ERROR: extra input 'CREATE'` after the first statement's semicolon. The App's `execute_sql` handler auto-splits multi-statement SQL as a safety net, but the Genie Code path does NOT — always issue one statement per call.
