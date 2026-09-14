"""Gunicorn production configuration for AI/BI Studio."""

import os

# Bind to the port assigned by Databricks Apps platform
bind = f"0.0.0.0:{os.environ.get('DATABRICKS_APP_PORT', '8080')}"

# Workers: LLM calls are I/O-bound, 2 workers sufficient
workers = int(os.environ.get('GUNICORN_WORKERS', '2'))

# Timeout: pipeline LLM calls can take 30-60s each
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '600'))

# Graceful restart
max_requests = 500
max_requests_jitter = 50

# Logging — both access and error to stdout so Databricks App logs capture them
accesslog = '-'
errorlog = '-'
loglevel = 'info'


def worker_exit(server, worker):
    """Flush running pipeline state to Lakebase on graceful worker shutdown.

    Gunicorn sends SIGTERM before SIGKILL. During the grace period (timeout=600s),
    this hook marks any in-flight runs as 'failed' in Lakebase so the UI shows
    'Resume All' immediately instead of requiring zombie detection on next poll.
    """
    try:
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
                    server.log.info(f"Flushed running state for run {run_id} to Lakebase")
                except Exception as e:
                    server.log.warning(f"Failed to flush run {run_id}: {e}")
    except Exception:
        pass  # Best-effort — don't prevent worker exit
