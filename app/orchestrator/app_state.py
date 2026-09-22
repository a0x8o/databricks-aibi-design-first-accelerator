"""App-only durable UI mirror. Never writes portable lifecycle contracts.

One cumulative workspace snapshot is the replay outbox. Lakebase receives the
same snapshot in one atomic run-row update; revision guards make replay idempotent.
"""
import copy
import json
import logging
import time
import posixpath
import yaml
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class AppStateMirror:
    def __init__(self, workspace, store, run, journal_path):
        self.workspace, self.store, self.run = workspace, store, run
        self.path = journal_path
        self.revision = int(run.get('mirror_revision', 0))

    def save(self):
        self.revision += 1
        self.run['mirror_revision'] = self.revision
        self.run['heartbeat_at'] = utcnow()
        snapshot = copy.deepcopy(self.run)
        snapshot.pop('persistence_warning', None)
        raw = json.dumps(snapshot, sort_keys=True)
        self.workspace.write_file(self.path, raw)
        if self.workspace.read_file(self.path) != raw:
            raise RuntimeError('App state outbox readback failed')
        for attempt in range(3):
            try:
                self.store.persist_app_snapshot(snapshot)
                self.run.pop('persistence_warning', None)
                return
            except Exception as exc:
                logger.warning('Lakebase mirror pending for %s: %s', self.run['run_id'], exc)
                if attempt < 2:
                    time.sleep(0.2 * (attempt + 1))
        self.run['persistence_warning'] = 'Lakebase synchronization pending; durable workspace snapshot retained.'

    def event(self, name, data):
        if name == 'phase_update':
            if data.get('phase_id') == 'run_selected':
                path = (data.get('stats') or {}).get('run_context_path')
                domain_root = posixpath.dirname(posixpath.dirname(self.path))
                if not isinstance(path, str) or posixpath.normpath(path) != path or not path.startswith(domain_root+'/'):
                    raise ValueError('App run locator is outside its domain')
                context = yaml.safe_load(self.workspace.read_file(path))
                domain = context.get('domain')
                if isinstance(domain, dict):
                    domain = domain.get('name')
                if domain != self.run['domain'] or context.get('created_by') != 'app' or context.get('run_context_path') != path:
                    raise ValueError('App run locator identity mismatch')
                version = context['version']
                self.run.update(canonical_run_id=context['run_id'], run_context_path=path,
                    version=version.get('number') if isinstance(version, dict) else version,
                    output_folder=context['output_folder'])
            step = data.get('step_name') or self.run.get('current_step') or 'master'
            self.run['current_step'] = step
            info = self.run.setdefault('step_data', {}).setdefault(step,
                dict(step_name=step, status='running', phases=[], tool_calls=[]))
            phase = dict(data)
            if phase.get('status') in ('started', 'update'):
                phase['status'] = 'running'
            phases = info['phases']
            phases[:] = [p for p in phases if p.get('phase_id') != phase.get('phase_id')]
            phases.append(phase)
            if phase.get('status') == 'failed':
                info['status'] = 'failed'
        elif name in ('tool_call', 'tool_result'):
            step = self.run.get('current_step') or 'master'
            info = self.run.setdefault('step_data', {}).setdefault(step,
                dict(step_name=step, status='running', phases=[], tool_calls=[]))
            calls = info.setdefault('tool_calls', [])
            if name == 'tool_call':
                calls.append(dict(tool_name=data.get('tool'), status='running',
                    args_summary=data.get('args_summary'), started_at=utcnow()))
            else:
                call = next((c for c in reversed(calls) if c['tool_name'] == data.get('tool')
                             and c['status'] == 'running'), None)
                if call is not None:
                    call.update(status='completed' if data.get('success') else 'failed',
                        duration_ms=data.get('duration_ms'),
                        error=None if data.get('success') else data.get('result_summary'))
            info['tool_calls'] = calls[-100:]
        elif name == 'llm_reasoning':
            self.run.setdefault('logs', []).append(data.get('content', ''))
            self.run['logs'] = self.run['logs'][-100:]
            step = self.run.get('current_step') or 'master'
            logs = self.run.setdefault('step_logs', {})
            logs[step] = (logs.get(step, '') + data.get('content', '') + '\n')[-100000:]
        elif name == 'critical_failure':
            self.run['last_failure'] = dict(data)
        else:
            return
        self.save()


def recover_snapshot(workspace, store, record):
    """Replay a newer outbox after worker loss; workspace errors remain visible."""
    config = record.get('config_json') or {}
    if isinstance(config, str):
        config = json.loads(config)
    if config.get('agent_skills_version') != 'v2':
        return None
    snapshot = json.loads(workspace.read_file(config['app_journal_path']))
    if snapshot.get('run_id') != record['run_id'] or snapshot.get('domain') != record['domain']:
        raise ValueError('App snapshot identity mismatch')
    if snapshot.get('mirror_revision', 0) < (config.get('app_snapshot') or {}).get('mirror_revision', 0):
        raise ValueError('App snapshot revision regressed')
    try:
        store.persist_app_snapshot(snapshot)
    except Exception:
        snapshot['persistence_warning'] = 'Lakebase synchronization pending; displaying durable workspace state.'
    if snapshot.get('status') in ('running', 'started', 'pending') and not store.app_execution_active(record['run_id']):
        # Serialize interruption reconciliation with execution startup and other UI workers.
        connection = store.open_app_execution(record['run_id'])
        try:
            latest = json.loads(workspace.read_file(config['app_journal_path']))
            if latest.get('run_id') != record['run_id'] or latest.get('domain') != record['domain']:
                raise ValueError('App snapshot identity changed during recovery')
            snapshot = latest
            if snapshot.get('status') in ('running', 'started', 'pending'):
                snapshot.update(status='failed', error='Interrupted: App execution owner disconnected. Resume through the master.',
                                completed_at=utcnow())
                AppStateMirror(workspace, store, snapshot, config['app_journal_path']).save()
        finally:
            connection.close()
    return snapshot
