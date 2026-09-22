# Running the v2 master prompt

The entry point is `framework/agent_skills/v2/prompts/00_master_prompt.md`.
The master selects the version, freezes inputs, runs enabled stages, verifies deployed
assets, and commits the final manifest. The Agentic App now invokes this same master.
Other agents use their native tools or authenticated Databricks SDK operations as
specified in `prompts/shared/agent_transport.md`.

## Workspace invocation

Sync the entire updated repository to your Databricks workspace, including
`framework/shared`, `framework/templates`, and the v2 prompts and contracts. Updating
only the master prompt is insufficient. Configure the domain's `accelerator.yaml`
and warehouse settings before starting.

Give Genie Code or another capable agent this instruction, replacing the workspace
paths and execution owner:

```text
Execute /Workspace/Users/<user>/accelerator/framework/agent_skills/v2/prompts/00_master_prompt.md.
REPO_ROOT=/Workspace/Users/<user>/accelerator
EXAMPLE_DIR=/Workspace/Users/<user>/accelerator/kpi_domains/member_claims
execution_owner=genie_code
requested_mode=fresh
requested_version=null
Generate a candidate UUID, complete the portable capability preflight, and execute
all configured enabled stages through terminal validation and lifecycle commit.
```

The agent needs workspace file operations, Python execution, warehouse SQL, vision
inference, notebook execution, and APIs for enabled assets. Prompts cannot provide
missing permissions or tools. The preflight must identify missing capabilities
before creating assets. Spark templates also require verified access to their
workspace files from the notebook runtime.

## App persistence and agent portability

In the App, select v2 and start a run. Lakebase is required by this host for durable
UI recovery; it is not required by the master prompt, Genie Code, or another host.
The App saves a cumulative snapshot in `runs.config_json.app_snapshot`: phases,
recent tool activity/logs, errors, version and canonical run locators, and the verified
terminal manifest. This uses the existing runs table without a new table migration.

Each snapshot is first written and verified at
`<EXAMPLE_DIR>/app_runs/<app_run_id>.json`. Lakebase receives an atomic, revision-guarded
update. Failed writes are retried three times; the UI shows a synchronization warning
and replays the workspace snapshot on recovery/polling. A Lakebase session advisory
lock distinguishes a live execution owner from a disconnected worker. Losing that
ownership connection interrupts the App host; workspace execution checkpoints remain
available for the master's next authenticated resume.

After a stopped run, the UI retry invokes the same master with the saved version and
`requested_mode=retry`. It does not choose phases from Lakebase statuses. A missing
saved version requires a fresh run rather than guessing a resume target. The App
request ID and canonical workspace run ID are stored separately, since resume may
select an existing workspace run.

This is a prompt-led architecture with deterministic execution adapters: the master
owns orchestration, helpers execute bounded operations, and hosts provide tools and
presentation. A capable agent can start from the master prompt path alone when the
repository/domain is unambiguous. The bootstrap derives paths, selects the sole domain,
and asks only when selection is ambiguous. Agents still need authenticated Databricks
capabilities; a prompt cannot create missing tools or permissions.

## Changes and migration

- `contracts/release.yaml` selects one exact set of helpers, templates, and policy
  inputs. The master freezes paths and SHA-256 digests. Obsolete nested copies under
  `v2/contracts/agent_skills` and `v2/contracts/templates` were removed.
- The data layer uses the canonical ERD helper, including greenfield datatype
  resolution and valid precision-only decimals. The model key is `erd_parse`;
  the portable bootstrap accepts the legacy `parse_erd` alias once.
- Workspace lifecycle allocation, locking, explicit retry history, and terminal
  writes use `framework/shared/run_contract.py`. The master owns stage decisions.
- Dashboard and Genie notebooks use v2-specific templates and attested helpers.
  They verify live API state against expected content and identities. Metric View
  verification failures now stop execution.
- The terminal sweep requires explicit expected inventory and evidence bindings;
  an empty or incomplete scope cannot pass. Genie benchmark execution remains a
  required producer phase, separate from API content validation.
- The App requires a canonical terminal manifest and matching workspace evidence
  before reporting success. A model's textual completion is insufficient.

Use a **fresh version for the first run after this update**. Existing runs have
frozen helper/template hashes and cannot silently adopt the new release. Preserve
old outputs for diagnosis. A process crash can leave a cooperative lifecycle lock;
verify its owner stopped before explicitly recovering it. Never delete it merely
because it is old.

## Verification

Run the local regression suite:

```sh
python3 -m unittest discover -s framework/tests -q
```

The suite covers schema rules, lifecycle transitions and failures, readback gates,
empty-scope rejection, App master completion, and rendered dashboard/Genie notebooks
against simulated SDK responses. These tests do not validate live permissions,
warehouse behavior, model-generated output quality, or Databricks notebook execution.
A live fresh-version run remains the integration acceptance check.
