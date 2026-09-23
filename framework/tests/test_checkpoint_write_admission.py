"""Reject the captured v8 writer's malformed VALID record before persistence."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import ModuleType, SimpleNamespace
import sys
from test_v2_portability import runtime


class CheckpointWriteAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(output_folder='/output/v8', target=dict(catalog='cat', schema='sch'),
            version=dict(asset_suffix='_v8'), phases_completed=[dict(step='create_data_layer',
                phase='reconcile_schema', checkpoint_status='VALID', output_fingerprints=[
                    dict(id='schema_reconciliation', kind='CANONICAL_JSON',
                         locator='/output/v8/schema_reconciliation.yaml', sha256='a'*64)])])

    def test_invalid_record_does_not_overwrite_existing_context(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'run_context.yaml'
            original = b'{"phases_completed": []}'
            path.write_bytes(original)
            with self.assertRaisesRegex(RuntimeError, 'CHECKPOINT_PERSISTENCE_ERROR'):
                runtime.LocalStore().write(str(path), runtime.encode(self.context))
            self.assertEqual(path.read_bytes(), original)

    def test_workspace_writer_rejects_before_any_sdk_mutation(self):
        module = ModuleType('databricks.sdk.service.workspace')
        module.ImportFormat = SimpleNamespace(RAW='RAW')
        client = Mock()
        with patch.dict(sys.modules, {'databricks.sdk.service.workspace': module}):
            with self.assertRaisesRegex(RuntimeError, 'exact output identities'):
                runtime.WorkspaceStore(client).write('/output/v8/run_context.yaml', runtime.encode(self.context))
        client.workspace.mkdirs.assert_not_called()
        client.workspace.upload.assert_not_called()

    def test_stage_defined_output_shapes_are_accepted_without_claiming_hash_truth(self):
        self.context['phases_completed'][0]['output_fingerprints'] = [
            dict(id='schema_reconciliation_artifact', kind='RAW_BYTES',
                 locator='/output/v8/schema_reconciliation.yaml', sha256='a'*64),
            dict(id='schema_reconciliation_catalog_readback', kind='CATALOG_READBACK',
                 locator='table_spec:cat.sch:_v8', sha256='b'*64)]
        runtime.validate_phase_checkpoint_shapes(self.context)
        wrong = copy.deepcopy(self.context)
        wrong['phases_completed'][0]['output_fingerprints'][1]['locator'] = 'table_spec:cat.sch:_v7'
        with self.assertRaises(RuntimeError):
            runtime.validate_phase_checkpoint_shapes(wrong)
