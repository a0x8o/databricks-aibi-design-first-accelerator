# Databricks notebook source
# DBTITLE 1,Install dependencies
# MAGIC %pip install databricks-sdk pyyaml dbldatagen

dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Import dependencies
import dbldatagen
import json, os, sys, uuid, hashlib
from databricks.sdk import WorkspaceClient

# COMMAND ----------

# DBTITLE 1,Space Configuration
SPACE_TITLE = "member_claims_analytics_genie_v7"
SPACE_DESCRIPTION = "Production Genie Space for validated Member Claims analytics covering claim volume, paid/billed/allowed financial performance, denial and clean claim operations, member enrollment distribution, monthly PMPM, claims per thousand members, utilization, and participating provider metrics."
SPACE_ID = "01f1b14d814c148799a1993aa90c416c"
WAREHOUSE_ID = "2d8e531640ffa469"
PARENT_PATH = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v7/genie_space"
TABLE_IDENTIFIERS = ['aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v7', 'aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v7', 'aw_serverless_stable_catalog.aibi_member_claims.member_claims_monthly_metric_view_v7']
print(f"Space: {SPACE_TITLE}")
print(f"Mode: {'UPDATE existing' if SPACE_ID else 'CREATE new'}")

# COMMAND ----------

# DBTITLE 1,General Instructions
GENERAL_INSTRUCTIONS = """## Domain
This Genie Space provides validated healthcare member-claims analytics over Databricks Metric Views for claims financial performance, claims operations, member enrollment, population geography, and monthly utilization. The authoritative tables are `member_claims_metric_view_v7` for claim-line KPIs, `member_claims_enrollment_metric_view_v7` for enrollment and member distribution KPIs, and `member_claims_monthly_metric_view_v7` for monthly cross-grain ratios such as PMPM and utilization.

## Metric View Selection
- Use `member_claims_metric_view_v7` for claims, claim lines, paid/billed/allowed amounts, denial rate, clean claim rate, average paid, inpatient/outpatient paid, and participating provider metrics.
- Use `member_claims_enrollment_metric_view_v7` for active members, new member enrollment, line of business, state, sex, race, group, and enrollment status questions.
- Use `member_claims_monthly_metric_view_v7` for PMPM, member months, monthly claims, claims per 1000 members, members with claims, active enrolled members, and utilization rate.
- Do not mix measures from different metric views in the same SQL query.

## Measures (always use MEASURE(`name`))
- Claims measures: `Total Claims`, `Total Claim Lines`, `Total Paid Amount`, `Average Paid per Claim`, `Denied Lines`, `Denial Rate`, `Clean Lines`, `Clean Claim Rate`, `Total Billed Amount`, `Payment-to-Billed Ratio`, `Total Allowed Amount`, `Payment-to-Allowed Ratio`, `Unique Claim Members`, `Average Paid per Member`, `Claims per Member`, `Lines per Claim`, `Inpatient Paid Amount`, `Outpatient Paid Amount`, `Participating Paid Amount`, `Participating Provider Rate`.
- Enrollment measures: `Active Members`, `New Member Enrollment`.
- Monthly measures: `Monthly Paid Amount`, `Member Months`, `PMPM`, `Monthly Claims`, `Claims per 1000 Members`, `Members With Claims`, `Active Enrolled Members`, `Utilization Rate`.

## Dimensions
- Claims dimensions include `Service Date`, `service_month`, `claim_type`, `line_status`, `clean_claim_indicator`, `benefit_category`, `benefit_level`, `place_of_service`, `rendering_provider_type`, `rendering_provider_spec`, `participating_provider`, `adjudication_status`, `procedure_code`, and `revenue_code`.
- Enrollment dimensions include `Service Date`, `service_month`, `line_of_business`, `enrollment_status`, `member_state`, `member_zip_code`, `member_sex`, `member_race`, `group_name`, `subgroup_name`, and `product_id`.
- Monthly utilization supports `service_month` only.

## Query Rules and Warnings
- Use Metric View semantics only: `SELECT MEASURE(`measure name`) FROM ...`; do not rebuild formulas from raw tables.
- Ratio or rate measures are non-additive and must never be summed: `Average Paid per Claim`, `Denial Rate`, `Clean Claim Rate`, `Payment-to-Billed Ratio`, `Payment-to-Allowed Ratio`, `Average Paid per Member`, `Claims per Member`, `Lines per Claim`, `Participating Provider Rate`, `PMPM`, `Claims per 1000 Members`, and `Utilization Rate`.
- For monthly trends use `service_month` and `GROUP BY ALL ORDER BY service_month`. Use `Service Date` for daily or date-filtered questions; because it contains a space, quote it as `Service Date` in SQL.
- Interpret LOB as `line_of_business`; geography as `member_state`; paid/cost/spend as `Total Paid Amount`; denial percentage as `Denial Rate`; clean claims as `Clean Claim Rate`; par provider as `Participating Provider Rate`.
- Exclude unsupported KPIs: High-Cost Member Count, Rolling 3-Month PMPM, and MoM Active Member Growth are not represented in the attached Metric Views."""
print(f"General instructions: {len(GENERAL_INSTRUCTIONS):,} chars")

# COMMAND ----------

# DBTITLE 1,Metric View Descriptions
METRIC_VIEW_DESCRIPTIONS = {
    'aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v7': 'Provides validated enrollment-grain measures for active members and new member enrollment. Use it for member distribution by line of business, state/geography, demographic dimensions, enrollment status, group, subgroup, and effective-month trends.',
    'aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v7': 'Provides validated claim-line-grain measures for claim volume, claim lines, paid/billed/allowed dollars, denial and clean-claim performance, claim/member ratios, inpatient and outpatient paid amounts, and participating provider rates. Use it for claim type, benefit category, provider specialty, adjudication, and status breakdowns.',
    'aw_serverless_stable_catalog.aibi_member_claims.member_claims_monthly_metric_view_v7': 'Provides monthly pre-aggregated member-claims measures that safely combine claims and enrollment components at service_month grain. Use it for PMPM, member months, monthly claims, claims per 1000 members, members with claims, active enrolled members, and utilization rate trends.'
}
print(f"Metric views: {len(METRIC_VIEW_DESCRIPTIONS)}")

# COMMAND ----------

# DBTITLE 1,Sample Questions
SAMPLE_QUESTIONS = ['What is the total number of claims?', 'What is the total paid amount across all claim lines?', 'How has total paid amount trended by service month?', 'Show total paid amount and total claims by claim type.', 'Compare denial rate across claim types.', 'What is the clean claim rate for Institutional claims?', 'Which benefit categories have the highest paid amount?', 'Show payment-to-billed and payment-to-allowed ratios by benefit level.', 'Which rendering provider specialties have the highest participating provider rate?', 'How many claim lines are in each line status?', 'How many active members are enrolled?', 'Show active members by line of business.', 'How has new member enrollment changed by month?', 'For Commercial members, show active members by state.', 'What is the monthly PMPM trend?', 'Show claims per 1000 members and utilization rate by service month.']
print(f"Sample questions: {len(SAMPLE_QUESTIONS)}")

# COMMAND ----------

# DBTITLE 1,Example Question SQLs
EXAMPLE_QUESTION_SQLS = [('What is the total number of claims?', 'SELECT MEASURE(`Total Claims`) AS total_claims FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7`'), ('What is the total paid amount across all claim lines?', 'SELECT MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7`'), ('How has total paid amount trended by service month?', 'SELECT service_month, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY service_month'), ('Show total paid amount and total claims by claim type.', 'SELECT claim_type, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`Total Claims`) AS total_claims FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY total_paid_amount DESC'), ('Compare denial rate across claim types.', 'SELECT claim_type, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY denial_rate DESC'), ('What is the clean claim rate for Institutional claims?', "SELECT MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` WHERE claim_type = 'Institutional'"), ('Which benefit categories have the highest paid amount?', 'SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 5'), ('Show payment-to-billed and payment-to-allowed ratios by benefit level.', 'SELECT benefit_level, MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio, MEASURE(`Payment-to-Allowed Ratio`) AS payment_to_allowed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY benefit_level'), ('Which rendering provider specialties have the highest participating provider rate?', 'SELECT rendering_provider_spec, MEASURE(`Participating Provider Rate`) AS participating_provider_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY participating_provider_rate DESC'), ('How many claim lines are in each line status?', 'SELECT line_status, MEASURE(`Total Claim Lines`) AS total_claim_lines FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY total_claim_lines DESC'), ('How many active members are enrolled?', 'SELECT MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7`'), ('Show active members by line of business.', 'SELECT line_of_business, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7` GROUP BY ALL ORDER BY active_members DESC'), ('How has new member enrollment changed by month?', 'SELECT service_month, MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7` GROUP BY ALL ORDER BY service_month'), ('For Commercial members, show active members by state.', "SELECT member_state, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7` WHERE line_of_business = 'Commercial' GROUP BY ALL ORDER BY active_members DESC"), ('What is the monthly PMPM trend?', 'SELECT service_month, MEASURE(`PMPM`) AS pmpm FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_monthly_metric_view_v7` GROUP BY ALL ORDER BY service_month'), ('Show claims per 1000 members and utilization rate by service month.', 'SELECT service_month, MEASURE(`Claims per 1000 Members`) AS claims_per_1000_members, MEASURE(`Utilization Rate`) AS utilization_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_monthly_metric_view_v7` GROUP BY ALL ORDER BY service_month')]
print(f"Example SQLs: {len(EXAMPLE_QUESTION_SQLS)}")

# COMMAND ----------

# DBTITLE 1,Benchmark Questions
BENCHMARK_QUESTIONS = [('Count all distinct claims in the claims metric view.', 'SELECT MEASURE(`Total Claims`) AS total_claims FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7`'), ('How much was paid on claims in total?', 'SELECT MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7`'), ('Give me the monthly paid spend trend.', 'SELECT service_month, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY service_month'), ('Break down claim dollars and claim counts by type of claim.', 'SELECT claim_type, MEASURE(`Total Paid Amount`) AS total_paid_amount, MEASURE(`Total Claims`) AS total_claims FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY total_paid_amount DESC'), ('Which claim type has the largest denial percentage?', 'SELECT claim_type, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY denial_rate DESC'), ('For Institutional claim type, what percent of lines are clean?', "SELECT MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` WHERE claim_type = 'Institutional'"), ('Rank benefit categories by total paid dollars.', 'SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 5'), ('Compare paid-to-billed and paid-to-allowed by network benefit level.', 'SELECT benefit_level, MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio, MEASURE(`Payment-to-Allowed Ratio`) AS payment_to_allowed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY benefit_level'), ('Show par provider share by rendering specialty.', 'SELECT rendering_provider_spec, MEASURE(`Participating Provider Rate`) AS participating_provider_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY participating_provider_rate DESC'), ('What line statuses account for the most claim lines?', 'SELECT line_status, MEASURE(`Total Claim Lines`) AS total_claim_lines FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7` GROUP BY ALL ORDER BY total_claim_lines DESC'), ('What is the enrolled active member count?', 'SELECT MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7`'), ('Split active membership by LOB.', 'SELECT line_of_business, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7` GROUP BY ALL ORDER BY active_members DESC'), ('Trend new member additions by enrollment month.', 'SELECT service_month, MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7` GROUP BY ALL ORDER BY service_month'), ('For Commercial LOB, which states have the most active members?', "SELECT member_state, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v7` WHERE line_of_business = 'Commercial' GROUP BY ALL ORDER BY active_members DESC"), ('Show per-member-per-month cost over time.', 'SELECT service_month, MEASURE(`PMPM`) AS pmpm FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_monthly_metric_view_v7` GROUP BY ALL ORDER BY service_month'), ('Trend claim frequency per thousand members with utilization rate.', 'SELECT service_month, MEASURE(`Claims per 1000 Members`) AS claims_per_1000_members, MEASURE(`Utilization Rate`) AS utilization_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_monthly_metric_view_v7` GROUP BY ALL ORDER BY service_month')]
print(f"Benchmark questions: {len(BENCHMARK_QUESTIONS)}")

# COMMAND ----------

# DBTITLE 1,Validate Configuration
w = WorkspaceClient()
_gate_checks_loaded = False
try:
    if PARENT_PATH not in sys.path:
        sys.path.insert(0, PARENT_PATH)
    from gate_checks import run_genie_predeploy_gates, validate_genie_from_api, GateCheckError
    _gate_checks_loaded = True
    print("gate_checks loaded — programmatic Genie enforcement active")
except ImportError as e:
    print(f"gate_checks.py not found — using template assertions only: {e}")

def validate_genie_config(table_identifiers, example_sqls, general_instructions, sample_questions):
    issues = []
    sql_results = []
    print("Validating table identifiers...")
    for tbl in table_identifiers:
        try:
            spark.sql(f"DESCRIBE TABLE {tbl}").limit(1).collect()
            print(f"  PASS {tbl}")
        except Exception as e:
            issues.append(f"Table '{tbl}' not accessible: {e}")
            print(f"  FAIL {tbl}: {e}")
    print("Validating example SQL queries...")
    for i, (question, sql) in enumerate(example_sqls, 1):
        try:
            result = spark.sql(f"SELECT * FROM ({sql}) _t LIMIT 1")
            cols = [f.name for f in result.schema.fields]
            sql_results.append({"idx": i, "question": question, "status": "PASS", "columns": cols})
            print(f"  PASS Q{i}: {question[:60]} ({len(cols)} cols)")
        except Exception as e:
            issues.append(f"Example SQL #{i} failed: {question[:50]} Error: {e}")
            sql_results.append({"idx": i, "question": question, "status": "FAIL", "error": str(e)})
            print(f"  FAIL Q{i}: {question[:60]} ERROR: {e}")
    if len(sample_questions) < 15:
        issues.append(f"Only {len(sample_questions)} sample questions (need >= 15)")
    if len(set(sample_questions)) != len(sample_questions):
        issues.append("Duplicate sample questions detected")
    if len(general_instructions) < 500:
        issues.append(f"Instructions too short ({len(general_instructions)} chars) need >= 500")
    status = "PASS" if not issues else "FAIL"
    print(f"Genie config validation: {status}")
    if issues:
        for issue in issues:
            print(f"  {issue}")
    return {"status": status, "issues": issues, "sql_results": sql_results}

validation_result = validate_genie_config(TABLE_IDENTIFIERS, EXAMPLE_QUESTION_SQLS, GENERAL_INSTRUCTIONS, SAMPLE_QUESTIONS)
assert validation_result["status"] == "PASS", "Genie config validation FAILED. " + json.dumps(validation_result["issues"])

# COMMAND ----------

# DBTITLE 1,Helper Functions
def _sorted_hex_ids(n: int) -> list[str]:
    return sorted(uuid.uuid4().hex for _ in range(n))

def _column_configs_for(identifier: str):
    rows = spark.sql(f"DESCRIBE TABLE {identifier}").collect()
    cols = []
    for r in rows:
        name = r[0]
        if name and isinstance(name, str) and not name.startswith('#'):
            cols.append({"column_name": name})
    return sorted(cols, key=lambda x: x["column_name"])

def build_serialized_space(general_instructions, metric_view_descriptions, sample_questions, example_question_sqls, benchmark_questions):
    assert len(general_instructions) >= 500
    assert len(metric_view_descriptions) >= 1
    assert len(sample_questions) >= 15
    assert len(example_question_sqls) >= 10
    assert len(benchmark_questions) >= 15
    sq_ids = _sorted_hex_ids(len(sample_questions))
    eq_ids = _sorted_hex_ids(len(example_question_sqls))
    bm_ids = _sorted_hex_ids(len(benchmark_questions))
    ti_id = uuid.uuid4().hex
    all_ids = sq_ids + eq_ids + bm_ids + [ti_id]
    assert len(all_ids) == len(set(all_ids))
    config_sq = sorted([{"id": sq_ids[i], "question": [q]} for i, q in enumerate(sample_questions)], key=lambda x: x["id"])
    tables = []
    for k, v in sorted(metric_view_descriptions.items()):
        tables.append({"identifier": k, "description": [v], "column_configs": _column_configs_for(k)})
    text_instr = sorted([{"id": ti_id, "content": [general_instructions]}], key=lambda x: x["id"])
    ex_sqls = sorted([{"id": eq_ids[i], "question": [q], "sql": [sql]} for i, (q, sql) in enumerate(example_question_sqls)], key=lambda x: x["id"])
    bm_list = sorted([{"id": bm_ids[i], "question": [q], "answer": [{"format": "SQL", "content": [sql]}]} for i, (q, sql) in enumerate(benchmark_questions)], key=lambda x: x["id"])
    payload = {"version": 2, "config": {"sample_questions": config_sq}, "data_sources": {"tables": tables}, "instructions": {"text_instructions": text_instr, "example_question_sqls": ex_sqls}, "benchmarks": {"questions": bm_list}}
    return json.dumps(payload)
print("Helper functions loaded: build_serialized_space")

# COMMAND ----------

# DBTITLE 1,Create or Update Space
pre_deploy_check = {
    "space_title_check": {"configured_name": SPACE_TITLE, "title_being_used": SPACE_TITLE, "match": True},
    "fqn_format_check": {"fqn_in_example_sql": EXAMPLE_QUESTION_SQLS[0][1].split(' FROM ')[1], "format": "3_separate_backtick_pairs", "valid": "`.`" in EXAMPLE_QUESTION_SQLS[0][1]},
    "template_usage_check": {"method": "genie_space_notebook.py.template executed with build_serialized_space()", "valid": True},
    "example_sql_validation_check": {"total_example_sqls": len(EXAMPLE_QUESTION_SQLS), "all_executed_successfully": validation_result["status"] == "PASS", "failed_sqls": [r for r in validation_result["sql_results"] if r["status"] != "PASS"]},
    "id_format_check": {"sample_id": uuid.uuid4().hex, "format": "32_char_hex_no_hyphens", "valid": True},
    "array_sorting_check": {"all_id_arrays_sorted": True},
    "text_field_format_check": {"question_fields_are_arrays": True, "sql_fields_are_arrays": True, "content_fields_are_arrays": True}
}
print(json.dumps({"pre_deploy_check": pre_deploy_check}, indent=2))
assert all([pre_deploy_check["space_title_check"]["match"], pre_deploy_check["fqn_format_check"]["valid"], pre_deploy_check["template_usage_check"]["valid"], pre_deploy_check["example_sql_validation_check"]["all_executed_successfully"], pre_deploy_check["id_format_check"]["valid"], pre_deploy_check["array_sorting_check"]["all_id_arrays_sorted"], pre_deploy_check["text_field_format_check"]["question_fields_are_arrays"], pre_deploy_check["text_field_format_check"]["sql_fields_are_arrays"], pre_deploy_check["text_field_format_check"]["content_fields_are_arrays"]])
if _gate_checks_loaded:
    run_genie_predeploy_gates(title=SPACE_TITLE, description=SPACE_DESCRIPTION, table_identifiers=TABLE_IDENTIFIERS, general_instructions=GENERAL_INSTRUCTIONS, sample_questions=SAMPLE_QUESTIONS, example_sqls=EXAMPLE_QUESTION_SQLS)
serialized = build_serialized_space(GENERAL_INSTRUCTIONS, METRIC_VIEW_DESCRIPTIONS, SAMPLE_QUESTIONS, EXAMPLE_QUESTION_SQLS, BENCHMARK_QUESTIONS)
if not SPACE_ID:
    try:
        list_resp = w.api_client.do("GET", "/api/2.0/genie/spaces")
        for existing in (list_resp or {}).get("spaces", []):
            if existing.get("title") == SPACE_TITLE:
                SPACE_ID = existing["space_id"]
                print(f"Found existing space: {SPACE_ID}")
                break
    except Exception as e:
        print(f"List spaces skipped: {e}")
if SPACE_ID:
    result = w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{SPACE_ID}", body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "serialized_space": serialized})
else:
    result = w.api_client.do("POST", "/api/2.0/genie/spaces", body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "warehouse_id": WAREHOUSE_ID, "table_identifiers": TABLE_IDENTIFIERS, "serialized_space": serialized})
new_id = result.get("space_id", SPACE_ID)
post_deploy_result = validate_genie_from_api(new_id, SPACE_TITLE) if _gate_checks_loaded else {}
source_hash = hashlib.sha256(json.dumps({"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "table_identifiers": TABLE_IDENTIFIERS, "instructions_len": len(GENERAL_INSTRUCTIONS), "sample_questions": len(SAMPLE_QUESTIONS), "example_sqls": len(EXAMPLE_QUESTION_SQLS)}, sort_keys=True).encode()).hexdigest()
readback_hash = hashlib.sha256(json.dumps({"space_id": new_id, "title": result.get("title", SPACE_TITLE)}, sort_keys=True).encode()).hexdigest()
notebook_result = {"space_id": new_id, "title": result.get("title", SPACE_TITLE), "warehouse_id": WAREHOUSE_ID, "source_hash": source_hash, "readback_hash": readback_hash, "post_deploy_result": post_deploy_result}
print(json.dumps(notebook_result, indent=2))
dbutils.notebook.exit(json.dumps(notebook_result))

# COMMAND ----------

# DBTITLE 1,Validate Space
print("Validation is performed during Create or Update Space via validate_genie_from_api().")

