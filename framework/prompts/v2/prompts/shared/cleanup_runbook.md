# Version Cleanup — Failure Runbook

> **FAILURE-ONLY.** Authenticate before use; never use this file to broaden a confirmed deletion inventory.

# Error Handling

### Partial Failure

If any deletion fails mid-execution:

1. HALT immediately
2. Report which assets were successfully deleted
3. Report which asset failed and the error
4. Present options to user:
   - Retry only the exact failed operation after its frozen identity, exact object kind,
     environment binding, and remaining confirmed inventory are revalidated
   - Abort (leave remaining assets intact)

There is no skip-and-continue branch. No later deletion, workspace removal, Lakebase
mutation, or registry write may run unless the exact failed operation is retried and
succeeds. A retry failure HALTS again; an abort preserves every remaining asset.

### Asset Not Found

If a confirmed asset no longer exists before its own deletion call (404/object-not-found):

```text
HALT — confirmed inventory changed; rebuild inventory and obtain a new exact confirmation
```

A 404 immediately after this cleanup deleted that same exact asset is the expected
post-delete verification result. Do not confuse that expected readback with pre-delete
inventory drift.

### Permission Denied

If deletion returns 403:

```text
⚠️ Permission denied: Cannot delete {asset_type} '{name}'
Required permission: {required_permission}
```

HALT and report. Do not silently skip.

---
