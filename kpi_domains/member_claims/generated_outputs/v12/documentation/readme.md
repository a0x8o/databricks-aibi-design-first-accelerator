# Member Claims Accelerator Run Summary

Generated: 2026-09-17T20:35:00Z  
Version: `_v12`  
Overall run status: **PARTIAL_SUCCESS**

The deployed data, metric, dashboard, and Genie assets validated successfully in their individual step artifacts. The run is classified as **PARTIAL_SUCCESS** because `ground_truth_validation.yaml` is missing, so the independent terminal cross-validation sweep did not complete. Asset status below is based on individual step manifests and validation artifacts, not an independent terminal audit.

## 1. Solution Overview

This accelerator run created a semantic analytics solution for **Member Claims** using `erd` data-source mode with greenfield synthetic data generation enabled.

| Item | Value |
|---|---|
| Domain display name | Member Claims |
| Resolved domain name | `member_claims` |
| Version suffix | `_v12` |
| Data-source mode | `erd` |
| Source catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| Target catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| Overall status | `PARTIAL_SUCCESS` |
| LLM model | `databricks-gpt-5-5` |
| Vision model | `databricks-gpt-5-5` |
| Dashboard design model | `databricks-gpt-5-5` |
| Genie design model | `databricks-gpt-5-5` |

The solution includes 8 Unity Catalog tables, 3 Metric Views, 2 published dashboards, and 1 validated Genie Space. Sixteen KPIs were implemented and validated in Metric Views. Two KPIs were documented as not implemented with reference SQL, and five KPIs were skipped due to unsafe grain, unsupported metric-view semantics, or unresolved relationships.

## 2. Architecture / Asset Flow

```text
ERD image
      ↓
Parsed ERD and semantic model
      ↓
Unity Catalog greenfield tables with synthetic data
      ↓
Metric Views by compatible source grain
      ↓
AI/BI dashboards
      ↓
Genie Space
      ↓
Validation artifacts and run documentation
```

The Metric View layer is split by grain: claim detail line, member enrollment, and current member. Dashboards and Genie attach only to validated Metric Views and exclude KPIs that were not validated in the Metric View layer.

## 3. Source Schema Summary

Source artifacts: `erd_parsed.yaml`, `semantic_model.yaml`, and `schema_profile.yaml`.

| Table | Role | Grain | Key Relationships |
|---|---|---|---|
| `dim_member_v12` | Dimension | One row represents a current member dimension record | Parent for address, identifiers, history, enrollment, and claim header |
| `dim_provider_v12` | Dimension | One row represents a provider dimension version or provider record | No confirmed claim/provider relationship used |
| `dim_address_v12` | Dimension | One row represents an address for an entity and address type | `entity_dimension_key` to `dim_member.member_sk` |
| `dim_member_identifier_v12` | Dimension | One row represents one identifier value for a member | `member_sk` to `dim_member.member_sk` |
| `dim_member_history_v12` | Snapshot | One row represents a historical member dimension version | `member_sk` to `dim_member.member_sk` |
| `fact_member_enrollment_v12` | Fact | One row represents a member enrollment record or coverage event | `member_sk` to `dim_member.member_sk` |
| `fact_claim_header_v12` | Fact | One row represents a claim header | `clm_member_sk` to `dim_member.member_sk` |
| `fact_claim_detail_v12` | Fact | One row represents a claim detail service line | `clm_dtl_claim_id` to `fact_claim_header.clm_claim_id` |

Schema profile summary:

- Tables profiled: 8
- Relationships validated in profile: 6
- Schema drift: none recorded
- Unresolved relationships in `schema_profile.yaml`: none
- ERD/semantic unresolved item: `dim_provider.provider_address_sk` may reference `dim_address.address_key`, but no visible relationship line was confirmed and it was not used in the semantic model.

## 4. Data Layer

Greenfield data generation ran and validated successfully.

| Table | FQN | Rows | Status |
|---|---|---:|---|
| `dim_member_v12` | `aw_serverless_stable_catalog.aibi_member_claims.dim_member_v12` | 500 | PASS |
| `dim_provider_v12` | `aw_serverless_stable_catalog.aibi_member_claims.dim_provider_v12` | 300 | PASS |
| `dim_address_v12` | `aw_serverless_stable_catalog.aibi_member_claims.dim_address_v12` | 600 | PASS |
| `dim_member_identifier_v12` | `aw_serverless_stable_catalog.aibi_member_claims.dim_member_identifier_v12` | 900 | PASS |
| `dim_member_history_v12` | `aw_serverless_stable_catalog.aibi_member_claims.dim_member_history_v12` | 1,000 | PASS |
| `fact_member_enrollment_v12` | `aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v12` | 3,000 | PASS |
| `fact_claim_header_v12` | `aw_serverless_stable_catalog.aibi_member_claims.fact_claim_header_v12` | 2,500 | PASS |
| `fact_claim_detail_v12` | `aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v12` | 9,000 | PASS |

Validation from `data_layer_validation.yaml`:

- Overall data-layer status: PASS
- Expected tables: 8
- Created tables: 8
- Primary-key tests: 8 tested, 0 failures
- Foreign-key tests: 6 tested, 0 orphan failures
- Join-stability tests: 6 tested, 0 fanout failures
- Semantic constraints: 2 tested, 0 failures
- Generic fallback columns: none

## 5. Metric Views

Metric View status is sourced from `metric_view_manifest.json` and `metric_view_validation.yaml`.

| Metric View | FQN | Source | Source Grain | Measures | Dimensions | Status |
|---|---|---|---|---:|---:|---|
| `member_claims_metric_view_v12` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v12` | `fact_claim_detail_v12` | One row represents a claim detail service line | 18 | 10 | PASS |
| `member_claims_enrollment_metric_view_v12` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v12` | `fact_member_enrollment_v12` | One row represents a member enrollment record or coverage event | 3 | 6 | PASS |
| `member_claims_member_metric_view_v12` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_member_metric_view_v12` | `dim_member_v12` | One row represents a current member dimension record | 2 | 9 | PASS |

No intermediate materialized views were created. All three Metric Views are direct-source metric views with zero joins included at runtime.

## 6. KPI Catalog

KPI implementation status is sourced from `metric_view_validation.yaml`. A KPI is listed as implemented only when its status is `IMPLEMENTED_AND_VALIDATED`.

| KPI | Metric View | Measure | Status | Notes |
|---|---|---|---|---|
| M-1 New Member Enrollment | `member_claims_enrollment_metric_view_v12` | `New Member Enrollment` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500 |
| M-2 Members by Line of Business | `member_claims_enrollment_metric_view_v12` | `Active Members` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500 |
| M-3 Members by Geography | `member_claims_member_metric_view_v12` | `Members by Geography` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 500 |
| C-1 Total Claims | `member_claims_metric_view_v12` | `Total Claims` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 2,500 |
| C-2 Total Claim Lines | `member_claims_metric_view_v12` | `Total Claim Lines` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 9,000 |
| C-3 Total Paid Amount | `member_claims_metric_view_v12` | `Total Paid Amount` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 40,495,500.00 |
| C-4 Average Paid per Claim | `member_claims_metric_view_v12` | `Average Paid per Claim` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 16,198.2 |
| MC-1 PMPM | Not applicable | Not applicable | SKIPPED_UNSAFE_GRAIN | Cross-grain paid numerator and enrollment denominator lack a safe common Metric View source |
| MC-2 Claims per 1,000 Members | Not applicable | Not applicable | SKIPPED_UNSAFE_GRAIN | Cross-grain claim numerator and enrollment denominator lack a safe common Metric View source |
| MC-3 Utilization Rate | Not applicable | Not applicable | SKIPPED_UNSAFE_GRAIN | Cross-grain utilization denominator and incompatible claim/enrollment member keys |
| MC-4 High-Cost Member Count | Not applicable | Not applicable | NOT_IMPLEMENTED | Requires HAVING after member-level pre-aggregation; reference SQL is documented below |
| W-1 Rolling 3-Month PMPM | Not applicable | Not applicable | SKIPPED_UNSUPPORTED_METRIC_VIEW_FEATURE | Rolling PMPM requires unsafe cross-grain numerator and denominator |
| W-2 MoM Active Member Growth | Not applicable | Not applicable | NOT_IMPLEMENTED | Requires LAG window function over monthly aggregate active members; reference SQL is documented below |
| ADD-1 Denial Rate | `member_claims_metric_view_v12` | `Denial Rate` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 0.0 |
| ADD-2 Clean Claim Rate | `member_claims_metric_view_v12` | `Clean Claim Rate` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 0.7864444444444444 |
| ADD-3 Payment-to-Billed Ratio | `member_claims_metric_view_v12` | `Payment-to-Billed Ratio` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 1.0 |
| ADD-4 Payment-to-Allowed Ratio | `member_claims_metric_view_v12` | `Payment-to-Allowed Ratio` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 1.0 |
| ADD-5 Average Paid per Member | `member_claims_metric_view_v12` | `Average Paid per Member` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 80,991.0 |
| ADD-6 Claims per Member | `member_claims_metric_view_v12` | `Claims per Member` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 5.0 |
| ADD-7 Lines per Claim | `member_claims_metric_view_v12` | `Lines per Claim` | IMPLEMENTED_AND_VALIDATED | Baseline and Metric View result both 3.6 |
| ADD-8 Inpatient Paid Amount | `member_claims_metric_view_v12` | `Inpatient Paid Amount` | IMPLEMENTED_AND_VALIDATED | Validation status PASS |
| ADD-9 Outpatient Paid Amount | `member_claims_metric_view_v12` | `Outpatient Paid Amount` | IMPLEMENTED_AND_VALIDATED | Validation status PASS |
| ADD-10 Participating Provider Rate | Not applicable | Not applicable | SKIPPED_UNRESOLVED_RELATIONSHIP | No confirmed provider relationship from claim source to `dim_provider` |

Implemented KPIs: 16. Not implemented with reference SQL: 2. Skipped without reference SQL: 5.

## 6.1 Not Implemented KPIs

The following KPIs could not be implemented as Metric View measures due to SQL semantics that are not expressible in this Metric View design. The validated SQL queries are provided for manual implementation if needed.

### MC-4: High-Cost Member Count

**Reason:** Requires pre-aggregation to member spend and HAVING threshold; Metric View measure syntax cannot express a member-level HAVING threshold over line-level spend safely.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT COUNT(*) AS high_cost_member_count
FROM (
  SELECT clm_dtl_member_nbr_sk, SUM(clm_dtl_paid_amt) AS member_paid
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v12
  GROUP BY clm_dtl_member_nbr_sk
  HAVING SUM(clm_dtl_paid_amt) > 10000
) h
```

**To implement manually:** Add as a named SQL dataset in the dashboard. It cannot be a Metric View measure because the KPI requires pre-aggregating spend by member and filtering with HAVING.

### W-2: MoM Active Member Growth

**Reason:** Requires LAG window function over monthly active member counts; documented as SQL because offset windows are not implemented in this Metric View design.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT service_month, active_members, prior_month_members,
       (active_members - prior_month_members) / NULLIF(prior_month_members, 0) AS mom_growth
FROM (
  SELECT service_month, active_members,
         LAG(active_members) OVER (ORDER BY service_month) AS prior_month_members
  FROM (
    SELECT date_trunc('MONTH', mbr_enr_effective_date) AS service_month,
           COUNT(DISTINCT member_sk) AS active_members
    FROM aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v12
    GROUP BY date_trunc('MONTH', mbr_enr_effective_date)
  ) m
) g
```

**To implement manually:** Add as a named SQL dataset in the dashboard. It cannot be a standard Metric View measure because it requires LAG over monthly aggregates.

## 7. Dashboards

Dashboard deployment status is sourced from API-readback dashboard manifests and validation files.

| Dashboard | ID | Pages | Canvas Widgets | Filters | Published | Validation |
|---|---|---:|---:|---:|---|---|
| `member_claims_kpis_dashboard_v12` | `01f1b2d63dc9100e8940ef1d240ebc48` | 4 total, 3 canvas, 1 filter | 21 | 4 | true | PASS |
| `member_claims_utilization_dashboard_v12` | `01f1b2d63ee91078840d3692c9aeb7cf` | 4 total, 3 canvas, 1 filter | 17 | 4 | true | PASS |

### Dashboard Details

#### `member_claims_kpis_dashboard_v12`

- Source Metric View: `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v12`
- Pages: Filters, Executive Summary, Quality and Adjudication, Utilization and Cost Detail
- Filter dimensions: `service_month`, `claim_type`, `line_status`, `adjudication_status`
- Dataset count from API readback: 1
- Canvas widget count from API readback: 21
- Visualization types in design: text, counter, bar, line
- Design source: LLM-assisted design from `llm_dashboard_design.yaml`
- Published link: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b2d63dc9100e8940ef1d240ebc48/published

#### `member_claims_utilization_dashboard_v12`

- Source Metric Views: `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v12`, `aw_serverless_stable_catalog.aibi_member_claims.member_claims_member_metric_view_v12`
- Pages: Filters, Enrollment Summary, Enrollment Trend and Plan Detail, Member Geography and Demographics
- Filter dimensions: `service_month`, `line_of_business`, `enrollment_status`, `plan_id`
- Dataset count from API readback: 2
- Canvas widget count from API readback: 17
- Visualization types in design: text, counter, bar, line
- Design source: LLM-assisted design from `llm_dashboard_design.yaml`
- Published link: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b2d63ee91078840d3692c9aeb7cf/published

`dashboard_validation.yaml` reports PASS for create, get, publish, dataset, widget, and filter checks for both dashboards.

## 8. Genie Space / Genie Agent

Genie deployment status is sourced from API-readback manifest and validation artifacts.

| Item | Value |
|---|---|
| Title | `member_claims_analytics_genie_v12` |
| Space ID | `01f1b2d846f41d2f8dbf8b7187dab740` |
| Warehouse ID | `2d8e531640ffa469` |
| Attached Metric Views | 3 |
| Instruction characters | 3,177 |
| Instruction format | Markdown with headers |
| Sample questions | 20 |
| Analytical patterns covered | 8 of 8 |
| Example SQL count | 20 |
| Example SQL validation | 20 passed, 0 failed |
| Benchmark questions | 20 |
| Benchmark pass rate | 100% |
| Configuration notebook | `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v12/genie_space/genie_space_configuration_member_claims` |
| Validation status | PASS |
| Genie link | https://fevm-aw-serverless-stable.cloud.databricks.com/genie/rooms/01f1b2d846f41d2f8dbf8b7187dab740 |

Attached Metric Views:

- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v12`
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v12`
- `aw_serverless_stable_catalog.aibi_member_claims.member_claims_member_metric_view_v12`

The Genie configuration was designed by the LLM reasoning model from `llm_genie_design.yaml` and validated by API readback in `member_claims_analytics_genie_v12_validation.yaml`.

## 9. LLM-Assisted Design Summary

### Dashboard Design

- Model used: `databricks-gpt-5-5`
- Dashboards designed: 2
- Canvas pages per dashboard: 3 each
- Visualization diversity: 4 designed types per dashboard: text, counter, bar, line
- Multi-page enforcement: PASS in `dashboard_design.yaml` page-count validation
- Design decisions: claim-detail KPIs were grouped into financial, quality/adjudication, and utilization/cost pages; enrollment and member-dimension KPIs were grouped into enrollment summary, plan/trend, and geography/demographics pages.

### Genie Space Design

- Model used: `databricks-gpt-5-5`
- Instruction character count: 3,177
- Instruction format: markdown with domain, metric catalog, measure rules, dimension/time rules, and query guidance sections
- Question pattern coverage: 8 of 8 patterns covered
- Example SQL validation: 20 passed out of 20
- Benchmark questions: 20, all validated against authoritative Metric View SQL

## 10. Validation Summary

Because `ground_truth_validation.yaml` is missing, this table uses individual validation artifacts and manifests.

| Layer | Validation | Result | Artifact |
|---|---|---|---|
| Data Layer | Schema/table creation | PASS | `data_layer_validation.yaml` |
| Data Layer | PK/FK integrity | PASS | `data_layer_validation.yaml` |
| Data Layer | Join stability/fanout | PASS | `data_layer_validation.yaml` |
| Metric Layer | Metric View deployment and smoke tests | PASS | `metric_view_manifest.json` |
| Metric Layer | KPI reconciliation | PASS | `metric_view_validation.yaml` |
| Metric Layer | Join fanout checks | PASS | `metric_view_validation.yaml` |
| Dashboards | Dataset SQL | PASS | `dashboard_dataset_validation.yaml` |
| Dashboards | API readback, filters, pages, widgets, publish | PASS | `dashboard_validation.yaml` |
| Genie | API readback and persisted configuration | PASS | `member_claims_analytics_genie_v12_validation.yaml` |
| Genie | Example SQL and benchmarks | PASS | `genie_benchmark_validation.yaml`, `benchmark_results.yaml` |
| Terminal Audit | Cross-validation sweep | MISSING | `ground_truth_validation.yaml` is not present |

## 11. Known Limitations

| Limitation | Layer | Impact | Reason |
|---|---|---|---|
| `ground_truth_validation.yaml` missing | Validation | Overall run classified as PARTIAL_SUCCESS | Cross-validation sweep did not complete; status is based on individual manifests and validations |
| MC-1 PMPM | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires claim paid numerator and enrollment member-month denominator at a safe common grain |
| MC-2 Claims per 1,000 Members | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires claim numerator and enrollment denominator at a safe common month grain |
| MC-3 Utilization Rate | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires distinct claim members and active enrolled members across incompatible grains and member-key types |
| W-1 Rolling 3-Month PMPM | Metric View | KPI not available in Metric Views, dashboards, or Genie | Requires rolling numerator and denominator across claim and enrollment grains |
| ADD-10 Participating Provider Rate | Metric View | KPI not available in Metric Views, dashboards, or Genie | No confirmed provider relationship from claims to `dim_provider` |
| MC-4 High-Cost Member Count | Metric View | Not in Metric Views, dashboards, or Genie; reference SQL provided | Requires member-level pre-aggregation and HAVING threshold |
| W-2 MoM Active Member Growth | Metric View | Not in Metric Views, dashboards, or Genie; reference SQL provided | Requires LAG over monthly aggregate active members |
| Provider-address relationship unresolved | Semantic Model | Provider geography and provider participation analytics were not used | `semantic_model.yaml` records the relationship as unconfirmed |

## 12. Usage

### Query Metric Views

Use `MEASURE()` syntax when querying Metric Views.

```sql
SELECT
  claim_type,
  MEASURE(`Total Paid Amount`) AS total_paid_amount
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v12`
GROUP BY ALL;
```

Additional validated examples are available in `genie_space/sample_queries_member_claims.sql`, including monthly paid trends, denial rate, clean claim rate, enrollment trends, and member geography.

### Dashboards

Open the published dashboards:

- KPI dashboard for claim volume, payment, denial, clean-claim, and utilization/cost detail: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b2d63dc9100e8940ef1d240ebc48/published
- Utilization dashboard for enrollment and member geography/demographics: https://fevm-aw-serverless-stable.cloud.databricks.com/dashboardsv3/01f1b2d63ee91078840d3692c9aeb7cf/published

Dashboard IDs are also recorded in the dashboard manifests under `generated_outputs/v12/dashboards/`.

### Genie

Open the Genie Space: https://fevm-aw-serverless-stable.cloud.databricks.com/genie/rooms/01f1b2d846f41d2f8dbf8b7187dab740

Use questions aligned to the configured semantic model. Representative sample questions from the generated inventory include:

- What is the total paid amount across all claims?
- How has total paid amount trended by service month?
- Which claim types have the highest number of total claims?
- Show active members and new member enrollment by line of business.
- Which states have the highest member counts?

## 13. Troubleshooting

This section is included because the overall status is `PARTIAL_SUCCESS`.

| Layer | Symptom | Root Cause | Resolution | Artifact |
|---|---|---|---|---|
| Validation | Consumers cannot confirm an independent terminal audit for all assets | `ground_truth_validation.yaml` is missing | Re-run the cross-validation sweep stage in the pipeline orchestration and regenerate documentation | `ground_truth_validation.yaml` |
| Metric Views | PMPM, utilization rate, rolling PMPM, participating provider rate, high-cost member count, and MoM growth are not available as Metric View measures | Metric View validation classified these KPIs as skipped or not implemented | Use documented reference SQL for MC-4 and W-2 if manual dashboard datasets are needed; design a common-grain pre-aggregation for cross-grain KPIs | `metric_view_validation.yaml`, `metric_view_plan.yaml` |
| Dashboards and Genie | Unsupported KPIs do not appear | Dashboards and Genie intentionally exclude KPIs not implemented and validated in the Metric View layer | Review KPI Catalog and Not Implemented sections before extending dashboards or Genie | `dashboard_validation.yaml`, `member_claims_analytics_genie_v12_validation.yaml` |

## 14. Generated Artifacts

Only files observed in this run are listed.

### Schema and Data

- `erd_parsed.yaml`
- `semantic_model.yaml`
- `table_spec.yaml`
- `ddl_manifest.json`
- `synthetic_data_spec.yaml`
- `synthetic_data_manifest.json`
- `data_layer_validation.yaml`

### Metric Views

- `metric_views/schema_profile.yaml`
- `metric_views/kpi_metric_mapping.yaml`
- `metric_views/metric_view_plan.yaml`
- `metric_views/metric_view_design.yaml`
- `metric_views/metric_view_spec.yaml`
- `metric_views/metric_view_manifest.json`
- `metric_views/metric_view_validation.yaml`
- `metric_views/metric_view_deployment.ipynb`

### Dashboards

- `dashboards/llm_dashboard_design.yaml`
- `dashboards/dashboard_design.yaml`
- `dashboards/dashboard_dataset_validation.yaml`
- `dashboards/dashboard_deployment.ipynb`
- `dashboards/member_claims_kpis_dashboard_v12.lvdash.json`
- `dashboards/member_claims_utilization_dashboard_v12.lvdash.json`
- `dashboards/member_claims_kpis_dashboard_v12_validation.yaml`
- `dashboards/member_claims_utilization_dashboard_v12_validation.yaml`
- `dashboards/member_claims_kpis_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_utilization_dashboard_dashboard_manifest.json`
- `dashboards/dashboard_validation.yaml`

### Genie

- `genie_space/genie_semantic_inventory.yaml`
- `genie_space/llm_genie_design.yaml`
- `genie_space/sample_queries_member_claims.sql`
- `genie_space/genie_space_configuration_member_claims`
- `genie_space/member_claims_analytics_genie_v12_manifest.json`
- `genie_space/genie_space_manifest.json`
- `genie_space/member_claims_analytics_genie_v12_validation.yaml`
- `genie_space/genie_benchmark_validation.yaml`
- `genie_space/benchmark_results.yaml`
- `genie_space/genie_space_deployment_note.md`

### Documentation and State

- `documentation/readme.md`
- `run_manifest.json`
- `run_context.yaml`
- `step_handoff.yaml`

## 15. Configuration Reference

Primary configuration values from `accelerator.yaml`:

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
| `assets.dashboards` | `member_claims_kpis_dashboard`, `member_claims_utilization_dashboard` |
| `assets.genie.space_name` | `member_claims_analytics_genie` |
| `assets.sample_queries_file` | `sample_queries_member_claims.sql` |
| `config.version_suffix` | `_v12` |

Refer to `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/accelerator.yaml` for the full configuration.
