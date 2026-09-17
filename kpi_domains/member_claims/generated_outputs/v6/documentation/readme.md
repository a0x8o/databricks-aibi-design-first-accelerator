# Member Claims Accelerator Run Summary

## 1. Solution Overview

This accelerator run created a semantic analytics solution for **Member Claims** (`member_claims`) using **ERD / greenfield synthetic data** mode. The solution includes **8 Unity Catalog tables**, **2 Metric Views**, **2 published AI/BI dashboards**, and **1 validated Genie Space**.

**Overall run status:** `PARTIAL_SUCCESS`

The core data, metric, dashboard, and Genie stages passed their individual validation artifacts. The run is classified as `PARTIAL_SUCCESS` because `ground_truth_validation.yaml` is missing, so the independent terminal cross-validation sweep did not complete, and because 7 KPIs were not available as Metric View measures: 3 are documented as `NOT_IMPLEMENTED` with reference SQL and 4 are skipped with specific data/grain reasons.

**Cross-validation authority note:** Cross-validation sweep did not complete. Asset status below is based on individual step manifests and validation artifacts, not an independent terminal audit.

**Configuration summary**

| Field | Value |
|---|---|
| Domain display name | Member Claims |
| Domain name | member_claims |
| Version suffix | `_v6` |
| Data-source mode | `erd` |
| Source catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| Target catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| SQL warehouse | `2d8e531640ffa469` |

**Reproducibility metadata**

| Field | Value |
|---|---|
| Generated | 2026-09-14T18:10:00Z |
| LLM Model | `databricks-gpt-5-5` |
| Vision Model | `databricks-gpt-5-5` |
| Dashboard Design Model | `databricks-gpt-5-5` |
| Genie Design Model | `databricks-gpt-5-5` |
| Version | `_v6` |

## 2. Architecture / Asset Flow

```text
Source ERD
      ↓
Parsed schema and semantic model
      ↓
Unity Catalog synthetic tables
      ↓
Metric Views by compatible fact grain
      ↓
AI/BI Dashboards
      ↓
Genie Space
      ↓
Validation artifacts and documentation
```

Generated assets are versioned with `_v6` and deployed in `aw_serverless_stable_catalog.aibi_member_claims`.

## 3. Source Schema Summary

The ERD-driven schema contains **8 tables** and **6 relationships** in `erd_parsed.yaml`. `semantic_model.yaml` retains **5 relationships** as usable semantic relationships and flags address/provider/address-related relationships as unresolved or excluded due ambiguous or name-only evidence.

| Table | Role | Grain | Key Relationships |
|---|---|---|---|
| `dim_member` | DIMENSION | one row represents a current member dimension record | parent to claim header, enrollment, member identifier, and member history |
| `dim_provider` | DIMENSION | one row represents a provider record or provider version | provider-address relationship excluded as name-only evidence |
| `dim_address` | DIMENSION | one row represents an address for an owning entity and address type | polymorphic member/address relationship unresolved |
| `dim_member_identifier` | DIMENSION | one row represents one identifier value for a member | `member_sk` to `dim_member.member_sk` |
| `dim_member_history` | SNAPSHOT | one row represents a historical version of a member record | `member_sk` to `dim_member.member_sk` |
| `fact_member_enrollment` | FACT | one row represents a member enrollment record | `member_sk` to `dim_member.member_sk` |
| `fact_claim_header` | FACT | one row represents a claim header | `clm_member_sk` to `dim_member.member_sk` |
| `fact_claim_detail` | FACT | one row represents a claim service line detail | `clm_dtl_claim_id` to `fact_claim_header.clm_claim_id` |

**Unresolved ERD elements**

- `dim_address.entity_dimension_key` to `dim_member.member_sk` was retained as unresolved because the relationship is polymorphic and the ERD label is ambiguous.
- `dim_provider.provider_address_sk` to `dim_address.address_key` was excluded because evidence was column-name only.
- `fact_claim_header.clm_service_facility_address_sk` to `dim_address.address_key` was excluded because evidence was column-name only.

The live-schema profile for the generated target objects shows no schema drift and relationship verification passed for the 5 modeled relationships.

## 4. Data Layer

Greenfield table creation and synthetic-data generation ran for this ERD-based configuration.

**Data-layer validation status:** `PASS`

| Table | FQN | Rows | PK validation |
|---|---|---:|---|
| `dim_member_v6` | `aw_serverless_stable_catalog.aibi_member_claims.dim_member_v6` | 500 | PASS, 0 duplicates |
| `dim_provider_v6` | `aw_serverless_stable_catalog.aibi_member_claims.dim_provider_v6` | 300 | PASS, 0 duplicates |
| `dim_address_v6` | `aw_serverless_stable_catalog.aibi_member_claims.dim_address_v6` | 400 | PASS, 0 duplicates |
| `dim_member_identifier_v6` | `aw_serverless_stable_catalog.aibi_member_claims.dim_member_identifier_v6` | 800 | PASS, 0 duplicates |
| `dim_member_history_v6` | `aw_serverless_stable_catalog.aibi_member_claims.dim_member_history_v6` | 1,000 | PASS, 0 duplicates |
| `fact_member_enrollment_v6` | `aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v6` | 1,500 | PASS, 0 duplicates |
| `fact_claim_header_v6` | `aw_serverless_stable_catalog.aibi_member_claims.fact_claim_header_v6` | 3,000 | PASS, 0 duplicates |
| `fact_claim_detail_v6` | `aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v6` | 9,000 | PASS, 0 duplicates |

**Validation results from `data_layer_validation.yaml`**

| Check | Result |
|---|---|
| Tables expected / created | 8 / 8 |
| Primary keys tested | 8; failures: 0 |
| Foreign keys tested | 5; orphan-count failures: 0 |
| Join stability / fanout | 5 tested; fanout failures: 0 |
| Semantic constraints | 3 tested; failures: 0 |
| Domain-value checks | 66 columns checked; generic-value failures: 0 |
| Generic fallback columns | 0 |

## 5. Metric Views

The metric layer created **2 Metric Views** because claim-line KPIs and enrollment/member KPIs have incompatible fact grains.

| Metric View | FQN | Source | Source Grain | Measures | Dimensions | Status |
|---|---|---|---|---:|---:|---|
| `member_claims_metric_view_v6` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v6` | `fact_claim_detail_v6` | one row represents a claim service line detail | 18 | 13 | PASS |
| `member_claims_enrollment_metric_view_v6` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v6` | `fact_member_enrollment_v6` joined to `dim_member_v6` | one row represents a member enrollment record / member-month enrollment snapshot | 5 | 11 | PASS |

**Validated measures**

- Claim metric view: `Total Claims`, `Total Claim Lines`, `Total Paid Amount`, `Average Paid per Claim`, `Denied Lines`, `Denial Rate`, `Clean Lines`, `Clean Claim Rate`, `Total Billed Amount`, `Payment-to-Billed Ratio`, `Total Allowed Amount`, `Payment-to-Allowed Ratio`, `Unique Claim Members`, `Average Paid per Member`, `Claims per Member`, `Lines per Claim`, `Inpatient Paid Amount`, `Outpatient Paid Amount`.
- Enrollment metric view: `New Member Enrollment`, `Active Members`, `Active Enrolled Members`, `Member Months`, `Members by Geography`.

No intermediate materialized views were created.

## 6. KPI Catalog

KPI statuses below come from `metric_view_validation.yaml`. A KPI is listed as implemented only when its status is `IMPLEMENTED_AND_VALIDATED`.

| KPI | Metric View | Measure | Status | Notes |
|---|---|---|---|---|
| M-1 New Member Enrollment | `member_claims_enrollment_metric_view_v6` | `New Member Enrollment` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500.0 |
| M-2 Members by Line of Business | `member_claims_enrollment_metric_view_v6` | `Active Members` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500.0 |
| M-3 Members by Geography | `member_claims_enrollment_metric_view_v6` | `Members by Geography` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500.0 |
| C-1 Total Claims | `member_claims_metric_view_v6` | `Total Claims` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 3000.0 |
| C-2 Total Claim Lines | `member_claims_metric_view_v6` | `Total Claim Lines` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 9000.0 |
| C-3 Total Paid Amount | `member_claims_metric_view_v6` | `Total Paid Amount` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 40495500.0 |
| C-4 Average Paid per Claim | `member_claims_metric_view_v6` | `Average Paid per Claim` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 13498.5 |
| MC-1 PMPM | none | none | SKIPPED_UNSAFE_GRAIN | Requires claim paid numerator and enrollment member-month denominator from different fact grains with no safe common metric view grain. |
| MC-2 Claims per 1,000 Members | none | none | SKIPPED_UNSAFE_GRAIN | Requires claim numerator and enrollment member-month denominator from different fact grains with no safe common metric view grain. |
| MC-3 Utilization Rate | none | none | SKIPPED_UNRESOLVED_RELATIONSHIP | Claim detail member key `clm_dtl_member_nbr_sk` is VARCHAR and no semantic relationship exists to enrollment `member_sk` BIGINT. |
| MC-4 High-Cost Member Count | none | none | NOT_IMPLEMENTED | Requires member-level pre-aggregation with HAVING threshold. Reference SQL is documented below. |
| W-1 Rolling 3-Month PMPM | none | none | NOT_IMPLEMENTED | Requires monthly cross-source pre-aggregation and trailing window calculation. Reference SQL is documented below. |
| W-2 MoM Active Member Growth | none | none | NOT_IMPLEMENTED | Requires LAG window offset on monthly active member counts. Reference SQL is documented below. |
| D-1 Denial Rate | `member_claims_metric_view_v6` | `Denial Rate` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 0.45511111111111113 |
| D-2 Clean Claim Rate | `member_claims_metric_view_v6` | `Clean Claim Rate` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 0.7864444444444444 |
| D-3 Payment-to-Billed Ratio | `member_claims_metric_view_v6` | `Payment-to-Billed Ratio` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 1.0 |
| D-4 Payment-to-Allowed Ratio | `member_claims_metric_view_v6` | `Payment-to-Allowed Ratio` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 1.0 |
| D-5 Average Paid per Member | `member_claims_metric_view_v6` | `Average Paid per Member` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 899900.0 |
| D-6 Claims per Member | `member_claims_metric_view_v6` | `Claims per Member` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 66.66666666666667 |
| D-7 Lines per Claim | `member_claims_metric_view_v6` | `Lines per Claim` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 3.0 |
| D-8 Inpatient Paid Amount | `member_claims_metric_view_v6` | `Inpatient Paid Amount` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 15065521.0 |
| D-9 Outpatient Paid Amount | `member_claims_metric_view_v6` | `Outpatient Paid Amount` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 18057740.0 |
| D-10 Participating Provider Rate | none | none | SKIPPED_MISSING_DATA | No participating provider flag and no safe rendering provider key exists in `fact_claim_detail_v6`. |
| E-1 Active Enrolled Members | `member_claims_enrollment_metric_view_v6` | `Active Enrolled Members` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 250.0 |
| E-2 Member Months | `member_claims_enrollment_metric_view_v6` | `Member Months` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 1500.0 |

## 6.1 Not Implemented KPIs

The following KPIs could not be implemented as metric view measures due to SQL semantics that Databricks Metric Views do not support. The validated SQL queries are provided below for manual implementation if needed. These KPIs are not in the dashboards or Genie Space as Metric View measures.

### MC-4: High-Cost Member Count

**Reason:** Requires member-level pre-aggregation with HAVING threshold, which is not expressible as a safe single metric view measure at raw claim-line grain.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
WITH member_spend AS (
  SELECT clm_dtl_member_nbr_sk AS member_key, SUM(clm_dtl_paid_amt) AS member_paid
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v6
  GROUP BY clm_dtl_member_nbr_sk
  HAVING SUM(clm_dtl_paid_amt) > 10000
)
SELECT COUNT(*) AS high_cost_member_count FROM member_spend
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be a metric view measure because it requires HAVING on a member-level aggregate.

### W-1: Rolling 3-Month PMPM

**Reason:** Requires monthly cross-source pre-aggregation plus trailing window over numerator and denominator.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
WITH paid_monthly AS (
  SELECT DATE_TRUNC('MONTH', clm_dtl_specific_dos_date) AS service_month,
         SUM(clm_dtl_paid_amt) AS total_paid
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v6
  GROUP BY DATE_TRUNC('MONTH', clm_dtl_specific_dos_date)
), enrollment_monthly AS (
  SELECT DATE_TRUNC('MONTH', mbr_enr_effective_date) AS service_month,
         COUNT(DISTINCT CONCAT(CAST(member_sk AS STRING), '-', CAST(DATE_TRUNC('MONTH', mbr_enr_effective_date) AS STRING))) AS member_months
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v6
  GROUP BY DATE_TRUNC('MONTH', mbr_enr_effective_date)
), combined AS (
  SELECT p.service_month, p.total_paid, e.member_months
  FROM paid_monthly p
  LEFT JOIN enrollment_monthly e ON p.service_month = e.service_month
), rolling AS (
  SELECT service_month,
         SUM(total_paid) OVER (ORDER BY service_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS trailing_3m_paid,
         SUM(member_months) OVER (ORDER BY service_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS trailing_3m_member_months
  FROM combined
)
SELECT service_month, trailing_3m_paid / NULLIF(trailing_3m_member_months, 0) AS rolling_3_month_pmpm
FROM rolling
ORDER BY service_month
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be a metric view measure due to cross-source monthly alignment and trailing window requirement.

### W-2: MoM Active Member Growth

**Reason:** Requires LAG window offset on monthly active member counts.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
WITH monthly AS (
  SELECT DATE_TRUNC('MONTH', mbr_enr_effective_date) AS service_month,
         COUNT(DISTINCT CASE WHEN is_active THEN member_sk END) AS active_members
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v6
  GROUP BY DATE_TRUNC('MONTH', mbr_enr_effective_date)
), lagged AS (
  SELECT service_month, active_members, LAG(active_members) OVER (ORDER BY service_month) AS prior_month_members
  FROM monthly
)
SELECT service_month,
       active_members,
       prior_month_members,
       (active_members - prior_month_members) / NULLIF(prior_month_members, 0) AS mom_active_member_growth
FROM lagged
WHERE prior_month_members IS NOT NULL
ORDER BY service_month
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be a metric view measure due to LAG window offset requirement.

## 7. Dashboards

Dashboard deployment status is documented only for dashboards with API-readback manifests and validation files. Both deployed dashboard manifests show `published: true` and `validation_source: api_readback`.

| Dashboard | ID | Pages | Canvas Pages | Widgets | Filters | Published | Validation |
|---|---|---:|---:|---:|---:|---|---|
| `member_claims_kpis_dashboard_v6` | `01f1b066aaf81eef8e38116ba8848735` | 4 | 3 | 13 | 4 | true | PASS |
| `member_claims_utilization_dashboard_v6` | `01f1b066ac4719e3928d1029bcaabc47` | 4 | 3 | 12 | 4 | true | PASS |

**Dashboard links**

- `member_claims_kpis_dashboard_v6`: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b066aaf81eef8e38116ba8848735/published
- `member_claims_utilization_dashboard_v6`: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b066ac4719e3928d1029bcaabc47/published

**Page structure and design details**

| Dashboard | Source Metric Views | Pages | Filter Dimensions | Viz Types | Design Source |
|---|---|---|---|---|---|
| `member_claims_kpis_dashboard_v6` | `member_claims_metric_view_v6` | Filters; Executive Summary; Trend Analysis; Segment Breakdown | `service_month`, `claim_type`, `benefit_category`, `line_status` | counter, bar, line | LLM-assisted design from `llm_dashboard_design.yaml` |
| `member_claims_utilization_dashboard_v6` | `member_claims_metric_view_v6` | Filters; Utilization Summary; Payment Performance; Quality and Detail | `service_month`, `claim_type`, `benefit_category`, `adjudication_status` | counter, bar, line | LLM-assisted design from `llm_dashboard_design.yaml` |

`dashboard_dataset_validation.yaml` validated 2 datasets with 0 failed datasets. Both dashboard datasets query the claim Metric View using `MEASURE()` syntax. Enrollment KPIs were intentionally excluded from dashboards by `dashboard_design.yaml` because the deterministic dashboard runtime binds filters to the first shared dataset per dashboard, while enrollment measures reside in a separate Metric View with incompatible filter dimensions.

## 8. Genie Space / Genie Agent

Genie is enabled and successfully deployed.

| Field | Value |
|---|---|
| Title | `member_claims_analytics_genie_v6` |
| Space ID | `01f1b068bd7b1f8ca29f776466c0ea9b` |
| Warehouse ID | `2d8e531640ffa469` |
| Metric Views attached | 2 |
| Instruction character count | 3,606 |
| Sample questions | 16 |
| Example SQL statements | 16 |
| Benchmarks | 16 |
| Benchmark pass rate | 1.0 |
| Validation status | PASS |
| Configuration notebook | `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v6/genie_space/genie_space_configuration_member_claims` |

**Genie link**

- https://fevm-aw-serverless-stable.cloud.databricks.com/genie/rooms/01f1b068bd7b1f8ca29f776466c0ea9b

The Genie Space attaches:

- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v6`
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v6`

Validation confirms 16 example SQL statements executed with 0 failures, 16 benchmark questions passed, semantic coverage includes 23 measures and 24 dimensions, and persisted configuration status is PASS.

## 9. LLM-Assisted Design Summary

### Dashboard Design

Dashboard design used `databricks-gpt-5-5` and produced 2 dashboards. Each dashboard has 3 canvas pages plus a filter page, 4 filters, and at least 3 visualization types: counter, bar, and line. API readback validation confirms 25 total canvas widgets across the dashboards and no dashboard validation issues.

### Genie Space Design

Genie design used `databricks-gpt-5-5`. The design artifact contains markdown-style instructions with section headers, 16 sample questions, 16 example SQL statements, and 16 benchmark questions. Question coverage spans 8 analytical patterns: HEADLINE, TIME_TREND, DIMENSION_BREAKDOWN, FILTERED, RANKING, COMPARISON, MULTI_MEASURE, and RATIO. Example SQL validation status is PASS, and benchmark validation passed 16 of 16 questions.

## 10. Validation Summary

| Layer | Validation | Result | Artifact |
|---|---|---|---|
| Data Layer | Schema integrity | PASS | `data_layer_validation.yaml` |
| Data Layer | PK/FK integrity | PASS | `data_layer_validation.yaml` |
| Data Layer | Join stability / fanout | PASS | `data_layer_validation.yaml` |
| Metric Layer | Metric View smoke tests | PASS | `metric_views/metric_view_validation.yaml` |
| Metric Layer | KPI reconciliation | PASS for 18 implemented KPIs | `metric_views/metric_view_validation.yaml` |
| Metric Layer | Join fanout checks | PASS | `metric_views/schema_profile.yaml` and `metric_views/metric_view_validation.yaml` |
| Dashboards | Dataset SQL | PASS | `dashboards/dashboard_dataset_validation.yaml` |
| Dashboards | API readback and publication | PASS | `dashboards/dashboard_validation.yaml` |
| Genie | API readback configuration | PASS | `genie_space/member_claims_analytics_genie_v6_validation.yaml` |
| Genie | Example SQL execution | PASS | `genie_space/member_claims_analytics_genie_v6_validation.yaml` |
| Genie | Benchmarks | PASS | `genie_space/genie_benchmark_validation.yaml` |
| Terminal Audit | Cross-validation sweep | NOT AVAILABLE | `ground_truth_validation.yaml` is missing |

## 11. Known Limitations

| Limitation | Layer | Impact | Reason |
|---|---|---|---|
| Missing `ground_truth_validation.yaml` | Validation | Final documentation uses individual manifests rather than independent terminal audit | Cross-validation sweep artifact is not present in the output folder |
| MC-1 PMPM | Metric View | KPI not available as a Metric View measure, dashboard KPI, or Genie-supported KPI | Requires claim paid numerator and enrollment member-month denominator from different fact grains with no safe common Metric View grain |
| MC-2 Claims per 1,000 Members | Metric View | KPI not available as a Metric View measure, dashboard KPI, or Genie-supported KPI | Requires claim numerator and enrollment member-month denominator from different fact grains with no safe common Metric View grain |
| MC-3 Utilization Rate | Metric View | KPI not available as a Metric View measure, dashboard KPI, or Genie-supported KPI | Claim detail member key is VARCHAR and no semantic relationship exists to enrollment `member_sk` BIGINT |
| MC-4 High-Cost Member Count | Metric View | KPI documented with reference SQL only | Requires member-level pre-aggregation with HAVING threshold |
| W-1 Rolling 3-Month PMPM | Metric View | KPI documented with reference SQL only | Requires cross-source monthly pre-aggregation and trailing window logic |
| W-2 MoM Active Member Growth | Metric View | KPI documented with reference SQL only | Requires LAG window offset |
| D-10 Participating Provider Rate | Metric View | KPI not available as a Metric View measure, dashboard KPI, or Genie-supported KPI | No participating provider flag and no safe rendering provider key exists in `fact_claim_detail_v6` |
| Enrollment KPIs omitted from dashboards | Dashboard | M-1, M-2, M-3, E-1, and E-2 are available in Metric Views and Genie but not in the dashboards | Dashboard runtime uses a shared dataset/filter binding pattern; enrollment measures reside in a separate Metric View with incompatible filters |
| Polymorphic address relationship unresolved | Schema / Semantic Model | Address dimensions are not joined into generated Metric Views | `dim_address.entity_dimension_key` relationship is ambiguous in the ERD |

## 12. Usage

### Query Metric Views

Use Databricks SQL with `MEASURE()` syntax.

Example for a claim Metric View measure:

```sql
SELECT
  claim_type,
  MEASURE(`Total Paid Amount`) AS total_paid_amount
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v6`
GROUP BY ALL;
```

Example for an enrollment Metric View measure:

```sql
SELECT
  line_of_business,
  MEASURE(`Active Members`) AS active_members
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v6`
GROUP BY ALL;
```

### Dashboards

Open the published dashboards using the links in Section 7:

- `member_claims_kpis_dashboard_v6` is intended for executive claims cost, volume, quality, trend, and segment breakdown analysis.
- `member_claims_utilization_dashboard_v6` is intended for utilization intensity, payment efficiency, inpatient/outpatient paid trends, and quality/detail analysis.

### Genie

Open `member_claims_analytics_genie_v6` using the Genie link in Section 8. Ask questions that are supported by the attached Metric Views and validated sample-question inventory, such as:

- What is the total paid amount across all claims?
- How have total claims trended by service month?
- Show total paid amount by claim type.
- How many active enrolled members are there?
- Which member states have the most members?

Do not ask Genie to answer skipped or documentation-only KPIs such as PMPM, Claims per 1,000 Members, Utilization Rate, Rolling 3-Month PMPM, MoM Active Member Growth, High-Cost Member Count, or Participating Provider Rate from Metric View measures.

## 13. Troubleshooting

Overall status is `PARTIAL_SUCCESS`, so degraded or incomplete layers are listed below.

| Layer | Symptom | Root Cause | Resolution | Artifact |
|---|---|---|---|---|
| Validation | Independent final audit is absent | `ground_truth_validation.yaml` is missing | Re-run the upstream cross-validation sweep stage that produces `ground_truth_validation.yaml`; do not regenerate documentation as a substitute for that audit | `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v6/ground_truth_validation.yaml` |
| Metric Views | PMPM and Claims per 1,000 Members are unavailable as Metric View measures | Cross-fact claim/enrollment grain is unsafe | Implement a governed monthly aggregate outside the Metric View or add a safe semantic bridge before creating these measures | `metric_views/metric_view_validation.yaml` |
| Metric Views | Utilization Rate is unavailable | Claim-detail member key type and relationship do not match enrollment member key | Add or validate a safe member relationship between claim detail and enrollment/member entities | `metric_views/metric_view_validation.yaml` |
| Metric Views | High-Cost Member Count, Rolling 3-Month PMPM, and MoM Active Member Growth are not Metric View measures | They require HAVING or window logic not expressed by the generated Metric Views | Use the reference SQL in Section 6.1 as named SQL datasets or materialized views if needed | `metric_views/metric_view_plan.yaml` |
| Dashboards | Enrollment KPIs do not appear in dashboards | Dashboard shared dataset/filter runtime selected claim Metric View datasets only | Create a separate enrollment dashboard or extend the dashboard runtime to support multiple independently filtered Metric View datasets | `dashboards/dashboard_design.yaml` |

## 14. Generated Artifacts

Schema and data layer

- `erd_parsed.yaml`
- `semantic_model.yaml`
- `table_spec.yaml`
- `ddl_manifest.json`
- `synthetic_data_spec.yaml`
- `synthetic_data_manifest.json`
- `data_layer_validation.yaml`

Metric layer

- `metric_views/schema_profile.yaml`
- `metric_views/kpi_metric_mapping.yaml`
- `metric_views/metric_view_plan.yaml`
- `metric_views/metric_view_design.yaml`
- `metric_views/metric_view_spec.yaml`
- `metric_views/metric_view_manifest.json`
- `metric_views/metric_view_validation.yaml`

Dashboards

- `dashboards/llm_dashboard_design.yaml`
- `dashboards/dashboard_design.yaml`
- `dashboards/dashboard_dataset_validation.yaml`
- `dashboards/member_claims_kpis_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_utilization_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_kpis_dashboard_v6_validation.yaml`
- `dashboards/member_claims_utilization_dashboard_v6_validation.yaml`
- `dashboards/dashboard_validation.yaml`

Genie

- `genie_space/genie_semantic_inventory.yaml`
- `genie_space/llm_genie_design.yaml`
- `genie_space/member_claims_analytics_genie_v6_manifest.json`
- `genie_space/member_claims_analytics_genie_v6_validation.yaml`
- `genie_space/benchmark_results.yaml`
- `genie_space/genie_benchmark_validation.yaml`
- `genie_space/sample_queries_member_claims.sql`
- `genie_space/genie_space_configuration_member_claims`

Run state

- `step_handoff.yaml`
- `run_context.yaml`
- `documentation/readme.md`
- `run_manifest.json`

Missing expected terminal audit artifact

- `ground_truth_validation.yaml`

## 15. Configuration Reference

Primary configuration values used by this run:

| Key | Value |
|---|---|
| `domain.name` | `member_claims` |
| `domain.display_name` | `Member Claims` |
| `data_source.type` | `erd` |
| `catalog.source.catalog` | `aw_serverless_stable_catalog` |
| `catalog.source.schema` | `aibi_member_claims` |
| `catalog.target.catalog` | `aw_serverless_stable_catalog` |
| `catalog.target.schema` | `aibi_member_claims` |
| `assets.metric_views.strategy` | `auto` |
| `assets.metric_views.naming_prefix` | `member_claims` |
| `assets.dashboards` | `member_claims_kpis_dashboard`, `member_claims_utilization_dashboard` |
| `assets.genie.space_name` | `member_claims_analytics_genie` |
| `assets.genie.notebook_name` | `genie_space_configuration_member_claims` |
| `assets.sample_queries_file` | `sample_queries_member_claims.sql` |
| `config.version_suffix` | `_v6` |
| `llm.default_model` | `databricks-gpt-5-5` |
| `llm.vision_model` | `databricks-gpt-5-5` |

See `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/accelerator.yaml` for the full configuration.
