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
    def test_composite_parent_key_not_sampled_independently(self):
        self.tables[0]['columns'].append({'name':'other'})
        self.spec['tables'][0]['pk_columns']=['id','other']
        with self.assertRaisesRegex(RuntimeError,'composite keys'): validate(self.spec,self.tables)
    def test_preflight_call_precedes_any_data_write(self):
        text=PATH.read_text()
        self.assertLess(text.index('validate_synthetic_spec(SPEC, TABLE_SPEC_TABLES)'),
                        text.index('df.write.format("delta").mode("append").saveAsTable'))


if __name__=='__main__': unittest.main()
