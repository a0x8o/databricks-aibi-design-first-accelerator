# State and Resume — Failure Runbook

> **FAILURE/RECOVERY ONLY.** Do not load during a normal successful run. Authenticate the frozen shared-runbook tuple before use.

### Genie Code State Recovery (User Asks "What's my run status?")

```text
User: "What's the status of my member_claims pipeline?"

LLM:
1. Run the shared resolver against the exact registry path and read only its selected run_context_path
2. Reconcile registry/run-context lifecycle identity; in the App, reconcile the optional UI mirror separately without making Lakebase portable lifecycle authority
3. Report: run_id, status, phases_completed, current_step
4. If status=running but no conversation is active → it was interrupted
5. Offer: "Would you like to resume from phase X?"
```


### RUN_SELECTION_NOT_ACKNOWLEDGED / Missing newly allocated run_context.yaml

Apply shared G-12. Allocation returns a future locator. During the same active
bootstrap, finish the master's freeze/write/readback steps before completion progress.
Do not write an empty placeholder, guess another path, or allocate another version
as an automatic repair. An orphan from a previous interrupted allocation follows
the resolver's existing recovery policy. Check access errors separately from absence.

### WORKSPACE_UPLOAD_FORMAT_REQUIRED / Archive error on a plain-file upload

Apply shared G-8 and the frozen workspace file-I/O input. Inspect the failing call's
format and payload type. A pre-execution rejection may be corrected and resubmitted;
a runtime archive error requires checking earlier writes before retrying. Keep
notebook imports separate from plain-file writes and never bypass permissions.
