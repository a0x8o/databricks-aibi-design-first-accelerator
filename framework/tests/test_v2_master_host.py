"""Master App transport tests; no live workspace or model calls."""
import copy
import hashlib
import json
import sys
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import Mock, patch

from test_v2_portability import ROOT, runtime, load
package=ModuleType('llm')
package.__path__=[str(ROOT/'app/llm')]
with patch.dict(sys.modules,{'llm':package}):
    host_module=load('portable_master_host','app/orchestrator/master_agent.py')
    from llm.agent_loop import AgentLoop
MasterAgentHost,verify_terminal=host_module.MasterAgentHost,host_module.verify_terminal


class Workspace:
    def __init__(self):
        self.files={}
        self._client=SimpleNamespace(config=SimpleNamespace(host='https://workspace.example'))
    def read_file(self,path):
        if path in self.files:
            return self.files[path]
        return (ROOT/path.removeprefix('/Workspace/repo/')).read_text()
    def list_dir(self,path):
        prefix=path.rstrip('/')+'/'
        return [SimpleNamespace(path=prefix+part) for part in {
            key[len(prefix):].split('/')[0] for key in self.files if key.startswith(prefix)}]


class MasterHostTests(unittest.TestCase):
    def setUp(self):
        self.ws=Workspace()
        self.example='/Workspace/repo/kpi_domains/demo'
        self.output=self.example+'/output/v1'
        self.path=self.output+'/run_manifest.json'
        self.context=dict(lifecycle_contract_version=1,domain='demo',version=1,
            run_id='run-1',created_by='app',output_folder=self.output,
            run_context_path=self.output+'/run_context.yaml',status='completed',
            registry_path=self.example+'/version_registry.yaml',checkpointing={})
        frozen=copy.deepcopy(self.context)
        frozen.pop('status')
        self.context['checkpointing']['frozen_run_contract_sha256']=runtime.canonical_sha256(frozen)
        report=dict(overall_status='PASS',run_id='run-1',output_folder=self.output,
            scope_input_binding='PASS',workspace_host_binding='PASS',
            expected_inventory={'tables':['cat.sch.t']},observed_inventory={'tables':['cat.sch.t']})
        self.ws.files[self.output+'/ground_truth_validation.yaml']=json.dumps(report)
        self.manifest=copy.deepcopy(self.context)
        self.manifest['validation']={'cross_validation':dict(status='PASS',source='cross_validation_sweep',
            ground_truth_validation_sha256=hashlib.sha256(json.dumps(report).encode()).hexdigest())}
        self.persist()
    def persist(self):
        self.ws.files[self.path]=json.dumps(self.manifest)
        self.ws.files[self.context['run_context_path']]=json.dumps(self.context)
        self.ws.files[self.context['registry_path']]=json.dumps({'versions':[self.context]})
    def verify(self):
        return verify_terminal(self.ws,[self.path],example_dir=self.example,domain='demo')
    def test_success_requires_persisted_evidence(self):
        self.assertEqual(self.verify()['status'],'completed')
    def test_manifest_mapping_domain_matches_lifecycle_identity(self):
        self.manifest['domain'] = {'name': 'demo', 'display_name': 'Demonstration'}
        self.persist()
        self.assertEqual(self.verify()['status'], 'completed')
    def test_wrong_domain_and_owner_remain_rejected_with_observed_values(self):
        for field, value, expected in [('domain', {'name': 'other'}, 'domain expected='),
                                       ('created_by', 'genie_code', 'created_by expected='),
                                       ('run_id', 123, 'run_id must be')]:
            with self.subTest(field=field):
                prior = self.manifest[field]
                self.manifest[field] = value
                self.persist()
                with self.assertRaisesRegex(RuntimeError, expected):
                    self.verify()
                self.manifest[field] = prior
    def test_normalized_domain_does_not_bypass_run_parity(self):
        self.manifest.update(domain={'name': 'demo'}, run_id='another-run')
        self.persist()
        with self.assertRaisesRegex(RuntimeError, 'lifecycle parity mismatch'):
            self.verify()
    def test_text_completion_cannot_replace_manifest(self):
        with self.assertRaisesRegex(RuntimeError,'locator required'):
            verify_terminal(self.ws,[],example_dir=self.example,domain='demo')
    def test_lock_rejects_completion(self):
        self.ws.files[self.context['registry_path']+'.lock']='busy'
        with self.assertRaisesRegex(RuntimeError,'active lifecycle lock'): self.verify()
    def test_tampered_frozen_context_rejected(self):
        self.context['runtime']={'workspace_host':'wrong'}
        self.persist()
        with self.assertRaisesRegex(RuntimeError,'frozen context'): self.verify()
    def test_stale_sweep_rejected(self):
        self.ws.files[self.output+'/ground_truth_validation.yaml']='{}'
        with self.assertRaisesRegex(RuntimeError,'sweep evidence'): self.verify()
    def test_master_host_uses_same_prompt_without_lakebase(self):
        config=SimpleNamespace(example_dir=self.example,deploy_root='/Workspace/repo',
            framework_root='/Workspace/repo/framework',sql_warehouse_id='warehouse')
        host=MasterAgentHost(config,{'workspace':self.ws},Mock())
        host.agent=Mock()
        host.agent.run.return_value=SimpleNamespace(artifacts=[self.path],error=None)
        result=host.run(domain='demo',run_id='candidate',steps=['create_data_layer'])
        self.assertEqual(result['status'],'completed')
        args,kwargs=host.agent.run.call_args
        self.assertEqual(args[0],(ROOT/'framework/agent_skills/v2/prompts/00_master_prompt.md').read_text())
        self.assertEqual(args[1]['workspace_host'],'https://workspace.example')
        self.assertEqual(args[1]['requested_steps'],['create_data_layer'])
        self.assertIn('Portable agent execution contract',kwargs['system_supplement'])
    def test_no_tool_response_is_not_master_success(self):
        llm=Mock()
        llm.chat_with_tools.return_value={'content':'Done','tool_calls':[]}
        result=AgentLoop(llm,Mock(),Mock()).run('master',{'STEP_NAME':'master'})
        self.assertFalse(result.success)


if __name__=='__main__': unittest.main()
