# Portable agent execution contract

This file governs transport for every v2 prompt. The master remains the orchestrator:
helpers implement bounded operations and never choose the next pipeline stage. Use
the same master in Genie Code, the Agentic app, or another capable agent.

## Bootstrap

Start from the master prompt's own absolute workspace path. If REPO_ROOT was not
supplied, derive it by removing the exact suffix
`/framework/agent_skills/v2/prompts/00_master_prompt.md`; verify the resulting root.
If EXAMPLE_DIR was not supplied, use the current domain directory when it contains
accelerator.yaml; otherwise list REPO_ROOT/kpi_domains and use its sole configured
domain. If multiple domains exist, ask which to run before allocation. Never guess.
Default requested_mode to auto, requested_version to null, generate a candidate UUID,
and derive a stable execution_owner from the actual host identity when omitted.
The caller may override REPO_ROOT and EXAMPLE_DIR with absolute workspace paths. Bind
AGENT_SKILLS_DIR to REPO_ROOT/framework/agent_skills/v2. Before allocation, read
contracts/release.yaml there. Resolve its paths against REPO_ROOT; read and hash
every selected file. Freeze helpers and templates as `{path, sha256}` entries under
run_context.templates. Freeze inputs at their documented run_context.inputs keys.
The release manifest is the only selector; contracts/templates and nested historical
copies are not runtime alternatives. A configured template must resolve to the release
path or fail preflight; do not silently select an old template from accelerator.yaml.
Record the release path/raw SHA and this transport path/raw SHA in run_context.inputs.

Normalize configuration BEFORE freezing it:
- Invocation `requested_steps`, when supplied, narrows the configured enabled stages;
  validate dependencies before allocation. Never skip required producers based on a
  UI resume hint. Resume admission belongs to authenticated master checkpoints.
- `requested_mode` controls version selection. Legacy UI `requested_run_mode=clean`
  or `new` means a fresh version, never deletion of earlier versions. Record this
  normalization; reject a conflicting explicit retry/version request. No caller
  setting may disable the terminal sweep or required documentation for enabled assets.
- `llm.steps.erd_parse` is canonical. Accept legacy `parse_erd` only if erd_parse is
  absent, rename it once, and record the normalization. Reject conflicting definitions.
- Resolve missing stage models from llm.default_model (ERD may use llm.vision_model).
  Preserve an explicitly supplied instruction; never index an absent instruction.
- Resolve relative input paths against EXAMPLE_DIR, release paths against REPO_ROOT.
- Freeze runtime.state_store as `workspace_only`. This is the portable lifecycle
  authority in every host, including the App. Lakebase/UI progress is an optional
  observational mirror; it never gates or chooses a workspace run. A separate adapter
  may mirror events after durable workspace commits, but must not replace this master.
- The App enables a host-side Lakebase mirror for durable UI history and recovery.
  Its provisioned database is an App startup requirement, not a requirement of this
  prompt. Mid-run mirror failures retain a verified workspace outbox for replay and
  surface a UI warning. Genie Code and other hosts do not initialize this adapter.
- created_by is a nonempty stable caller-supplied execution-owner string, e.g.
  `genie_code`, `app`, or another host identifier. Do not impersonate another owner.

## Capability preflight (before creating assets)

Require authenticated workspace byte read/write/list/delete, create-only writes,
Python execution (native or a submitted notebook), SQL warehouse execution, vision
model invocation, notebook import/run, and enabled-asset SDK/API access. Verify the
host against requested runtime.workspace_host. Missing capabilities are
AGENT_CAPABILITY_ERROR. Report the exact missing operation before asset creation.
Permission denials remain operational errors. A different approved transport is
selected during this preflight, never after a safety/permission block.

Names in stage prompts denote OPERATIONS, not a required installed tool registry:

| Operation | Native implementation | Portable implementation |
|---|---|---|
| read/write workspace file | Host workspace tools | WorkspaceStore via authenticated SDK |
| execute Python | Genie Code/native Python | Import and execute a control notebook |
| execute_sql / describe_table | Host warehouse tool | SDK Statement Execution API, frozen warehouse |
| call_vision_model | Host vision tool with frozen model | SDK serving invocation with image bytes |
| deploy_from_template | Host substitution tool | Read verified bytes, literal `{{KEY}}` substitution, reject remaining placeholders, import notebook |
| execute_notebook | Host notebook runner | Jobs submit/run and poll terminal result |
| report_progress | Optional host event tool | Persist checkpoint first, then emit structured JSON to the transcript |
| report_step_complete | Optional host event tool | Return structured stage result to the master |

No stage requires Flask, app/shared imports, an app event bridge, or Lakebase.
Use the attested WorkspaceStore for lifecycle writes; do not invent a `put()` wrapper
that omits upload format. Plain-file writes use explicit ImportFormat.RAW, UTF-8
bytes, and verified readback. Notebook deployment uses its explicit notebook format.
Templates and Python helpers may run in a notebook. If runtime filesystem access to
/Workspace files is required by a selected Spark template, verify that exact mount
is readable/writable in its execution environment before deployment. Do not assume
agent-local paths refer to remote workspace files. Control-plane writes use the SDK
store. A mounted runtime uses atomic replacement and verified readback under the same
single-writer run policy; never use dbutils.fs on /Workspace paths.

## Lifecycle helper calls

Read the exact release-selected run_contract.py bytes with workspace tools/SDK,
verify the frozen digest, stage in a digest-qualified local temporary directory,
re-hash, and import with importlib.util.spec_from_file_location. Do not discover it
through sys.path. Bind `runtime` to that attested module and `w` to the authenticated
WorkspaceClient whose host passed preflight.

```python
store = runtime.WorkspaceStore(w)
selection = runtime.resolve_version(
    registry_path=EXAMPLE_DIR + '/version_registry.yaml',
    domain=request['domain']['name'],
    output_root=resolved_output_root,  # EXAMPLE_DIR + requested output_subpath
    created_by=execution_owner,
    run_id=candidate_uuid,
    store=store,
    mode=requested_mode,              # auto, retry, fresh
    explicit_version=requested_version,
)
```

This returns a mapping with the exact master selection fields. The master builds
and persists run_context and step_handoff, then invokes stages with run_context_path.
A fresh allocation has no context until that master write. An interrupted allocation
without context cannot resume; a fresh version preserves the orphan for diagnosis.
A missing registry reserves exact existing vN folders before allocation.

WorkspaceStore's cooperative lock is a create-only workspace file, shared by every
lifecycle writer. It is never stolen based on age. A crashed lock requires explicit
owner recovery after checking the previous execution stopped. Retry uses immutable
history and a transition marker; malformed or incomplete transitions halt.

The master composes the canonical terminal manifest from authenticated evidence and calls:

```python
runtime.commit_terminal(
    store=store, registry_path=run_context['registry_path'],
    run_context_path=run_context_path, manifest=canonical_manifest,
)
```

Do not separately flip registry status. Keep optional App telemetry outside this
transaction. WorkspaceStore replaces one complete object per SDK upload and verifies
exact byte readback while holding the cooperative lifecycle lock. Multi-file changes
are a verified transaction with rollback, not a claim of distributed ACID semantics.
All readers must reject an active lifecycle lock/transition before trusting parity.

If bootstrap or allocation fails before a valid run context exists, report the
bootstrap failure and retained allocation evidence. Do not invent a terminal manifest
or mutate another run to satisfy the post-allocation failure transaction.


Template deployment carries the master's persisted `run_context_path` explicitly.
A fresh host process can authenticate it without replaying `run_selected` progress.
When an older caller supplies only OUTPUT_FOLDER, use its canonical context child
as a candidate locator and authenticate identity before deployment. Never consult
an in-memory acknowledgement flag or scan output versions to choose a context.
