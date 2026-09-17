# Member Claims Accelerator Run Summary

Generated: 2026-09-15T21:30:00Z  
Version: `_v7`  
Overall run status: **PARTIAL_SUCCESS**

Cross-validation sweep did not complete. Asset status below is based on individual step manifests, not an independent terminal audit.

## 1. Solution Overview

This accelerator run created a semantic analytics solution for **Member Claims** (`member_claims`) using `erd` data-source mode with greenfield synthetic data enabled. The solution includes:

- 8 Unity Catalog tables generated from the ERD-derived schema
- 3 Databricks Metric Views
- 2 published AI/BI dashboards
- 1 validated Genie Space
- 20 KPIs implemented and validated in Metric Views
- 3 KPIs documented as `NOT_IMPLEMENTED` with validated reference SQL

Configuration and reproducibility metadata:

| Item | Value |
|---|---|
| Domain display name | Member Claims |
| Resolved domain name | member_claims |
| Version suffix | `_v7` |
| Data-source mode | `erd` |
| Source catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| Target catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| Default LLM model | `databricks-gpt-5-5` |
| Vision model | `databricks-gpt-5-5` |
| Dashboard design model | `databricks-gpt-5-5` |
| Genie design model | `databricks-gpt-5-5` |
| SQL warehouse ID | `2d8e531640ffa469` |

The overall status is `PARTIAL_SUCCESS` because all available individual validation artifacts report `PASS`, but the mandatory terminal `ground_truth_validation.yaml` artifact is missing. The README therefore uses API-readback manifests and individual validation artifacts as the best available evidence.

## 2. Architecture / Asset Flow

```text
ERD Image
      ↓
erd_parsed.yaml / semantic_model.yaml
      ↓
Unity Catalog Tables with Synthetic Data
      ↓
Metric Views and Intermediate Views
      ↓
AI/BI Dashboards
      ↓
Genie Space
      ↓
Individual Validation Artifacts
      ↓
README and run_manifest.json
```

## 3. Source Schema Summary

The ERD was parsed into 8 tables and 6 relationships. One unresolved ERD item remains: the `dim_address` relationship to `dim_member` is conditional on `entity_type_key` indicating a member; the exact condition was unresolved but did not block synthetic-data generation.

| Table | Role | Grain | Key Relationships |
|---|---|---|---|
| `dim_member` | DIMENSION | One current member record per `member_sk` | Parent for address, identifiers, history, enrollment, and claim header |
| `dim_provider` | DIMENSION | One provider record or provider version per `provider_sk` | No resolved foreign keys in semantic model |
| `dim_address` | DIMENSION | One address record per `address_key` for a typed entity | `entity_dimension_key` to `dim_member.member_sk` |
| `dim_member_identifier` | DIMENSION | One identifier record per `mbr_identifier_sk` | `member_sk` to `dim_member.member_sk` |
| `dim_member_history` | SNAPSHOT | One historical member version per `mbr_history_sk` | `member_sk` to `dim_member.member_sk` |
| `fact_member_enrollment` | FACT | One member enrollment record per `enrollment_sk` | `member_sk` to `dim_member.member_sk` |
| `fact_claim_header` | FACT | One claim header per `clm_header_sk` | `clm_member_sk` to `dim_member.member_sk` |
| `fact_claim_detail` | FACT | One claim detail line per `clm_dtl_claim_id` and `clm_dtl_line_nbr` | `clm_dtl_claim_id` to `fact_claim_header.clm_claim_id` |

`schema_profile.yaml` also reports 8 profiled tables, 6 relationship checks with `PASS`, no schema drift, no unresolved live relationships, and a minimum join-key diversity of 500.

## 4. Data Layer

Greenfield data generation ran for this run. `data_layer_validation.yaml` reports `overall_status: PASS`.

| Table | Row Count | PK Validation |
|---|---:|---|
| `dim_member_v7` | 500 | 0 duplicates |
| `dim_provider_v7` | 250 | 0 duplicates |
| `dim_address_v7` | 500 | 0 duplicates |
| `dim_member_identifier_v7` | 750 | 0 duplicates |
| `dim_member_history_v7` | 1,000 | 0 duplicates |
| `fact_member_enrollment_v7` | 2,000 | 0 duplicates |
| `fact_claim_header_v7` | 2,000 | 0 duplicates |
| `fact_claim_detail_v7` | 5,000 | 0 duplicates |

Validation summary from `data_layer_validation.yaml`:

| Check | Result |
|---|---|
| Expected tables created | 8 of 8 |
| Primary-key checks | PASS, 8 tested, 0 failures |
| Foreign-key orphan checks | PASS, 6 tested, 0 orphan counts |
| Join stability / fanout | PASS, 6 tested, 0 fanout failures |
| Semantic constraints | PASS, 3 tested, 0 failures |
| Domain-value checks | PASS, 6 columns checked, 0 generic value failures |
| Generic fallback columns | None reported |

## 5. Metric Views

`metric_view_validation.yaml` reports `status: PASS`. Three Metric Views were created to keep facts at compatible grains: claim-line grain, enrollment grain enriched with member attributes, and monthly pre-aggregated cross-grain components.

| Metric View | FQN | Source | Source Grain | Measures | Dimensions | Status |
|---|---|---|---|---:|---:|---|
| `member_claims_metric_view_v7` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v7` | `fact_claim_detail_v7` | One claim detail line per claim ID and line number | 20 | 14 | PASS |
| `member_claims_enrollment_metric_view_v7` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v7` | `fact_member_enrollment_enriched_v7` | One member enrollment record enriched with current member attributes | 2 | 11 | PASS |
| `member_claims_monthly_metric_view_v7` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_monthly_metric_view_v7` | `member_claims_monthly_summary_v7` | One row per `service_month` with independently pre-aggregated claim and enrollment components | 8 | 1 | PASS |

Validated measure groups include claim volume, claim lines, paid/billed/allowed amounts, denial and clean-claim rates, member enrollment, PMPM, claims per 1,000 members, utilization rate, and participating-provider metrics.

Intermediate materialized views:

| Intermediate View | Source Tables | Join Type | Fanout Check |
|---|---|---|---|
| `fact_member_enrollment_enriched_v7` | `fact_member_enrollment_v7`, `dim_member_v7` | N:1 | PASS; 2,000 source rows and 2,000 joined rows |
| `member_claims_monthly_summary_v7` | `fact_claim_detail_v7`, `fact_member_enrollment_v7` | Monthly pre-aggregate alignment | PASS; 60 source rows and 60 joined rows |

## 6. KPI Catalog

KPI status is sourced from `metric_view_validation.yaml`. Only KPIs marked `IMPLEMENTED_AND_VALIDATED` are documented as implemented.

| KPI | Metric View | Measure | Status | Notes |
|---|---|---|---|---|
| M-1 New Member Enrollment | `member_claims_enrollment_metric_view_v7` | `New Member Enrollment` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500 |
| M-2 Members by Line of Business | `member_claims_enrollment_metric_view_v7` | `Active Members` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500 |
| M-3 Members by Geography | `member_claims_enrollment_metric_view_v7` | `Active Members` | IMPLEMENTED_AND_VALIDATED | Geography slices validated by `member_state` queryability |
| C-1 Total Claims | `member_claims_metric_view_v7` | `Total Claims` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 2,000 |
| C-2 Total Claim Lines | `member_claims_metric_view_v7` | `Total Claim Lines` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 5,000 |
| C-3 Total Paid Amount | `member_claims_metric_view_v7` | `Total Paid Amount` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 12,497,500.000000 |
| C-4 Average Paid per Claim | `member_claims_metric_view_v7` | `Average Paid per Claim` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 6,248.750000 |
| MC-1 PMPM | `member_claims_monthly_metric_view_v7` | `PMPM` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 6,248.750000 |
| MC-2 Claims per 1,000 Members | `member_claims_monthly_metric_view_v7` | `Claims per 1000 Members` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 2,500.000000 |
| MC-3 Utilization Rate | `member_claims_monthly_metric_view_v7` | `Utilization Rate` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 1.500000 |
| MC-4 High-Cost Member Count | None | None | NOT_IMPLEMENTED | Requires member-level HAVING threshold pre-aggregation |
| W-1 Rolling 3-Month PMPM | None | None | NOT_IMPLEMENTED | Requires rolling window calculation over cross-grain components |
| W-2 MoM Active Member Growth | None | None | NOT_IMPLEMENTED | Requires LAG window function over monthly active member counts |
| ADD-1 Denial Rate | `member_claims_metric_view_v7` | `Denial Rate` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 0.286400 |
| ADD-2 Clean Claim Rate | `member_claims_metric_view_v7` | `Clean Claim Rate` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-3 Payment-to-Billed Ratio | `member_claims_metric_view_v7` | `Payment-to-Billed Ratio` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-4 Payment-to-Allowed Ratio | `member_claims_metric_view_v7` | `Payment-to-Allowed Ratio` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-5 Average Paid per Member | `member_claims_metric_view_v7` | `Average Paid per Member` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-6 Claims per Member | `member_claims_metric_view_v7` | `Claims per Member` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-7 Lines per Claim | `member_claims_metric_view_v7` | `Lines per Claim` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-8 Inpatient Paid Amount | `member_claims_metric_view_v7` | `Inpatient Paid Amount` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-9 Outpatient Paid Amount | `member_claims_metric_view_v7` | `Outpatient Paid Amount` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |
| ADD-10 Participating Provider Rate | `member_claims_metric_view_v7` | `Participating Provider Rate` | IMPLEMENTED_AND_VALIDATED | Validated by smoke and source expression |

## 6.1 Not Implemented KPIs

The following KPIs could not be implemented as metric view measures due to SQL semantics that Databricks Metric Views do not support for this run. The validated SQL queries are provided below for manual implementation if needed. These KPIs are not included in dashboards or Genie.

### MC-4: High-Cost Member Count

**Reason:** Requires member-level pre-aggregation and HAVING threshold filtering before distinct member count; not represented as a single safe metric view measure on the raw claim line grain.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT COUNT(*) AS high_cost_member_count
FROM (
  SELECT h.clm_member_sk, SUM(d.clm_dtl_paid_amt) AS member_paid
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v7 d
  JOIN aw_serverless_stable_catalog.aibi_member_claims.fact_claim_header_v7 h ON d.clm_dtl_claim_id = h.clm_claim_id
  GROUP BY h.clm_member_sk
  HAVING SUM(d.clm_dtl_paid_amt) > 10000
) x
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be a metric view measure due to required member-level HAVING pre-aggregation.

### W-1: Rolling 3-Month PMPM

**Reason:** Requires rolling window calculation over separately aggregated paid and member-month components; excluded from metric view measures for this run.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
WITH claim_months AS (
  SELECT DATE_TRUNC('MONTH', clm_dtl_specific_dos_date) AS service_month, SUM(clm_dtl_paid_amt) AS paid_amount
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v7
  GROUP BY DATE_TRUNC('MONTH', clm_dtl_specific_dos_date)
), enrollment_months AS (
  SELECT DATE_TRUNC('MONTH', mbr_enr_effective_date) AS service_month, COUNT(DISTINCT CONCAT(CAST(member_sk AS STRING), '-', CAST(DATE_TRUNC('MONTH', mbr_enr_effective_date) AS STRING))) AS member_months
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v7
  GROUP BY DATE_TRUNC('MONTH', mbr_enr_effective_date)
)
SELECT c.service_month,
       SUM(c.paid_amount) OVER (ORDER BY c.service_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) / NULLIF(SUM(e.member_months) OVER (ORDER BY c.service_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS rolling_3m_pmpm
FROM claim_months c
JOIN enrollment_months e ON c.service_month = e.service_month
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be represented here due to windowed cross-grain numerator/denominator logic.

### W-2: MoM Active Member Growth

**Reason:** Requires LAG window function over monthly active member counts.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
WITH enrollment_months AS (
  SELECT DATE_TRUNC('MONTH', mbr_enr_effective_date) AS service_month, COUNT(DISTINCT member_sk) AS active_members
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v7
  GROUP BY DATE_TRUNC('MONTH', mbr_enr_effective_date)
)
SELECT service_month, (active_members - LAG(active_members) OVER (ORDER BY service_month)) / NULLIF(LAG(active_members) OVER (ORDER BY service_month), 0) AS mom_growth
FROM enrollment_months
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be represented here due to required LAG window function.

## 7. Dashboards

Dashboard deployment state is sourced from API-readback dashboard manifests and validation files. Both dashboards have `published: true` in their manifests.

| Dashboard | ID | Pages | Widgets | Filters | Published | Validation |
|---|---|---:|---:|---:|---|---|
| `member_claims_kpis_dashboard_v7` | `01f1b14ace041a4b9cb0b619813277a1` | 4 total; 3 canvas; 1 filter | 18 | 4 | true | PASS |
| `member_claims_utilization_dashboard_v7` | `01f1b14acf381ccaa5016309073a475d` | 4 total; 3 canvas; 1 filter | 16 | 4 | true | PASS |

### Dashboard Detail

| Dashboard | Source Metric Views | Page Structure | Widget Types | Filter Dimensions | Design Source |
|---|---|---|---|---|---|
| `member_claims_kpis_dashboard_v7` | `member_claims_metric_view_v7` | Filters; Executive Summary; Financial Performance; Quality and Provider Performance | 10 counters, 5 bar charts, 3 line charts; 3 distinct visualization types | `Service Date`, `claim_type`, `line_status`, `benefit_category` | LLM-assisted from `llm_dashboard_design.yaml` |
| `member_claims_utilization_dashboard_v7` | `member_claims_enrollment_metric_view_v7`, `member_claims_monthly_metric_view_v7` | Filters; Enrollment Summary; Utilization Trends; Member Exposure and Claims | 9 counters, 2 bar charts, 5 line charts; 3 distinct visualization types | `Service Date`, `line_of_business`, `member_state`, `member_sex` | LLM-assisted from `llm_dashboard_design.yaml` |

`dashboard_validation.yaml` reports 2 validated dashboards, 2 published dashboards, 6 canvas pages, 2 filter pages, 34 total canvas widgets, 8 total filters, and `dataset_sql_status: PASS`.

### Deployed Asset Links

- Dashboard `member_claims_kpis_dashboard_v7`: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b14ace041a4b9cb0b619813277a1/published
- Dashboard `member_claims_utilization_dashboard_v7`: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b14acf381ccaa5016309073a475d/published

## 8. Genie Space / Genie Agent

Genie is enabled and the deployed Genie Space is validated by API readback.

| Item | Value |
|---|---|
| Title | `member_claims_analytics_genie_v7` |
| Space ID | `01f1b14d814c148799a1993aa90c416c` |
| Warehouse ID | `2d8e531640ffa469` |
| Attached Metric Views | 3 |
| Instruction quality | 3,581 characters; markdown; 5 sections |
| Sample questions | 16 |
| Analytical pattern coverage | 8 of 8 patterns: HEADLINE, TIME_TREND, DIMENSION_BREAKDOWN, FILTERED, RANKING, COMPARISON, MULTI_MEASURE, RATIO |
| Example SQL | 16 total; 16 executed; 0 failed |
| Benchmarks | 16 total; 16 passed; pass rate 1.0 |
| Design source | LLM-assisted from `llm_genie_design.yaml` |
| Configuration notebook path | `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v7/genie_space/genie_space_configuration_member_claims` |
| Validation status | PASS |

Attached Metric Views:

- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v7`
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v7`
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_monthly_metric_view_v7`

Genie Space link: https://fevm-aw-serverless-stable.cloud.databricks.com/genie/rooms/01f1b14d814c148799a1993aa90c416c

## 9. LLM-Assisted Design Summary

### Dashboard Design

Dashboard design used model `databricks-gpt-5-5`. `llm_dashboard_design.yaml` contains 2 designed dashboards. Each dashboard has 3 canvas pages plus a filter page. Each dashboard uses at least 3 visualization types: counters, bar charts, and line charts. The deployed validation artifacts show multi-page deployment passed with 3 actual canvas pages per dashboard.

Key design decisions documented in the design artifacts:

- Claim-line KPIs were grouped into executive, financial, and quality/provider pages.
- Enrollment and monthly utilization KPIs were separated from claim-line KPIs because they rely on different Metric Views and grains.
- Global filters were scoped to dimensions present in each dashboard's datasets.

### Genie Space Design

Genie design used model `databricks-gpt-5-5`. `llm_genie_design.yaml` provides markdown instructions, Metric View selection guidance, query rules, sample questions, example SQL, and benchmark questions. API readback validation confirms 3,581 instruction characters, 16 sample questions, 16 example SQL statements, and 16 benchmarks persisted. Benchmark validation reports 16 of 16 passed.

## 10. Validation Summary

| Layer | Validation | Result | Artifact |
|---|---|---|---|
| Data Layer | Schema integrity and table creation | PASS | `data_layer_validation.yaml` |
| Data Layer | PK/FK integrity | PASS | `data_layer_validation.yaml` |
| Data Layer | Join fanout / cardinality stability | PASS | `data_layer_validation.yaml` |
| Data Layer | Domain values and semantic constraints | PASS | `data_layer_validation.yaml` |
| Metric Layer | Metric View deployment readback | PASS | `metric_views/metric_view_manifest.json` |
| Metric Layer | KPI reconciliation | PASS | `metric_views/metric_view_validation.yaml` |
| Metric Layer | Intermediate view fanout checks | PASS | `metric_views/metric_view_validation.yaml` |
| Dashboards | Dataset SQL | PASS | `dashboards/dashboard_dataset_validation.yaml` |
| Dashboards | API readback, pages, widgets, filters, publish | PASS | `dashboards/dashboard_validation.yaml` |
| Genie | API readback and persisted configuration | PASS | `genie_space/member_claims_analytics_genie_v7_validation.yaml` |
| Genie | Example SQL and benchmarks | PASS | `genie_space/genie_benchmark_validation.yaml` |
| Terminal Audit | Cross-validation sweep | MISSING | `ground_truth_validation.yaml` not present |

## 11. Known Limitations

| Limitation | Layer | Impact | Reason |
|---|---|---|---|
| Missing terminal cross-validation sweep | Validation | Overall run classified as `PARTIAL_SUCCESS` instead of `PASS` | `ground_truth_validation.yaml` is not present; status uses individual manifests and validations |
| Address-to-member relationship condition unresolved | Source Schema | Exact `dim_address` entity filtering condition is not documented in the semantic model | ERD parse notes conditional relationship on `entity_type_key` but not the exact condition |
| MC-4 High-Cost Member Count | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires member-level HAVING threshold pre-aggregation |
| W-1 Rolling 3-Month PMPM | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires rolling window calculation over cross-grain components |
| W-2 MoM Active Member Growth | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires LAG window function over monthly active member counts |

No generic fallback columns were reported by `data_layer_validation.yaml`. No failed Genie benchmark questions were reported.

## 12. Usage

### Query Metric Views

Use Databricks Metric View `MEASURE()` syntax when querying measures.

```sql
SELECT
  claim_type,
  MEASURE(`Total Paid Amount`) AS total_paid_amount
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v7`
GROUP BY ALL;
```

Additional validated examples are available in `genie_space/sample_queries_member_claims.sql`, including:

```sql
SELECT service_month, MEASURE(`PMPM`) AS pmpm
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_monthly_metric_view_v7`
GROUP BY ALL
ORDER BY service_month;
```

### Dashboards

Open the published dashboards listed in Section 7:

- `member_claims_kpis_dashboard_v7` for claims financial performance, denial/clean-claim metrics, and provider participation analysis.
- `member_claims_utilization_dashboard_v7` for enrollment, PMPM, claims per 1,000 members, member-month exposure, and utilization analysis.

Dashboard IDs and links are documented in Section 7 and in each dashboard manifest.

### Genie

Open `member_claims_analytics_genie_v7` and ask questions grounded in the attached Metric Views. Representative validated sample questions include:

- What is the total number of claims?
- Show total paid amount and total claims by claim type.
- Compare denial rate across claim types.
- Show active members by line of business.
- What is the monthly PMPM trend?
- Show claims per 1000 members and utilization rate by service month.

Unsupported KPIs `MC-4`, `W-1`, and `W-2` are intentionally excluded from Genie.

## 13. Troubleshooting

This section is included because the overall run status is `PARTIAL_SUCCESS`.

| Layer | Symptom | Root Cause | Resolution | Artifact |
|---|---|---|---|---|
| Validation | Consumers cannot rely on an independent terminal audit artifact | `ground_truth_validation.yaml` is missing | Run the Step 5.3 cross-validation sweep in the pipeline orchestration and regenerate documentation | Expected `ground_truth_validation.yaml` |
| Metric Views | High-cost member count, rolling PMPM, or MoM growth is unavailable as a semantic measure | These KPIs require HAVING or window functions outside this run's Metric View implementation | Use the reference SQL in Section 6.1 as dashboard SQL datasets or manual analyses | `metric_views/metric_view_plan.yaml` |
| Source Schema | Address analysis may require extra filtering by entity type | ERD relationship to `dim_member` is conditional on `entity_type_key` and the exact predicate is unresolved | Confirm address entity semantics before using `dim_address` outside generated relationship checks | `erd_parsed.yaml` |

## 14. Generated Artifacts

Schema and data layer:

- `erd_parsed.yaml`
- `semantic_model.yaml`
- `table_spec.yaml`
- `ddl_manifest.json`
- `synthetic_data_spec.yaml`
- `synthetic_data_manifest.json`
- `data_layer_validation.yaml`

Metric layer:

- `metric_views/schema_profile.yaml`
- `metric_views/kpi_metric_mapping.yaml`
- `metric_views/metric_view_plan.yaml`
- `metric_views/metric_view_design.yaml`
- `metric_views/metric_view_spec.yaml`
- `metric_views/metric_view_manifest.json`
- `metric_views/metric_view_validation.yaml`

Dashboards:

- `dashboards/llm_dashboard_design.yaml`
- `dashboards/dashboard_design.yaml`
- `dashboards/dashboard_dataset_validation.yaml`
- `dashboards/pre_deploy_check.yaml`
- `dashboards/member_claims_kpis_dashboard_v7_validation.yaml`
- `dashboards/member_claims_utilization_dashboard_v7_validation.yaml`
- `dashboards/member_claims_kpis_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_utilization_dashboard_dashboard_manifest.json`
- `dashboards/dashboard_validation.yaml`

Genie:

- `genie_space/genie_semantic_inventory.yaml`
- `genie_space/llm_genie_design.yaml`
- `genie_space/sample_queries_member_claims.sql`
- `genie_space/benchmark_results.yaml`
- `genie_space/genie_benchmark_validation.yaml`
- `genie_space/member_claims_analytics_genie_v7_validation.yaml`
- `genie_space/member_claims_analytics_genie_v7_manifest.json`
- `genie_space/genie_space_configuration_member_claims`

Run state and documentation:

- `run_context.yaml`
- `documentation/readme.md`
- `run_manifest.json`

Missing expected terminal artifact:

- `ground_truth_validation.yaml`

## 15. Configuration Reference

Primary run configuration from `accelerator.yaml`:

| Key | Value |
|---|---|
| `domain.name` | `member_claims` |
| `domain.display_name` | `Member Claims` |
| `data_source.type` | `erd` |
| `data_source.greenfield.enabled` | `true` |
| `data_source.greenfield.synthetic_data` | `true` |
| `catalog.source.catalog` | `aw_serverless_stable_catalog` |
| `catalog.source.schema` | `aibi_member_claims` |
| `catalog.target.catalog` | `aw_serverless_stable_catalog` |
| `catalog.target.schema` | `aibi_member_claims` |
| `assets.metric_views.strategy` | `auto` |
| `assets.metric_views.naming_prefix` | `member_claims` |
| `assets.dashboards` | `member_claims_kpis_dashboard`, `member_claims_utilization_dashboard` |
| `assets.genie.space_name` | `member_claims_analytics_genie` |
| `assets.sample_queries_file` | `sample_queries_member_claims.sql` |
| `config.version_suffix` | `_v7` |

Refer to `kpi_domains/member_claims/accelerator.yaml` for the full configuration.