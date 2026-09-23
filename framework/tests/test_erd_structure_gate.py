"""Run the prompt-owned structural gate against incomplete vision artifacts."""
import copy
from pathlib import Path
import re
import unittest


class ERDStructureGateTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'agent_skills/v2/prompts/data_layer/validation.md'
        source = next(b for b in re.findall(r'```python\n(.*?)```', path.read_text(), re.S)
                      if 'def validate_erd_structure(' in b)
        namespace = {}
        exec(compile(source, str(path), 'exec'), namespace)
        self.validate = namespace['validate_erd_structure']
        self.valid = {'tables': [{'name': 'arbitrary_entity', 'observed': {
            'columns': [{'name': 'business_key', 'datatype': 'STRING'}]}}]}

    def test_canonical_input_preserved(self):
        before = copy.deepcopy(self.valid)
        self.assertIs(self.validate(self.valid), self.valid)
        self.assertEqual(self.valid, before)

    def test_missing_empty_and_misplaced_columns_rejected(self):
        for fields in ({}, {'observed': {}}, {'observed': {'columns': []}},
                       {'columns': [{'name': 'business_key', 'type': 'STRING'}]},
                       {'observed': {'columns': {'business_key': 'STRING'}}}):
            with self.subTest(fields=fields):
                doc = {'tables': [{'name': 'arbitrary_entity', **fields}]}
                before = copy.deepcopy(doc)
                with self.assertRaisesRegex(RuntimeError, 'observed.columns'):
                    self.validate(doc)
                self.assertEqual(doc, before)

    def test_all_tables_checked(self):
        self.valid['tables'].append({'name': 'second_entity'})
        with self.assertRaisesRegex(RuntimeError, 'second_entity'):
            self.validate(self.valid)

    def test_duplicate_column_and_table_names_rejected(self):
        self.valid['tables'][0]['observed']['columns'].append({'name': 'BUSINESS_KEY'})
        with self.assertRaisesRegex(RuntimeError, 'duplicate'):
            self.validate(self.valid)
        self.valid['tables'][0]['observed']['columns'].pop()
        self.valid['tables'].append(copy.deepcopy(self.valid['tables'][0]))
        with self.assertRaisesRegex(RuntimeError, 'duplicate'):
            self.validate(self.valid)

    def test_missing_column_identity_rejected(self):
        self.valid['tables'][0]['observed']['columns'] = [{}]
        with self.assertRaisesRegex(RuntimeError, 'missing identity'):
            self.validate(self.valid)
