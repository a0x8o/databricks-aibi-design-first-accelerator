"""Exercise Metric View file transport without a /Workspace filesystem mount."""
import ast
import io
import posixpath
import sys
from pathlib import Path
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
TEMPLATE=ROOT/'framework/templates/metric_view_notebook.py.template'
source=TEMPLATE.read_text()
tree=ast.parse(source)
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('read_workspace_bytes','write_workspace_bytes')]
ns={'posixpath':posixpath}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(TEMPLATE),'exec'),ns)

class MVWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.files={};self.uploads=[]
        def download(path):
            if path not in self.files: raise FileNotFoundError(path)
            return io.BytesIO(self.files[path])
        def upload(path,payload,format,overwrite):
            self.uploads.append((format,overwrite));self.files[path]=payload
        self.client=SimpleNamespace(workspace=SimpleNamespace(download=download,upload=upload,mkdirs=lambda p:None))
        errors=ModuleType('databricks.sdk.errors');errors.NotFound=FileNotFoundError
        workspace=ModuleType('databricks.sdk.service.workspace');workspace.ImportFormat=SimpleNamespace(RAW='RAW')
        patcher=patch.dict(sys.modules,{'databricks.sdk.errors':errors,'databricks.sdk.service.workspace':workspace})
        patcher.start();self.addCleanup(patcher.stop)
    def test_spec_read_succeeds_without_local_mount(self):
        path='/Workspace/remote/v1/metric_views/metric_view_spec.yaml'
        self.files[path]=b'metric_views: []\n'
        with patch('builtins.open',side_effect=AssertionError('local file access forbidden')):
            self.assertEqual(ns['read_workspace_bytes'](self.client,path),self.files[path])
    def test_missing_spec_has_actionable_path_and_no_write(self):
        path='/Workspace/remote/v1/metric_views/metric_view_spec.yaml'
        with self.assertRaisesRegex(RuntimeError,'METRIC_VIEW_INPUT_NOT_FOUND: '+path):
            ns['read_workspace_bytes'](self.client,path)
        self.assertEqual(self.uploads,[])
    def test_permission_denial_is_not_converted_to_missing_file(self):
        def denied(path): raise PermissionError('denied')
        self.client.workspace.download=denied
        with self.assertRaises(PermissionError): ns['read_workspace_bytes'](self.client,'/Workspace/file')
    def test_manifest_write_uses_raw_and_verifies_bytes(self):
        ns['write_workspace_bytes'](self.client,'/Workspace/remote/manifest.json',b'{}')
        self.assertEqual(self.uploads,[('RAW',True)])
    def test_manifest_readback_mismatch_fails(self):
        self.client.workspace.download=lambda p:io.BytesIO(b'wrong')
        with self.assertRaisesRegex(RuntimeError,'METRIC_VIEW_OUTPUT_READBACK_ERROR'):
            ns['write_workspace_bytes'](self.client,'/Workspace/remote/manifest.json',b'{}')
    def test_no_local_open_remains_in_template(self):
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='open' for n in ast.walk(tree)))
        self.assertLess(source.index('spec_bytes = read_workspace_bytes(w, SPEC_PATH)'),source.index('CREATE OR REPLACE VIEW'))

if __name__=='__main__': unittest.main()
