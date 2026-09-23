"""Exercise the template's actual pure preflight before its Spark write loop."""
import ast
import copy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT/'framework/templates/dbldatagen_notebook.py.template'
TREE = ast.parse('\n'.join(line if not line.lstrip().startswith('%') else '# '+line for line in PATH.read_text().splitlines()))
FN = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_synthetic_spec')
NS = {}
exec(compile(ast.Module(body=[FN],type_ignores=[]),str(PATH),'exec'), NS)
validate = NS['validate_synthetic_spec']
KEY_FN = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_parent_key_values')
exec(compile(ast.Module(body=[KEY_FN], type_ignores=[]), str(PATH), 'exec'), NS)


class SyntheticSpecTests(unittest.TestCase):
    def setUp(self):
        self.tables = [dict(name='parent',columns=[{'name':'id'}]),
                       dict(name='child',columns=[{'name':'id'},{'name':'parent_id'}])]
        self.spec = {'tables':[
            dict(name='parent',rows=10,pk_columns=['id'],domain_columns={},fk_columns={}),
            dict(name='child',rows=20,pk_columns=['id'],domain_columns={},
                 fk_columns={'parent_id':dict(parent_table='parent',parent_pk='id')})]}
    def test_valid_parent_before_child(self):
        self.assertIs(validate(self.spec,self.tables),self.spec)
    def test_missing_parent_pk_reports_location_before_writes(self):
        del self.spec['tables'][1]['fk_columns']['parent_id']['parent_pk']
        with self.assertRaisesRegex(RuntimeError,r'child.fk_columns.parent_id:.*parent_pk.*no data writes started'):
            validate(self.spec,self.tables)
    def test_alias_not_silently_guessed(self):
        fk=self.spec['tables'][1]['fk_columns']['parent_id']
        fk['parent_column']=fk.pop('parent_pk')
        with self.assertRaisesRegex(RuntimeError,'aliases'): validate(self.spec,self.tables)
    def test_unknown_parent_column(self):
        self.spec['tables'][1]['fk_columns']['parent_id']['parent_pk']='missing'
        with self.assertRaisesRegex(RuntimeError,'unknown parent key'): validate(self.spec,self.tables)
    def test_child_before_parent(self):
        self.spec['tables'].reverse()
        with self.assertRaisesRegex(RuntimeError,'parent must precede child'): validate(self.spec,self.tables)
    def test_invalid_domain_in_later_table_rejected_upfront(self):
        self.spec['tables'][1]['domain_columns']={'id':{'values':[1,2],'weights':[1]}}
        with self.assertRaisesRegex(RuntimeError,'equal-length'): validate(self.spec,self.tables)
    def test_multiple_independently_unique_generation_columns_are_supported(self):
        self.tables[0]['columns'].append({'name':'other'})
        self.spec['tables'][0]['pk_columns']=['id','other']
        self.assertIs(validate(self.spec,self.tables), self.spec)
    def test_member_claims_alternate_reference_regression(self):
        # Reproduces the saved semantic/spec mismatch: surrogate PK plus business
        # reference, both generated uniquely (not one composite relationship).
        tables = [dict(name='fact_claim_header', columns=[
            {'name': 'clm_header_sk'}, {'name': 'clm_claim_id'}]),
            dict(name='fact_claim_detail', columns=[{'name': 'clm_dtl_claim_id'}])]
        spec = {'tables': [dict(name='fact_claim_header', rows=10,
            pk_columns=['clm_header_sk', 'clm_claim_id'], domain_columns={}, fk_columns={}),
            dict(name='fact_claim_detail', rows=20, pk_columns=[], domain_columns={},
                 fk_columns={'clm_dtl_claim_id': dict(parent_table='fact_claim_header', parent_pk='clm_claim_id')})]}
        self.assertIs(validate(spec, tables), spec)
    def test_reference_without_unique_generation_strategy_is_rejected(self):
        self.spec['tables'][0]['pk_columns'] = []
        with self.assertRaisesRegex(RuntimeError, 'independently-unique generation'):
            validate(self.spec, self.tables)
    def test_scalar_sampler_rejects_duplicate_composite_components_and_nulls(self):
        check = NS['validate_parent_key_values']
        self.assertEqual(check(['a', 'b'], 'parent.business_id'), ['a', 'b'])
        for values in ([], [None], [1, 1], ['a', 'a']):
            with self.subTest(values=values), self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_SPEC_ERROR'):
                check(values, 'parent.business_id')
    def test_preflight_call_precedes_any_data_write(self):
        text=PATH.read_text()
        self.assertLess(text.index('validate_synthetic_spec(SPEC, TABLE_SPEC_TABLES)'),
                        text.index('df.write.format("delta").mode("append").saveAsTable'))


if __name__=='__main__': unittest.main()
