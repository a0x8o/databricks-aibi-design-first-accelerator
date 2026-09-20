# Terminal Cross-Validation — Guardrails

> **Always loaded.**

1. The sweep is unconditional, non-checkpointable, and re-runs on every terminal attempt.
2. Build expected scope before reading manifests; manifests are locators only.
3. Use current catalog and official API GET readback as deployed-state authority.
4. Load only the digest-pinned `gate_checks` helper; never embed or discover a substitute.
5. Do not create, repair, redeploy, delete, or reinterpret producer assets in this stage.
6. Never load the failure runbook before an owner and error are classified.
