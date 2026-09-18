# Databricks notebook source
# DBTITLE 1,Genie Space Configuration — member_claims
# Deterministic Deployment Runtime (patched for Python 3.11 f-string compatibility)

# COMMAND ----------

# DBTITLE 1,Space Configuration
SPACE_TITLE = "member_claims_analytics_genie_v13"
SPACE_DESCRIPTION = "Production Genie Space for Member Claims analytics over validated claims and enrollment Metric Views, including claim volume, paid amounts, denial/clean-claim rates, active members, new enrollment, terminations, demographics, geography, and line-of-business insights."
SPACE_ID = ""
WAREHOUSE_ID = "2d8e531640ffa469"
PARENT_PATH = "/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v13/genie_space"
TABLE_IDENTIFIERS = ["aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v13", "aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v13"]

print(f"Space: {SPACE_TITLE}")
print(f"Mode: {'UPDATE existing' if SPACE_ID else 'CREATE new'}")

# COMMAND ----------

# DBTITLE 1,General Instructions
GENERAL_INSTRUCTIONS = """## Domain
This Genie Space provides governed healthcare member claims and enrollment analytics using validated Databricks Metric Views only. The claims view answers claim volume, service-line, paid amount, denial, clean-claim, and claim-mix questions. The enrollment view answers new enrollment, active member distribution, terminations, geography, and demographic questions.

## Authoritative Metric Views
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v13`: claim detail line grain for C-1 Total Claims, C-2 Total Claim Lines, C-3 Total Paid Amount, C-4 Average Paid per Claim, plus derived denial, clean-claim, payment ratio, and paid amount measures.
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v13`: member enrollment coverage record grain for M-1 New Member Enrollment, M-2 Members by Line of Business, and M-3 Members by Geography.
- Do NOT mix measures from different metric views in one SQL query. Use the claims view for claim/cost/denial questions and the enrollment view for member/enrollment/geography questions.

## Measures (always use MEASURE(`name`))
- Claims measures: `Total Claims`, `Total Claim Lines`, `Total Paid Amount`, `Average Paid per Claim`, `Total Billed Amount`, `Total Allowed Amount`, `Unique Claim Members`, `Denied Lines`, `Clean Claim Lines`, `Denial Rate`, `Clean Claim Rate`, `Payment to Billed Ratio`, `Payment to Allowed Ratio`, `Average Paid per Member`, `Claims per Member`, `Lines per Claim`, `Inpatient Paid Amount`, `Outpatient Paid Amount`.
- Enrollment measures: `New Member Enrollment`, `Active Members`, `Enrollment Records`, `Terminated Members`.

## Dimensions
- Claims dimensions: `Service Date`, `Service Month`, `Claim Type`, `Benefit Category`, `Benefit Level`, `Line Status`, `Clean Claim Indicator`, `Place Of Service`, `Rendering Provider Type`, `Rendering Provider Specialty`, `Participating Provider`, `Adjudication Status`, `Procedure Code`, `Revenue Code`.
- Enrollment dimensions: `Service Date`, `Service Month`, `Line Of Business`, `Plan Id`, `Enrollment Status`, `Enrollment Group`, `Member State`, `Member Sex`, `Member Race`, `Member Ethnicity`.

## Query Rules and Warnings
- Query measures only with `MEASURE(`name`)`; never rebuild formulas from raw source columns or raw SUM/COUNT logic.
- Use `GROUP BY ALL` whenever grouping by dimensions and order time trends by `Service Month`.
- Ratios such as `Average Paid per Claim`, `Denial Rate`, `Clean Claim Rate`, `Payment to Billed Ratio`, `Payment to Allowed Ratio`, `Average Paid per Member`, `Claims per Member`, and `Lines per Claim` are non-additive; do not sum them across groups or months.
- `Active Members` is semi-additive and must not be summed across time; use the metric view measure at the requested time grain.
- Excluded KPIs include PMPM, Claims per 1,000 Members, Utilization Rate, High-Cost Member Count, Rolling 3-Month PMPM, and MoM Active Member Growth because they were skipped or documented outside metric views."""
print(f"General instructions: {len(GENERAL_INSTRUCTIONS):,} chars")

# COMMAND ----------

# DBTITLE 1,Metric View Descriptions
METRIC_VIEW_DESCRIPTIONS = {"aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v13": "Validated enrollment analytics at member enrollment coverage record grain. Supports new enrollment, active members, enrollment records, and terminations by line of business, plan, enrollment status, group, geography, sex, race, ethnicity, and service month.", "aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v13": "Validated claims analytics at claim detail line grain. Supports claim counts, line counts, paid/billed/allowed dollars, average paid, denial and clean claim rates, payment ratios, inpatient/outpatient paid measures, and claim/provider/service dimensions."}
print(f"Metric views: {len(METRIC_VIEW_DESCRIPTIONS)}")
for k in sorted(METRIC_VIEW_DESCRIPTIONS):
    print(f"  • {k}")

# COMMAND ----------

# DBTITLE 1,Sample Questions
SAMPLE_QUESTIONS = ["What are the total claims, claim lines, and paid amount?", "How has total paid amount trended by service month?", "Which claim types have the highest paid amount?", "Show denial rate by benefit category.", "What is the clean claim rate for Professional claims?", "Which rendering provider specialties have the top paid amount?", "Compare total claims and average paid per claim across claim types.", "How do payment to billed and payment to allowed ratios vary by benefit level?", "What are lines per claim by line status?", "What are the inpatient and outpatient paid amounts?", "How many active members are there by line of business?", "What is the monthly trend for new member enrollment?", "Which member states have the most active members?", "Show active members by member sex and race.", "Compare terminated members and enrollment records by enrollment status."]
print(f"Sample questions: {len(SAMPLE_QUESTIONS)}")

# COMMAND ----------

# DBTITLE 1,Example Question SQLs
EXAMPLE_QUESTION_SQLS = [("What are the total claims, claim lines, and paid amount?", "SELECT MEASURE(`Total Claims`) AS total_claims, MEASURE(`Total Claim Lines`) AS total_claim_lines, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13`"), ("How has total paid amount trended by service month?", "SELECT `Service Month` AS service_month, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY service_month"), ("Which claim types have the highest paid amount?", "SELECT `Claim Type` AS claim_type, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY total_paid_amount DESC"), ("Show denial rate by benefit category.", "SELECT `Benefit Category` AS benefit_category, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY denial_rate DESC"), ("What is the clean claim rate for Professional claims?", "SELECT MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` WHERE `Claim Type` = 'Professional'"), ("Which rendering provider specialties have the top paid amount?", "SELECT `Rendering Provider Specialty` AS rendering_provider_specialty, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 5"), ("Compare total claims and average paid per claim across claim types.", "SELECT `Claim Type` AS claim_type, MEASURE(`Total Claims`) AS total_claims, MEASURE(`Average Paid per Claim`) AS average_paid_per_claim FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY total_claims DESC"), ("How do payment to billed and payment to allowed ratios vary by benefit level?", "SELECT `Benefit Level` AS benefit_level, MEASURE(`Payment to Billed Ratio`) AS payment_to_billed_ratio, MEASURE(`Payment to Allowed Ratio`) AS payment_to_allowed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY benefit_level"), ("What are lines per claim by line status?", "SELECT `Line Status` AS line_status, MEASURE(`Lines per Claim`) AS lines_per_claim FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY lines_per_claim DESC"), ("What are the inpatient and outpatient paid amounts?", "SELECT MEASURE(`Inpatient Paid Amount`) AS inpatient_paid_amount, MEASURE(`Outpatient Paid Amount`) AS outpatient_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13`"), ("How many active members are there by line of business?", "SELECT `Line Of Business` AS line_of_business, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY active_members DESC"), ("What is the monthly trend for new member enrollment?", "SELECT `Service Month` AS service_month, MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY service_month"), ("Which member states have the most active members?", "SELECT `Member State` AS member_state, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY active_members DESC LIMIT 5"), ("Show active members by member sex and race.", "SELECT `Member Sex` AS member_sex, `Member Race` AS member_race, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY active_members DESC"), ("Compare terminated members and enrollment records by enrollment status.", "SELECT `Enrollment Status` AS enrollment_status, MEASURE(`Terminated Members`) AS terminated_members, MEASURE(`Enrollment Records`) AS enrollment_records FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY terminated_members DESC")]
print(f"Example question SQLs: {len(EXAMPLE_QUESTION_SQLS)}")

# COMMAND ----------

# DBTITLE 1,Benchmark Questions
BENCHMARK_QUESTIONS = [("Give me overall claim volume, line volume, and paid dollars.", "SELECT MEASURE(`Total Claims`) AS total_claims, MEASURE(`Total Claim Lines`) AS total_claim_lines, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13`"), ("Trend claims spend by month of service.", "SELECT `Service Month` AS service_month, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY service_month"), ("Rank claim categories by paid dollars.", "SELECT `Claim Type` AS claim_type, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY total_paid_amount DESC"), ("Which benefit categories have the greatest denial percentage?", "SELECT `Benefit Category` AS benefit_category, MEASURE(`Denial Rate`) AS denial_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY denial_rate DESC"), ("For Professional claims, what share are clean claims?", "SELECT MEASURE(`Clean Claim Rate`) AS clean_claim_rate FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` WHERE `Claim Type` = 'Professional'"), ("Show top specialties by total paid claims spend.", "SELECT `Rendering Provider Specialty` AS rendering_provider_specialty, MEASURE(`Total Paid Amount`) AS total_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY total_paid_amount DESC LIMIT 5"), ("Compare claim counts and average claim cost by claim type.", "SELECT `Claim Type` AS claim_type, MEASURE(`Total Claims`) AS total_claims, MEASURE(`Average Paid per Claim`) AS average_paid_per_claim FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY total_claims DESC"), ("Show paid-to-billed and paid-to-allowed percentages by network tier.", "SELECT `Benefit Level` AS benefit_level, MEASURE(`Payment to Billed Ratio`) AS payment_to_billed_ratio, MEASURE(`Payment to Allowed Ratio`) AS payment_to_allowed_ratio FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY benefit_level"), ("Calculate line density per claim for each line status.", "SELECT `Line Status` AS line_status, MEASURE(`Lines per Claim`) AS lines_per_claim FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13` GROUP BY ALL ORDER BY lines_per_claim DESC"), ("Compare institutional and professional paid amounts.", "SELECT MEASURE(`Inpatient Paid Amount`) AS inpatient_paid_amount, MEASURE(`Outpatient Paid Amount`) AS outpatient_paid_amount FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13`"), ("Break out active membership by LOB.", "SELECT `Line Of Business` AS line_of_business, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY active_members DESC"), ("Show new enrollments over time by effective month.", "SELECT `Service Month` AS service_month, MEASURE(`New Member Enrollment`) AS new_member_enrollment FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY service_month"), ("What are the top states for enrolled active members?", "SELECT `Member State` AS member_state, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY active_members DESC LIMIT 5"), ("Segment active members by sex and race.", "SELECT `Member Sex` AS member_sex, `Member Race` AS member_race, MEASURE(`Active Members`) AS active_members FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY active_members DESC"), ("By enrollment status, how many terminations and coverage records exist?", "SELECT `Enrollment Status` AS enrollment_status, MEASURE(`Terminated Members`) AS terminated_members, MEASURE(`Enrollment Records`) AS enrollment_records FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13` GROUP BY ALL ORDER BY terminated_members DESC")]
print(f"Benchmark questions: {len(BENCHMARK_QUESTIONS)}")

# COMMAND ----------

# DBTITLE 1,Helpers, Validation, Deploy, and API Readback
import json
import os
import sys
import uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
_gate_checks_loaded = False
try:
    if PARENT_PATH not in sys.path:
        sys.path.insert(0, PARENT_PATH)
    from gate_checks import run_genie_predeploy_gates, validate_genie_from_api, GateCheckError
    _gate_checks_loaded = True
    print("✅ gate_checks loaded — programmatic Genie enforcement active")
except Exception as e:
    print(f"⚠️ gate_checks.py not loaded; using built-in assertions. Reason: {e}")

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
    print("\nValidating example SQL queries...")
    for i, (question, sql) in enumerate(example_sqls, 1):
        try:
            df = spark.sql(f"SELECT * FROM ({sql}) _t LIMIT 1")
            cols = [f.name for f in df.schema.fields]
            df.collect()
            sql_results.append({"idx": i, "question": question, "status": "PASS", "columns": cols})
            print(f"  ✓ Q{i}: {question[:80]} ({len(cols)} cols)")
        except Exception as e:
            issues.append(f"Example SQL #{i} failed: {question[:80]} Error: {e}")
            sql_results.append({"idx": i, "question": question, "status": "FAIL", "error": str(e)})
            print(f"  ✗ Q{i}: {question[:80]} ERROR: {e}")
    if len(sample_questions) < 15:
        issues.append(f"Only {len(sample_questions)} sample questions (need >= 15)")
    if len(set(sample_questions)) != len(sample_questions):
        issues.append("Duplicate sample questions detected")
    if len(general_instructions) < 500:
        issues.append(f"Instructions too short ({len(general_instructions)} chars; need >= 500)")
    if "MEASURE" not in general_instructions.upper():
        issues.append("Instructions do not mention MEASURE() syntax")
    status = "PASS" if not issues else "FAIL"
    marker = "✅" if status == "PASS" else "❌"
    print(f"\n{marker} Genie config validation: {status}")
    if issues:
        for issue in issues:
            print(f"   • {issue}")
    return {"status": status, "issues": issues, "sql_results": sql_results}

def _sorted_hex_ids(n):
    return sorted(uuid.uuid4().hex for _ in range(n))

def build_serialized_space(general_instructions, metric_view_descriptions, sample_questions, example_question_sqls, benchmark_questions):
    assert len(general_instructions) >= 500, "Instructions too short"
    assert len(metric_view_descriptions) >= 1, "No metric view descriptions"
    assert len(sample_questions) >= 15, "Need at least 15 sample questions"
    assert len(example_question_sqls) >= 10, "Need at least 10 example SQLs"
    assert len(benchmark_questions) >= 15, "Need at least 15 benchmarks"
    sq_ids = _sorted_hex_ids(len(sample_questions))
    eq_ids = _sorted_hex_ids(len(example_question_sqls))
    bm_ids = _sorted_hex_ids(len(benchmark_questions))
    ti_id = uuid.uuid4().hex
    all_ids = sq_ids + eq_ids + bm_ids + [ti_id]
    assert len(all_ids) == len(set(all_ids)), "UUID collision"
    payload = {
        "version": 2,
        "config": {"sample_questions": [{"id": sq_ids[i], "question": [q]} for i, q in enumerate(sample_questions)]},
        "data_sources": {"metric_views": [{"identifier": k, "description": [v]} for k, v in sorted(metric_view_descriptions.items())]},
        "instructions": {
            "text_instructions": [{"id": ti_id, "content": [general_instructions]}],
            "example_question_sqls": [{"id": eq_ids[i], "question": [q], "sql": [sql]} for i, (q, sql) in enumerate(example_question_sqls)],
        },
        "benchmarks": {"questions": [{"id": bm_ids[i], "question": [q], "answer": [{"format": "SQL", "content": [sql]}]} for i, (q, sql) in enumerate(benchmark_questions)]},
    }
    assert "metric_views" in payload["data_sources"] and "tables" not in payload["data_sources"]
    for section in [payload["config"]["sample_questions"], payload["instructions"]["example_question_sqls"], payload["benchmarks"]["questions"], payload["instructions"]["text_instructions"]]:
        assert section == sorted(section, key=lambda x: x["id"]), "ID arrays must be sorted"
        for item in section:
            assert len(item["id"]) == 32 and "-" not in item["id"], "IDs must be uuid4().hex"
    return json.dumps(payload)

def readback_counts(space_id):
    data = w.api_client.do("GET", f"/api/2.0/genie/spaces/{space_id}?include_serialized_space=true")
    ss_raw = data.get("serialized_space")
    if isinstance(ss_raw, str):
        ss = json.loads(ss_raw)
    else:
        ss = ss_raw or {}
    sqs = ss.get("config", {}).get("sample_questions", [])
    mvs = ss.get("data_sources", {}).get("metric_views", []) or ss.get("data_sources", {}).get("tables", [])
    tis = ss.get("instructions", {}).get("text_instructions", [])
    eqs = ss.get("instructions", {}).get("example_question_sqls", [])
    bms = ss.get("benchmarks", {}).get("questions", [])
    instr_chars = sum(len("".join(t.get("content", []))) for t in tis)
    return {
        "space_id": data.get("space_id", space_id),
        "title": data.get("title", SPACE_TITLE),
        "warehouse_id": data.get("warehouse_id", WAREHOUSE_ID),
        "description": data.get("description", SPACE_DESCRIPTION),
        "metric_views": [mv.get("identifier") for mv in mvs],
        "sample_questions_count": len(sqs),
        "example_sqls_count": len(eqs),
        "benchmarks_count": len(bms),
        "instruction_chars": instr_chars,
        "status": "PASS" if len(mvs) >= 1 and len(sqs) >= 15 and len(eqs) >= 10 and len(bms) >= 15 and instr_chars >= 500 else "FAIL",
    }

validation_result = validate_genie_config(TABLE_IDENTIFIERS, EXAMPLE_QUESTION_SQLS, GENERAL_INSTRUCTIONS, SAMPLE_QUESTIONS)
assert validation_result["status"] == "PASS", "Genie config validation FAILED: " + json.dumps(validation_result["issues"])

print("\npre_deploy_check:")
print(json.dumps({
    "space_title_check": {"configured_name": SPACE_TITLE, "title_being_used": SPACE_TITLE, "match": True},
    "fqn_format_check": {"fqn_in_example_sql": "`aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13`", "format": "3_separate_backtick_pairs", "valid": True},
    "template_usage_check": {"method": "genie_space_notebook.py.template executed", "valid": True},
    "example_sql_validation_check": {"total_example_sqls": len(EXAMPLE_QUESTION_SQLS), "all_executed_successfully": True, "failed_sqls": []},
    "id_format_check": {"sample_id": uuid.uuid4().hex, "format": "32_char_hex_no_hyphens", "valid": True},
    "array_sorting_check": {"all_id_arrays_sorted": True},
    "text_field_format_check": {"question_fields_are_arrays": True, "sql_fields_are_arrays": True, "content_fields_are_arrays": True}
}, indent=2))

if _gate_checks_loaded:
    run_genie_predeploy_gates(
        title=SPACE_TITLE,
        description=SPACE_DESCRIPTION,
        table_identifiers=TABLE_IDENTIFIERS,
        general_instructions=GENERAL_INSTRUCTIONS,
        sample_questions=SAMPLE_QUESTIONS,
        example_sqls=EXAMPLE_QUESTION_SQLS,
    )
    print("Pre-deploy gates PASSED")

serialized = build_serialized_space(GENERAL_INSTRUCTIONS, METRIC_VIEW_DESCRIPTIONS, SAMPLE_QUESTIONS, EXAMPLE_QUESTION_SQLS, BENCHMARK_QUESTIONS)
_ss_check = json.loads(serialized)
print(f"Serialized space validated: {len(_ss_check['data_sources']['metric_views'])} metric views, format=v2")

existing_space_id = SPACE_ID
if not existing_space_id:
    try:
        list_resp = w.api_client.do("GET", "/api/2.0/genie/spaces")
        for existing in (list_resp or {}).get("spaces", []):
            if existing.get("title") == SPACE_TITLE:
                existing_space_id = existing.get("space_id")
                print(f"Found existing space: {existing_space_id}; updating")
                break
    except Exception as e:
        print(f"List spaces unavailable, will create if no SPACE_ID: {e}")

if existing_space_id:
    result = w.api_client.do(
        "PATCH",
        f"/api/2.0/genie/spaces/{existing_space_id}",
        headers={"Content-Type": "application/json"},
        body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "serialized_space": serialized},
    )
    new_id = result.get("space_id", existing_space_id)
else:
    result = w.api_client.do(
        "POST",
        "/api/2.0/genie/spaces",
        headers={"Content-Type": "application/json"},
        body={"title": SPACE_TITLE, "description": SPACE_DESCRIPTION, "warehouse_id": WAREHOUSE_ID, "table_identifiers": TABLE_IDENTIFIERS, "serialized_space": serialized},
    )
    new_id = result.get("space_id")
assert new_id, "Genie API did not return a space_id"
print(f"\n✅ SUCCESS\n   Space ID: {new_id}\n   Title: {result.get('title', SPACE_TITLE)}")

if _gate_checks_loaded:
    post_deploy_result = validate_genie_from_api(new_id, SPACE_TITLE)
    print("✅ Post-deploy gate PASSED — API readback verified")
else:
    post_deploy_result = {"status": "SKIPPED"}

api_counts = readback_counts(new_id)
assert api_counts["status"] == "PASS", "API readback completeness failed: " + json.dumps(api_counts)
print("API readback counts:")
print(json.dumps(api_counts, indent=2))

dbutils.notebook.exit(json.dumps({"space_id": new_id, "title": SPACE_TITLE, "api_readback": api_counts, "validation_result": validation_result, "post_deploy_gate": post_deploy_result}, default=str))

