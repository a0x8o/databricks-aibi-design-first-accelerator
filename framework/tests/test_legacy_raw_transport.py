"""Exercise plain-file transport when the notebook SDK predates RAW."""
import ast
import base64
from enum import Enum
import io
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_v2_portability import runtime
from test_metric_view_workspace_io import ns

LegacyFormat = Enum('LegacyFormat', {'AUTO': 'AUTO', 'SOURCE': 'SOURCE'})


class LegacyRawTests(unittest.TestCase):
    def setUp(self):
        module = ModuleType('databricks.sdk.service.workspace')
        module.ImportFormat = LegacyFormat
        errors = ModuleType('databricks.sdk.errors')
        errors.NotFound = FileNotFoundError
        patcher = patch.dict(sys.modules, {'databricks.sdk.service.workspace': module,
                                          'databricks.sdk.errors': errors})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.files = {}
        def send(method, endpoint, *, body):
            self.assertEqual((method, endpoint), ('POST', '/api/2.0/workspace/import'))
            self.assertEqual(body['format'], 'RAW')
            if body['path'] in self.files and not body['overwrite']:
                raise FileExistsError(body['path'])
            self.files[body['path']] = base64.b64decode(body['content'])
        self.send = Mock(side_effect=send)
        self.client = SimpleNamespace(
            api_client=SimpleNamespace(do=self.send),
            workspace=SimpleNamespace(mkdirs=Mock(), upload=Mock(),
                                      download=lambda path: io.BytesIO(self.files[path])))

    def test_store_preserves_bytes_and_create_only(self):
        store = runtime.WorkspaceStore(self.client)
        raw = 'name: café\n'.encode()
        store.write('/Workspace/state.yaml', raw, overwrite=False)
        self.assertEqual(self.files['/Workspace/state.yaml'], raw)
        self.assertFalse(self.send.call_args.kwargs['body']['overwrite'])
        with self.assertRaises(FileExistsError):
            store.write('/Workspace/state.yaml', b'changed', overwrite=False)
        self.assertEqual(self.files['/Workspace/state.yaml'], raw)
        self.client.workspace.upload.assert_not_called()

    def test_api_error_is_not_retried(self):
        self.send.side_effect = PermissionError('denied')
        with self.assertRaises(PermissionError):
            runtime.WorkspaceStore(self.client).write('/Workspace/state.yaml', b'{}')
        self.send.assert_called_once()
        self.client.workspace.upload.assert_not_called()

    def test_store_checks_readback(self):
        self.client.workspace.download = lambda path: io.BytesIO(b'wrong')
        with self.assertRaises(RuntimeError):
            runtime.WorkspaceStore(self.client).write('/Workspace/state.yaml', b'{}')

    def test_metric_view_uses_legacy_transport(self):
        ns['write_workspace_bytes'](self.client, '/Workspace/manifest.json', b'{}')
        self.assertEqual(self.files['/Workspace/manifest.json'], b'{}')
        self.client.workspace.upload.assert_not_called()
        self.assertTrue(self.send.call_args.kwargs['body']['overwrite'])

    def test_app_writer_uses_legacy_transport(self):
        path = Path(__file__).resolve().parents[2] / 'app/services/workspace_io.py'
        tree = ast.parse(path.read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'write_file')
        scope = {'base64': base64, 'ImportFormat': LegacyFormat, 'logger': Mock(),
                 'WorkspaceError': RuntimeError}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), scope)
        service = SimpleNamespace(_client=self.client, mkdirs=Mock())
        scope['write_file'](service, '/Workspace/app.yaml', 'name: café\n', overwrite=False)
        self.assertEqual(self.files['/Workspace/app.yaml'], 'name: café\n'.encode())
        self.assertFalse(self.send.call_args.kwargs['body']['overwrite'])


if __name__ == '__main__':
    unittest.main()
