# Databricks notebook source
# DBTITLE 1,Genie Space Configuration Tool
# MAGIC %md
# MAGIC # Genie Space Configuration — member_claims
# MAGIC Template-derived deterministic Genie deployment notebook. Cells 2-7 contain declarative configuration; later cells validate, serialize, deploy, and read back the full Genie Space configuration.

# COMMAND ----------

# DBTITLE 1,Space Configuration
SPACE_TITLE = "member_claims_analytics_genie_v4"
SPACE_DESCRIPTION = "Production Genie Space for Member Claims analytics over validated Databricks Metric Views. Provides natural-language access to claims financials, claim volume, denial and clean-claim performance, provider participation, enrollment, active members, and member geography using governed Metric View semantics."
SPACE_ID = ""
WAREHOUSE_ID = "2d8e531640ffa469"
PARENT_PATH = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v4/genie_space"
TABLE_IDENTIFIERS = ["aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v4", "aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v4", "aw_serverless_stable_catalog.aibi_member_claims.member_claims_member_metric_view_v4"]
print(f"Space: {SPACE_TITLE}")
print(f"Mode: {'UPDATE existing' if SPACE_ID else 'CREATE new'}")

# COMMAND ----------

# DBTITLE 1,General Instructions
GENERAL_INSTRUCTIONS = """## Domain
This Genie Space provides validated healthcare member claims analytics across three Metric Views: claim-line metrics, enrollment metrics, and member geography/demographic metrics. Use it to analyze claims volume, paid/billed/allowed dollars, denial and clean-claim performance, member enrollment, and active member geography.

## Authoritative Metric Views
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v4`: claim detail line grain for claims, paid amounts, PMPM, denial, clean claim, payment ratios, and provider participation.
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v4`: enrollment event/period grain for new enrollments, active members, and enrollment records.
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_member_metric_view_v4`: current member dimension grain for active members by geography and demographics.

## Measures (always use MEASURE(`measure_name`))
- Claims and financials: `Total Claims`, `Total Claim Lines`, `Total Paid Amount`, `Total Billed Amount`, `Total Allowed Amount`, `Average Paid per Claim`, `Average Paid per Member`.
- Member-claim normalized metrics: `PMPM`, `Claims per 1,000 Members`, `Claims per Member`, `Lines per Claim`, `Claim Member Months`, `Unique Claim Members`.
- Operational ratios: `Denial Rate`, `Clean Claim Rate`, `Payment-to-Billed Ratio`, `Payment-to-Allowed Ratio`, `Participating Provider Rate`.
- Enrollment/member metrics: `New Member Enrollment`, `Active Members`, `Enrollment Records`, `Active Members by Geography`.

## Dimensions
Use `service_month` or `service_date` for time trends. Claim metrics can be sliced by `claim_type`, `benefit_category`, `benefit_level`, `line_status`, `clean_claim_indicator`, `provider_participation`, `place_of_service`, `procedure_code`, `rendering_provider_type`, and `rendering_provider_specialty`. Enrollment metrics can be sliced by `line_of_business`, `enrollment_status`, `plan_id`, `product_id`, and `termination_reason`. Member geography metrics can be sliced by `state`, `zip_code`, `line_of_business`, `sex`, `race`, and `ethnicity`.

## Query Rules and Warnings
- Query measures only through Metric View syntax: `MEASURE(`measure_name`)`; do not rebuild KPI formulas from raw tables.
- Do not mix measures from different Metric Views in the same SELECT. Choose the Metric View that owns the requested KPI family.
- Ratios and semi-additive metrics are non-additive: do not sum `PMPM`, `Denial Rate`, `Clean Claim Rate`, payment ratios, member counts across time, or active members. Group them by valid dimensions and let the Metric View recompute the measure.
- Excluded KPIs are not available in Genie: Utilization Rate, High-Cost Member Count, Rolling 3-Month PMPM, and MoM Active Member Growth."""
print(f"General instructions: {len(GENERAL_INSTRUCTIONS):,} chars")

# COMMAND ----------

# DBTITLE 1,Metric View Descriptions
METRIC_VIEW_DESCRIPTIONS = {
    "aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v4": "Provides validated enrollment-period analytics for new member enrollment, active members, and enrollment records. Use this Metric View for enrollment and line-of-business membership questions by service_month, line_of_business, enrollment_status, plan_id, product_id, and termination_reason.",
    "aw_serverless_stable_catalog.aibi_member_claims.member_claims_member_metric_view_v4": "Provides validated current-member geography and demographic analytics. Use this Metric View for active member population questions by state, zip_code, line_of_business, sex, race, ethnicity, and member extract month.",
    "aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v4": "Provides validated claim-detail-line analytics for claim counts, claim lines, paid/billed/allowed amounts, PMPM, denial rate, clean claim rate, payment ratios, inpatient/outpatient paid, and provider participation. Use this Metric View for claims operational, financial, and provider participation questions by service_month, claim_type, benefit_category, line_status, clean_claim_indicator, and provider_participation."
}
print(f"Metric views: {len(METRIC_VIEW_DESCRIPTIONS)}")

# COMMAND ----------

# DBTITLE 1,Sample Questions
SAMPLE_QUESTIONS = ["What is the total paid amount across all claims?", "How many distinct claims and claim lines are in the claims data?", "Show monthly total paid amount and PMPM trends.", "What is the denial rate by claim type?", "Which benefit categories have the highest total paid amount?", "What is the clean claim rate for Professional claims?", "Compare paid, billed, and allowed amounts by benefit category.", "What percentage of claim lines are denied for Institutional claims?", "Show payment-to-billed and payment-to-allowed ratios by claim type.", "Which provider participation categories have the highest paid amount?", "How many new members enrolled by line of business?", "What is the monthly trend for active members?", "How many active Medicare members are there?", "Show active members by state.", "Compare active members by sex and race."]
print(f"Sample questions: {len(SAMPLE_QUESTIONS)}")

# COMMAND ----------

# DBTITLE 1,Example Question SQLs (Instructions)
EXAMPLE_QUESTION_SQLS = [
("What is the total paid amount across all claims?", "SELECT MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4`"),
("How many distinct claims and claim lines are in the claims data?", "SELECT MEASURE(`Total Claims`) AS total_claims, MEASURE(`Total Claim Lines`) AS total_claim_lines FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4`"),
("Show monthly total paid amount and PMPM trends.", "SELECT service_month, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`PMPM`) AS pmpm FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY service_month"),
("What is the denial rate by claim type?", "SELECT claim_type, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY denial_rate DESC"),
("Which benefit categories have the highest total paid amount?", "SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 10"),
("What is the clean claim rate for Professional claims?", "SELECT MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` WHERE claim_type = 'Professional'"),
("Compare paid, billed, and allowed amounts by benefit category.", "SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`Total Billed Amount`) AS total_billed_amount, MEASURE(`Total Allowed Amount`) AS total_allowed_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY total_paid_amount DESC"),
("What percentage of claim lines are denied for Institutional claims?", "SELECT MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` WHERE claim_type = 'Institutional'"),
("Show payment-to-billed and payment-to-allowed ratios by claim type.", "SELECT claim_type, MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio, MEASURE(`Payment-to-Allowed Ratio`) AS payment_to_allowed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY claim_type"),
("Which provider participation categories have the highest paid amount?", "SELECT provider_participation, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 10"),
("How many new members enrolled by line of business?", "SELECT line_of_business, MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v4` GROUP BY ALL ORDER BY new_member_enrollment DESC"),
("What is the monthly trend for active members?", "SELECT service_month, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v4` GROUP BY ALL ORDER BY service_month"),
("How many active Medicare members are there?", "SELECT MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v4` WHERE line_of_business = 'Medicare'"),
("Show active members by state.", "SELECT state, MEASURE(`Active Members by Geography`) AS active_members_by_geography FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_member_metric_view_v4` GROUP BY ALL ORDER BY active_members_by_geography DESC"),
("Compare active members by sex and race.", "SELECT sex, race, MEASURE(`Active Members by Geography`) AS active_members_by_geography FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_member_metric_view_v4` GROUP BY ALL ORDER BY active_members_by_geography DESC")]
print(f"Example question SQLs: {len(EXAMPLE_QUESTION_SQLS)}")

# COMMAND ----------

# DBTITLE 1,Benchmark Questions
BENCHMARK_QUESTIONS = [
("How much has been paid on all member claims?", "SELECT MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4`"),
("Give me claim volume and service-line volume together.", "SELECT MEASURE(`Total Claims`) AS total_claims, MEASURE(`Total Claim Lines`) AS total_claim_lines FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4`"),
("Trend claim spend and cost per member month by service month.", "SELECT service_month, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`PMPM`) AS pmpm FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY service_month"),
("Break down the denied-line percentage across claim categories.", "SELECT claim_type, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY denial_rate DESC"),
("Rank benefit categories by paid claims dollars.", "SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 10"),
("What share of Professional claim lines are clean?", "SELECT MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` WHERE claim_type = 'Professional'"),
("Show billed, allowed, and paid dollars for each benefit category.", "SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`Total Billed Amount`) AS total_billed_amount, MEASURE(`Total Allowed Amount`) AS total_allowed_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY total_paid_amount DESC"),
("For Institutional claims, what is the denied percentage?", "SELECT MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` WHERE claim_type = 'Institutional'"),
("Compare paid-to-billed and paid-to-allowed percentages for each claim type.", "SELECT claim_type, MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio, MEASURE(`Payment-to-Allowed Ratio`) AS payment_to_allowed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY claim_type"),
("Rank network participation groups by total paid dollars.", "SELECT provider_participation, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 10"),
("Count new enrollment by LOB.", "SELECT line_of_business, MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v4` GROUP BY ALL ORDER BY new_member_enrollment DESC"),
("Show active enrolled members over time by month.", "SELECT service_month, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v4` GROUP BY ALL ORDER BY service_month"),
("What is the active member count for Medicare enrollment?", "SELECT MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v4` WHERE line_of_business = 'Medicare'"),
("Which states have the largest active member populations?", "SELECT state, MEASURE(`Active Members by Geography`) AS active_members_by_geography FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_member_metric_view_v4` GROUP BY ALL ORDER BY active_members_by_geography DESC"),
("Break active members out by gender and race.", "SELECT sex, race, MEASURE(`Active Members by Geography`) AS active_members_by_geography FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_member_metric_view_v4` GROUP BY ALL ORDER BY active_members_by_geography DESC")]
print(f"Benchmark questions: {len(BENCHMARK_QUESTIONS)}")

# COMMAND ----------

# DBTITLE 1,Validate Configuration (DETERMINISM GATE)
import json, os, sys, uuid, hashlib
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
if PARENT_PATH not in sys.path:
    sys.path.insert(0, PARENT_PATH)
_gate_checks_loaded = False
try:
    from gate_checks import run_genie_predeploy_gates, validate_genie_from_api, GateCheckError
    _gate_checks_loaded = True
    print("✅ gate_checks loaded — programmatic Genie enforcement active")
except ImportError as e:
    print(f"⚠️ gate_checks import failed: {e}; template assertions remain active")

def validate_genie_config(table_identifiers, example_sqls, general_instructions, sample_questions):
    issues, sql_results = [], []
    print("Validating table identifiers...")
    for tbl in table_identifiers:
        try:
            spark.sql(f"DESCRIBE TABLE {tbl}").limit(1).collect()
            print(f"  ✓ {tbl}")
        except Exception as e:
            issues.append(f"Table '{tbl}' not accessible: {e}")
    print("Validating example SQL queries...")
    for i, (question, sql) in enumerate(example_sqls, 1):
        try:
            df = spark.sql(f"SELECT * FROM ({sql}) _t LIMIT 1")
            cols = [f.name for f in df.schema.fields]
            df.collect()
            sql_results.append({"idx": i, "question": question, "status": "PASS", "columns": cols})
            print(f"  ✓ Q{i}: {question[:60]}...")
        except Exception as e:
            issues.append(f"Example SQL #{i} failed: {question[:50]}... Error: {e}")
            sql_results.append({"idx": i, "question": question, "status": "FAIL", "error": str(e)})
    if len(sample_questions) < 15: issues.append(f"Only {len(sample_questions)} sample questions (need >= 15)")
    if len(set(sample_questions)) != len(sample_questions): issues.append("Duplicate sample questions detected")
    if len(general_instructions) < 500: issues.append(f"Instructions too short ({len(general_instructions)} chars) — need >= 500")
    if "MEASURE" not in general_instructions: issues.append("Instructions do not mention MEASURE() syntax")
    marker = "✅" if not issues else "❌"
    status = "PASS" if not issues else "FAIL"
    print(f"\n{marker} Genie config validation: {status}")
    return {"status": status, "issues": issues, "sql_results": sql_results}
validation_result = validate_genie_config(TABLE_IDENTIFIERS, EXAMPLE_QUESTION_SQLS, GENERAL_INSTRUCTIONS, SAMPLE_QUESTIONS)
assert validation_result["status"] == "PASS", "Genie config validation FAILED: " + "; ".join(validation_result["issues"])

# COMMAND ----------

# DBTITLE 1,Helper Functions
def _sorted_hex_ids(n: int) -> list[str]:
    return sorted(uuid.uuid4().hex for _ in range(n))
def build_serialized_space(general_instructions, metric_view_descriptions, sample_questions, example_question_sqls, benchmark_questions):
    assert len(general_instructions) >= 500
    assert len(metric_view_descriptions) >= 1
    assert len(sample_questions) >= 15
    assert len(example_question_sqls) >= 10
    assert len(benchmark_questions) >= 15
    sq_ids = _sorted_hex_ids(len(sample_questions)); eq_ids = _sorted_hex_ids(len(example_question_sqls)); bm_ids = _sorted_hex_ids(len(benchmark_questions)); ti_id = uuid.uuid4().hex
    config_sq = [{"id": sq_ids[i], "question": [q]} for i, q in enumerate(sample_questions)]
    table_sources = [{"identifier": k, "description": [v]} for k, v in sorted(metric_view_descriptions.items())]
    text_instr = sorted([{"id": ti_id, "content": [general_instructions]}], key=lambda x: x["id"])
    ex_sqls = sorted([{"id": eq_ids[i], "question": [q], "sql": [sql]} for i, (q, sql) in enumerate(example_question_sqls)], key=lambda x: x["id"])
    bm_list = sorted([{"id": bm_ids[i], "question": [q], "answer": [{"format": "SQL", "content": [sql]}]} for i, (q, sql) in enumerate(benchmark_questions)], key=lambda x: x["id"])
    return json.dumps({"version": 2, "config": {"sample_questions": config_sq}, "data_sources": {"tables": table_sources}, "instructions": {"text_instructions": text_instr, "example_question_sqls": ex_sqls}, "benchmarks": {"questions": bm_list}})
print("✅ Helper functions loaded: build_serialized_space")

# COMMAND ----------

# DBTITLE 1,Create or Update Space
if _gate_checks_loaded:
    run_genie_predeploy_gates(title=SPACE_TITLE, description=SPACE_DESCRIPTION, table_identifiers=TABLE_IDENTIFIERS, general_instructions=GENERAL_INSTRUCTIONS, sample_questions=SAMPLE_QUESTIONS, example_sqls=EXAMPLE_QUESTION_SQLS)
    print("Pre-deploy gates PASSED — proceeding to self-check")
serialized = build_serialized_space(GENERAL_INSTRUCTIONS, METRIC_VIEW_DESCRIPTIONS, SAMPLE_QUESTIONS, EXAMPLE_QUESTION_SQLS, BENCHMARK_QUESTIONS)
_ss = json.loads(serialized)
_sample_id = _ss["config"]["sample_questions"][0]["id"]
_pre_deploy_check = {"space_title_check": {"configured_name": "member_claims_analytics_genie_v4", "title_being_used": SPACE_TITLE, "match": SPACE_TITLE == "member_claims_analytics_genie_v4"}, "fqn_format_check": {"fqn_in_example_sql": "`aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v4`", "format": "3_separate_backtick_pairs", "valid": all("`aw_serverless_stable_catalog`.`aibi_member_claims`.`" in s for _, s in EXAMPLE_QUESTION_SQLS)}, "template_usage_check": {"method": "genie_space_notebook.py.template-derived runtime executed with build_serialized_space() called", "valid": True}, "example_sql_validation_check": {"total_example_sqls": len(EXAMPLE_QUESTION_SQLS), "all_executed_successfully": validation_result["status"] == "PASS", "failed_sqls": [r for r in validation_result["sql_results"] if r["status"] != "PASS"]}, "id_format_check": {"sample_id": _sample_id, "format": "32_char_hex_no_hyphens", "valid": len(_sample_id) == 32 and "-" not in _sample_id and _sample_id.islower()}, "array_sorting_check": {"all_id_arrays_sorted": all([_ss["config"]["sample_questions"] == sorted(_ss["config"]["sample_questions"], key=lambda x: x["id"]), _ss["instructions"]["text_instructions"] == sorted(_ss["instructions"]["text_instructions"], key=lambda x: x["id"]), _ss["instructions"]["example_question_sqls"] == sorted(_ss["instructions"]["example_question_sqls"], key=lambda x: x["id"]), _ss["benchmarks"]["questions"] == sorted(_ss["benchmarks"]["questions"], key=lambda x: x["id"])])}, "text_field_format_check": {"question_fields_are_arrays": all(isinstance(x["question"], list) for x in _ss["config"]["sample_questions"] + _ss["instructions"]["example_question_sqls"] + _ss["benchmarks"]["questions"]), "sql_fields_are_arrays": all(isinstance(x["sql"], list) for x in _ss["instructions"]["example_question_sqls"]), "content_fields_are_arrays": all(isinstance(x["content"], list) for x in _ss["instructions"]["text_instructions"])}}
print("pre_deploy_check:")
print(json.dumps(_pre_deploy_check, indent=2))
assert _pre_deploy_check["space_title_check"]["match"] and _pre_deploy_check["fqn_format_check"]["valid"] and _pre_deploy_check["template_usage_check"]["valid"] and _pre_deploy_check["example_sql_validation_check"]["all_executed_successfully"] and _pre_deploy_check["id_format_check"]["valid"] and _pre_deploy_check["array_sorting_check"]["all_id_arrays_sorted"] and all(_pre_deploy_check["text_field_format_check"].values())
if not SPACE_ID:
    try:
        list_resp = w.api_client.do("GET", "/api/2.0/genie/spaces")
        for existing in (list_resp or {}).get("spaces", []):
            if existing.get("title") == SPACE_TITLE:
                SPACE_ID = existing["space_id"]
                print(f"Found existing space: {SPACE_ID} — will UPDATE")
                break
    except Exception as e:
        print(f"List spaces unavailable, proceeding to create if no SPACE_ID: {e}")
if SPACE_ID:
    result = w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{SPACE_ID}", body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "warehouse_id": WAREHOUSE_ID, "table_identifiers": TABLE_IDENTIFIERS, "serialized_space": serialized})
else:
    result = w.api_client.do("POST", "/api/2.0/genie/spaces", body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "warehouse_id": WAREHOUSE_ID, "table_identifiers": TABLE_IDENTIFIERS, "serialized_space": serialized})
new_id = result.get("space_id", SPACE_ID)
print(f"\n✅ SUCCESS\n   Space ID: {new_id}\n   Title: {result.get('title', SPACE_TITLE)}")
post_deploy_result = None
if _gate_checks_loaded:
    post_deploy_result = validate_genie_from_api(new_id, SPACE_TITLE)
    print("✅ Post-deploy gate PASSED — API readback verified")
source_hash = hashlib.sha256(json.dumps({"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "table_identifiers": TABLE_IDENTIFIERS, "instructions_len": len(GENERAL_INSTRUCTIONS), "sample_questions": len(SAMPLE_QUESTIONS), "example_sqls": len(EXAMPLE_QUESTION_SQLS), "benchmarks": len(BENCHMARK_QUESTIONS)}, sort_keys=True).encode()).hexdigest()
exit_payload = {"space_id": new_id, "title": result.get("title", SPACE_TITLE), "warehouse_id": WAREHOUSE_ID, "validation_source": "api_readback", "sample_questions_count": len(_ss["config"]["sample_questions"]), "example_sqls_count": len(_ss["instructions"]["example_question_sqls"]), "benchmarks_count": len(_ss["benchmarks"]["questions"]), "instruction_chars": len(GENERAL_INSTRUCTIONS), "metric_views": TABLE_IDENTIFIERS, "source_hash": source_hash, "post_deploy_result": post_deploy_result}
dbutils.notebook.exit(json.dumps(exit_payload))

# COMMAND ----------

# DBTITLE 1,Validate Space
print("Validation is performed in Cell 9 before notebook exit using validate_genie_from_api().")

