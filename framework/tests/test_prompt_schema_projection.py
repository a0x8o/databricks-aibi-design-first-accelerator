"""Exercise the prompt projection with the real release validator."""
import copy
from pathlib import Path
import re
import unittest
from test_schema_contract import erd_validation


class PromptProjectionTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'agent_skills/v2/prompts/data_layer/validation.md'
        source = next(block for block in re.findall(r'```python\n(.*?)```', path.read_text(), re.S)
                      if 'def project_table_spec_types(' in block)
        namespace = {}
        exec(compile(source, str(path), 'exec'), namespace)
        self.project = namespace['project_table_spec_types']
        self.validate = erd_validation.validate_table_spec_projection
        self.erd = [{'name': 'example', 'observed': {'columns': [
            {'name': 'key', 'datatype': 'BIGINT'}, {'name': 'value', 'datatype': 'DECIMAL(27,4)'}]}}]
        self.spec = {'catalog': 'target', 'schema': 'example', 'tables': [
            {'name': 'example', 'columns': [{'name': 'key', 'datatype': 'BIGINT', 'nullable': False},
                                          {'name': 'value', 'datatype': 'DECIMAL(27,4)'}]}]}

    def test_erd_field_copied_verbatim_is_projected_before_terminal_check(self):
        self.assertEqual(self.validate(self.erd, self.spec)['status'], 'FAIL')
        original = copy.deepcopy(self.spec)
        candidate, replacements = self.project(self.erd, self.spec, self.validate)
        self.assertEqual(self.validate(self.erd, candidate)['status'], 'PASS')
        self.assertEqual([c['type'] for c in candidate['tables'][0]['columns']], ['BIGINT', 'DECIMAL(27,4)'])
        self.assertFalse(candidate['tables'][0]['columns'][0]['nullable'])
        self.assertEqual(len(replacements), 2)
        self.assertEqual(self.spec, original)
        second, replacements = self.project(self.erd, candidate, self.validate)
        self.assertEqual(second, candidate)
        self.assertEqual(replacements, [])

    def test_empty_authoritative_datatype_is_not_invented(self):
        self.erd[0]['observed']['columns'][0]['datatype'] = ''
        with self.assertRaisesRegex(RuntimeError, 'ERD_EXTRACTION_ERROR'):
            self.project(self.erd, self.spec, self.validate)
        self.assertNotIn('type', self.spec['tables'][0]['columns'][0])

    def test_structural_mismatch_is_not_repaired(self):
        self.spec['tables'][0]['columns'].reverse()
        with self.assertRaisesRegex(RuntimeError, 'column inventory/order mismatch'):
            self.project(self.erd, self.spec, self.validate)

    def test_duplicate_identity_is_rejected_by_real_validator(self):
        self.erd.append(copy.deepcopy(self.erd[0]))
        self.spec['tables'].append(copy.deepcopy(self.spec['tables'][0]))
        with self.assertRaisesRegex(RuntimeError, 'duplicate table names'):
            self.project(self.erd, self.spec, self.validate)
