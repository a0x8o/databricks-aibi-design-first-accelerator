"""Run the portable bootstrap exactly as supplied by the shared prompt."""
import hashlib
import inspect
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_v2_portability import ROOT, load

Executor = load('introspection_executor', 'app/llm/tool_executor.py').ToolExecutor


class LifecyclePromptLoaderTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT / 'framework/agent_skills/v2/prompts/shared/agent_transport.md').read_text()
        source = next(block for block in re.findall(r'```python\n(.*?)```', text, re.S)
                      if 'def load_lifecycle_runtime(' in block)
        namespace = {}
        exec(compile(source, 'agent_transport.md', 'exec'), namespace)
        self.bootstrap = namespace['load_lifecycle_runtime']
        self.raw = (ROOT / 'framework/shared/run_contract.py').read_bytes()
        self.digest = hashlib.sha256(self.raw).hexdigest()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.patch = patch('tempfile.mkdtemp', return_value=self.directory.name)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_real_helper_bootstrap_registers_file_backed_module(self):
        runtime = self.bootstrap(self.raw, self.digest)
        self.addCleanup(sys.modules.pop, runtime.__name__, None)
        self.assertIs(sys.modules[runtime.__name__], runtime)
        self.assertEqual(Path(runtime.__file__).read_bytes(), self.raw)
        client = object()
        self.assertIs(runtime.WorkspaceStore(client).client, client)
        # Reflection is not a production gate; this reproduces the reported failure
        # and proves why registration matters even for a file-backed import.
        self.assertIn('class WorkspaceStore', inspect.getsource(runtime.WorkspaceStore))
        sys.modules.pop(runtime.__name__)
        with self.assertRaisesRegex(TypeError, 'built-in class'):
            inspect.getsource(runtime.WorkspaceStore)

    def test_digest_mismatch_never_executes(self):
        raw = b'raise AssertionError("must not execute")'
        with self.assertRaisesRegex(RuntimeError, 'source digest mismatch'):
            self.bootstrap(raw, self.digest)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_failed_import_cleans_module_registration(self):
        raw = b'raise RuntimeError("load failure")'
        modules_before = set(sys.modules)
        with self.assertRaisesRegex(RuntimeError, 'load failure'):
            self.bootstrap(raw, hashlib.sha256(raw).hexdigest())
        self.assertFalse([name for name in set(sys.modules) - modules_before
                          if name.startswith('aibi_lifecycle_')])

    def test_introspection_error_does_not_get_unrelated_workspace_hint(self):
        error = ('Traceback (most recent call last):\n  File "/usr/lib/python3.11/inspect.py", line 905\n'
                 "TypeError: <class 'rc.WorkspaceStore'> is a built-in class")
        executor = Executor(SimpleNamespace(), {})
        with patch('subprocess.run', return_value=SimpleNamespace(returncode=1, stderr=error)):
            result = executor.execute('execute_python', {'code':
                "path='/Workspace/helper.py'\nopen('/tmp/helper.py')\ninspect.getsource(rc.WorkspaceStore)"})
        self.assertIn(error, result)
        self.assertIn('HELPER_INTROSPECTION_ERROR', result)
        self.assertNotIn('HINT: /Workspace', result)

    def test_actual_workspace_open_error_retains_specific_hint(self):
        error = "FileNotFoundError: [Errno 2] No such file or directory: '/Workspace/run.yaml'"
        executor = Executor(SimpleNamespace(), {})
        with patch('subprocess.run', return_value=SimpleNamespace(returncode=1, stderr=error)):
            result = executor.execute('execute_python', {'code': "open('/Workspace/run.yaml')"})
        self.assertIn('HINT: /Workspace', result)
        self.assertNotIn('HELPER_INTROSPECTION_ERROR', result)
