"""Render and execute complete v2 deployment notebooks against an in-memory SDK.

Exercises transport bootstrap, attested imports, compiler, API calls and persisted
readbacks together. No Databricks access or Spark session is involved.
"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from test_v2_portability import ROOT, runtime, dashboard_policy, genie_policy, gates


class NotFound(Exception):
    pass


class NotebookExit(Exception):
    pass


class FakeWorkspace:
    def __init__(self):
        self.files={}
    def download(self,path):
        if path in self.files:
            return io.BytesIO(self.files[path])
        if Path(path).is_file():
            return io.BytesIO(Path(path).read_bytes())
        raise NotFound(path)
    def upload(self,path,raw,format=None,overwrite=False):
        if not overwrite and path in self.files:
            raise FileExistsError(path)
        self.files[path]=raw
    def mkdirs(self,path):
        pass
    def delete(self,path):
        if path not in self.files:
            raise NotFound(path)
        del self.files[path]
    def list(self,path):
        return []


class NotebookClient:
    def __init__(self):
        self.workspace=FakeWorkspace()
        self.config=SimpleNamespace(host='https://example.databricks.com')
        self.api_client=self
        self.statement_execution=self
        self.dashboard=None
        self.space=None
        self.mutations=[]
    def execute_statement(self,warehouse_id,statement,wait_timeout):
        if statement.startswith('DESCRIBE'):
            names=['col_name','data_type']
            rows=[['period','date'],['amount','bigint measure']]
        else:
            names=['period','amount'];rows=[['2026-01-01','1']]
        return SimpleNamespace(status=SimpleNamespace(state='SUCCEEDED'),
            manifest=SimpleNamespace(schema=SimpleNamespace(columns=[SimpleNamespace(name=n) for n in names])),
            result=SimpleNamespace(data_array=rows))
    def do(self,method,path,body=None,query=None,headers=None):
        if method in {'POST','PATCH','DELETE'} and path != '/api/2.0/sql/statements':
            self.mutations.append((method,path))
        if path == '/api/2.0/sql/statements':
            return {'status':{'state':'SUCCEEDED'},'result':{'data_array':[['1']]},
                'manifest':{'schema':{'columns':[{'name':'amount'}]}}}
        if path == '/api/2.0/lakeview/dashboards':
            if method == 'GET':
                return {'dashboards':[]}
            self.dashboard=dict(body,dashboard_id='dash',update_time='2026-09-22T00:00:00Z')
            return self.dashboard
        if path == '/api/2.0/lakeview/dashboards/dash/published':
            return {'display_name':self.dashboard['display_name'],'warehouse_id':'wh',
                    'revision_create_time':'2026-09-22T00:00:02Z'}
        if path == '/api/2.0/lakeview/dashboards/dash':
            return self.dashboard
        if path == '/api/2.0/genie/spaces':
            if method == 'GET':
                return {'spaces':[]}
            self.space=dict(body,space_id='space')
            return self.space
        if path == '/api/2.0/genie/spaces/space':
            return self.space
        raise AssertionError((method,path))


def reference(path):
    p=ROOT/path
    return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


class NotebookIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client=NotebookClient()
        self.output='/Workspace/test/generated_outputs/v1'
        self.context_path=self.output+'/run_context.yaml'
        self.context=dict(run_id='00000000-0000-0000-0000-000000000001',run_context_path=self.context_path,
            output_folder=self.output,registry_path='/Workspace/test/version_registry.yaml',
            runtime={'workspace_host':self.client.config.host,'state_store':'workspace_only'},
            templates={'run_contract':reference('framework/shared/run_contract.py'),
                'gate_checks':reference('framework/templates/v2_gate_checks.py'),
                'lakeview_dashboard_helpers':reference('framework/templates/v2_lakeview_dashboard_helpers.py')},
            validation=genie_policy(),quality_gates=dashboard_policy(),checkpointing={},phases_completed=[])
        self.context['checkpointing']['frozen_run_contract_sha256']=runtime.canonical_sha256({k:v for k,v in self.context.items() if k != 'phases_completed'})
        self.client.workspace.files[self.context_path]=runtime.encode(self.context)
        self.handoff=dict(warehouse_id='wh',parent_path='/Workspace/test',genie_parent_path='/Workspace/test',
            genie_title='Genie',metric_view_fqns=[{'sql_fqn':'`cat`.`sch`.`mv`','name':'mv','primary':True}])
        self.client.workspace.files[self.output+'/step_handoff.yaml']=runtime.encode(self.handoff)
        sdk=ModuleType('databricks.sdk');sdk.WorkspaceClient=lambda:self.client
        errors=ModuleType('databricks.sdk.errors');errors.NotFound=NotFound
        sql=ModuleType('databricks.sdk.service.sql');sql.StatementState=SimpleNamespace(SUCCEEDED='SUCCEEDED')
        workspace=ModuleType('databricks.sdk.service.workspace');workspace.ImportFormat=SimpleNamespace(AUTO='AUTO')
        modules={'databricks':ModuleType('databricks'),'databricks.sdk':sdk,'databricks.sdk.errors':errors,
            'databricks.sdk.service':ModuleType('databricks.sdk.service'),'databricks.sdk.service.sql':sql,
            'databricks.sdk.service.workspace':workspace}
        self.patch=patch.dict(sys.modules,modules);self.patch.start();self.addCleanup(self.patch.stop)
        self.placeholders=dict(RUN_CONTEXT_PATH=self.context_path,
            RUN_CONTRACT_PATH=self.context['templates']['run_contract']['path'],
            RUN_CONTRACT_SHA256=self.context['templates']['run_contract']['sha256'],DOMAIN_NAME='test')

    def execute(self,name,values):
        source=(ROOT/'framework/templates'/name).read_text()
        for key,value in dict(self.placeholders,**values).items():
            source=source.replace('{{'+key+'}}',value)
        self.assertFalse(re.findall(r'\{\{[A-Z_]+\}\}',source))
        def exit_notebook(value):
            raise NotebookExit(value)
        namespace={'dbutils':SimpleNamespace(notebook=SimpleNamespace(exit=exit_notebook))}
        with contextlib.redirect_stdout(io.StringIO()), patch('time.sleep'):
            try:
                exec(compile(source,name,'exec'),namespace)
            except NotebookExit:
                pass
        return namespace

    def design(self):
        return {'dashboards':[dict(name='Dashboard',metric_views=['`cat`.`sch`.`mv`'],filter_dimensions=['period'],
            primary_kpi_contexts={'KPI_1':['total']},page_contract={'expected_page_ids':['overview']},
            pages=[{'id':'overview','title':'Overview','widgets':[{'id':'total','type':'counter','measure':'amount','title':'Total'}]}])]}

    def test_dashboard_complete_notebook_preserves_design_and_writes_readback(self):
        path=self.output+'/dashboards/dashboard_design.yaml'
        original=runtime.encode(self.design());self.client.workspace.files[path]=original
        self.execute('v2_dashboard_notebook.py.template',dict(CATALOG='cat',SCHEMA='sch',VERSION_SUFFIX='_v1',
            WAREHOUSE_ID='wh',PARENT_PATH='/Workspace/test',OUTPUT_FOLDER=self.output,DEPLOY_ROOT='/Workspace/test',
            METRIC_VIEW_FQNS=repr(['`cat`.`sch`.`mv`']),QUALITY_GATES=repr(dashboard_policy())))
        self.assertEqual(self.client.workspace.files[path],original)
        report=runtime.decode(self.client.workspace.files[self.output+'/dashboards/Dashboard_validation.yaml'])
        self.assertEqual(report['stage_status'],'PASS')
        self.assertIn(self.output+'/dashboards/Dashboard_dashboard_manifest.json',self.client.workspace.files)
        self.assertIn(('POST','/api/2.0/lakeview/dashboards'),self.client.mutations)

    def test_genie_complete_notebook_uses_pinned_gates_and_store(self):
        self.execute('v2_genie_space_notebook.py.template',dict(SPACE_TITLE='Genie',SPACE_DESCRIPTION='A test space',
            WAREHOUSE_ID='wh',PARENT_PATH='/Workspace/test',TABLE_IDENTIFIERS=repr(['cat.sch.mv']),
            GENERAL_INSTRUCTIONS='Use approved measures.',METRIC_VIEW_DESCRIPTIONS=repr({'cat.sch.mv':'Metric view'}),
            SAMPLE_QUESTIONS=repr(['How much?']),EXAMPLE_SQLS=repr([('How much?','SELECT 1')]),
            BENCHMARK_QUESTIONS=repr([('Total?','SELECT 1')]),
            GATE_CHECKS_PATH=self.context['templates']['gate_checks']['path'],
            GATE_CHECKS_SHA256=self.context['templates']['gate_checks']['sha256']))
        report=runtime.decode(self.client.workspace.files[self.output+'/genie_space/Genie_deployment_readback.yaml'])
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['metric_view_fqns'],['cat.sch.mv'])
        self.assertIn(self.output+'/genie_space/Genie_expected.json',self.client.workspace.files)

    def test_bad_runtime_hash_stops_before_mutation(self):
        self.placeholders['RUN_CONTRACT_SHA256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'runtime hash mismatch'):
            self.execute('v2_dashboard_notebook.py.template',dict(CATALOG='cat',SCHEMA='sch',VERSION_SUFFIX='_v1',
                WAREHOUSE_ID='wh',PARENT_PATH='/Workspace/test',OUTPUT_FOLDER=self.output,DEPLOY_ROOT='/Workspace/test',
                METRIC_VIEW_FQNS=repr(['`cat`.`sch`.`mv`']),QUALITY_GATES=repr(dashboard_policy())))
        self.assertFalse(self.client.mutations)


if __name__ == '__main__':
    unittest.main()
