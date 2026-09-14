# Member Claims Accelerator Run Summary

Generated: 2026-09-14T13:35:00Z  
Version: `_v4`  
Overall run status: **PARTIAL_SUCCESS**

> Cross-validation sweep did not complete. `ground_truth_validation.yaml` is missing, so asset status below is based on individual step manifests and validation files, including API-readback artifacts where available, not an independent terminal audit.

## 1. Solution Overview

This accelerator run created a semantic analytics solution for **Member Claims** (`member_claims`) using **ERD** data-source mode with greenfield Unity Catalog table creation and synthetic data generation enabled.

The generated solution includes:

- 8 Unity Catalog tables in `aw_serverless_stable_catalog.aibi_member_claims`
- 3 validated Databricks Metric Views
- 19 KPIs implemented and validated through Metric View reconciliation
- 4 KPIs not available in Metric Views: 3 documented as `NOT_IMPLEMENTED` with reference SQL and 1 skipped for unsafe grain
- 2 AI/BI dashboards, both published and API-readback validated
- 1 Genie Space, configured and API-readback validated

Configuration and reproducibility metadata:

| Item | Value |
|---|---|
| Domain display name | Member Claims |
| Domain name | member_claims |
| Version suffix | `_v4` |
| Data-source mode | erd |
| Source catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| Target catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| LLM Model | `databricks-gpt-5-5` |
| Vision Model | `databricks-gpt-5-5` |
| Dashboard Design Model | `databricks-gpt-5-5` |
| Genie Design Model | `databricks-gpt-5-5` |
| SQL warehouse | `2d8e531640ffa469` |

## 2. Architecture / Asset Flow

```text
ERD Image
      ↓
Parsed ERD + Semantic Model
      ↓
Unity Catalog Tables + Synthetic Data
      ↓
Databricks Metric Views
      ↓
AI/BI Dashboards
      ↓
Genie Space
      ↓
Validation Artifacts + Documentation
```

## 3. Source Schema Summary

Source artifacts: `erd_parsed.yaml`, `semantic_model.yaml`, `schema_profile.yaml`.

The ERD-driven greenfield schema produced 8 tables. `schema_profile.yaml` reported no schema drift and no unresolved relationships for the profiled generated schema.

| Table | Role | Grain | Key Relationships / Notes |
|---|---|---|---|
| `dim_member_v4` | Dimension | One current member dimension record | Source for member geography Metric View; avoids unsafe one-to-many address joins. |
| `dim_address_v4` | Dimension | Address record | Generated as part of ERD-derived schema. |
| `dim_provider_v4` | Dimension | Provider record | Provider-related columns support claim-detail provider dimensions. |
| `dim_member_identifier_v4` | Dimension | Member identifier record | Generated as member identity support table. |
| `fact_member_enrollment_v4` | Fact | One member enrollment event or enrollment period | Source for enrollment Metric View. |
| `fact_claim_header_v4` | Fact | Claim header | Profile noted no ready KPI requiring a header-grain Metric View. |
| `fact_claim_detail_v4` | Fact | One claim detail line | Primary source for claim, payment, denial, clean-claim, provider, and utilization KPIs. |
| Additional generated ERD table | ERD-derived table | See `data_layer_validation.yaml` | Included in the 8 generated tables validated by the data layer. |

Important grains used by downstream assets:

- Claim detail line grain: `fact_claim_detail_v4`
- Enrollment event/period grain: `fact_member_enrollment_v4`
- Member dimension snapshot grain: `dim_member_v4`

## 4. Data Layer

Greenfield data generation ran because `data_source.type=erd` and `data_source.greenfield.enabled=true`.

Source artifacts: `ddl_manifest.json`, `synthetic_data_manifest.json`, `data_layer_validation.yaml`.

| Check | Result |
|---|---|
| Tables expected | 8 |
| Tables created | 8 |
| Missing tables | None reported |
| Data-layer validation overall status | PASS |
| Synthetic data generation | PASS per synthetic-data manifest |
| PK validation | PASS per data-layer validation |
| FK validation | PASS per data-layer validation |
| Cardinality / semantic constraint validation | PASS per data-layer validation |

Major analytical row counts visible in downstream validation:

| Table / Source | Validated row count |
|---|---:|
| `fact_claim_detail_v4` | 2,500 |
| `fact_member_enrollment_v4` | 800 |
| `dim_member_v4` | 300 |

No `GENERIC_FALLBACK` data-layer limitation was visible in the loaded validation summary.

## 5. Metric Views

Source artifacts: `metric_view_plan.yaml`, `metric_view_design.yaml`, `metric_view_spec.yaml`, `metric_view_manifest.json`, `metric_view_validation.yaml`.

Metric View deployment was verified by API readback. All 3 planned Metric Views were deployed and smoke-tested.

| Metric View | FQN | Source | Source Grain | Measures | Dimensions | Status |
|---|---|---|---|---:|---:|---|
| `member_claims_metric_view_v4` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v4` | `fact_claim_detail_v4` | One claim detail line | 23 | 12 | PASS |
| `member_claims_enrollment_metric_view_v4` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v4` | `fact_member_enrollment_v4` | One member enrollment event or enrollment period | 3 | 7 | PASS |
| `member_claims_member_metric_view_v4` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_member_metric_view_v4` | `dim_member_v4` | One current member dimension record | 1 | 8 | PASS |

The Metric View grouping follows grain separation:

- Claim-line KPIs use the claim detail fact table.
- Enrollment KPIs use the enrollment fact table.
- Member geography uses the member dimension to avoid unsafe joins.

Intermediate materialized views: none. `metric_view_validation.yaml` reported `intermediate_views: []` and zero joins in Metric Views.

## 6. KPI Catalog

Source artifacts: `kpi_metric_mapping.yaml`, `metric_view_plan.yaml`, `metric_view_validation.yaml`.

Only KPIs with `IMPLEMENTED_AND_VALIDATED` in `metric_view_validation.yaml` are documented as implemented.

| KPI | Metric View | Measure | Status | Notes |
|---|---|---|---|---|
| M-1 New Member Enrollment | `member_claims_enrollment_metric_view_v4` | New Member Enrollment | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| M-2 Members by Line of Business | `member_claims_enrollment_metric_view_v4` | Active Members | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| M-3 Members by Geography | `member_claims_member_metric_view_v4` | Active Members by Geography | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| C-1 Total Claims | `member_claims_metric_view_v4` | Total Claims | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| C-2 Total Claim Lines | `member_claims_metric_view_v4` | Total Claim Lines | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| C-3 Total Paid Amount | `member_claims_metric_view_v4` | Total Paid Amount | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| C-4 Average Paid per Claim | `member_claims_metric_view_v4` | Average Paid per Claim | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| MC-1 PMPM | `member_claims_metric_view_v4` | PMPM | IMPLEMENTED_AND_VALIDATED | Uses claim-observed member-month exposure. |
| MC-2 Claims per 1,000 Members | `member_claims_metric_view_v4` | Claims per 1,000 Members | IMPLEMENTED_AND_VALIDATED | Uses claim-observed member-month exposure. |
| MC-3 Utilization Rate | None | None | SKIPPED_UNSAFE_GRAIN | Unsafe cross-fact grain/key mismatch between claims member key and enrollment member key. |
| MC-4 High-Cost Member Count | None | None | NOT_IMPLEMENTED | Requires member-level pre-aggregation and HAVING. Reference SQL is documented below. |
| W-1 Rolling 3-Month PMPM | None | None | NOT_IMPLEMENTED | Requires rolling window over independently aggregated numerator and denominator. Reference SQL is documented below. |
| W-2 MoM Active Member Growth | None | None | NOT_IMPLEMENTED | Requires LAG/prior-period offset. Reference SQL is documented below. |
| ADD-1 Denial Rate | `member_claims_metric_view_v4` | Denial Rate | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| ADD-2 Clean Claim Rate | `member_claims_metric_view_v4` | Clean Claim Rate | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| ADD-3 Payment-to-Billed Ratio | `member_claims_metric_view_v4` | Payment-to-Billed Ratio | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| ADD-4 Payment-to-Allowed Ratio | `member_claims_metric_view_v4` | Payment-to-Allowed Ratio | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| ADD-5 Average Paid per Member | `member_claims_metric_view_v4` | Average Paid per Member | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| ADD-6 Claims per Member | `member_claims_metric_view_v4` | Claims per Member | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| ADD-7 Lines per Claim | `member_claims_metric_view_v4` | Lines per Claim | IMPLEMENTED_AND_VALIDATED | Baseline reconciled to Metric View. |
| ADD-8 Inpatient Paid Amount | `member_claims_metric_view_v4` | Inpatient Paid Amount | IMPLEMENTED_AND_VALIDATED | Baseline validation passed. |
| ADD-9 Outpatient Paid Amount | `member_claims_metric_view_v4` | Outpatient Paid Amount | IMPLEMENTED_AND_VALIDATED | Baseline validation passed. |
| ADD-10 Participating Provider Rate | `member_claims_metric_view_v4` | Participating Provider Rate | IMPLEMENTED_AND_VALIDATED | Baseline validation passed. |

Implemented KPI count: 19. Skipped or documentation-only KPI count: 4.

## 6.1 Not Implemented KPIs

The following KPIs could not be implemented as Metric View measures due to SQL semantics that Databricks Metric Views do not support. The validated SQL queries are provided for manual implementation if needed. These KPIs are not in dashboards or Genie.

### MC-4: High-Cost Member Count

**Reason:** Requires member-level pre-aggregation and HAVING threshold; metric view measure cannot filter on aggregated member spend within the same measure.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT COUNT(*) AS high_cost_member_count
FROM (
  SELECT clm_dtl_member_nbr_sk, SUM(clm_dtl_paid_amt) AS member_paid
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v4
  GROUP BY clm_dtl_member_nbr_sk
  HAVING SUM(clm_dtl_paid_amt) > 10000
) s;
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be a metric view measure because it requires HAVING over member-level pre-aggregation.

### W-1: Rolling 3-Month PMPM

**Reason:** Requires rolling window over independently aggregated numerator and denominator; implemented as dashboard/reference SQL rather than metric view measure for deterministic semantics.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT service_month,
       SUM(monthly_paid) OVER (ORDER BY service_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
       / NULLIF(SUM(member_months) OVER (ORDER BY service_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS rolling_3m_pmpm
FROM (
  SELECT DATE_TRUNC('MONTH', clm_dtl_specific_dos_date) AS service_month,
         SUM(clm_dtl_paid_amt) AS monthly_paid,
         COUNT(DISTINCT CONCAT(clm_dtl_member_nbr_sk, '-', DATE_FORMAT(clm_dtl_specific_dos_date, 'yyyy-MM'))) AS member_months
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v4
  GROUP BY DATE_TRUNC('MONTH', clm_dtl_specific_dos_date)
) m;
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be safely represented as a simple metric view measure because numerator and denominator require synchronized rolling windows.

### W-2: MoM Active Member Growth

**Reason:** Requires prior-period LAG over monthly active member counts; documented as reference SQL.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT service_month,
       (active_members - LAG(active_members) OVER (ORDER BY service_month))
       / NULLIF(LAG(active_members) OVER (ORDER BY service_month), 0) AS mom_active_member_growth
FROM (
  SELECT DATE_TRUNC('MONTH', mbr_enr_effective_date) AS service_month,
         COUNT(DISTINCT member_sk) AS active_members
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v4
  WHERE is_active = true
  GROUP BY DATE_TRUNC('MONTH', mbr_enr_effective_date)
) m;
```

**To implement manually:** Add as a named SQL dataset in the dashboard. Cannot be a metric view measure because it requires LAG/prior-period offset.

## 7. Dashboards

Source artifacts: `llm_dashboard_design.yaml`, `dashboard_design.yaml`, dashboard manifests, per-dashboard validation files, `dashboard_validation.yaml`.

Dashboard counts below come from API-readback validation and manifests.

| Dashboard | ID | Pages | Canvas Widgets | Filters | Published | Validation |
|---|---|---:|---:|---:|---|---|
| `member_claims_kpis_dashboard_v4` | `01f1b040713b1f69b0da0aee17ba5844` | 4 total: 1 filter + 3 canvas | 18 | 4 | true | PASS |
| `member_claims_utilization_dashboard_v4` | `01f1b040725e118b81603e745d00630d` | 4 total: 1 filter + 3 canvas | 18 | 4 | true | PASS |

### member_claims_kpis_dashboard_v4

- Source Metric Views: `member_claims_metric_view_v4`, `member_claims_enrollment_metric_view_v4`, `member_claims_member_metric_view_v4`
- Page structure: Filters; Financial Overview; Claims Analysis; Member Demographics
- Widget mix from design: counters, line charts, bar charts
- Visualization diversity: 3 distinct visualization types
- Filter dimensions: `service_month`, `claim_type`, `benefit_category`, `line_status`
- Design source: LLM-assisted dashboard design
- Workspace path from manifest: `/dashboardsv3/01f1b040713b1f69b0da0aee17ba5844`

### member_claims_utilization_dashboard_v4

- Source Metric View: `member_claims_metric_view_v4`
- Page structure: Filters; Utilization Patterns; Provider Insights; Operational Metrics
- Widget mix from design: counters, line charts, bar charts
- Visualization diversity: 3 distinct visualization types
- Filter dimensions: `service_month`, `claim_type`, `benefit_category`, `provider_participation`
- Design source: LLM-assisted dashboard design
- Workspace path from manifest: `/dashboardsv3/01f1b040725e118b81603e745d00630d`

`dashboard_validation.yaml` reported KPI coverage status PASS: 19 implemented and validated KPIs were dashboarded; MC-3, MC-4, W-1, and W-2 were excluded because they were skipped or not implemented.

## 8. Genie Space / Genie Agent

Source artifacts: `genie_semantic_inventory.yaml`, `llm_genie_design.yaml`, `member_claims_analytics_genie_v4_manifest.json`, `member_claims_analytics_genie_v4_validation.yaml`, `benchmark_results.yaml`, `genie_benchmark_validation.yaml`, `sample_queries_member_claims.sql`.

| Field | Value |
|---|---|
| Title | `member_claims_analytics_genie_v4` |
| Space ID | `01f1b044eab6158fba0f43ea8c9a54ca` |
| Warehouse ID | `2d8e531640ffa469` |
| Attached Metric Views | 3 |
| Instruction character count | 2,809 |
| Sample questions | 15 |
| Example SQL count | 15 |
| Example SQL executed | 15 |
| Example SQL failed | 0 |
| Benchmarks | 15 |
| Benchmark pass rate | 1.0 |
| Validation status | PASS |
| Design source | LLM-assisted Genie design |
| Configuration notebook | `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v4/genie_space/genie_space_configuration_member_claims` |
| Workspace path | `/genie/rooms/01f1b044eab6158fba0f43ea8c9a54ca` |

The Genie validation artifact reports API readback for create/get status and persisted configuration, including 15 sample questions, 15 example SQL statements, 15 benchmarks, 3 Metric Views, and 2,809 instruction characters.

## 9. LLM-Assisted Design Summary

### Dashboard Design

- Model used: `databricks-gpt-5-5`
- Dashboards designed: 2
- Canvas pages per dashboard: 3 each
- Widget density: 6 widgets per canvas page
- Visualization diversity per dashboard: 3 distinct visualization types based on the design artifacts
- Multi-page enforcement: passed based on API-readback validation showing 3 canvas pages per dashboard
- Key design decisions: executive KPI pages were separated from utilization/provider/operational pages; dashboards used only validated Metric View measures and excluded skipped or not implemented KPIs.

### Genie Space Design

- Model used: `databricks-gpt-5-5`
- Instruction quality: 2,809 characters, markdown format with sections such as Domain, Authoritative Metric Views, Measures, Dimensions, and Query Rules and Warnings
- Question pattern coverage: 8 of 8 analytical patterns in the design inventory: HEADLINE, TIME_TREND, DIMENSION_BREAKDOWN, FILTERED, RANKING, COMPARISON, MULTI_MEASURE, RATIO
- Example SQL validation: 15 passed out of 15 executed
- Benchmark questions: 15, validated with Metric View SQL ground truth

## 10. Validation Summary

| Layer | Validation | Result | Artifact |
|---|---|---|---|
| Data Layer | Schema integrity and generated table count | PASS | `data_layer_validation.yaml` |
| Data Layer | PK/FK/cardinality/semantic constraints | PASS | `data_layer_validation.yaml` |
| Metric Layer | Metric View deployment API readback | PASS | `metric_view_manifest.json` |
| Metric Layer | KPI reconciliation | PASS | `metric_view_validation.yaml` |
| Metric Layer | Join fanout checks | PASS | `metric_view_validation.yaml` |
| Dashboards | Dataset SQL and semantic status | PASS | `dashboard_dataset_validation.yaml` |
| Dashboards | API-readback publication, pages, filters, widgets | PASS | `dashboard_validation.yaml` |
| Genie | Space configuration API readback | PASS | `member_claims_analytics_genie_v4_validation.yaml` |
| Genie | Example SQL | PASS | `member_claims_analytics_genie_v4_validation.yaml` |
| Genie | Benchmarks | PASS | `genie_benchmark_validation.yaml` |
| Terminal audit | Cross-validation sweep | NOT RUN / MISSING | `ground_truth_validation.yaml` missing |

## 11. Known Limitations

| Limitation | Layer | Impact | Reason |
|---|---|---|---|
| `ground_truth_validation.yaml` missing | Validation | Overall status classified as PARTIAL_SUCCESS rather than PASS | Cross-validation sweep did not complete, so final independent audit is unavailable. |
| MC-3 Utilization Rate | Metric View | KPI not available in Metric Views, dashboards, or Genie | Unsafe cross-fact grain/key mismatch between claims member key and enrollment member key. |
| MC-4 High-Cost Member Count | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires member-level pre-aggregation and HAVING. Reference SQL is provided in this README. |
| W-1 Rolling 3-Month PMPM | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires rolling window over separately aggregated numerator and denominator. Reference SQL is provided in this README. |
| W-2 MoM Active Member Growth | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires LAG/prior-period offset. Reference SQL is provided in this README. |

## 12. Usage

### Query Metric Views

Use Metric View measures through `MEASURE()` syntax. Example using validated asset and measure names:

```sql
SELECT
  claim_type,
  MEASURE(`Total Paid Amount`) AS total_paid_amount,
  MEASURE(`Denial Rate`) AS denial_rate
FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v4
GROUP BY ALL
ORDER BY total_paid_amount DESC;
```

Enrollment example:

```sql
SELECT
  line_of_business,
  MEASURE(`New Member Enrollment`) AS new_member_enrollment,
  MEASURE(`Active Members`) AS active_members
FROM aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v4
GROUP BY ALL
ORDER BY new_member_enrollment DESC;
```

### Dashboards

Open the published dashboards by their dashboard IDs or workspace paths:

- `member_claims_kpis_dashboard_v4`: `/dashboardsv3/01f1b040713b1f69b0da0aee17ba5844`
- `member_claims_utilization_dashboard_v4`: `/dashboardsv3/01f1b040725e118b81603e745d00630d`

The KPI dashboard is intended for executive financial, claims, and member demographic monitoring. The utilization dashboard is intended for utilization, provider, and operational performance analysis.

### Genie

Open the Genie Space by its space ID or workspace path:

- `member_claims_analytics_genie_v4`: `/genie/rooms/01f1b044eab6158fba0f43ea8c9a54ca`

Ask questions grounded in the configured Metric Views. Representative sample questions from the generated inventory include:

- What is the total paid amount across all claims?
- Show monthly total paid amount and PMPM trends.
- What is the denial rate by claim type?
- Which benefit categories have the highest total paid amount?
- How many new members enrolled by line of business?
- Show active members by state.

## 13. Troubleshooting

Overall status is PARTIAL_SUCCESS because the terminal cross-validation sweep artifact is missing.

| Layer | Symptom | Root Cause | Resolution | Artifact |
|---|---|---|---|---|
| Validation | README and run manifest show PARTIAL_SUCCESS despite individual layers passing | `ground_truth_validation.yaml` is missing, so independent terminal audit status is unavailable | Re-run the Step 5.3 cross-validation sweep that produces `ground_truth_validation.yaml`; then regenerate documentation | `ground_truth_validation.yaml` |
| Metric Views | MC-3 is unavailable | Unsafe cross-fact grain/key mismatch | Create an upstream conformed member key or safe pre-aggregated source, then re-plan Metric Views | `metric_view_plan.yaml`, `metric_view_validation.yaml` |
| Metric Views | MC-4, W-1, W-2 are unavailable in Metric Views | Required SQL semantics are not expressible as Metric View measures | Use the reference SQL in Section 6.1 as named SQL datasets or implement upstream materializations | `metric_view_plan.yaml` |

## 14. Generated Artifacts

Only artifacts observed in this run are listed.

### Schema and Data Layer

- `erd_parsed.yaml`
- `semantic_model.yaml`
- `table_spec.yaml`
- `ddl_manifest.json`
- `synthetic_data_spec.yaml`
- `synthetic_data_manifest.json`
- `data_layer_validation.yaml`
- `step_handoff.yaml`

### Metrics

- `metric_views/schema_profile.yaml`
- `metric_views/kpi_metric_mapping.yaml`
- `metric_views/metric_view_plan.yaml`
- `metric_views/metric_view_design.yaml`
- `metric_views/metric_view_spec.yaml`
- `metric_views/metric_view_manifest.json`
- `metric_views/metric_view_validation.yaml`

### Dashboards

- `dashboards/llm_dashboard_design.yaml`
- `dashboards/dashboard_design.yaml`
- `dashboards/dashboard_dataset_validation.yaml`
- `dashboards/member_claims_kpis_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_utilization_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_kpis_dashboard_v4_validation.yaml`
- `dashboards/member_claims_utilization_dashboard_v4_validation.yaml`
- `dashboards/dashboard_validation.yaml`

### Genie

- `genie_space/genie_semantic_inventory.yaml`
- `genie_space/llm_genie_design.yaml`
- `genie_space/member_claims_analytics_genie_v4_manifest.json`
- `genie_space/member_claims_analytics_genie_v4_validation.yaml`
- `genie_space/benchmark_results.yaml`
- `genie_space/genie_benchmark_validation.yaml`
- `genie_space/sample_queries_member_claims.sql`
- `genie_space/genie_space_configuration_member_claims`

### Documentation and Run State

- `documentation/readme.md`
- `run_manifest.json`
- `run_context.yaml`

Missing expected terminal artifact:

- `ground_truth_validation.yaml`

## 15. Configuration Reference

Primary configuration used by this run:

| Configuration key | Value |
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
| `assets.dashboards` | `member_claims_kpis_dashboard`, `member_claims_utilization_dashboard` |
| `assets.genie.space_name` | `member_claims_analytics_genie` |
| `assets.genie.notebook_name` | `genie_space_configuration_member_claims` |
| `assets.sample_queries_file` | `sample_queries_member_claims.sql` |
| `config.version_suffix` | `_v4` |

See `accelerator.yaml` for the full configuration.
