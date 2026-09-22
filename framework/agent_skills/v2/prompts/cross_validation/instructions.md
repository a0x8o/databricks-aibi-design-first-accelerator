# AIBI Design-First Accelerator — Terminal Cross-Validation Stage

> **Transport:** apply the frozen `shared/agent_transport.md` contract. Tool names are portable operations; App/Lakebase integration is optional. Runtime paths come only from `contracts/release.yaml`.

## Contract Loading

Always load `{AGENT_SKILLS_DIR}/prompts/cross_validation/validation.md`, `{AGENT_SKILLS_DIR}/prompts/cross_validation/guardrails.md`,
`{AGENT_SKILLS_DIR}/prompts/shared/global_guardrails.md`, and `{AGENT_SKILLS_DIR}/prompts/shared/state_contract.md`. Do not load
`{AGENT_SKILLS_DIR}/prompts/cross_validation/runbook.md` unless the sweep has produced a classified failure. On failure,
authenticate its frozen tuple and load only the matching owner/recovery section.


> **Execution position:** after all enabled creation stages and before documentation.
>
> **Always read with:** `{AGENT_SKILLS_DIR}/prompts/shared/global_guardrails.md`, `{AGENT_SKILLS_DIR}/prompts/shared/state_contract.md`, the exact
> resolver-selected `run_context.yaml`, and the exact sibling `step_handoff.yaml`.
>
> **Runtime authority:** the exact path-and-digest reference at
> `run_context.templates.gate_checks`.

## Purpose

Run one current-readback reconciliation across every enabled current-run asset. This stage proves
that the deployed inventory matches the frozen request and authenticated producer evidence before
documentation or terminal lifecycle reconciliation can claim success.

This stage does not design, create, repair, or delete assets. It never treats a manifest as proof of
deployed content. It produces only:

```text
{OUTPUT_FOLDER}/ground_truth_validation.yaml
```

The master owns routing, final manifest creation, and terminal lifecycle commits.

## Non-Reusable Terminal Stage

The sweep runs on every terminal attempt, including resumes. It is current-readback reconciliation,
not a reusable phase checkpoint. Never skip it because a prior report, manifest, output hash, or
completed phase exists. A prior report may be retained as attempt history, but it cannot authorize
the current sweep.

## Bootstrap and Self-Authentication

Before reading sibling artifacts:

1. Bind the exact tool-supplied `run_context_path`; require an absolute normalized path whose
   basename is `run_context.yaml`.
2. Parse YAML with duplicate-key rejection and require a non-empty `run_id`.
3. Require normalized `dirname(run_context_path) == run_context.output_folder`.
4. Read only the sibling `step_handoff.yaml`; require the duplicated identity, path, suffix,
   catalog/schema, runtime, dashboard, Genie, and Metric View fields to pass the master handoff
   parity contract.
5. Authenticate the complete `run_context.inputs.orchestration_prompts.cross_validate_run` object.
   Require the exact key set `path`, `version`, `sha256`, `validation_path`,
   `validation_sha256`, `guardrails_path`, `guardrails_sha256`, `runbook_path`,
   `runbook_version`, and `runbook_sha256`; require both versions to equal `1`; and require exact
   normalized paths and raw-byte hashes for this file plus the validation, guardrails, and runbook
   files. Do not load the authenticated runbook bytes unless a failure is subsequently classified.
6. Recompute and require the complete frozen-run contract, state-contract hash, producer
   instruction/control bundles, and every retained checkpoint under `{AGENT_SKILLS_DIR}/prompts/shared/state_contract.md`.
7. Reject any disabled-stage phase, stale retained phase, cross-run artifact, unbound locator,
   duplicate identity, or path outside the exact current output folder.

Any bootstrap or self-authentication failure is owned by `MASTER_RESOLVER` and halts without
asset repair.

## Authority Rules

Apply G-3 from `{AGENT_SKILLS_DIR}/prompts/shared/global_guardrails.md` field by field:

- frozen configuration and design artifacts own requested intent;
- `step_handoff.yaml` owns exact resolved identities only after its authentication passes;
- catalog inspection owns current table and Metric View reality;
- official Dashboard and Genie API GET responses own current remote reality;
- validations record comparisons only when bound to the exact same run, identity, source, and
  current readback;
- manifests are canonical locators and deployment-attempt records, never semantic or deployed-state
  authority;
- the approved Metric View capability contract owns accelerator capability policy;
- the approved Genie quality contract and its frozen effective snapshot own thresholds and outcome
  semantics.

When sources disagree, fail the owning validation. Never choose the convenient source, repair a
producer artifact here, or turn observed reality into requested intent.

## Stage 1 — Freeze Expected Scope

Build the expected inventory before reading deployment manifests. Derive it only from the frozen
run plus authenticated producer contracts:

| Inventory class | Scope authority |
|---|---|
| Generated tables and intermediate materialized views | authenticated `table_spec.yaml`, data-layer validation, and frozen target coordinates |
| Metric Views | authenticated strategy-aware plan, capability tuple, validation, and handoff producer checkpoint |
| Dashboards | frozen dashboard IDs/names and authenticated `dashboard_design.yaml` |
| Genie Space | frozen Genie identity and authenticated `genie_semantic_inventory.yaml` |

For every enabled class, require a duplicate-free ordered inventory and exactly one canonical
locator for each API-created asset. For disabled classes, require no locator, successful manifest,
or retained phase record. Manifests may supply the locator for an already-expected API asset; they
may not add, remove, rename, or reprioritize inventory.

Canonicalize the complete scope object with `CANONICAL_JSON_UTF8_SHA256_V1` and retain its lowercase
64-hex digest as `scope_inputs_sha256`. The object must bind at least:

```yaml
run_id: <exact current run>
output_folder: <exact current output folder>
workspace_host: <normalized frozen host>
frozen_run_contract_sha256: <exact frozen digest>
producer_bundles: <exact five producer-bundle digests>
expected_inventory: <complete duplicate-free inventory>
metric_view_capability_contract: <name/version/raw sha256 when enabled>
genie_quality_contract: <name/version/raw sha256/policy/effective-policy sha256 when enabled>
```

Set `scope_input_binding: PASS` only after exact re-read and digest equality. Missing, extra,
duplicated, ambiguous, or unbound items fail before current readback.

## Stage 2 — Authenticate the Runtime

Load `gate_checks.py` only through the exact frozen `run_context.templates.gate_checks` reference:

1. Require an absolute normalized path under the frozen approved template root.
2. Require a lowercase 64-hex expected digest and exact raw-byte equality.
3. Copy to a digest-qualified temporary directory.
4. Re-hash the copy and import it under a digest-qualified module name.
5. Require the loaded module file to equal the verified copy.
6. Require the approved `GateCheckError`, `run_cross_validation`, and
   `write_ground_truth_validation` callables and their expected signatures.

Never import an ambient module, trust `sys.modules`, search by basename, load an output-folder copy,
or embed a substitute implementation in this prompt.

## Stage 3 — Perform Current Readback

Call the authenticated `run_cross_validation(workspace_client, scope=scope,
quality_gates=run_context["quality_gates"], validation=run_context["validation"])` once.
The function returns a diagnostic mapping on PASS and FAIL; always persist it using
`write_ground_truth_validation(path, report, source="cross_validation_sweep", store=store)`.
That writer returns the persisted raw-byte digest. Never turn an exception into PASS.

The scope uses this executable schema in addition to the identity/hash fields above:

```yaml
warehouse_id: <frozen warehouse>
enabled_asset_classes: [tables, metric_views, dashboards, genie_spaces]
expected_inventory:
  tables:
    - sql_fqn: "`catalog`.`schema`.`table`"
      columns: [[column_name, exact_describe_type]]
      definition: <authenticated producer SHOW CREATE TABLE readback>
      validation_queries: [{sql: "SELECT COUNT(*) FROM ...", check: positive_count}]
  metric_views:
    - sql_fqn: "`catalog`.`schema`.`metric_view`"
      columns: [[column_name, exact_describe_type]]
      definition: <authenticated producer SHOW CREATE TABLE readback>
      validation_queries: [{sql: "SELECT MEASURE(...) FROM ...", check: nonempty}]
  dashboards:
    - id: <authenticated locator>
      name: <exact handoff display name>
      expected: <the producer validator's authenticated expected argument>
  genie_spaces:
    - id: <authenticated locator>
      name: <exact handoff title>
      expected: <the producer validator's authenticated expected argument>
      benchmark_evidence: {run_id: ..., space_id: ..., readback_sha256: ..., passed: 15, total: 15}
```

Disabled classes are empty arrays and absent from enabled_asset_classes. Generated
intermediate materialized views belong in `tables` with their producer's definition,
columns and readiness queries; their scope comes from the Metric View plan, not table_spec.
Every enabled class must be nonempty. Bind producer definitions to their validated intent
before constructing scope. Every implemented KPI contributes an executed validation query.
Authenticate benchmark evidence against its current-run artifact fingerprint and preserve
per-question execution evidence; it cannot be fabricated from configuration counts.
Persist the complete scope as `{OUTPUT_FOLDER}/cross_validation_scope.json` before readback,
re-read it, and require its canonical digest to equal the report's scope_inputs_sha256.
Documentation reads that exact scope file to recompute the digest. The helper must read current
reality rather than copy producer assertions.

Required checks include:

### Data layer

- exact expected table/materialized-view inventory;
- object kind, normalized three-part identity, required columns/types, and current row-count or
  other stage-defined readiness evidence;
- parity with authenticated data-layer validation.

### Metric Views

- exact strategy-aware handoff/plan/checkpoint/capability identity binding;
- catalog object kind and current definition/readback;
- current validation-query success for implemented KPIs;
- no unsupported feature silently emitted outside the approved capability/fallback policy.

### Dashboards

- official API GET on every expected dashboard locator using the frozen workspace host;
- exact ID/display-name binding, published state, dataset/widget/page references, non-empty required
  canvases, filter bindings, and structural-gate success;
- exact mapped-page inventory when the KPI specification supplies a Dashboard Mapping;
- authenticated quality-target outcome without promoting `WARN` to `PASS`.

A Dashboard quality-target miss may yield `quality_target_status: WARN` and
`stage_status: PARTIAL_SUCCESS` while structural cross-validation remains `PASS`. It does not become
a structural failure and does not block the manifest by itself.

### Genie

- official API GET for the exact expected Space locator and title;
- non-empty instructions, questions, examples, tables, and other configured semantic inventory;
- current readback counts and verified benchmark evidence;
- exact approved quality-contract tuple, frozen effective-policy hash, outcome, action, and stage
  status. Never derive Genie status from `overall_status: PASS` alone.

Normalize and compare the current client host with `run_context.runtime.workspace_host`; set
`workspace_host_binding: PASS` only on exact approved normalization parity.

## Stage 4 — Persist and Re-Read the Report

Write the report through the authenticated helper to exactly:

```text
{OUTPUT_FOLDER}/ground_truth_validation.yaml
```

Write atomically, then re-read with duplicate-key rejection. A successful report must contain and
authenticate at least:

```yaml
source: cross_validation_sweep
overall_status: PASS
run_id: <exact current run_id>
output_folder: <exact current output folder>
scope_input_binding: PASS
scope_inputs_sha256: <exact frozen scope digest>
workspace_host_binding: PASS
expected_inventory: <exact frozen inventory>
observed_inventory: <exact duplicate-free inventory parity>
asset_results: <one current-readback result per expected asset>
failure_owner: null
```

When Metric Views are enabled, retain their approved capability tuple and strategy-aware producer
binding. When Genie is enabled, retain its source/effective quality-policy tuple and exact
per-outcome action/stage status. Dashboard results retain separate structural and quality-target
statuses.

Require exact expected/observed key-set and per-key inventory equality. Require every asset result
to bind to one expected identity and prove its applicable current-readback checks. Unknown extra
keys do not authorize extra assets.

Hash the exact persisted report bytes after the final successful re-read. Return that digest to the
master as `ground_truth_validation_sha256`; do not place the file's digest inside the file itself.
