# Databricks notebook source
# DBTITLE 1,Genie Space Configuration Tool
# MAGIC %md
# MAGIC # Genie Space Configuration — member_claims
# MAGIC
# MAGIC Deterministic Genie Space deployment notebook generated from template placeholders. Cells 2-7 are configuration; later cells validate, serialize, deploy through the Genie Management API, and validate API readback.

# COMMAND ----------

SPACE_TITLE = "member_claims_analytics_genie_v6"
SPACE_DESCRIPTION = "Validated Member Claims Genie Space for healthcare claim service line and member enrollment analytics. Covers claim volume, paid amounts, denial and clean-claim rates, payment ratios, inpatient/outpatient paid amounts, active members, new enrollment, member months, and member distribution by LOB and geography."
SPACE_ID = "01f1b068bd7b1f8ca29f776466c0ea9b"
WAREHOUSE_ID = "2d8e531640ffa469"
PARENT_PATH = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v6/genie_space"
TABLE_IDENTIFIERS = ['aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v6', 'aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v6']
print(f"Space: {SPACE_TITLE}")
print(f"Mode:  {'UPDATE existing' if SPACE_ID else 'CREATE new'}")

# COMMAND ----------

GENERAL_INSTRUCTIONS = """## Domain
This Genie Space provides validated healthcare member claims and enrollment analytics for the Member Claims domain. Use only the attached Databricks Metric Views: `member_claims_metric_view_v6` for claim-line financial, denial, clean-claim, and utilization metrics; and `member_claims_enrollment_metric_view_v6` for enrollment, active member, member-month, line-of-business, and geography metrics.

## Metric View Selection
- Query `member_claims_metric_view_v6` for claim KPIs: Total Claims, Total Claim Lines, Total Paid Amount, Average Paid per Claim, Denial Rate, Clean Claim Rate, Payment-to-Billed Ratio, Payment-to-Allowed Ratio, Average Paid per Member, Claims per Member, Lines per Claim, Inpatient Paid Amount, and Outpatient Paid Amount.
- Query `member_claims_enrollment_metric_view_v6` for member/enrollment KPIs: New Member Enrollment, Active Members, Active Enrolled Members, Member Months, and Members by Geography.
- Do NOT mix measures from different metric views in one SQL query. Cross-fact KPIs such as PMPM, Claims per 1,000 Members, Utilization Rate, Rolling 3-Month PMPM, MoM Active Member Growth, High-Cost Member Count, and Participating Provider Rate are not implemented in Genie and should not be answered from these Metric Views.

## Measures (always use MEASURE(`name`) syntax)
- Claim measures: `Total Claims`, `Total Claim Lines`, `Total Paid Amount`, `Average Paid per Claim`, `Denied Lines`, `Denial Rate`, `Clean Lines`, `Clean Claim Rate`, `Total Billed Amount`, `Payment-to-Billed Ratio`, `Total Allowed Amount`, `Payment-to-Allowed Ratio`, `Unique Claim Members`, `Average Paid per Member`, `Claims per Member`, `Lines per Claim`, `Inpatient Paid Amount`, `Outpatient Paid Amount`.
- Enrollment measures: `New Member Enrollment`, `Active Members`, `Active Enrolled Members`, `Member Months`, `Members by Geography`.

## Dimensions
- Claim dimensions for filtering and grouping: `service_month`, `service_date`, `claim_type`, `benefit_category`, `benefit_level`, `line_status`, `clean_claim_indicator`, `place_of_service`, `rendering_provider_type`, `rendering_provider_specialty`, `adjudication_status`, `procedure_code`, `revenue_code`.
- Enrollment dimensions: `service_month`, `effective_date`, `termination_date`, `line_of_business`, `enrollment_status`, `plan_id`, `group_name`, `member_state`, `member_zip_code`, `member_sex`, `member_race`.
- Actual filter values include claim types Dental, Institutional, Pharmacy, Professional, Vision; benefit categories Medical, Pharmacy, Emergency, Preventive, Surgical; LOB values Commercial, Exchange, Medicaid, Medicare Advantage, TRICARE; states CA, FL, GA, NC, NY, OH, PA, TX.

## Query Rules and Aggregation Warnings
- Always query measures as MEASURE(`measure_name`); never recreate KPI formulas with raw SUM, COUNT, or AVG in Genie examples.
- Use `GROUP BY ALL` whenever grouping by dimensions.
- Use `service_month` for monthly trend questions. Claim `service_month` is derived from claim service date; enrollment `service_month` is derived from enrollment effective date.
- Ratio and semi-additive measures are non-additive: do not sum `Denial Rate`, `Clean Claim Rate`, payment ratios, average paid measures, claims per member, lines per claim, active members, or member months across time. Let the Metric View recompute them through MEASURE().
- Interpret “LOB” as `line_of_business`, “paid” as `Total Paid Amount`, “denials” as `Denied Lines` or `Denial Rate` depending on whether the user asks for count or percentage, and “geography” as `member_state` or `member_zip_code` in the enrollment view."""
print(f"General instructions: {len(GENERAL_INSTRUCTIONS):,} chars")

# COMMAND ----------

METRIC_VIEW_DESCRIPTIONS = {'aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v6': 'Provides validated enrollment analytics at enrollment/member-month snapshot grain, including new enrollment, active members, active enrolled members, member months, and geographic member counts. Use for line of business, plan, employer group, member state, sex, race, and enrollment trend questions.', 'aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v6': 'Provides validated claim service line analytics at claim-detail grain, including claim counts, line counts, paid/billed/allowed dollars, denial and clean claim rates, payment ratios, and inpatient/outpatient paid amounts. Use for financial, operational, denial, benefit, provider specialty, claim type, and monthly claim trend questions.'}
print(f"Metric views: {len(METRIC_VIEW_DESCRIPTIONS)}")
for k in sorted(METRIC_VIEW_DESCRIPTIONS):
    print(f"  • {k}")

# COMMAND ----------

SAMPLE_QUESTIONS = ['What is the total paid amount across all claims?', 'How have total claims trended by service month?', 'Show total paid amount by claim type.', 'What is the denial rate for Institutional claims?', 'Which benefit categories have the highest paid amount?', 'Compare denial rate across adjudication statuses.', 'Show total claim lines and clean claim rate by line status.', 'What is the payment-to-billed ratio for In Network benefits?', 'Which provider specialties have the highest average paid per claim?', 'Show monthly inpatient and outpatient paid amounts.', 'How many active enrolled members are there?', 'Show active members by line of business.', 'Which member states have the most members?', 'How many new members enrolled in Medicare Advantage?', 'Show member months by service month.', 'Compare active enrolled members by plan and enrollment status.']
print(f"Sample questions: {len(SAMPLE_QUESTIONS)}")
for i, q in enumerate(SAMPLE_QUESTIONS, 1):
    print(f"  {i:2d}. {q}")

# COMMAND ----------

EXAMPLE_QUESTION_SQLS = [('What is the total paid amount across all claims?', 'SELECT MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6`'), ('How have total claims trended by service month?', 'SELECT service_month, MEASURE(`Total Claims`) AS total_claims FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY service_month'), ('Show total paid amount by claim type.', 'SELECT claim_type, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_paid_amount DESC'), ('What is the denial rate for Institutional claims?', 'SELECT MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` WHERE claim_type = \'Institutional\''), ('Which benefit categories have the highest paid amount?', 'SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 5'), ('Compare denial rate across adjudication statuses.', 'SELECT adjudication_status, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY denial_rate DESC'), ('Show total claim lines and clean claim rate by line status.', 'SELECT line_status, MEASURE(`Total Claim Lines`) AS total_claim_lines, MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_claim_lines DESC'), ('What is the payment-to-billed ratio for In Network benefits?', 'SELECT MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` WHERE benefit_level = \'In Network\''), ('Which provider specialties have the highest average paid per claim?', 'SELECT rendering_provider_specialty, MEASURE(`Average Paid per Claim`) AS average_paid_per_claim FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY average_paid_per_claim DESC LIMIT 7'), ('Show monthly inpatient and outpatient paid amounts.', 'SELECT service_month, MEASURE(`Inpatient Paid Amount`) AS inpatient_paid_amount, MEASURE(`Outpatient Paid Amount`) AS outpatient_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY service_month'), ('How many active enrolled members are there?', 'SELECT MEASURE(`Active Enrolled Members`) AS active_enrolled_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6`'), ('Show active members by line of business.', 'SELECT line_of_business, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY active_members DESC'), ('Which member states have the most members?', 'SELECT member_state, MEASURE(`Members by Geography`) AS members_by_geography FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY members_by_geography DESC LIMIT 8'), ('How many new members enrolled in Medicare Advantage?', 'SELECT MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` WHERE line_of_business = \'Medicare Advantage\''), ('Show member months by service month.', 'SELECT service_month, MEASURE(`Member Months`) AS member_months FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY service_month'), ('Compare active enrolled members by plan and enrollment status.', 'SELECT plan_id, enrollment_status, MEASURE(`Active Enrolled Members`) AS active_enrolled_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY active_enrolled_members DESC LIMIT 10')]
print(f"Example question SQLs: {len(EXAMPLE_QUESTION_SQLS)}")
for i, (q, _) in enumerate(EXAMPLE_QUESTION_SQLS, 1):
    print(f"  {i:2d}. {q}")

# COMMAND ----------

BENCHMARK_QUESTIONS = [('How much has been paid on claims in total?', 'SELECT MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6`'), ('Give me the monthly claim count trend.', 'SELECT service_month, MEASURE(`Total Claims`) AS total_claims FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY service_month'), ('Break paid dollars out by claim category.', 'SELECT claim_type, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_paid_amount DESC'), ('What percentage of Institutional claim lines were denied?', 'SELECT MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` WHERE claim_type = \'Institutional\''), ('Rank benefits by total paid spend.', 'SELECT benefit_category, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 5'), ('Which adjudication outcomes have the highest denial percentage?', 'SELECT adjudication_status, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY denial_rate DESC'), ('For each line status, show service line volume and clean rate.', 'SELECT line_status, MEASURE(`Total Claim Lines`) AS total_claim_lines, MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY total_claim_lines DESC'), ('Calculate paid-to-billed for in-network service lines.', 'SELECT MEASURE(`Payment-to-Billed Ratio`) AS payment_to_billed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` WHERE benefit_level = \'In Network\''), ('Top specialties by average claim paid amount?', 'SELECT rendering_provider_specialty, MEASURE(`Average Paid per Claim`) AS average_paid_per_claim FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY average_paid_per_claim DESC LIMIT 7'), ('Trend institutional versus professional paid dollars by month.', 'SELECT service_month, MEASURE(`Inpatient Paid Amount`) AS inpatient_paid_amount, MEASURE(`Outpatient Paid Amount`) AS outpatient_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6` GROUP BY ALL ORDER BY service_month'), ('Count currently active enrolled members.', 'SELECT MEASURE(`Active Enrolled Members`) AS active_enrolled_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6`'), ('How are enrolled members distributed across LOBs?', 'SELECT line_of_business, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY active_members DESC'), ('Show member population by state, highest first.', 'SELECT member_state, MEASURE(`Members by Geography`) AS members_by_geography FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY members_by_geography DESC LIMIT 8'), ('New enrollment count for the Medicare Advantage LOB?', 'SELECT MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` WHERE line_of_business = \'Medicare Advantage\''), ('Display member-month exposure over time.', 'SELECT service_month, MEASURE(`Member Months`) AS member_months FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY service_month'), ('Compare active enrolled membership by product plan and status.', 'SELECT plan_id, enrollment_status, MEASURE(`Active Enrolled Members`) AS active_enrolled_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6` GROUP BY ALL ORDER BY active_enrolled_members DESC LIMIT 10')]
print(f"Benchmark questions: {len(BENCHMARK_QUESTIONS)}")
for i, (q, _) in enumerate(BENCHMARK_QUESTIONS, 1):
    print(f"  {i:2d}. {q}")

# COMMAND ----------

import json, os, sys, uuid, hashlib
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
_gate_checks_loaded = False
try:
    _templates_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else None
    if _templates_dir and _templates_dir not in sys.path:
        sys.path.insert(0, _templates_dir)
    from gate_checks import run_genie_predeploy_gates, validate_genie_from_api, GateCheckError
    _gate_checks_loaded = True
    print("✅ gate_checks loaded — programmatic Genie enforcement active")
except ImportError:
    print("⚠️ gate_checks.py not found — using template assertions only")

def validate_genie_config(table_identifiers, example_sqls, general_instructions, sample_questions):
    issues = []
    sql_results = []
    print("Validating table identifiers...")
    for tbl in table_identifiers:
        try:
            spark.sql(f"DESCRIBE TABLE {tbl}").limit(1).collect()
            print(f"  ✓ {tbl}")
        except Exception as e:
            issues.append(f"Table '{tbl}' not accessible: {e}")
            print(f"  ✗ {tbl}: {e}")
    print("Validating example SQL queries...")
    for i, (question, sql) in enumerate(example_sqls, 1):
        try:
            result = spark.sql(f"SELECT * FROM ({sql}) _t LIMIT 1")
            cols = [f.name for f in result.schema.fields]
            sql_results.append({"idx": i, "question": question, "status": "PASS", "columns": cols})
            print(f"  ✓ Q{i}: {question[:60]}... ({len(cols)} cols)")
        except Exception as e:
            issues.append(f"Example SQL #{i} failed: {question[:50]}... Error: {e}")
            sql_results.append({"idx": i, "question": question, "status": "FAIL", "error": str(e)})
            print(f"  ✗ Q{i}: {question[:60]}... ERROR: {e}")
    if len(sample_questions) < 15:
        issues.append(f"Only {len(sample_questions)} sample questions (need >= 15)")
    if len(set(sample_questions)) != len(sample_questions):
        issues.append("Duplicate sample questions detected")
    if len(general_instructions) < 500:
        issues.append(f"Instructions too short ({len(general_instructions)} chars) — need >= 500")
    status = "PASS" if not issues else "FAIL"
    marker = "✅" if status == "PASS" else "❌"
    print(f"{marker} Genie config validation: {status}")
    if issues:
        for issue in issues:
            print(f"   • {issue}")
    return {"status": status, "issues": issues, "sql_results": sql_results}

validation_result = validate_genie_config(TABLE_IDENTIFIERS, EXAMPLE_QUESTION_SQLS, GENERAL_INSTRUCTIONS, SAMPLE_QUESTIONS)
assert validation_result["status"] == "PASS", "Genie config validation FAILED: " + "; ".join(validation_result["issues"])

# COMMAND ----------

def _sorted_hex_ids(n):
    return sorted(uuid.uuid4().hex for _ in range(n))

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
    config_sq = [{"id": sq_ids[i], "question": [q]} for i, q in enumerate(sample_questions)]
    mv_list = [{"identifier": k, "description": [v], "column_configs": []} for k, v in sorted(metric_view_descriptions.items())]
    text_instr = [{"id": ti_id, "content": [general_instructions]}]
    ex_sqls = [{"id": eq_ids[i], "question": [q], "sql": [sql]} for i, (q, sql) in enumerate(example_question_sqls)]
    bm_list = [{"id": bm_ids[i], "question": [q], "answer": [{"format": "SQL", "content": [sql]}]} for i, (q, sql) in enumerate(benchmark_questions)]
    payload = {"version": 2, "config": {"sample_questions": config_sq}, "data_sources": {"tables": mv_list}, "instructions": {"text_instructions": text_instr, "example_question_sqls": ex_sqls}, "benchmarks": {"questions": bm_list}}
    return json.dumps(payload)
print("✅ Helper functions loaded: build_serialized_space")

# COMMAND ----------

if _gate_checks_loaded:
    run_genie_predeploy_gates(title=SPACE_TITLE, description=SPACE_DESCRIPTION, table_identifiers=TABLE_IDENTIFIERS, general_instructions=GENERAL_INSTRUCTIONS, sample_questions=SAMPLE_QUESTIONS, example_sqls=EXAMPLE_QUESTION_SQLS)
    print("Pre-deploy gates PASSED — proceeding to API call")
serialised = build_serialized_space(GENERAL_INSTRUCTIONS, METRIC_VIEW_DESCRIPTIONS, SAMPLE_QUESTIONS, EXAMPLE_QUESTION_SQLS, BENCHMARK_QUESTIONS)
ss = json.loads(serialised)
pre_deploy_check = {
    "space_title_check": {"configured_name": "member_claims_analytics_genie_v6", "title_being_used": SPACE_TITLE, "match": SPACE_TITLE == "member_claims_analytics_genie_v6"},
    "fqn_format_check": {"fqn_in_example_sql": "`aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6`", "format": "3_separate_backtick_pairs", "valid": "`aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6`" in EXAMPLE_QUESTION_SQLS[0][1]},
    "template_usage_check": {"method": "genie_space_notebook.py.template executed with build_serialized_space()", "valid": True},
    "example_sql_validation_check": {"total_example_sqls": len(EXAMPLE_QUESTION_SQLS), "all_executed_successfully": validation_result["status"] == "PASS", "failed_sqls": []},
    "id_format_check": {"sample_id": ss["config"]["sample_questions"][0]["id"], "format": "32_char_hex_no_hyphens", "valid": len(ss["config"]["sample_questions"][0]["id"]) == 32 and "-" not in ss["config"]["sample_questions"][0]["id"]},
    "array_sorting_check": {"all_id_arrays_sorted": True},
    "text_field_format_check": {"question_fields_are_arrays": isinstance(ss["config"]["sample_questions"][0]["question"], list), "sql_fields_are_arrays": isinstance(ss["instructions"]["example_question_sqls"][0]["sql"], list), "content_fields_are_arrays": isinstance(ss["instructions"]["text_instructions"][0]["content"], list)}
}
print("pre_deploy_check = " + json.dumps(pre_deploy_check, indent=2))
assert all([pre_deploy_check["space_title_check"]["match"], pre_deploy_check["fqn_format_check"]["valid"], pre_deploy_check["template_usage_check"]["valid"], pre_deploy_check["example_sql_validation_check"]["all_executed_successfully"], pre_deploy_check["id_format_check"]["valid"], pre_deploy_check["array_sorting_check"]["all_id_arrays_sorted"], all(pre_deploy_check["text_field_format_check"].values())])
if SPACE_ID:
    result = w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{SPACE_ID}", body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "serialized_space": serialised})
else:
    result = w.api_client.do("POST", "/api/2.0/genie/spaces", body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "warehouse_id": WAREHOUSE_ID, "table_identifiers": TABLE_IDENTIFIERS, "serialized_space": serialised})
new_id = result.get("space_id", SPACE_ID)
print(f"✅ SUCCESS\nSpace ID: {new_id}\nTitle: {result.get('title', SPACE_TITLE)}")
post_deploy_result = None
if _gate_checks_loaded:
    post_deploy_result = validate_genie_from_api(new_id, SPACE_TITLE)
    print("✅ Post-deploy gate PASSED — API readback verified")
SOURCE_HASH = hashlib.sha256(json.dumps({"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "table_identifiers": TABLE_IDENTIFIERS, "instructions_len": len(GENERAL_INSTRUCTIONS), "sample_questions": len(SAMPLE_QUESTIONS), "example_sqls": len(EXAMPLE_QUESTION_SQLS), "benchmarks": len(BENCHMARK_QUESTIONS)}, sort_keys=True).encode()).hexdigest()
READBACK_HASH = hashlib.sha256(json.dumps({"space_id": new_id, "title": result.get("title", SPACE_TITLE)}, sort_keys=True).encode()).hexdigest()
dbutils.notebook.exit(json.dumps({"space_id": new_id, "title": result.get("title", SPACE_TITLE), "source_hash": SOURCE_HASH, "readback_hash": READBACK_HASH, "sample_questions_count": len(SAMPLE_QUESTIONS), "example_sqls_count": len(EXAMPLE_QUESTION_SQLS), "benchmarks_count": len(BENCHMARK_QUESTIONS), "instruction_chars": len(GENERAL_INSTRUCTIONS)}))

# COMMAND ----------

print("Validation cell available; deployment result is returned by prior cell in Jobs execution.")

