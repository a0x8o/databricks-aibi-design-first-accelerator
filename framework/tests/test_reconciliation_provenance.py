"""Check actual DDL-produced provenance against prompt and consumer contracts."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReconciliationProvenanceTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT/'agent_skills/v2/prompts/data_layer/validation.md').read_text()
        source = next(b for b in re.findall(r'```python\n(.*?)```', text, re.S)
                      if 'def validate_reconciliation_provenance(' in b)
        ns = {}
        exec(compile(source, 'validation.md', 'exec'), ns)
        self.validate = ns['validate_reconciliation_provenance']
        source = (ROOT/'templates/ddl_notebook.py.template').read_text()
        tree = ast.parse('\n'.join('# '+line if line.startswith('%') else line for line in source.splitlines()))
        output = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'reconciliation' for t in n.targets))
        self.metadata = {ast.literal_eval(k): ast.literal_eval(v) for k, v in zip(output.keys, output.values)
                         if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
        constants = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
                     and isinstance(n.value, ast.Constant) for t in n.targets if isinstance(t, ast.Name)}
        self.metadata['policy_id'] = constants['POLICY_ID']
        self.metadata['datatype_resolution_policy_id'] = constants['DATATYPE_RESOLUTION_POLICY_ID']
        self.producer_fields = {ast.literal_eval(k) for k in output.keys}
        self.metadata.update(status='PASS', canonical_comparison='MATCH', unresolved_mismatches=[],
            run_id='example', asset_suffix='_v5', table_spec_path='/output/table_spec.yaml',
            schema_assumptions_path='/output/schema_assumptions.yaml',
            table_spec_sha256='a'*64, schema_assumptions_sha256='b'*64,
            expected_schema_sha256='c'*64, observed_schema_sha256='c'*64,
            expected_schema_inventory=[{'table_fqn': 'c.s.t', 'schema': []}],
            observed_schema_inventory=[{'table_fqn': 'c.s.t', 'schema': []}])

    def test_current_producer_matches_gate_and_consumer(self):
        self.assertIs(self.validate(self.metadata), self.metadata)
        self.assertTrue(set(self.metadata).issubset(self.producer_fields))
        source = (ROOT/'templates/dbldatagen_notebook.py.template').read_text()
        tree = ast.parse('\n'.join('# '+line if line.startswith('%') else line for line in source.splitlines()))
        checks = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'parity_checks' for t in n.targets))
        for key, value in zip(checks.keys, checks.values):
            label = ast.literal_eval(key)
            field = label.removeprefix('reconciliation.')
            if label.startswith('reconciliation.') and field in ('artifact_type', 'contract_version', 'producer_step', 'producer_phase'):
                self.assertEqual(self.metadata[field], ast.literal_eval(value.elts[1]))

    def test_absent_null_wrong_provenance_rejected_without_mutation(self):
        for value in (None, 'generate_synthetic_data', ''):
            artifact = {**self.metadata, 'producer_step': value}
            before = dict(artifact)
            with self.assertRaisesRegex(RuntimeError, 'reconciliation.producer_step'):
                self.validate(artifact)
            self.assertEqual(artifact, before)
        del artifact['producer_step']
        with self.assertRaisesRegex(RuntimeError, 'reconciliation.producer_step'):
            self.validate(artifact)

    def test_v5_summary_shaped_artifact_reports_all_defects(self):
        artifact = dict(artifact_type='schema_reconciliation', contract_version=1,
            run_id='example', asset_suffix='_v5', producer_phase='reconcile_schema',
            policy='DEPLOYED_DATATYPE_REPAIR_V1', status='PASS',
            expected_schema_hash='a'*64, observed_schema_hash='a'*64,
            unresolved_mismatches=0, mismatches=[], deployed_tables=[])
        before = dict(artifact)
        with self.assertRaises(RuntimeError) as caught:
            self.validate(artifact)
        for field in ('producer_step', 'policy_id', 'unresolved_mismatches',
                      'table_spec_sha256', 'expected_schema_sha256', 'expected_schema_inventory'):
            self.assertIn('reconciliation.' + field, str(caught.exception))
        self.assertEqual(artifact, before)
