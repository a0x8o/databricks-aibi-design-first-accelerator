# Member Claims Accelerator Run Summary

Generated: 2026-09-18T00:00:00Z  
Version: `_v13`  
Domain: `member_claims`  
Overall run status: `PARTIAL_SUCCESS`

> Cross-validation sweep did not complete. Asset status below is based on individual step manifests and API-readback validation artifacts, not an independent terminal audit. The expected `ground_truth_validation.yaml` artifact was not present in the run output folder.

## 1. Solution Overview

This accelerator run created a semantic analytics solution for **Member Claims** using `erd` data-source mode with greenfield Unity Catalog table creation and synthetic data generation enabled. The solution includes 8 generated Unity Catalog tables, 2 Metric Views, 2 published AI/BI dashboards, and 1 configured Genie Space.

Configuration and reproducibility metadata:

| Item | Value |
|---|---|
| Domain display name | Member Claims |
| Resolved domain name | `member_claims` |
| Version suffix | `_v13` |
| Data-source mode | `erd` |
| Source catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| Target catalog/schema | `aw_serverless_stable_catalog.aibi_member_claims` |
| LLM model | `databricks-gpt-5-5` |
| Vision model | `databricks-gpt-5-5` |
| Dashboard design model | `databricks-gpt-5-5` |
| Genie design model | `databricks-gpt-5-5` |
| SQL warehouse | `2d8e531640ffa469` |

Status rationale: core generated assets have individual PASS/API-readback validations, but the terminal `ground_truth_validation.yaml` cross-validation artifact is missing. The run is therefore documented as `PARTIAL_SUCCESS` rather than `PASS`.

## 2. Architecture / Asset Flow

```text
ERD Image
      ↓
Parsed Schema and Semantic Model
      ↓
Unity Catalog Tables with Synthetic Data
      ↓
Databricks Metric Views
      ↓
AI/BI Dashboards
      ↓
Genie Space
      ↓
Validation Artifacts and Run Documentation
```

The ERD was parsed into schema artifacts, table DDL and synthetic data were generated, Metric Views were created over the generated fact tables, dashboards were deployed against Metric View datasets, and Genie was configured with the validated Metric Views.

## 3. Source Schema Summary

Source artifacts used: `erd_parsed.yaml`, `semantic_model.yaml`, `table_spec.yaml`, and `schema_profile.yaml`.

The ERD-derived semantic layer contains 8 generated tables. The data-layer validation artifact reports 8 expected tables and 8 created tables. The major analytical grains used by downstream assets are claim detail line grain and member enrollment coverage-record grain.

| Table or table group | Role | Grain | Key relationships used downstream |
|---|---|---|---|
| `fact_claim_detail_v13` | Fact | One row per claim detail service line | Links to claim header by claim identifier; supports claim counts, line counts, paid/billed/allowed amounts, denial, clean-claim, and utilization analytics |
| `fact_claim_header_v13` | Fact/Header | One row per claim header | Connects claim-level member and provider context to claim detail records |
| `fact_member_enrollment_v13` | Fact | One row per member enrollment coverage record for a plan/group/product period or event | Supports enrollment, active member, line-of-business, geography, and demographic analytics |
| `dim_member_v13` | Dimension | One row per current member record | Member context for claims and enrollment analytics |
| `dim_provider_v13` | Dimension | One row per provider | Provider specialty/type/network participation context for claims analytics |
| `dim_address_v13` | Dimension | One row per address | Member/provider geography context |
| `dim_member_identifier_v13` | Dimension | One row per member identifier record | Member identifier context |
| Other generated supporting table from ERD | Dimension/supporting table | ERD-derived support grain | Included in DDL/data validation counts; no separate Metric View was created directly over it |

ERD parsing noted conceptual/inferred relationships in the source diagram. No blocking unresolved ERD element is recorded in the data-layer validation artifact.

Live-schema profiling was also produced under `metric_views/schema_profile.yaml` for the generated Unity Catalog schema. The profile identifies the generated source tables and classifies the claim detail and enrollment fact tables used for Metric Views.

## 4. Data Layer

Greenfield data generation ran for this run.

Authoritative artifacts:

- `ddl_manifest.json` with `validation_source: api_readback`
- `synthetic_data_manifest.json`
- `data_layer_validation.yaml`

Data-layer validation summary:

| Check | Result | Evidence |
|---|---|---|
| Tables expected | 8 | `data_layer_validation.yaml` |
| Tables created | 8 | `data_layer_validation.yaml` |
| Schema reconciliation | PASS | `data_layer_validation.yaml` |
| Primary keys | PASS; 8 tables tested | `data_layer_validation.yaml` |
| Foreign keys | PASS | `data_layer_validation.yaml` |
| Cardinality validation | PASS | `data_layer_validation.yaml` |
| Synthetic data generation | PASS; 8 tables generated | `synthetic_data_manifest.json` |

Major generated analytical sources:

| Table | Downstream use | Validated row evidence |
|---|---|---|
| `fact_claim_detail_v13` | Source for `member_claims_metric_view_v13` | Genie semantic inventory reports the claims Metric View row count as 10,000 |
| `fact_member_enrollment_v13` | Source for `member_claims_enrollment_metric_view_v13` | Genie semantic inventory reports the enrollment Metric View row count as 2,000 |

No data-layer validation failure was observed in the loaded artifacts.

## 5. Metric Views

Authoritative artifacts: `metric_view_plan.yaml`, `metric_view_design.yaml`, `metric_view_manifest.json`, and `metric_view_validation.yaml`.

Two Metric Views were generated because the implemented KPIs use incompatible fact grains: claim-line grain for claim cost and claim operations metrics, and member-enrollment record grain for enrollment and member distribution metrics.

| Metric View | FQN | Source | Source Grain | Validated Measures | Major Dimensions | Status |
|---|---|---|---|---|---|---|
| `member_claims_metric_view_v13` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v13` | `fact_claim_detail_v13` | One row represents one claim detail line for a claim | `Total Claims`, `Total Claim Lines`, `Total Paid Amount`, `Average Paid per Claim` plus derived measures including denial, clean-claim, payment-ratio, inpatient/outpatient paid, and line-density measures | `Service Date`, `Service Month`, `Claim Type`, `Benefit Category`, `Benefit Level`, `Line Status`, `Clean Claim Indicator`, provider and procedure dimensions | PASS |
| `member_claims_enrollment_metric_view_v13` | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v13` | `fact_member_enrollment_v13` | One row represents one member enrollment coverage record for a plan/group/product period or event | `New Member Enrollment`, `Active Members`, `Enrollment Records`, `Terminated Members` | `Service Date`, `Service Month`, `Line Of Business`, `Plan Id`, `Enrollment Status`, `Enrollment Group`, `Member State`, demographic dimensions | PASS |

No intermediate materialized views were required. `metric_view_plan.yaml` records `intermediate_view: null` for both generated Metric Views.

## 6. KPI Catalog

Sources: `kpi_metric_mapping.yaml`, `metric_view_plan.yaml`, and `metric_view_validation.yaml`. KPIs are marked implemented only when Metric View validation confirms `IMPLEMENTED_AND_VALIDATED`.

| KPI | Metric View | Measure | Status | Notes |
|---|---|---|---|---|
| M-1 New Member Enrollment | `member_claims_enrollment_metric_view_v13` | `New Member Enrollment` | IMPLEMENTED_AND_VALIDATED | Distinct members entering coverage by enrollment effective date |
| M-2 Members by Line of Business | `member_claims_enrollment_metric_view_v13` | `Active Members` | IMPLEMENTED_AND_VALIDATED | Active member distribution by LOB and plan |
| M-3 Members by Geography | `member_claims_enrollment_metric_view_v13` | `Active Members` | IMPLEMENTED_AND_VALIDATED | Active members by state and LOB |
| C-1 Total Claims | `member_claims_metric_view_v13` | `Total Claims` | IMPLEMENTED_AND_VALIDATED | Distinct claim count |
| C-2 Total Claim Lines | `member_claims_metric_view_v13` | `Total Claim Lines` | IMPLEMENTED_AND_VALIDATED | Claim service line count |
| C-3 Total Paid Amount | `member_claims_metric_view_v13` | `Total Paid Amount` | IMPLEMENTED_AND_VALIDATED | Sum of paid amount |
| C-4 Average Paid per Claim | `member_claims_metric_view_v13` | `Average Paid per Claim` | IMPLEMENTED_AND_VALIDATED | Paid amount divided by distinct claim count |
| MC-1 PMPM | Not applicable | Not applicable | SKIPPED_UNSAFE_GRAIN | Requires paid claims and member-month exposure at common monthly grain; no physical co-grained member-month exposure table exists |
| MC-2 Claims per 1,000 Members | Not applicable | Not applicable | SKIPPED_UNSAFE_GRAIN | Requires member-month denominator at common grain with claim counts; no physical co-grained denominator source exists |
| MC-3 Utilization Rate | Not applicable | Not applicable | SKIPPED_UNSAFE_GRAIN | Requires active enrolled denominator and members-with-claims numerator at common monthly grain; no pre-aggregated utilization population source exists |
| MC-4 High-Cost Member Count | Documentation only | Documentation only | NOT_IMPLEMENTED | Requires member-level pre-aggregation and HAVING threshold; not expressible as a grain-safe Metric View measure over claim-line source |
| W-2 MoM Active Member Growth | Documentation only | Documentation only | NOT_IMPLEMENTED | Requires LAG window offset over monthly active member counts; documented as SQL because Metric View implementation is avoided for this window KPI |

KPI counts:

| Category | Count |
|---|---:|
| Total KPIs in plan | 12 |
| Implemented and validated | 7 |
| Not implemented with reference SQL | 2 |
| Skipped due to unsafe grain | 3 |

## 6.1 Not Implemented KPIs

The following KPIs could not be implemented as Metric View measures due to SQL semantics that Databricks Metric Views do not support or due to required pre-aggregation semantics. The validated SQL queries are provided below for manual implementation if needed. These KPIs are not included in dashboards or Genie spaces.

### MC-4: High-Cost Member Count

**Reason:** Requires pre-aggregation to member level and HAVING threshold; not expressible as a grain-safe metric view measure over claim-line source.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT member_key, total_paid_amount
FROM (
  SELECT h.clm_member_sk AS member_key, SUM(d.clm_dtl_paid_amt) AS total_paid_amount
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_claim_detail_v13 d
  JOIN aw_serverless_stable_catalog.aibi_member_claims.fact_claim_header_v13 h ON d.clm_dtl_claim_id = h.clm_claim_id
  GROUP BY h.clm_member_sk
  HAVING SUM(d.clm_dtl_paid_amt) > 10000
) q
```

**To implement manually:** Add as a named SQL dataset in a dashboard or create a pre-aggregated member-spend table. Cannot be a Metric View measure due to member-level HAVING threshold.

### W-2: MoM Active Member Growth

**Reason:** Requires LAG window offset over monthly active member counts; documented as SQL because Metric View implementation is avoided for this window KPI.

**Status:** NOT_IMPLEMENTED — documentation only

```sql
SELECT service_month, active_members, prior_month_members,
       (active_members - prior_month_members) / NULLIF(prior_month_members, 0) AS mom_active_member_growth
FROM (
  SELECT date_trunc('MONTH', mbr_enr_effective_date) AS service_month,
         COUNT(DISTINCT member_sk) AS active_members,
         LAG(COUNT(DISTINCT member_sk)) OVER (ORDER BY date_trunc('MONTH', mbr_enr_effective_date)) AS prior_month_members
  FROM aw_serverless_stable_catalog.aibi_member_claims.fact_member_enrollment_v13
  GROUP BY date_trunc('MONTH', mbr_enr_effective_date)
) m
```

**To implement manually:** Add as a named SQL dataset using LAG in the dashboard. Cannot be represented as a simple Metric View measure without window offset semantics.

## 7. Dashboards

Authoritative sources: dashboard manifests and dashboard API-readback validation files under `dashboards/`.

Both configured dashboards have manifests and API-readback validation artifacts with `published: true` and `status: PASS`.

| Dashboard | ID | Pages | Widgets | Filters | Published | Validation |
|---|---|---:|---:|---:|---|---|
| `member_claims_kpis_dashboard_v13` | `01f1b2fec53a1f179d94457d25e6f3d1` | 4 total: Filters, Financial Overview, Claims Analysis, Member Demographics | 22 canvas widgets | 4 | true | PASS |
| `member_claims_utilization_dashboard_v13` | `01f1b2fec68618f7b0d06e6c075561e1` | 4 total: Filters, Utilization Patterns, Provider Insights, Operational Metrics | 22 canvas widgets | 4 | true | PASS |

Dashboard details:

| Dashboard | Source Metric Views | Design source | Dataset count | Filter dimensions and widget-type breakdown |
|---|---|---|---:|---|
| `member_claims_kpis_dashboard_v13` | Claims and enrollment Metric Views | LLM-assisted design from `llm_dashboard_design.yaml`; API readback validates pages, datasets, filters, and canvas widget counts | 2 | API-readback validation reports 4 filters. Exact filter dimension names and widget-type counts are in dashboard design artifacts but not included in API-readback validation counts, so they are not treated as independently audited here. |
| `member_claims_utilization_dashboard_v13` | Claims Metric View | LLM-assisted design from `llm_dashboard_design.yaml`; API readback validates pages, datasets, filters, and canvas widget counts | 1 | API-readback validation reports 4 filters. Exact filter dimension names and widget-type counts are in dashboard design artifacts but not included in API-readback validation counts, so they are not treated as independently audited here. |

Deployed asset links are recorded as relative Databricks paths because `workspace.host` was not loaded as a generated run artifact:

- `member_claims_kpis_dashboard_v13`: `/dashboardsv3/01f1b2fec53a1f179d94457d25e6f3d1/published`
- `member_claims_utilization_dashboard_v13`: `/dashboardsv3/01f1b2fec68618f7b0d06e6c075561e1/published`

Dashboard design quality from API-readback validation:

| Dashboard | Canvas pages | Canvas widgets | Widget density | Multi-page requirement |
|---|---:|---:|---|---|
| `member_claims_kpis_dashboard_v13` | 3 | 22 | 7, 8, and 7 widgets across the three canvas pages | PASS |
| `member_claims_utilization_dashboard_v13` | 3 | 22 | 7, 7, and 8 widgets across the three canvas pages | PASS |

## 8. Genie Space / Genie Agent

Genie is enabled and deployed for this run.

Authoritative sources: `genie_semantic_inventory.yaml`, `member_claims_analytics_genie_v13_manifest.json`, `genie_manifest.json`, `member_claims_analytics_genie_v13_validation.yaml`, `benchmark_results.yaml`, and `genie_benchmark_validation.yaml`.

| Item | Value |
|---|---|
| Title | `member_claims_analytics_genie_v13` |
| Space ID | `01f1b31272b01bef962dd25299c857ae` |
| Warehouse ID | `2d8e531640ffa469` |
| Attached Metric Views | `aw_serverless_stable_catalog.aibi_member_claims.member_claims_metric_view_v13`; `aw_serverless_stable_catalog.aibi_member_claims.member_claims_enrollment_metric_view_v13` |
| Instruction character count | 3,030 |
| Instruction format | Markdown with section headers in `llm_genie_design.yaml` |
| Sample questions | 15 |
| Example SQL count | 15 |
| Example SQL validation | 15 executed, 0 failed |
| Benchmark questions | 15 |
| Benchmark pass rate | 15/15 passed, 1.0 pass rate |
| Semantic coverage | 22 measures, 24 dimensions, 7 KPIs |
| Configuration notebook | `/Workspace/Users/arun.wagle@databricks.com/databricks-aibi-design-first-accelerator/kpi_domains/member_claims/generated_outputs/v13/genie_space/genie_space_configuration_member_claims` |
| Validation status | PASS |

Relative Genie link:

- `/genie/rooms/01f1b31272b01bef962dd25299c857ae`

Representative sample questions from the generated inventory:

- What are the total claims, claim lines, and paid amount?
- How has total paid amount trended by service month?
- Which claim types have the highest paid amount?
- Show denial rate by benefit category.
- How many active members are there by line of business?
- Which member states have the most active members?

## 9. LLM-Assisted Design Summary

LLM-assisted design artifacts exist for both dashboards and Genie.

### Dashboard Design

| Item | Value |
|---|---|
| Model | `databricks-gpt-5-5` |
| Dashboards designed | 2 |
| Published dashboards validated by API readback | 2 |
| Canvas pages per dashboard | 3 each |
| Total canvas widgets per dashboard | 22 each |
| Multi-page enforcement | PASS by API-readback page counts |
| Design decisions evidenced by page structure | KPI dashboard separates Financial Overview, Claims Analysis, and Member Demographics; utilization dashboard separates Utilization Patterns, Provider Insights, and Operational Metrics |

The `llm_dashboard_design.yaml` artifact exists and was used as the design source. API-readback validation confirms deployment structure, pages, datasets, filters, and total canvas widgets. Visualization type diversity is not separately counted in the API-readback validation artifact, so this README does not claim an independently audited distinct visualization-type count.

### Genie Space Design

| Item | Value |
|---|---|
| Model | `databricks-gpt-5-5` |
| Instruction character count | 3,030 |
| Instruction format | Markdown sections including Domain, Authoritative Metric Views, Measures, Dimensions, and Query Rules and Warnings |
| Question pattern coverage | 8 analytical patterns represented in the design inventory: HEADLINE, TIME_TREND, DIMENSION_BREAKDOWN, FILTERED, RANKING, COMPARISON, MULTI_MEASURE, RATIO |
| Example SQL validation | 15 passed out of 15 |
| Benchmark validation | 15 passed out of 15 |
| Benchmark answer format | SQL ground-truth execution results |

## 10. Validation Summary

| Layer | Validation | Result | Artifact |
|---|---|---|---|
| Data Layer | Schema reconciliation | PASS | `data_layer_validation.yaml` |
| Data Layer | Primary-key integrity | PASS | `data_layer_validation.yaml` |
| Data Layer | Foreign-key/cardinality readiness | PASS | `data_layer_validation.yaml` |
| Metric Layer | Metric View deployment/API readback | PASS | `metric_view_manifest.json` |
| Metric Layer | KPI reconciliation | PASS for 7 implemented KPIs; 5 not delivered as Metric View measures | `metric_view_validation.yaml`, `metric_view_plan.yaml` |
| Dashboards | Dataset SQL validation | PASS | `dashboard_dataset_validation.yaml` |
| Dashboards | API-readback deployment validation | PASS for both dashboards | `member_claims_kpis_dashboard_v13_validation.yaml`, `member_claims_utilization_dashboard_v13_validation.yaml` |
| Genie | Space API-readback validation | PASS | `member_claims_analytics_genie_v13_validation.yaml` |
| Genie | Example SQL validation | PASS; 15 executed and 0 failed | `member_claims_analytics_genie_v13_validation.yaml` |
| Genie | Benchmark validation | PASS; 15/15 passed | `benchmark_results.yaml`, `genie_benchmark_validation.yaml` |
| Terminal audit | Cross-validation sweep | MISSING | `ground_truth_validation.yaml` not present |

## 11. Known Limitations

| Limitation | Layer | Impact | Reason |
|---|---|---|---|
| Missing `ground_truth_validation.yaml` | Run validation | Overall status is `PARTIAL_SUCCESS`; status is based on individual manifests/API-readback files rather than terminal cross-validation sweep | Step 5.3 cross-validation sweep artifact was not present in output folder |
| MC-1 PMPM | Metric View | KPI not available as a Metric View measure, dashboard KPI, or Genie KPI | Requires paid claims and member-month exposure at common monthly grain; no physical co-grained member-month exposure table exists |
| MC-2 Claims per 1,000 Members | Metric View | KPI not available as a Metric View measure, dashboard KPI, or Genie KPI | Requires member-month denominator at common grain with claim counts; no physical co-grained denominator source exists |
| MC-3 Utilization Rate | Metric View | KPI not available as a Metric View measure, dashboard KPI, or Genie KPI | Requires active enrolled denominator and members-with-claims numerator at common monthly grain; no pre-aggregated utilization population source exists |
| MC-4 High-Cost Member Count | Metric View | Not implemented as Metric View measure; reference SQL is documented | Requires member-level pre-aggregation and HAVING threshold |
| W-2 MoM Active Member Growth | Metric View | Not implemented as Metric View measure; reference SQL is documented | Requires LAG window offset over monthly active member counts |
| Dashboard widget-type breakdown not independently audited | Dashboard | README reports API-readback total widgets/filters/pages, not an audited breakdown by visualization type | API-readback validation artifacts contain total counts but not visualization-type distribution |

## 12. Usage

### Query Metric Views

Use the generated Metric Views with Databricks Metric View syntax and `MEASURE()` expressions.

Claims example:

```sql
SELECT
  `Claim Type`,
  MEASURE(`Total Claims`) AS total_claims,
  MEASURE(`Total Paid Amount`) AS total_paid_amount
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_metric_view_v13`
GROUP BY ALL;
```

Enrollment example:

```sql
SELECT
  `Line Of Business`,
  MEASURE(`Active Members`) AS active_members
FROM `aw_serverless_stable_catalog`.`aibi_member_claims`.`member_claims_enrollment_metric_view_v13`
GROUP BY ALL;
```

### Dashboards

Open these published dashboards from the Databricks workspace:

- `member_claims_kpis_dashboard_v13`, dashboard ID `01f1b2fec53a1f179d94457d25e6f3d1`, relative path `/dashboardsv3/01f1b2fec53a1f179d94457d25e6f3d1/published`
- `member_claims_utilization_dashboard_v13`, dashboard ID `01f1b2fec68618f7b0d06e6c075561e1`, relative path `/dashboardsv3/01f1b2fec68618f7b0d06e6c075561e1/published`

The KPI dashboard is intended for financial, claims, and member-demographic monitoring. The utilization dashboard is intended for utilization patterns, provider insights, and operational metrics.

### Genie

Open Genie Space `member_claims_analytics_genie_v13`, space ID `01f1b31272b01bef962dd25299c857ae`, relative path `/genie/rooms/01f1b31272b01bef962dd25299c857ae`.

Ask questions grounded in the configured Metric Views. Representative generated questions include:

- What are the total claims, claim lines, and paid amount?
- How has total paid amount trended by service month?
- Which rendering provider specialties have the top paid amount?
- How many active members are there by line of business?
- What is the monthly trend for new member enrollment?

Avoid asking for skipped KPIs such as PMPM, Claims per 1,000 Members, Utilization Rate, High-Cost Member Count, or MoM Active Member Growth unless using the reference SQL outside Genie.

## 13. Troubleshooting

This section is included because the overall status is `PARTIAL_SUCCESS`.

| Layer | Symptom | Root Cause | Resolution | Artifact |
|---|---|---|---|---|
| Terminal validation | Run summary does not claim terminal-audit PASS | `ground_truth_validation.yaml` is missing | Re-run the cross-validation sweep step that produces `ground_truth_validation.yaml`; do not use this documentation as proof of independent terminal audit until that artifact exists | Expected path: `ground_truth_validation.yaml` |
| Metric Views | PMPM, Claims per 1,000 Members, and Utilization Rate are unavailable | Grain mismatch and missing co-grained member-month denominator source | Create a member-month exposure/pre-aggregation table and re-run Metric View planning | `metric_view_plan.yaml` |
| Metric Views | High-Cost Member Count is unavailable as a Metric View measure | KPI requires member-level HAVING threshold | Implement the documented reference SQL as a dashboard dataset or pre-aggregated table | `metric_view_plan.yaml` |
| Metric Views | MoM Active Member Growth is unavailable as a Metric View measure | KPI requires LAG window semantics | Implement the documented reference SQL as a dashboard SQL dataset if needed | `metric_view_plan.yaml` |
| Dashboards | User needs visualization-type breakdown | API-readback validation confirms widget totals but does not report widget-type counts | Inspect `dashboard_design.yaml` or the deployed dashboard directly for visualization-type distribution | `dashboard_design.yaml`; dashboard validation YAML files |

## 14. Generated Artifacts

Only files observed in the run output are listed.

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
- `dashboards/member_claims_kpis_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_kpis_dashboard_v13_validation.yaml`
- `dashboards/member_claims_utilization_dashboard_dashboard_manifest.json`
- `dashboards/member_claims_utilization_dashboard_v13_validation.yaml`

Genie:

- `genie_space/genie_semantic_inventory.yaml`
- `genie_space/llm_genie_design.yaml`
- `genie_space/member_claims_analytics_genie_v13_manifest.json`
- `genie_space/genie_manifest.json`
- `genie_space/member_claims_analytics_genie_v13_validation.yaml`
- `genie_space/benchmark_results.yaml`
- `genie_space/genie_benchmark_validation.yaml`
- `genie_space/sample_queries_member_claims.sql`
- `genie_space/genie_space_configuration_member_claims`

Run state and documentation:

- `run_context.yaml`
- `step_handoff.yaml`
- `documentation/readme.md`
- `run_manifest.json`

Missing expected terminal artifact:

- `ground_truth_validation.yaml`

## 15. Configuration Reference

Primary configuration values used by this run:

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
| `config.version_suffix` | `_v13` |

Refer to `accelerator.yaml` for the full configuration.
