"""Template failures must not be followed by consumer notebook execution."""
import ast
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_v2_portability import load, ROOT
from test_v2_master_host import AgentLoop

Executor=load('admission_executor','app/llm/tool_executor.py').ToolExecutor

class DeploymentAdmissionTests(unittest.TestCase):
    def test_missing_placeholders_prevent_import(self):
        ws=Mock();ws.read_file.return_value='catalog="{{TARGET_CATALOG}}"\nschema="{{TARGET_SCHEMA}}"'
        result=Executor(SimpleNamespace(),{'workspace':ws}).execute('deploy_from_template',
            dict(template_path='/template',output_path='/notebook',placeholders={'CATALOG':'wrong'}))
        self.assertIn('TARGET_CATALOG',result); self.assertIn('TARGET_SCHEMA',result)
        ws.import_notebook.assert_not_called()
    def test_null_and_empty_placeholders_rejected(self):
        ws=Mock();ws.read_file.return_value='{{TARGET_CATALOG}} {{TARGET_SCHEMA}}'
        result=Executor(SimpleNamespace(),{'workspace':ws}).execute('deploy_from_template',
            dict(template_path='/template',output_path='/notebook',placeholders={'TARGET_CATALOG':None,'TARGET_SCHEMA':''}))
        self.assertIn('TEMPLATE_BINDING_ERROR',result)
        ws.import_notebook.assert_not_called()
    def test_template_failure_halts_before_next_tool_even_in_same_response(self):
        executor=Mock();executor.execute.return_value='ERROR: TEMPLATE_BINDING_ERROR: TARGET_CATALOG missing'
        calls=[{'id':str(i),'type':'function','function':{'name':name,'arguments':'{}'}}
               for i,name in enumerate(['deploy_from_template','execute_notebook'])]
        llm=Mock();llm.chat_with_tools.return_value={'content':'','tool_calls':calls}
        result=AgentLoop(llm,executor,SimpleNamespace()).run('master',{'STEP_NAME':'master'})
        self.assertFalse(result.success)
        self.assertEqual(executor.execute.call_count,1)
        self.assertIn('deploy_from_template',result.error)
    def test_legacy_dashboard_rejected_by_release(self):
        root='/Workspace/repo';old=root+'/framework/templates/dashboard_notebook.py.template'
        files={old:'legacy source',root+'/framework/agent_skills/v2/contracts/release.yaml':
               'templates:\n  dashboard_notebook: framework/templates/v2_dashboard_notebook.py.template\n'}
        ws=Mock();ws.read_file.side_effect=files.__getitem__
        config=SimpleNamespace(agent_skills_version='v2',framework_root=root+'/framework',deploy_root=root)
        result=Executor(config,{'workspace':ws}).execute('deploy_from_template',dict(template_path=old,output_path='/out'))
        self.assertIn('TEMPLATE_AUTHORITY_ERROR',result);ws.import_notebook.assert_not_called()
    def test_selected_template_requires_matching_frozen_digest(self):
        root='/Workspace/repo';template=root+'/framework/templates/v2_dashboard_notebook.py.template'
        context=root+'/run_context.yaml'
        files={template:'valid source',root+'/framework/agent_skills/v2/contracts/release.yaml':
            'templates:\n  dashboard_notebook: framework/templates/v2_dashboard_notebook.py.template\n',
            context:json.dumps({'templates':{'dashboard_notebook':{'path':template,'sha256':'wrong'}}})}
        ws=Mock();ws.read_file.side_effect=files.__getitem__
        executor=Executor(SimpleNamespace(agent_skills_version='v2',framework_root=root+'/framework',deploy_root=root),{'workspace':ws})
        executor._run_context_path=context
        args=dict(template_path=template,output_path='/out')
        self.assertIn('frozen path/digest',executor.execute('deploy_from_template',args))
        ws.import_notebook.assert_not_called()
        files[context]=json.dumps({'templates':{'dashboard_notebook':{'path':template,'sha256':hashlib.sha256(b'valid source').hexdigest()}}})
        self.assertTrue(executor.execute('deploy_from_template',args).startswith('SUCCESS'))
        ws.import_notebook.assert_called_once()
    def test_notebook_error_tail_survives_agent_and_callback(self):
        error='NOTEBOOK ERROR: '+('x'*3000)+' /Workspace/full/path/dashboard_design.yaml'
        executor=Mock();executor.execute.return_value=error
        llm=Mock();llm.chat_with_tools.return_value={'content':'','tool_calls':[{'id':'one','type':'function',
            'function':{'name':'execute_notebook','arguments':'{}'}}]}
        events=[]
        result=AgentLoop(llm,executor,SimpleNamespace()).run('master',{'STEP_NAME':'master'},callback=lambda n,d:events.append((n,d)))
        self.assertTrue(result.error.endswith('dashboard_design.yaml'))
        critical=next(d for n,d in events if n=='critical_failure')
        self.assertEqual(critical['error'],error)
    def test_jobs_traceback_is_preserved(self):
        path=ROOT/'app/services/jobs_client.py';tree=ast.parse(path.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_format_run_error')
        ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns)
        self.assertEqual(ns['_format_run_error'](SimpleNamespace(error='summary',error_trace='full traceback')),
                         'summary\n\nfull traceback')

if __name__=='__main__': unittest.main()
