"""Identify reconciliation changes without modifying canonical run evidence."""
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_run_selection_progress import ToolExecutor, Workspace


class ProducerDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.root = '/Workspace/domain/output/v5'
        self.path = self.root + '/schema_reconciliation.yaml'
        self.jobs = Mock()
        self.executor = ToolExecutor(SimpleNamespace(), {'workspace': self.ws, 'jobs': self.jobs})
        self.executor._diagnostic_run = dict(run_id='canonical', output_folder=self.root)

    def records(self):
        return [json.loads(value) for path, value in self.ws.files.items()
                if '/diagnostics/' in path and path.endswith('.json')]

    def test_later_python_replacement_preserves_both_versions_and_source_hash(self):
        original = 'producer_step: create_data_layer\npolicy_id: DEPLOYED_DATATYPE_REPAIR_V1\n'
        replacement = 'policy: DEPLOYED_DATATYPE_REPAIR_V1\n'
        self.ws.files[self.path] = original
        def handler(args):
            self.ws.files[self.path] = replacement
            return 'SUCCESS'
        self.executor._handle_execute_python = handler
        source = 'sensitive_code_payload'
        self.assertEqual(self.executor.execute('execute_python', {'code': source}), 'SUCCESS')
        record = self.records()[0]
        self.assertTrue(record['change_observed'])
        self.assertEqual(record['tool'], 'execute_python')
        self.assertEqual(self.ws.files[record['before']['snapshot_path']], original)
        self.assertEqual(self.ws.files[record['after']['snapshot_path']], replacement)
        self.assertEqual(record['argument_source_sha256']['code'], hashlib.sha256(source.encode()).hexdigest())
        self.assertNotIn(source, json.dumps(record))
        self.assertEqual(self.ws.files[self.path], replacement)

    def test_notebook_production_records_actual_source_and_job_id(self):
        notebook = self.root + '/notebooks/ddl.py'
        self.ws.files[notebook] = 'print("ddl")'
        self.jobs.run_notebook.return_value = 123
        def finish(*args, **kwargs):
            self.ws.files[self.path] = 'producer_step: create_data_layer\n'
            return SimpleNamespace(result_state='SUCCESS', duration_s=1, output='done')
        self.jobs.wait_for_run.side_effect = finish
        with patch.object(self.executor, '_py_compile_check', return_value=None):
            result = self.executor.execute('execute_notebook', {'path': notebook})
        record = self.records()[0]
        self.assertIn('run_id=123', result)
        self.assertEqual(record['execution']['notebook_run_id'], 123)
        self.assertEqual(record['execution']['executed_source_sha256'],
                         hashlib.sha256(self.ws.files[notebook].encode()).hexdigest())
        self.assertEqual(record['before']['state'], 'unreadable')
        self.assertIn('snapshot_path', record['after'])

    def test_diagnostic_failure_does_not_replace_original_error(self):
        self.executor._handle_execute_python = lambda args: 'ERROR: original failure'
        with patch.object(self.ws, 'write_file', side_effect=PermissionError('denied')):
            with self.assertLogs(level='WARNING') as logs:
                result = self.executor.execute('execute_python', {'code': 'pass'})
        self.assertEqual(result, 'ERROR: original failure')
        self.assertTrue(any('DIAGNOSTIC_UNAVAILABLE' in line for line in logs.output))
