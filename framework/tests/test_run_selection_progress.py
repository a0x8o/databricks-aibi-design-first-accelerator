"""Selection reporting must not turn premature progress into a host exception."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_v2_portability import load
from test_v2_master_host import AgentLoop

ToolExecutor = load('selection_tool_executor','app/llm/tool_executor.py').ToolExecutor
AppStateMirror = load('selection_app_mirror','app/orchestrator/app_state.py').AppStateMirror


class Workspace:
    def __init__(self): self.files = {}; self.reads = []
    def read_file(self,path):
        self.reads.append(path)
        if path not in self.files: raise FileNotFoundError(f'Path ({path}) does not exist')
        return self.files[path]
    def write_file(self,path,content): self.files[path] = content


class SelectionProgressTests(unittest.TestCase):
    def setUp(self):
        self.root='/Workspace/repo/kpi_domains/demo'
        self.path=self.root+'/generated_outputs/v12/run_context.yaml'
        self.ws=Workspace()
        self.config=SimpleNamespace(example_dir=self.root, domain_name='demo', agent_skills_version='v2')
        self.executor=ToolExecutor(self.config, {'workspace':self.ws})
        self.context=dict(domain={'name':'demo'}, version={'number':12}, created_by='app',
            run_id='canonical', output_folder=self.path.rsplit('/',1)[0], run_context_path=self.path)
        self.args=dict(step_name='load_configuration',phase_id='run_selected',phase_name='Run selection',
            status='completed',stats={'run_context_path':self.path})
        self.run=dict(run_id='request',domain='demo',status='running',step_data={})
        self.mirror=AppStateMirror(self.ws,Mock(),self.run,self.root+'/app_runs/request.json')
    def test_started_event_does_not_read_context(self):
        result=self.executor.execute('report_progress',{**self.args,'status':'started'})
        self.mirror.event('phase_update',json.loads(result))
        self.assertNotIn(self.path,self.ws.reads)
        self.assertNotIn('canonical_run_id',self.run)
    def test_early_completion_returns_tool_error(self):
        result=self.executor.execute('report_progress',self.args)
        self.assertTrue(result.startswith('ERROR: RUN_SELECTION_NOT_ACKNOWLEDGED'))
        self.assertIn('does not create run_context.yaml',result)
        self.assertNotIn('canonical_run_id',self.run)
    def test_completed_readback_is_not_repeated_by_ui(self):
        self.ws.files[self.path]=json.dumps(self.context)
        progress=json.loads(self.executor.execute('report_progress',self.args))
        self.ws.reads.clear()
        self.mirror.event('phase_update',progress)
        self.assertNotIn(self.path,self.ws.reads)
        self.assertEqual(self.run['version'],12)
    def test_wrong_domain_cannot_be_acknowledged(self):
        self.ws.files[self.path]=json.dumps({**self.context,'domain':'other'})
        self.assertIn('identity mismatch',self.executor.execute('report_progress',self.args))
    def test_duplicate_context_key_rejected(self):
        self.ws.files[self.path]='domain: demo\ndomain: other\n'
        self.assertIn('duplicate contract key',self.executor.execute('report_progress',self.args))
    def test_missing_path_for_started_is_allowed(self):
        progress=json.loads(self.executor.execute('report_progress',{**self.args,'status':'started','stats':{}}))
        self.mirror.event('phase_update',progress)
        self.assertNotIn('canonical_run_id',self.run)
    def test_malformed_locator_is_diagnosed_without_reading_or_reallocating(self):
        for path in (None, '', {'value': self.path}, self.root + '/generated_outputs/v12',
                     '/Workspace/other/run_context.yaml', self.root + '/../run_context.yaml'):
            with self.subTest(path=path):
                result = self.executor.execute('report_progress', {
                    **self.args, 'stats': {'run_context_path': path}})
                self.assertIn('RUN_SELECTION_NOT_ACKNOWLEDGED', result)
                self.assertIn(repr(path), result)
                self.assertNotIn('allocation does not create', result)
                self.assertIn('Do not allocate another version', result)
        self.assertEqual(self.ws.reads, [])

    def test_corrected_selection_report_preserves_existing_context(self):
        self.ws.files[self.path] = json.dumps(self.context)
        before = dict(self.ws.files)
        result = self.executor.execute('report_progress', {**self.args, 'stats': {}})
        self.assertIn('nonempty plain string', result)
        result = json.loads(self.executor.execute('report_progress', self.args))
        self.assertEqual(result['_validated_run_selection']['canonical_run_id'], 'canonical')
        self.assertEqual(self.ws.files, before)
    def test_agent_can_repair_early_completion_in_same_run(self):
        def response(tool,args,index):
            return {'content':'','tool_calls':[{'id':str(index),'type':'function',
                'function':{'name':tool,'arguments':json.dumps(args)}}]}
        llm=Mock()
        llm.chat_with_tools.side_effect=[
            response('report_progress',{**self.args,'status':'started'},1),
            response('report_progress',self.args,2),
            response('write_workspace_file',{'path':self.path,'content':json.dumps(self.context)},3),
            response('report_progress',self.args,4),
            response('report_step_complete',{'summary':'Contract reporting tested','artifacts':[]},5)]
        captured=[]
        def event(name,data):
            captured.append((name,copy.deepcopy(data)))
            self.mirror.event(name,data)
        result=AgentLoop(llm,self.executor,self.config).run('test',{'STEP_NAME':'master'},callback=event)
        self.assertTrue(result.success)
        self.assertEqual(self.run['canonical_run_id'],'canonical')
        phases=[d for n,d in captured if n=='phase_update']
        self.assertEqual([p['status'] for p in phases],['started','completed'])
        messages=llm.chat_with_tools.call_args_list[2].kwargs['messages']
        self.assertTrue(any('RUN_SELECTION_NOT_ACKNOWLEDGED' in str(m.get('content')) for m in messages))


if __name__=='__main__': unittest.main()
