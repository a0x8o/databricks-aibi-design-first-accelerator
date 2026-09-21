"""Regression tests for the data-layer schema reconciliation contract."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import yaml


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


def _load_ddl_projection_functions():
    path = PROJECT_ROOT / "templates/ddl_notebook.py.template"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Import) and any(alias.name == "re" for alias in node.names):
            selected.append(node)
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any(name in {
                "_SIMPLE_TYPE_ALIASES", "_SIMPLE_TYPES", "_SEMANTIC_TOKENS",
                "_DECIMAL_DEFAULTS", "_TYPE_SYNONYMS",
                "DATATYPE_RESOLUTION_POLICY_ID",
            } for name in targets):
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {
            "canonicalize_datatype",
            "_semantic_family",
            "_strict_decimal_parts",
            "_strict_majority",
            "_peer_scale",
            "_fallback_from_column_name",
            "_merge_resolution_provenance",
            "_resolve_greenfield_synthetic_datatypes",
            "_datatype_resolution_is_eligible",
            "_synchronize_erd_projection",
        }:
            selected.append(node)
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


ddl_projection = _load_ddl_projection_functions()


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
        incomplete = ["DECIMAL(27", "NUMERIC(", "DECIMAL(38,)", ""]
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

    def test_documented_databricks_decimal_defaults_are_canonicalized(self):
        self.assertEqual(erd_validation.canonicalize_datatype("DECIMAL"), "decimal(10,0)")
        self.assertEqual(erd_validation.canonicalize_datatype("DECIMAL(28)"), "decimal(28,0)")
        self.assertEqual(gate_checks.canonicalize_databricks_type("NUMERIC"), "decimal(10,0)")

    def test_governed_resolution_uses_semantic_peer_scale_and_is_idempotent(self):
        tables = [
            {
                "name": "fact_claim_detail",
                "observed": {
                    "columns": [
                        {"name": "clm_dtl_allowed_amt", "datatype": "decimal(28"},
                        {"name": "clm_dtl_billed_amt", "datatype": "decimal(27,4)"},
                        {"name": "clm_dtl_paid_amt", "datatype": "decimal(28,4)"},
                    ]
                },
            }
        ]

        resolved, decisions = erd_validation.resolve_greenfield_synthetic_datatypes(tables)

        self.assertEqual(
            resolved[0]["observed"]["columns"][0]["datatype"], "decimal(28,4)"
        )
        self.assertEqual(decisions[0]["resolution_source"], "SAME_TABLE_SEMANTIC_PEER_MODE")
        self.assertFalse(decisions[0]["observed"])
        resolved_again, second_decisions = (
            erd_validation.resolve_greenfield_synthetic_datatypes(resolved)
        )
        self.assertIs(resolved_again, resolved)
        self.assertEqual(second_decisions, [])

    def test_governed_resolution_has_total_safe_fallbacks(self):
        tables = [
            {
                "name": "fact_claim_header",
                "observed": {
                    "columns": [
                        {"name": "clm_birth_weight", "datatype": "decimal"},
                        {"name": "member_description", "datatype": "varchar("},
                        {"name": "opaque_code", "datatype": None},
                    ]
                },
            }
        ]

        resolved, decisions = erd_validation.resolve_greenfield_synthetic_datatypes(tables)
        datatypes = [c["datatype"] for c in resolved[0]["observed"]["columns"]]

        self.assertEqual(datatypes, ["decimal(10,0)", "string", "string"])
        self.assertEqual(len(decisions), 3)
        self.assertEqual(decisions[0]["resolution_source"], "DATABRICKS_DEFAULT_EXPANSION")
        self.assertFalse(decisions[0]["inference"])
        self.assertEqual(decisions[1]["resolution_source"], "NON_TRUNCATING_STRING_FALLBACK")
        self.assertTrue(all(erd_validation.validate_datatype(value) is None for value in datatypes))

    def test_reported_claim_amount_columns_preserve_precision_and_use_scale_four(self):
        raw_columns = [
            ("clm_dtl_allowed_amt", "decimal(28"),
            ("clm_dtl_billed_amt", "decimal(27"),
            ("clm_dtl_deduct_amt", "decimal(27"),
            ("clm_dtl_net_amt", "decimal(28"),
            ("clm_dtl_paid_amt", "decimal(28"),
            ("clm_dtl_actual_paid_amt", "decimal(38"),
            ("clm_dtl_not_covered_amt", "decimal(27"),
        ]
        tables = [
            {
                "name": "fact_claim_detail",
                "observed": {
                    "columns": [
                        {"name": name, "datatype": datatype}
                        for name, datatype in raw_columns
                    ]
                },
            }
        ]

        resolved, decisions = erd_validation.resolve_greenfield_synthetic_datatypes(tables)
        actual = [
            column["datatype"]
            for column in resolved[0]["observed"]["columns"]
        ]

        self.assertEqual(
            actual,
            [
                "decimal(28,4)", "decimal(27,4)", "decimal(27,4)",
                "decimal(28,4)", "decimal(28,4)", "decimal(38,4)",
                "decimal(27,4)",
            ],
        )
        self.assertEqual(len(decisions), len(raw_columns))

    def test_invalid_decimal_bounds_are_rejected(self):
        invalid = ["DECIMAL(0,0)", "DECIMAL(39,4)", "DECIMAL(10,11)"]

        for datatype in invalid:
            with self.subTest(datatype=datatype):
                self.assertIsNotNone(erd_validation.validate_datatype(datatype))
                with self.assertRaises(ValueError):
                    gate_checks.canonicalize_databricks_type(datatype)

    def test_table_spec_projection_accepts_exact_validated_erd(self):
        erd_tables = _erd_table("DECIMAL(28,4)")
        table_spec = {
            "tables": [
                {
                    "name": "fact_claim_detail",
                    "columns": [{"name": "amount_0", "type": "decimal(28,4)"}],
                }
            ]
        }

        report = erd_validation.validate_table_spec_projection(erd_tables, table_spec)

        self.assertEqual(report["status"], "PASS")
        self.assertIsNone(report["failure_code"])

    def test_invalid_cached_erd_routes_to_extraction_error(self):
        erd_tables = _erd_table("DECIMAL(")
        table_spec = {
            "tables": [
                {
                    "name": "fact_claim_detail",
                    "columns": [{"name": "amount_0", "type": "DECIMAL("}],
                }
            ]
        }

        report = erd_validation.validate_table_spec_projection(erd_tables, table_spec)

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["failure_code"], "ERD_EXTRACTION_ERROR")
        self.assertIn("'DECIMAL('", report["errors"][0])

    def test_invalid_table_spec_is_blocked_before_notebook(self):
        erd_tables = _erd_table("DECIMAL(28,4)")
        table_spec = {
            "tables": [
                {
                    "name": "fact_claim_detail",
                    "columns": [{"name": "amount_0", "type": "DECIMAL(28"}],
                }
            ]
        }

        report = erd_validation.validate_table_spec_projection(erd_tables, table_spec)

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["failure_code"], "SCHEMA_CONTRACT_ERROR")
        self.assertIn("invalid table-spec datatype", report["errors"][0])


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


class DDLProjectionRuntimeTests(unittest.TestCase):
    def test_runtime_provenance_merge_keeps_parse_decision_history(self):
        previous = [{
            "table": "fact_claim_detail",
            "column": "allowed_amt",
            "resolved_datatype": "decimal(28,2)",
            "resolution_source": "PARSE_TIME_EVIDENCE",
        }]
        current = [{
            "table": "fact_claim_detail",
            "column": "allowed_amt",
            "resolved_datatype": "decimal(28,4)",
            "resolution_source": "SEMANTIC_DECIMAL_POLICY",
        }]

        merged = ddl_projection["_merge_resolution_provenance"](previous, current)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["resolved_datatype"], "decimal(28,4)")
        self.assertEqual(merged[0]["resolution_stage"], "DDL_RUNTIME_BACKSTOP")
        self.assertEqual(
            merged[0]["provenance_history"][0]["resolution_source"],
            "PARSE_TIME_EVIDENCE",
        )

    def test_runtime_resolution_scope_is_greenfield_synthetic_only(self):
        eligible = {
            "data_source": {
                "type": "erd",
                "greenfield": {"enabled": True, "synthetic_data": True},
            }
        }
        live = {
            "data_source": {
                "type": "live_schema",
                "greenfield": {"enabled": True, "synthetic_data": True},
            }
        }
        retained = {
            "data_source": {
                "type": "erd",
                "greenfield": {"enabled": True, "synthetic_data": False},
            }
        }

        self.assertTrue(ddl_projection["_datatype_resolution_is_eligible"](eligible))
        self.assertFalse(ddl_projection["_datatype_resolution_is_eligible"](live))
        self.assertFalse(ddl_projection["_datatype_resolution_is_eligible"](retained))

    def test_versioned_policy_contract_matches_both_implementations(self):
        contract = yaml.safe_load(
            (PROJECT_ROOT / "agent_skills/v2/contracts/datatype_resolution_policy.yaml")
            .read_text(encoding="utf-8")
        )
        expected = {
            name: (values["precision"], values["scale"])
            for name, values in contract["semantic_decimal_defaults"].items()
        }

        self.assertEqual(
            contract["contract"]["policy_id"],
            erd_validation.DATATYPE_RESOLUTION_POLICY_ID,
        )
        self.assertEqual(expected, erd_validation._DECIMAL_DEFAULTS)
        self.assertEqual(expected, ddl_projection["_DECIMAL_DEFAULTS"])

    def test_helper_and_runtime_resolution_policies_match(self):
        tables = [
            {
                "name": "fact_claim_detail",
                "observed": {
                    "columns": [
                        {"name": "allowed_amt", "datatype": "decimal(28"},
                        {"name": "paid_amt", "datatype": "decimal(27,4)"},
                        {"name": "claim_rate", "datatype": "numeric("},
                        {"name": "description", "datatype": "varchar("},
                        {"name": "opaque_code", "datatype": None},
                    ]
                },
            }
        ]
        helper_tables, helper_decisions = (
            erd_validation.resolve_greenfield_synthetic_datatypes(copy.deepcopy(tables))
        )
        runtime_erd = {"tables": copy.deepcopy(tables)}
        runtime_decisions = ddl_projection["_resolve_greenfield_synthetic_datatypes"](
            runtime_erd
        )

        self.assertEqual(runtime_erd["tables"], helper_tables)
        self.assertEqual(runtime_decisions, helper_decisions)
        self.assertEqual(
            ddl_projection["DATATYPE_RESOLUTION_POLICY_ID"],
            erd_validation.DATATYPE_RESOLUTION_POLICY_ID,
        )

    def test_incomplete_derived_type_is_regenerated_from_complete_erd(self):
        erd = {"tables": _erd_table("DECIMAL(28,4)")}
        spec = {
            "tables": [
                {
                    "name": "fact_claim_detail",
                    "columns": [{"name": "amount_0", "type": "decimal(28"}],
                }
            ]
        }

        changes = ddl_projection["_synchronize_erd_projection"](erd, spec)

        self.assertEqual(spec["tables"][0]["columns"][0]["type"], "DECIMAL(28,4)")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["reason"], "INCOMPLETE_OR_INVALID_DERIVED_DATATYPE")

    def test_complete_but_wrong_derived_scale_is_regenerated_from_erd(self):
        erd = {"tables": _erd_table("DECIMAL(28,4)")}
        spec = {
            "tables": [
                {
                    "name": "fact_claim_detail",
                    "columns": [{"name": "amount_0", "type": "DECIMAL(28,2)"}],
                }
            ]
        }

        changes = ddl_projection["_synchronize_erd_projection"](erd, spec)

        self.assertEqual(spec["tables"][0]["columns"][0]["type"], "DECIMAL(28,4)")
        self.assertEqual(changes[0]["reason"], "DATATYPE_MISMATCH")

    def test_strict_projection_still_rejects_unresolved_erd(self):
        erd = {"tables": _erd_table("decimal(28")}
        spec = {
            "tables": [
                {
                    "name": "fact_claim_detail",
                    "columns": [{"name": "amount_0", "type": "decimal(28"}],
                }
            ]
        }

        with self.assertRaisesRegex(RuntimeError, "^ERD_EXTRACTION_ERROR:"):
            ddl_projection["_synchronize_erd_projection"](erd, spec)

        self.assertEqual(spec["tables"][0]["columns"][0]["type"], "decimal(28")

    def test_runtime_resolver_corrects_incomplete_erd_before_projection(self):
        erd = {"tables": _erd_table("decimal(28")}
        erd["tables"][0]["observed"]["columns"][0]["name"] = "clm_dtl_allowed_amt"
        spec = {
            "tables": [
                {
                    "name": "fact_claim_detail",
                    "columns": [{"name": "clm_dtl_allowed_amt", "type": "decimal(28"}],
                }
            ]
        }

        decisions = ddl_projection["_resolve_greenfield_synthetic_datatypes"](erd)
        changes = ddl_projection["_synchronize_erd_projection"](erd, spec)

        self.assertEqual(erd["tables"][0]["observed"]["columns"][0]["datatype"], "decimal(28,4)")
        self.assertEqual(spec["tables"][0]["columns"][0]["type"], "decimal(28,4)")
        self.assertEqual(len(decisions), 1)
        self.assertEqual(len(changes), 1)


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
        self.assertIn("schema_assumptions.yaml", self.ddl_template)
        self.assertIn("schema_assumptions.yaml", self.data_template)
        self.assertIn("schema_assumptions_sha256", self.ddl_template)
        self.assertIn("schema_assumptions_sha256", self.data_template)

    def test_ddl_runtime_revalidates_erd_projection_before_catalog_mutation(self):
        validation_call = "_synchronize_erd_projection(erd_document, spec)"
        first_mutation = 'spark.sql(f"CREATE SCHEMA IF NOT EXISTS'
        self.assertIn('ERD_PARSED_PATH = f"{OUTPUT_FOLDER}/erd_parsed.yaml"', self.ddl_template)
        self.assertLess(
            self.ddl_template.index(validation_call),
            self.ddl_template.index(first_mutation),
        )
        self.assertIn("REGENERATED_TABLE_SPEC_TYPES_FROM_VALIDATED_ERD", self.ddl_template)
        self.assertIn('"catalog_mutation_started": False', self.ddl_template)
        self.assertIn("schema_assumptions.yaml", self.ddl_template)
        self.assertIn("GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1", self.ddl_template)
        self.assertLess(
            self.ddl_template.index("_resolve_greenfield_synthetic_datatypes(erd_document)"),
            self.ddl_template.index(first_mutation),
        )
        self.assertIn('greenfield_value.get("synthetic_data") is True', self.ddl_template)

    def test_preflight_integration_self_corrects_before_first_spark_statement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            spec = {
                "catalog": "test_catalog",
                "schema": "test_schema",
                "asset_suffix": "_v1",
                "tables": [
                    {
                        "name": "fact_claim_detail",
                        "columns": [
                            {"name": "clm_dtl_allowed_amt", "type": "decimal(28"}
                        ],
                    }
                ],
            }
            erd = {
                "tables": [
                    {
                        "name": "fact_claim_detail",
                        "observed": {
                            "columns": [
                                {
                                    "name": "clm_dtl_allowed_amt",
                                    "datatype": "decimal(28",
                                }
                            ]
                        },
                    }
                ]
            }
            run_context = {
                "run_id": "run-1",
                "output_folder": str(output),
                "target": {"catalog": "test_catalog", "schema": "test_schema"},
                "version": {"asset_suffix": "_v1"},
                "data_source": {
                    "type": "erd",
                    "greenfield": {"enabled": True, "synthetic_data": True},
                },
            }
            handoff = {
                "run_id": "run-1",
                "catalog": "test_catalog",
                "schema": "test_schema",
                "asset_suffix": "_v1",
                "output_folder": str(output),
            }
            for name, value in (
                ("table_spec.yaml", spec),
                ("erd_parsed.yaml", erd),
                ("run_context.yaml", run_context),
                ("step_handoff.yaml", handoff),
            ):
                (output / name).write_text(
                    yaml.safe_dump(value, sort_keys=False), encoding="utf-8"
                )

            prefix = self.ddl_template.split(
                'spark.sql(f"CREATE SCHEMA IF NOT EXISTS', 1
            )[0]
            rendered = (
                prefix.replace("{{OUTPUT_FOLDER}}", str(output))
                .replace("{{TARGET_CATALOG}}", "test_catalog")
                .replace("{{TARGET_SCHEMA}}", "test_schema")
                .replace("{{DOMAIN_NAME}}", "test_domain")
            )
            exec(compile(rendered, "ddl_preflight_integration", "exec"), {})

            resolved_erd = yaml.safe_load(
                (output / "erd_parsed.yaml").read_text(encoding="utf-8")
            )
            resolved_spec = yaml.safe_load(
                (output / "table_spec.yaml").read_text(encoding="utf-8")
            )
            assumptions = yaml.safe_load(
                (output / "schema_assumptions.yaml").read_text(encoding="utf-8")
            )
            preflight = yaml.safe_load(
                (output / "ddl_preflight.yaml").read_text(encoding="utf-8")
            )

            self.assertEqual(
                resolved_erd["tables"][0]["observed"]["columns"][0]["datatype"],
                "decimal(28,4)",
            )
            self.assertEqual(
                resolved_spec["tables"][0]["columns"][0]["type"],
                "decimal(28,4)",
            )
            self.assertEqual(assumptions["resolution_count"], 1)
            self.assertEqual(assumptions["unresolved_datatypes"], [])
            self.assertEqual(preflight["status"], "PASS")
            self.assertFalse(preflight["catalog_mutation_started"])
            self.assertTrue(preflight["parse_checkpoint_refresh_required"])

    def test_strict_valid_erd_preserves_existing_assumptions_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            spec = {
                "catalog": "test_catalog",
                "schema": "test_schema",
                "asset_suffix": "_v1",
                "tables": [{
                    "name": "fact_claim_detail",
                    "columns": [{"name": "amount_0", "type": "decimal(28,4)"}],
                }],
            }
            erd = {"tables": [{
                "name": "fact_claim_detail",
                "observed": {"columns": [{
                    "name": "amount_0", "datatype": "decimal(28,4)"
                }]},
            }]}
            run_context = {
                "run_id": "run-strict",
                "output_folder": str(output),
                "target": {"catalog": "test_catalog", "schema": "test_schema"},
                "version": {"asset_suffix": "_v1"},
                "data_source": {
                    "type": "erd",
                    "greenfield": {"enabled": True, "synthetic_data": True},
                },
            }
            handoff = {
                "run_id": "run-strict",
                "catalog": "test_catalog",
                "schema": "test_schema",
                "asset_suffix": "_v1",
                "output_folder": str(output),
            }
            for name, value in (
                ("table_spec.yaml", spec),
                ("erd_parsed.yaml", erd),
                ("run_context.yaml", run_context),
                ("step_handoff.yaml", handoff),
            ):
                (output / name).write_text(
                    yaml.safe_dump(value, sort_keys=False), encoding="utf-8"
                )
            assumptions_bytes = (
                "artifact_type: schema_assumptions\n"
                "contract_version: 1\n"
                "policy_id: GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1\n"
                "run_id: run-strict\n"
                "asset_suffix: _v1\n"
                "catalog: test_catalog\n"
                "schema: test_schema\n"
                "status: PASS\n"
                "unresolved_datatypes: []\n"
                "resolution_count: 0\n"
                "resolutions: []\n"
                "erd_output_sha256: PLACEHOLDER\n"
                "producer_phase: parse_erd\n"
            ).replace(
                "PLACEHOLDER",
                hashlib.sha256((output / "erd_parsed.yaml").read_bytes()).hexdigest(),
            ).encode("utf-8")
            (output / "schema_assumptions.yaml").write_bytes(assumptions_bytes)

            prefix = self.ddl_template.split(
                'spark.sql(f"CREATE SCHEMA IF NOT EXISTS', 1
            )[0]
            rendered = (
                prefix.replace("{{OUTPUT_FOLDER}}", str(output))
                .replace("{{TARGET_CATALOG}}", "test_catalog")
                .replace("{{TARGET_SCHEMA}}", "test_schema")
                .replace("{{DOMAIN_NAME}}", "test_domain")
            )
            exec(compile(rendered, "ddl_strict_valid_integration", "exec"), {})

            self.assertEqual(
                (output / "schema_assumptions.yaml").read_bytes(), assumptions_bytes
            )
            preflight = yaml.safe_load(
                (output / "ddl_preflight.yaml").read_text(encoding="utf-8")
            )
            self.assertFalse(preflight["parse_checkpoint_refresh_required"])

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


class AuthorityBootstrapPromptTests(unittest.TestCase):
    """Keep the bootstrap contract compatible with fresh and legacy runs."""

    @classmethod
    def setUpClass(cls):
        prompts = PROJECT_ROOT / "agent_skills/v2/prompts"
        cls.master_prompt = (prompts / "00_master_prompt.md").read_text(encoding="utf-8")
        cls.data_instructions = (prompts / "data_layer/instructions.md").read_text(encoding="utf-8")
        cls.data_validation = (prompts / "data_layer/validation.md").read_text(encoding="utf-8")
        cls.global_guardrails = (prompts / "shared/global_guardrails.md").read_text(encoding="utf-8")

    def test_fresh_parse_does_not_require_its_own_outputs_before_write(self):
        self.assertIn("A fresh parse creates both outputs before this check", self.data_instructions)
        self.assertIn("Neither output is a required\ninput before that first persistence", self.data_validation)
        self.assertIn("fresh phase", self.data_instructions)

    def test_legacy_datatype_policy_metadata_is_optional(self):
        expected = "run_context.inputs.datatype_resolution_policy"
        self.assertIn(expected, self.data_instructions)
        self.assertIn("absence MUST NOT raise `DATA_LAYER_INPUT_AUTHORITY_ERROR`", self.data_instructions)
        self.assertIn("not a mandatory\nruntime input", self.master_prompt)

    def test_deploy_root_omission_is_backward_compatible_but_mismatch_is_not(self):
        self.assertIn("both omit `deploy_root`", self.data_instructions)
        self.assertIn("deploy_root is present on only one authority artifact", self.data_instructions)
        self.assertIn("deploy_root authority mismatch", self.data_instructions)
        self.assertNotIn("step_handoff.yaml is missing deploy_root", self.data_instructions)

    def test_missing_authority_rule_has_a_producer_creation_exception(self):
        self.assertIn("after its defined creation point", self.global_guardrails)
        self.assertIn("producer phase's own output before its first execution", self.global_guardrails)

    def test_output_hashes_are_not_prewrite_inputs_for_fresh_phases(self):
        self.assertIn("phase's own outputs do not exist yet and are never pre-write authority", self.data_instructions)
        self.assertIn("For a skip/resume candidate, also recompute its output hashes", self.data_instructions)


if __name__ == "__main__":
    unittest.main()
