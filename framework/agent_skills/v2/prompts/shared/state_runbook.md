# State and Resume — Failure Runbook

> **FAILURE/RECOVERY ONLY.** Do not load during a normal successful run. Authenticate the frozen shared-runbook tuple before use.

### Genie Code State Recovery (User Asks "What's my run status?")

```text
User: "What's the status of my member_claims pipeline?"

LLM:
1. Run the shared resolver against the exact registry path and read only its selected run_context_path
2. Reconcile registry/run-context lifecycle identity (and Lakebase too in App mode)
3. Report: run_id, status, phases_completed, current_step
4. If status=running but no conversation is active → it was interrupted
5. Offer: "Would you like to resume from phase X?"
```
