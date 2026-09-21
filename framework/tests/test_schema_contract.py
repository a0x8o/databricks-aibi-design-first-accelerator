"""Regression tests for the data-layer schema reconciliation contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str):
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


erd_validation = _load_module(
    "erd_validation_utils_under_test", "templates/erd_validation_utils.py"
)
gate_checks = _load_module("gate_checks_under_test", "templates/gate_checks.py")


def _erd_table(*datatypes: str) -> list[dict]:
    return [
        {
            "name": "fact_claim_detail",
            "observed": {
                "columns": [
                    {
                        "name": f"amount_{index}",
                        "datatype": datatype,
                        "key_marker": "PK" if index == 0 else "",
                    }
                    for index, datatype in enumerate(datatypes)
                ]
            },
        }
    ]


class DatatypeValidationTests(unittest.TestCase):
    def test_complete_decimal_types_are_preserved(self):
        expected = ["DECIMAL(27,4)", "DECIMAL(28,4)", "DECIMAL(38,4)"]
        tables = _erd_table(*expected)

        normalized, changes = erd_validation.validate_and_fix_datatypes(tables)

        self.assertEqual(changes, [])
        self.assertEqual(
            [column["datatype"] for column in normalized[0]["observed"]["columns"]],
            expected,
        )
        self.assertEqual(
            erd_validation.validate_schema_for_ddl(normalized)["status"], "PASS"
        )

    def test_incomplete_decimals_are_rejected_without_mutation(self):
        incomplete = ["DECIMAL(27", "DECIMAL(28)", "DECIMAL(38,)", ""]
        tables = _erd_table(*incomplete)

        normalized, changes = erd_validation.validate_and_fix_datatypes(tables)
        report = erd_validation.validate_schema_for_ddl(normalized)

        self.assertEqual(changes, [])
        self.assertEqual(
            [column["datatype"] for column in normalized[0]["observed"]["columns"]],
            incomplete,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(len(report["errors"]), len(incomplete))
        self.assertNotIn("DECIMAL(27,2)", repr(normalized))
        self.assertNotIn("DECIMAL(28,2)", repr(normalized))
        self.assertNotIn("DECIMAL(38,2)", repr(normalized))

    def test_invalid_decimal_bounds_are_rejected(self):
        invalid = ["DECIMAL(0,0)", "DECIMAL(39,4)", "DECIMAL(10,11)"]

        for datatype in invalid:
            with self.subTest(datatype=datatype):
                self.assertIsNotNone(erd_validation.validate_datatype(datatype))
                with self.assertRaises(ValueError):
                    gate_checks.canonicalize_databricks_type(datatype)


class DeploymentGateTests(unittest.TestCase):
    SPEC = {
        "tables": [
            {
                "name": "fact_claim_detail",
                "columns": [
                    {"name": "claim_id", "type": "BIGINT"},
                    {"name": "allowed_amt", "type": "DECIMAL(28,4)"},
                ],
            }
        ]
    }

    def test_canonicalizer_preserves_decimal_scale(self):
        expected = gate_checks.canonicalize_databricks_type(" DECIMAL ( 28 , 4 ) ")
        observed = gate_checks.canonicalize_databricks_type("decimal(28,2)")

        self.assertEqual(expected, "decimal(28,4)")
        self.assertEqual(observed, "decimal(28,2)")
        self.assertNotEqual(expected, observed)

    def test_gate4_rejects_full_schema_datatype_mismatch(self):
        deployed = {
            "fact_claim_detail_v1": [
                {"column": "claim_id", "datatype": "bigint"},
                {"column": "allowed_amt", "datatype": "decimal(28,2)"},
            ]
        }

        result = gate_checks.gate4_deployment_ddl(self.SPEC, deployed, "_v1")

        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("expected DECIMAL(28,4)" in issue for issue in result.issues))

    def test_gate4_accepts_exact_names_order_and_types(self):
        deployed = {
            "fact_claim_detail_v1": [
                {"column": "claim_id", "datatype": "bigint"},
                {"column": "allowed_amt", "datatype": "decimal(28,4)"},
            ]
        }

        result = gate_checks.gate4_deployment_ddl(self.SPEC, deployed, "_v1")

        self.assertEqual(result.status, "PASS")


class ContractTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ddl_template = (
            PROJECT_ROOT / "templates/ddl_notebook.py.template"
        ).read_text(encoding="utf-8")
        cls.data_template = (
            PROJECT_ROOT / "templates/dbldatagen_notebook.py.template"
        ).read_text(encoding="utf-8")
        cls.state_contract = (
            PROJECT_ROOT / "agent_skills/v2/prompts/shared/state_contract.md"
        ).read_text(encoding="utf-8")

    def test_reconciliation_artifact_is_a_hard_runtime_dependency(self):
        self.assertIn("schema_reconciliation.yaml", self.ddl_template)
        self.assertIn('"producer_phase": "reconcile_schema"', self.ddl_template)
        self.assertIn("schema_reconciliation.yaml", self.data_template)

    def test_state_graph_has_explicit_reconcile_schema_phase(self):
        expected_graph = (
            "parse_erd → build_semantic_model → generate_ddl → "
            "reconcile_schema → generate_synthetic_data → validate_data"
        )
        self.assertIn(expected_graph, self.state_contract)
        self.assertIn("| reconcile_schema |", self.state_contract)

    def test_data_template_uses_target_placeholders_only(self):
        for placeholder in (
            "{{OUTPUT_FOLDER}}",
            "{{TARGET_CATALOG}}",
            "{{TARGET_SCHEMA}}",
            "{{ASSET_SUFFIX}}",
        ):
            with self.subTest(placeholder=placeholder):
                self.assertIn(placeholder, self.data_template)

        self.assertNotIn("SOURCE_CATALOG", self.data_template)
        self.assertNotIn("SOURCE_SCHEMA", self.data_template)


if __name__ == "__main__":
    unittest.main()
