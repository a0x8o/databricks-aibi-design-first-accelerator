"""Validate resolved target identifiers before any UC DDL mutation."""
import ast
from pathlib import Path
import unittest
from test_v2_portability import load

ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'framework/templates/ddl_notebook.py.template'
tree=ast.parse(path.read_text())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_uc_target_names')
ns={}
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns)
validate=ns['validate_uc_target_names']
erd=load('identifier_erd_helper','framework/templates/erd_validation_utils.py')


class IdentifierTests(unittest.TestCase):
    def test_dotted_name_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'GENERATED_IDENTIFIER_ERROR'):
            validate('cat','sch',[{'name':'dim.provider'}],'_v14')
    def test_all_targets_validated_before_create_schema(self):
        text=path.read_text()
        self.assertLess(text.index("validate_uc_target_names(CATALOG, SCHEMA, spec.get('tables', []), ASSET_SUFFIX)"),
                        text.index('spark.sql(f"CREATE SCHEMA'))
    def test_valid_names_are_not_rewritten(self):
        tables=[{'name':'dim_provider'},{'name':'provider-detail'},{'name':'医師'}]
        original=repr(tables)
        validate('cat','sch',tables,'_v14')
        self.assertEqual(repr(tables),original)
    def test_suffix_length_limit(self):
        with self.assertRaisesRegex(RuntimeError,'deployed table name'):
            validate('cat','sch',[{'name':'a'*252}],'_v14')
    def test_collision_after_case_folding(self):
        with self.assertRaisesRegex(RuntimeError,'collision'):
            validate('cat','sch',[{'name':'Provider'},{'name':'provider'}],'_v14')
    def test_namespace_and_suffix_are_checked(self):
        for cat,sch,suffix in [('cat.a','sch','_v14'),('cat','some schema','_v14'),('cat','sch','.v14')]:
            with self.subTest(cat=cat,sch=sch,suffix=suffix),self.assertRaises(RuntimeError):
                validate(cat,sch,[{'name':'provider'}],suffix)
    def test_erd_rejects_bad_name_before_ddl(self):
        tables=[{'name':'dim.provider','observed':{'columns':[{'name':'id','datatype':'bigint','key_marker':'PK'}]}}]
        _,report=erd.validate_erd_output(tables)
        self.assertEqual(report['status'],'FAIL')
        self.assertTrue(any('GENERATED_IDENTIFIER_ERROR' in e for e in report['errors']))


if __name__=='__main__': unittest.main()
