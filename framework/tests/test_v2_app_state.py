"""App mirror persistence/recovery with no live Lakebase dependency."""
import copy
import json
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
from test_v2_portability import ROOT, load

mirror = load('portable_app_state', 'app/orchestrator/app_state.py')
with patch.dict(sys.modules, {'pg8000': ModuleType('pg8000')}):
    state_module = load('app_state_store', 'app/services/state_store.py')


class Workspace:
    def __init__(self): self.files = {}
    def write_file(self, path, raw): self.files[path] = raw
    def read_file(self, path): return self.files[path]


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.ws, self.store = Workspace(), Mock()
        self.path = '/Workspace/repo/kpi_domains/demo/app_runs/run-1.json'
        self.run = dict(run_id='run-1', domain='demo', status='running',
                        agent_skills_version='v2', step_data={}, logs=[])
        self.adapter = mirror.AppStateMirror(self.ws, self.store, self.run, self.path)
    def record(self):
        return dict(run_id='run-1', domain='demo', config_json=dict(
            agent_skills_version='v2', app_journal_path=self.path))
    def test_progress_snapshot_preserves_structured_fields(self):
        self.adapter.event('phase_update', dict(step_name='create_data_layer',
            phase_id='parse_erd', phase_name='Parse ERD', status='completed',
            stats={'tables': 3}, findings=['Validated'], happenings=[]))
        saved = self.store.persist_app_snapshot.call_args.args[0]
        self.assertEqual(saved['step_data']['create_data_layer']['phases'][0]['stats'], {'tables': 3})
        self.assertEqual(json.loads(self.ws.files[self.path]), saved)
    def test_next_phase_does_not_leave_previous_running_or_invent_success(self):
        for phase in ('generate_ddl', 'generate_synthetic_data'):
            self.adapter.event('phase_update', dict(step_name='create_data_layer',
                phase_id=phase, phase_name=phase, status='started'))
        phases = self.run['step_data']['create_data_layer']['phases']
        self.assertEqual([p['status'] for p in phases], ['unverified', 'running'])
        saved = json.loads(self.ws.files[self.path])
        self.assertEqual(saved['step_data']['create_data_layer']['phases'][0]['status'],'unverified')
    def test_critical_failure_closes_active_phase_and_tool(self):
        self.adapter.event('phase_update', dict(step_name='create_data_layer',
            phase_id='generate_synthetic_data', status='started'))
        self.adapter.event('tool_call', dict(tool='execute_notebook'))
        self.adapter.event('critical_failure', dict(tool='execute_notebook', error="KeyError: parent_pk"))
        info = self.run['step_data']['create_data_layer']
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['phases'][0]['status'], 'failed')
        self.assertEqual(info['tool_calls'][0]['status'], 'failed')
    def test_first_seen_completion_closes_stale_phase_without_inventing_success(self):
        for phase_id, status in [('parse_erd', 'started'), ('generate_ddl', 'completed'),
                                 ('reconcile_schema', 'completed')]:
            self.adapter.event('phase_update', dict(step_name='create_data_layer',
                phase_id=phase_id, status=status))
        phases = self.run['step_data']['create_data_layer']['phases']
        self.assertEqual([p['status'] for p in phases], ['unverified', 'completed', 'completed'])
        self.adapter.event('tool_call', dict(tool='execute_notebook', args_summary='synthetic notebook'))
        self.assertEqual(phases[0]['status'], 'unverified')

    def test_delayed_completion_preserves_current_phase_and_original_order(self):
        for phase_id, status in [('parse_erd', 'started'), ('generate_ddl', 'started'),
                                 ('parse_erd', 'completed')]:
            self.adapter.event('phase_update', dict(step_name='create_data_layer',
                phase_id=phase_id, status=status))
        phases = self.run['step_data']['create_data_layer']['phases']
        self.assertEqual([p['phase_id'] for p in phases], ['parse_erd', 'generate_ddl'])
        self.assertEqual([p['status'] for p in phases], ['completed', 'running'])
    def test_outage_retries_and_retains_outbox(self):
        self.store.persist_app_snapshot.side_effect = RuntimeError('offline')
        with patch.object(mirror.time, 'sleep'):
            self.adapter.save()
        self.assertEqual(self.store.persist_app_snapshot.call_count, 3)
        self.assertIn('persistence_warning', self.run)
        self.assertIn(self.path, self.ws.files)
    def test_replay_after_restart(self):
        self.run.update(status='failed', error='Notebook failed', version=2,
                        canonical_run_id='canonical-run', run_context_path='/output/v2/run_context.yaml')
        self.adapter.save()
        recovered = mirror.recover_snapshot(self.ws, self.store, self.record())
        self.assertEqual(recovered['error'], 'Notebook failed')
        self.assertEqual(recovered['canonical_run_id'], 'canonical-run')
    def test_replay_identity_mismatch_rejected(self):
        self.adapter.save()
        record = self.record(); record['domain'] = 'other'
        with self.assertRaises(ValueError): mirror.recover_snapshot(self.ws, self.store, record)
    def test_replay_old_revision_rejected(self):
        self.adapter.save()
        record = self.record(); record['config_json']['app_snapshot'] = {'mirror_revision': 9}
        with self.assertRaises(ValueError): mirror.recover_snapshot(self.ws, self.store, record)
    def test_workspace_failure_not_silently_acknowledged(self):
        self.ws.write_file = Mock(side_effect=RuntimeError('denied'))
        with self.assertRaises(RuntimeError): self.adapter.save()
        self.store.persist_app_snapshot.assert_not_called()
    def test_selected_locator_persisted_before_failure(self):
        path = '/Workspace/repo/kpi_domains/demo/output/v3/run_context.yaml'
        self.ws.files[path] = json.dumps(dict(run_id='canonical', domain={'name':'demo'},
            version={'number':3}, created_by='app', run_context_path=path, output_folder=path.rsplit('/',1)[0]))
        self.adapter.event('phase_update', dict(step_name='load_configuration',
            phase_id='run_selected', status='completed', stats={'run_context_path':path},
            _validated_run_selection=dict(canonical_run_id='canonical', version=3,
                run_context_path=path, output_folder=path.rsplit('/',1)[0])))
        self.assertEqual(self.run['version'], 3)
        self.assertEqual(self.run['canonical_run_id'], 'canonical')
    def test_tool_error_survives_snapshot(self):
        self.adapter.event('tool_call', dict(tool='execute_notebook', args_summary='run notebook'))
        self.adapter.event('tool_result', dict(tool='execute_notebook', success=False,
                           duration_ms=20, result_summary='permission denied'))
        saved = json.loads(self.ws.files[self.path])
        self.assertEqual(saved['step_data']['master']['tool_calls'][0]['error'], 'permission denied')
    def test_genie_has_no_adapter_dependency(self):
        text = (ROOT/'framework/agent_skills/v2/prompts/shared/agent_transport.md').read_text()
        self.assertIn('Genie Code and other hosts do not initialize this adapter', text)
        self.assertNotIn('app_state', (ROOT/'framework/shared/run_contract.py').read_text())


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = object.__new__(state_module.StateStore)
        self.store._execute_one = Mock()
        self.snapshot = dict(run_id='one', status='failed', mirror_revision=2, error='failure')
    def test_execution_owner_holds_connection_until_release(self):
        connection = Mock()
        connection.cursor.return_value.fetchone.return_value = (True,)
        self.store._connect = Mock(return_value=connection)
        self.assertIs(self.store.open_app_execution('one'), connection)
        connection.close.assert_not_called()
    def test_duplicate_execution_owner_is_rejected(self):
        connection = Mock()
        connection.cursor.return_value.fetchone.return_value = (False,)
        self.store._connect = Mock(return_value=connection)
        with self.assertRaisesRegex(RuntimeError, 'active execution owner'):
            self.store.open_app_execution('one')
        connection.close.assert_called_once()
    def test_owner_probe_releases_its_connection(self):
        connection = Mock()
        connection.cursor.return_value.fetchone.return_value = (False,)
        self.store._connect = Mock(return_value=connection)
        self.assertTrue(self.store.app_execution_active('one'))
        connection.close.assert_called_once()
    def test_snapshot_update_is_one_atomic_statement(self):
        self.store._execute_one.return_value = {'run_id':'one'}
        self.store.persist_app_snapshot(self.snapshot)
        sql, args = self.store._execute_one.call_args.args
        self.assertIn("'{app_snapshot}'", sql)
        self.assertIn('mirror_revision', sql)
        self.assertEqual(json.loads(args[0]), self.snapshot)
        self.assertEqual(self.store._execute_one.call_count, 1)
    def test_equal_revision_replay_is_idempotent(self):
        self.store._execute_one.side_effect = [None, {'config_json': {'app_snapshot':self.snapshot}}]
        self.store.persist_app_snapshot(self.snapshot)
    def test_same_revision_different_payload_fails(self):
        different = {**self.snapshot, 'error':'different'}
        self.store._execute_one.side_effect = [None, {'config_json': {'app_snapshot':different}}]
        with self.assertRaisesRegex(RuntimeError,'conflicting'): self.store.persist_app_snapshot(self.snapshot)
    def test_missing_run_is_not_success(self):
        self.store._execute_one.return_value = None
        with self.assertRaisesRegex(RuntimeError,'missing'): self.store.persist_app_snapshot(self.snapshot)
    def test_cache_hydration_uses_v2_snapshot(self):
        self.store._execute_one.return_value = dict(config_json={
            'agent_skills_version':'v2','app_snapshot':self.snapshot})
        self.assertEqual(self.store.load_run_full('one')['error'],'failure')




class RouteRecoveryTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        self.routes = load('mirror_test_routes','app/routes/pipeline_routes.py')
        self.app = Flask(__name__)
        self.app.register_blueprint(self.routes.pipeline_bp)
        self.client = self.app.test_client()
        self.ws, self.store = Workspace(), Mock()
        self.path = '/Workspace/repo/kpi_domains/demo/app_runs/r.json'
        self.snapshot = dict(run_id='r', domain='demo', status='running',
            agent_skills_version='v2', mirror_revision=1, step_data={},
            version=3, app_journal_path=self.path, requested_steps=None)
        self.ws.files[self.path] = json.dumps(self.snapshot)
        self.record = {**self.snapshot, 'config_json':dict(agent_skills_version='v2',app_journal_path=self.path)}
        self.store.load_run_full.return_value = copy.deepcopy(self.record)
        self.store.get_run.return_value = self.record
        self.store.app_execution_active.return_value = True
        self.patches = [patch.object(self.routes,'_get_state_store',return_value=self.store),
                        patch.object(self.routes,'_get_services',return_value={'workspace':self.ws}),
                        patch.dict(sys.modules, {'orchestrator.app_state':mirror})]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
    def test_other_worker_live_run_is_not_marked_failed(self):
        response = self.client.get('/api/pipeline/run/r/status')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['status'],'running')
    def test_completed_step_does_not_promote_unverified_phases(self):
        self.snapshot['step_data'] = {'load_configuration': dict(status='completed', phases=[
            dict(phase_id='load', status='unverified', current_task='No completion event'),
            dict(phase_id='old', status='running'),
            dict(phase_id='run_selected', status='completed')])}
        self.ws.files[self.path] = json.dumps(self.snapshot)
        response = self.client.get('/api/pipeline/run/r/status')
        self.assertEqual(response.status_code, 200)
        phases = response.json['steps'][0]['phases']
        self.assertEqual([p['status'] for p in phases], ['unverified', 'unverified', 'completed'])
    def test_disconnected_worker_recovers_as_retryable_failure(self):
        self.store.app_execution_active.return_value = False
        response = self.client.get('/api/pipeline/run/r/status')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['status'],'failed')
        self.assertIn('disconnected',response.json['error'])
        self.assertEqual(json.loads(self.ws.files[self.path])['status'],'failed')
    def test_cached_remote_run_refreshes_on_next_poll(self):
        self.client.get('/api/pipeline/run/r/status')
        updated = {**self.snapshot,'status':'failed','error':'Saved failure','mirror_revision':2}
        self.ws.files[self.path] = json.dumps(updated)
        response = self.client.get('/api/pipeline/run/r/status')
        self.assertEqual(response.json['error'],'Saved failure')
    def test_failed_retry_uses_master_and_explicit_version(self):
        self.ws.files[self.path] = json.dumps({**self.snapshot,'status':'failed'})
        rule = next(str(r) for r in self.app.url_map.iter_rules() if r.endpoint.endswith('rerun_from_failure'))
        with patch.object(self.routes.threading,'Thread') as thread:
            response = self.client.post(rule.replace('<run_id>','r'))
            self.assertEqual(response.status_code,202)
            self.assertEqual(thread.call_args.kwargs['kwargs'],{'version_mode':'retry','agent_skills_version':'v2'})
            self.assertEqual(thread.call_args.kwargs['args'][4],3)


if __name__ == '__main__': unittest.main()
