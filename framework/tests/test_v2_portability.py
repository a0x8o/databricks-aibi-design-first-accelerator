"""Contract integration tests with fake transport; no credentials or live assets."""
import ast
import copy
import importlib.util
import inspect
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('v2_run_contract', 'framework/shared/run_contract.py')
gates = load('v2_readback', 'framework/templates/v2_gate_checks.py')


def dashboard():
    query = {'name':'main','query':{'datasetName':'ds','fields':[{'name':'amount','expression':'amount'}]}}
    return {'datasets':[{'name':'ds','queryLines':['SELECT 1 AS amount']}], 'pages':[
        {'name':'overview','pageType':'PAGE_TYPE_CANVAS','layout':[{'widget':{
            'name':'total','queries':[query], 'spec':{'widgetType':'counter'}}}]},
        {'name':'filters','pageType':'PAGE_TYPE_GLOBAL_FILTERS','layout':[{'widget':{
            'name':'filter','queries':[query], 'spec':{'widgetType':'filter-single-select',
                'encodings':{'fields':[{'queryName':'main','fieldName':'amount'}]}}}}]}]}


def dashboard_policy():
    result={key:1 for key in ['min_canvas_pages_per_dashboard','min_widgets_per_canvas_page',
        'max_widgets_per_canvas_page','min_visualization_types_per_dashboard','min_filters_per_dashboard',
        'min_filter_pages_per_dashboard','min_widget_contexts_per_primary_kpi']}
    result['max_widgets_per_canvas_page']=8
    result['dashboard_policy']={'policy_id':'DASHBOARD_GATE_POLICY_V1', 'quality_target_fields':[
        key for key in result if key != 'min_filter_pages_per_dashboard']}
    return result


def genie():
    return {'version':2,'data_sources':{'metric_views':[{'identifier':'cat.sch.mv'}]},
        'config':{'sample_questions':[{'id':'q','question':['How much?']}]},
        'instructions':{'text_instructions':[{'id':'t','content':['Use approved measures.']}],
            'example_question_sqls':[{'id':'e','question':['How much?'],'sql':['SELECT 1']}]},
        'benchmarks':{'questions':[{'id':'b','question':['Total?'],'answer':[{'format':'SQL','content':['SELECT 1']}]}]}}


def genie_policy():
    path=ROOT/'framework/agent_skills/v2/contracts/genie_quality_contract.yaml'
    contract=yaml.safe_load(path.read_text())
    result=dict(contract['thresholds'])
    result.update(min_instruction_chars=1,min_sample_questions=1,min_example_sqls=1,min_benchmark_questions=1)
    result['benchmark_outcomes']=contract['outcome_semantics']['benchmark']
    result.update(genie_quality_contract_name='genie_quality', genie_quality_contract_version=contract['contract']['contract_version'],
        genie_quality_contract_sha256=runtime.hashlib.sha256(path.read_bytes()).hexdigest(),
        genie_quality_policy_id=contract['contract']['policy_id'])
    result['genie_quality_effective_policy_sha256']=gates.canonical_sha256(dict(policy_id=result['genie_quality_policy_id'],
        thresholds={key:result[key] for key in contract['thresholds']},benchmark_outcomes=result['benchmark_outcomes']))
    return result


class Client:
    def __init__(self):
        self.config=SimpleNamespace(host='https://example.databricks.com/')
        self.api_client=self
        self.sd=dashboard()
        self.ss=genie()
        self.calls=[]
        self.sql_failure=False
        self.publication={'display_name':'Dashboard','warehouse_id':'wh','revision_create_time':'2026-09-22T00:00:02Z'}
        self.title='Genie'

    def do(self, method, path, body=None, query=None):
        self.calls.append((method,path,body))
        if path.endswith('/published'):
            return self.publication
        if path == '/api/2.0/lakeview/dashboards/dash':
            return dict(dashboard_id='dash',display_name='Dashboard',serialized_dashboard=self.sd,
                etag='draft',update_time='2026-09-22T00:00:01Z')
        if path == '/api/2.0/genie/spaces/space':
            return dict(space_id='space', title=self.title, warehouse_id='wh', serialized_space=self.ss)
        if path == '/api/2.0/sql/statements':
            if self.sql_failure:
                return {'status':{'state':'FAILED','error':'simulated failure'}}
            sql=body['statement']
            rows = [['id','int']] if sql.startswith('DESCRIBE') else [['CREATE TABLE cat.sch.tbl (id INT) USING DELTA']] if sql.startswith('SHOW CREATE') else [['1']]
            return {'status':{'state':'SUCCEEDED'},'result':{'data_array':rows},'manifest':{'schema':{'columns':[{'name':'result'}]}}}
        raise AssertionError(f'Unexpected API call: {method} {path}')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=self.directory.name
        self.store=runtime.LocalStore()
        self.arguments=dict(registry_path=self.root+'/version_registry.yaml',domain='test',
            output_root=self.root+'/outputs',created_by='another_agent',run_id=str(uuid.uuid4()),store=self.store)

    def allocate(self):
        selection=runtime.resolve_version(**self.arguments)
        context={k:v for k,v in selection.items() if k not in {'is_new','version_suffix'}}
        context['retry_attempt']=0
        self.store.write(selection['run_context_path'],runtime.encode(context))
        return selection,context

    def test_fresh_and_same_owner_resume_preserve_identity(self):
        selected,context=self.allocate()
        again=runtime.resolve_version(**dict(self.arguments,run_id=str(uuid.uuid4())))
        self.assertFalse(again['is_new'])
        self.assertEqual(again['run_id'],selected['run_id'])
        self.assertEqual(again['registry_path'],self.arguments['registry_path'])
        self.assertEqual(again['version_suffix'],'_v1')

    def test_new_owner_gets_new_version(self):
        self.allocate()
        self.assertEqual(runtime.resolve_version(**dict(self.arguments,created_by='genie_code'))['version'],2)

    def test_orphan_allocation_cannot_resume(self):
        runtime.resolve_version(**self.arguments)
        with self.assertRaisesRegex(RuntimeError,'context missing'):
            runtime.resolve_version(**self.arguments)

    def test_legacy_folders_reserve_versions(self):
        Path(self.arguments['output_root']+'/v12').mkdir(parents=True)
        Path(self.arguments['output_root']+'/v99_old').mkdir()
        self.assertEqual(runtime.resolve_version(**self.arguments)['version'],13)

    def test_conflicting_identity_stops_resume(self):
        selected,context=self.allocate()
        context['run_id']=str(uuid.uuid4())
        self.store.write(selected['run_context_path'],runtime.encode(context))
        with self.assertRaisesRegex(RuntimeError,'parity'):
            runtime.resolve_version(**self.arguments)

    def test_failed_retry_archives_and_reopens_all_workspace_stores(self):
        selected,context=self.allocate()
        manifest=dict(context,status='failed',error='test error')
        runtime.commit_terminal(store=self.store,registry_path=self.arguments['registry_path'],run_context_path=selected['run_context_path'],manifest=manifest)
        again=runtime.resolve_version(**dict(self.arguments,mode='retry',run_id=str(uuid.uuid4())))
        reopened=runtime.decode(self.store.read(selected['run_context_path']))
        self.assertEqual((again['run_id'],again['status'],reopened['retry_attempt']),(selected['run_id'],'running',1))
        self.assertIsNone(self.store.read(selected['output_folder']+'/run_manifest.json'))
        self.assertEqual(runtime.decode(self.store.read(selected['output_folder']+'/.lifecycle/attempt_0_manifest.json'))['status'],'failed')
        self.assertIsNone(self.store.read(selected['output_folder']+'/.lifecycle/retry_transition.yaml'))

    def test_failed_auto_allocates_fresh_version(self):
        selected,context=self.allocate()
        runtime.commit_terminal(store=self.store,registry_path=self.arguments['registry_path'],run_context_path=selected['run_context_path'],manifest=dict(context,status='failed'))
        self.assertEqual(runtime.resolve_version(**self.arguments)['version'],2)

    def test_terminal_failure_rolls_back(self):
        selected,context=self.allocate()
        write=self.store.write
        failures=[True]
        # Fail only the final registry write, after manifest/context writes.
        def fail_registry(path,raw,**kwargs):
            if path == self.arguments['registry_path'] and failures:
                failures.pop()
                raise OSError('simulated transport failure')
            write(path,raw,**kwargs)
        with patch.object(self.store,'write',side_effect=fail_registry):
            with self.assertRaises(OSError):
                runtime.commit_terminal(store=self.store,registry_path=self.arguments['registry_path'],run_context_path=selected['run_context_path'],manifest=dict(context,status='completed'))
        self.assertEqual(runtime.decode(self.store.read(selected['run_context_path']))['status'],'running')
        self.assertIsNone(self.store.read(selected['output_folder']+'/run_manifest.json'))

    def test_lock_is_not_stolen(self):
        with self.store.lock(self.arguments['registry_path']+'.lock'):
            with self.assertRaises(FileExistsError):
                runtime.resolve_version(**self.arguments)

    def test_duplicate_yaml_keys_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            runtime.decode(b'run_id: one\nrun_id: two\n')

    def test_attested_loader_rejects_wrong_bytes(self):
        with self.assertRaisesRegex(RuntimeError,'hash mismatch'):
            runtime.load_attested(self.store,{'path':str(ROOT/'framework/templates/v2_gate_checks.py'),'sha256':'0'*64})


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.client=Client()
        self.expected=dict(workspace_host=self.client.config.host.rstrip('/'),warehouse_id='wh',
            serialized_dashboard=copy.deepcopy(self.client.sd),primary_kpi_contexts={'KPI_1':['total']})
        self.genie_expected=dict(workspace_host=self.expected['workspace_host'],warehouse_id='wh',
            serialized_space=copy.deepcopy(self.client.ss),metric_view_fqns=['`cat`.`sch`.`mv`'])

    def dashboard(self,policy=None):
        return gates.validate_dashboard_from_api(self.client,'dash','Dashboard',quality_gates=policy or dashboard_policy(),expected=self.expected)

    def test_dashboard_pass_with_complete_contract(self):
        result=self.dashboard()
        self.assertEqual(result['stage_status'],'PASS')
        self.assertEqual(result['workspace_host_binding'],'PASS')
        self.assertTrue(result['datasets_validated'])
        self.assertEqual(result['readback_counts']['dataset_count'],1)

    def test_quality_target_miss_is_warn_not_structural_failure(self):
        policy=dashboard_policy();policy['min_widgets_per_canvas_page']=4
        result=self.dashboard(policy)
        self.assertEqual((result['structural_status'],result['quality_target_status'],result['stage_status']),('PASS','WARN','PARTIAL_SUCCESS'))

    def test_empty_canvas_fails(self):
        self.client.sd['pages'][0]['layout']=[]
        self.expected['serialized_dashboard']=copy.deepcopy(self.client.sd)
        with self.assertRaisesRegex(gates.GateCheckError,'Empty page'):
            self.dashboard()

    def test_host_mismatch_fails_before_api(self):
        self.expected['workspace_host']='https://wrong.example'
        with self.assertRaisesRegex(gates.GateCheckError,'host mismatch'):
            self.dashboard()
        self.assertFalse(self.client.calls)

    def test_readback_drift_fails(self):
        self.client.sd['datasets'][0]['queryLines']=['SELECT 2']
        with self.assertRaisesRegex(gates.GateCheckError,'differs'):
            self.dashboard()

    def test_old_publication_does_not_validate_new_draft(self):
        self.client.publication['revision_create_time']='2026-09-21T00:00:00Z'
        with self.assertRaisesRegex(gates.GateCheckError,'predates'):
            self.dashboard()

    def test_sql_failure_blocks_dashboard(self):
        self.client.sql_failure=True
        with self.assertRaisesRegex(gates.GateCheckError,'SQL readback failed'):
            self.dashboard()

    def test_invalid_filter_binding_fails(self):
        self.expected['serialized_dashboard']['pages'][1]['layout'][0]['widget']['spec']['encodings']['fields'][0]['queryName']='missing'
        with self.assertRaisesRegex(gates.GateCheckError,'binding'):
            self.dashboard()

    def test_genie_pass_and_response_alias(self):
        self.client.ss['data_sources']['tables']=self.client.ss['data_sources'].pop('metric_views')
        result=gates.validate_genie_from_api(self.client,'space','Genie',validation=genie_policy(),expected=self.genie_expected)
        self.assertEqual(result['metric_view_fqns'],['cat.sch.mv'])
        self.assertEqual(result['readback_counts']['benchmark_count'],1)

    def test_genie_content_drift_fails(self):
        self.client.ss['instructions']['text_instructions'][0]['content']=['Different instructions']
        with self.assertRaisesRegex(gates.GateCheckError,'content differs'):
            gates.validate_genie_from_api(self.client,'space','Genie',validation=genie_policy(),expected=self.genie_expected)

    def test_genie_threshold_and_title_fail(self):
        self.client.title='Wrong title'
        with self.assertRaisesRegex(gates.GateCheckError,'identity'):
            gates.validate_genie_from_api(self.client,'space','Genie',validation=genie_policy(),expected=self.genie_expected)

    def test_sweep_rejects_empty_scope(self):
        result=gates.run_cross_validation(self.client,scope={},quality_gates={},validation={})
        self.assertEqual(result['overall_status'],'FAIL')
        self.assertTrue(result['errors'])

    def scope(self):
        return dict(run_id=str(uuid.uuid4()),output_folder='/Workspace/test/v1',workspace_host=self.client.config.host,
            warehouse_id='wh',frozen_run_contract_sha256='a'*64,producer_bundles={key:'b'*64 for key in ['create_data_layer','create_metric_views','create_dashboards','create_genie_space','generate_documentation']},enabled_asset_classes=['tables'],expected_inventory={
                'tables':[{'sql_fqn':'`cat`.`sch`.`tbl`','columns':[['id','int']],
                    'definition':'CREATE TABLE cat.sch.tbl (id INT) USING DELTA',
                    'validation_queries':[{'sql':'SELECT COUNT(*) FROM `cat`.`sch`.`tbl`','check':'positive_count'}]}],
                'metric_views':[],'dashboards':[],'genie_spaces':[]})

    def test_sweep_checks_table_definition_schema_and_rows(self):
        result=gates.run_cross_validation(self.client,scope=self.scope(),quality_gates={},validation={})
        self.assertEqual(result['overall_status'],'PASS')
        self.assertEqual(result['observed_inventory'],result['expected_inventory'])
        self.assertEqual(len(self.client.calls),3)

    def test_sweep_reports_owner_on_schema_failure(self):
        scope=self.scope();scope['expected_inventory']['tables'][0]['columns']=[['wrong','int']]
        result=gates.run_cross_validation(self.client,scope=scope,quality_gates={},validation={})
        self.assertEqual((result['overall_status'],result['failure_owner']),('FAIL','DATA_LAYER_STAGE'))

    def test_sweep_rejects_missing_enabled_asset_inventory(self):
        scope=self.scope();scope['enabled_asset_classes'].append('dashboards')
        result=gates.run_cross_validation(self.client,scope=scope,quality_gates={},validation={})
        self.assertEqual(result['overall_status'],'FAIL')

    def test_failure_report_is_persisted_and_hashed(self):
        result=gates.run_cross_validation(self.client,scope={},quality_gates={},validation={})
        with tempfile.TemporaryDirectory() as directory:
            path=directory+'/ground_truth_validation.yaml';store=runtime.LocalStore()
            digest=gates.write_ground_truth_validation(path,result,store=store)
            self.assertEqual(runtime.decode(store.read(path))['overall_status'],'FAIL')
            self.assertEqual(len(digest),64)


class ReleaseTests(unittest.TestCase):
    def test_release_paths_exist_and_erd_interface_is_current(self):
        release=yaml.safe_load((ROOT/'framework/agent_skills/v2/contracts/release.yaml').read_text())
        for section in ('helpers','templates','inputs'):
            for path in release[section].values():
                self.assertTrue((ROOT/path).is_file(),path)
        erd=load('release_erd',release['helpers']['erd_validation_utils'])
        self.assertTrue(callable(erd.resolve_greenfield_synthetic_datatypes))
        self.assertIsNone(erd.validate_datatype('DECIMAL(28)'))

    def test_example_bootstrap_matches_master_contract(self):
        folder=ROOT/'kpi_domains/member_claims'
        config=yaml.safe_load((folder/'accelerator.yaml').read_text())
        master=config['paths']['master_prompt'].format(agent_skills_version=config['workspace']['agent_skills_version'])
        self.assertTrue((folder/master).is_file())
        self.assertIn('erd_parse',config['llm']['steps'])

    def test_template_python_syntax_and_attestation_placeholders(self):
        for name in ['v2_dashboard_notebook.py.template','v2_genie_space_notebook.py.template']:
            source=(ROOT/'framework/templates'/name).read_text()
            ast.parse(re.sub(r'\{\{[A-Z_]+\}\}','None',source))
            for key in ('RUN_CONTEXT_PATH','RUN_CONTRACT_PATH','RUN_CONTRACT_SHA256'):
                self.assertIn('{{'+key+'}}',source)
            self.assertNotIn('except ImportError:',source)
            self.assertNotIn('spark.sql(',source)

    def test_metric_verification_halts_on_failed_query(self):
        source=(ROOT/'framework/templates/metric_view_notebook.py.template').read_text()
        start=source.index('VERIFICATION_RESULTS = []');end=source.index('# COMMAND ----------',start)
        def sql(statement):
            if statement.startswith('SHOW VIEWS'):
                return SimpleNamespace(result=SimpleNamespace(data_array=[['view']]))
            raise RuntimeError('failed query')
        context=dict(MV_SPECS=[{'name':'mv','yaml':{'measures':[{'name':'amount'}]}}],CATALOG='c',SCHEMA='s',
            DEPLOYED_VIEWS=['mv'],execute_sql=sql)
        with self.assertRaisesRegex(RuntimeError,'Verification FAILED'):
            exec(source[start:end],context)

    def test_validator_interfaces_match_documented_calls(self):
        inspect.signature(gates.validate_dashboard_from_api).bind(Client(),'id','name',quality_gates={},expected={})
        inspect.signature(gates.validate_genie_from_api).bind(Client(),'id','name',validation={},expected={})


if __name__ == '__main__':
    unittest.main()
