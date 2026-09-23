"""Producer, prompt gate, and consumer must agree on checkpoint fingerprints."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tree(name):
    source = (ROOT/'templates'/name).read_text()
    return ast.parse('\n'.join('# '+line if line.startswith('%') else line for line in source.splitlines()))


class FingerprintContractTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT/'agent_skills/v2/prompts/data_layer/validation.md').read_text()
        block = next(b for b in re.findall(r'```python\n(.*?)```', text, re.S)
                     if 'def validate_reconciliation_fingerprints(' in b)
        ns = {}
        exec(compile(block, 'validation.md', 'exec'), ns)
        self.validate = ns['validate_reconciliation_fingerprints']
        self.raw = b'status: PASS\n'
        self.inventory = [{'table_fqn': 'cat.sch.parent_v6', 'schema': [
            {'column': 'id', 'datatype': 'bigint', 'canonical_datatype': 'BIGINT'}]}]
        canonical = lambda x: hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        env = dict(RECONCILIATION_PATH='/out/v6/schema_reconciliation.yaml', CATALOG='cat',
                   SCHEMA='sch', ASSET_SUFFIX='_v6', reconciliation_hash=hashlib.sha256(self.raw).hexdigest(),
                   observed_inventory=self.inventory, _canonical_sha256=canonical)
        manifest = next(n.value for n in tree('ddl_notebook.py.template').body
                        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'manifest' for t in n.targets))
        field = next(v for k, v in zip(manifest.keys, manifest.values)
                     if ast.literal_eval(k) == 'reconcile_schema_output_fingerprints')
        self.produced = eval(compile(ast.Expression(field), 'ddl_template', 'eval'), env)
        consumer = next(n.value for n in tree('dbldatagen_notebook.py.template').body
                        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'expected_output_fingerprints' for t in n.targets))
        self.expected = eval(compile(ast.Expression(consumer), 'synthetic_template', 'eval'),
            {**env, 'artifact_sha256': env['reconciliation_hash'], 'readback_sha256': canonical(self.inventory),
             'readback_locator': 'table_spec:cat.sch:_v6'})

    def check(self, entries):
        return self.validate(entries, self.raw, self.inventory, '/out/v6', 'cat', 'sch', '_v6')

    def test_producer_receipt_matches_prompt_and_consumer(self):
        self.assertEqual(self.produced, self.expected)
        self.assertEqual(self.check(self.produced), self.expected)

    def test_inexact_fields_and_missing_readback_are_rejected(self):
        cases = [self.produced[:1], self.produced + [self.produced[0]]]
        for field, value in [('id', 'schema_reconciliation'), ('kind', 'CANONICAL_JSON'),
                             ('locator', '/out/v5/schema_reconciliation.yaml'), ('sha256', '0'*64)]:
            wrong = copy.deepcopy(self.produced)
            wrong[0][field] = value
            cases.append(wrong)
        for entries in cases:
            with self.subTest(entries=entries), self.assertRaisesRegex(RuntimeError, 'expected=.*observed='):
                self.check(entries)

    def test_changed_artifact_or_catalog_cannot_be_relabelled_valid(self):
        self.raw += b'# changed\n'
        with self.assertRaises(RuntimeError):
            self.check(self.produced)
        self.raw = b'status: PASS\n'
        self.inventory[0]['schema'][0]['datatype'] = 'string'
        with self.assertRaises(RuntimeError):
            self.check(self.produced)
