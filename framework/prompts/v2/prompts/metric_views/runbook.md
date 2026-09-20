# Metric Views — Failure Runbook

> **FAILURE-ONLY — DO NOT LOAD ON A SUCCESSFUL PATH.** Authenticate this file's exact frozen path/version/raw SHA-256 after the stage has emitted a classified error. Load only the matching section needed for diagnosis. A runbook never changes authority, weakens a gate, or authorizes an unclassified retry. Record the selected section and digest in the failure evidence.

## Anti-Patterns

### AP-MV-7: Join Entry Missing 'on' Field
**Pattern:** Metric View YAML contains a join with `name` and `source` but no single-quoted `'on'`
field, so structural validation halts.
**Root cause:** The join condition was inferred from an example or omitted when the join appeared
optional; unquoted `on` is also a YAML reserved scalar.
**Fix:** Under the approved contract, `join_condition_using` resolves through the
`JOIN_CONDITION_ON` fallback. Require `name`, `source`, and single-quoted `'on'`; add `rely` only
after validation. If no joins are required, omit `joins` entirely.

### AP-MV-1: Single Metric View When 2 Grains Exist
**Pattern:** Plan says 2 metric views (claims + enrollment), validation shows 1. Enrollment MV was dropped because "only 1 KPI".
**Root cause:** Threshold of "fewer than 2 KPIs" in `metric_views/instructions.md` allowed dropping secondary grain.
**Fix:** Changed threshold from 2 to 1. GATE 5.7 now enforces plan-vs-created parity.

### AP-MV-2: Column Name Mismatch
**Pattern:** Metric view aliases differ from source table columns (e.g., `clm_dtl_claim_type` → `claim_type`). Dashboard SQL uses source names → fails.
**Fix:** During Metric View generation, validate physical expressions against `DESCRIBE TABLE` for the source. After deployment, dashboards and Genie must use aliases returned by `DESCRIBE`/query of the Metric View, not source-table names.

### AP-MV-4: UNRESOLVED_COLUMN in Metric View Deployment
**Pattern:** `UNRESOLVED_COLUMN.WITH_SUGGESTION` at CREATE VIEW time. Column name from ERD/spec doesn't match actual table column.
**Root cause:** LLM references column names from `erd_parsed.yaml` or `table_spec.yaml` in measure expressions without verifying they exist in the deployed table. Column names can differ between ERD parse runs.
**Fix:** Template now includes Gate 2b: after DESCRIBE TABLE, every column reference in every field/measure expression is validated against the actual schema. Missing columns halt before compilation with the exact column name and expression.

### AP-MV-3: Premature NOT_IMPLEMENTED
**Pattern:** Agent classifies KPI as NOT_IMPLEMENTED at planning stage because it thinks "only 1 KPI per grain is insufficient." The KPI was actually implementable.
**Fix:** A distinct valid grain with at least one implementable KPI receives a metric view. GATE 4.3 reserves NOT_IMPLEMENTED for resolved capability blockers and requires constraint scope.

### AP-MV-5: Disabled Native Feature Without Fallback Evaluation
**Pattern:** A capability is `enabled: false`, so the KPI is immediately marked `NOT_IMPLEMENTED` even though the contract declares an equivalent fallback.
**Fix:** Resolve native use first, then execute and validate the declared fallback. A successful fallback remains implemented and records the strategy and checks. Use `NOT_IMPLEMENTED` only after a resolved capability blocker remains.

### AP-MV-6: Capability Contract Drift on Resume
**Pattern:** A run resumes from a plan or deployed Metric View created under a different capability-contract hash.
**Fix:** GATE 3.0 pins the raw-byte SHA-256 and GATE 10.2 enforces tuple parity. A changed contract version/hash makes planning and all dependent artifacts stale.

# Validated Learnings (from production runs)

**1. `version` MUST be the quoted specification string resolved from the contract**

Bare integer `1` causes `Invalid YAML version: 1`. Omitting the field causes `Invalid YAML version: null`. Emit `execution_target.yaml_specification` as a string (the current approved contract resolves to `"1.1"`); never select or hardcode a different version from model memory.

**2. `type` is NOT a valid column property**

Only: `name`, `expr`, `comment`, `display_name`, `format`, `synonyms`, `window`. Using `type: date` causes `Unrecognized field "type"`.

**3. `agg` is NOT a valid measure property**

Measures use full SQL in `expr`. No separate aggregation field. `agg: sum` causes `Unrecognized field "agg"`.

**4. Derived measures use `MEASURE()` composition**

```yaml
- name: avg_paid_per_claim
  expr: MEASURE(`total_paid`) / NULLIF(MEASURE(`total_claims`), 0)
```

No `agg: derived` property exists.

**5. `MEASURE()` references MUST use backtick quoting for multi-word names**

Without backticks, `MEASURE(Total Paid Amount)` causes `PARSE_SYNTAX_ERROR: Syntax error at or near 'Paid'`. The parser interprets spaces as expression boundaries.

```yaml
# WRONG — causes PARSE_SYNTAX_ERROR:
  expr: MEASURE(Total Paid Amount) / NULLIF(MEASURE(Total Claims), 0)

# CORRECT — backtick-quoted:
  expr: MEASURE(`Total Paid Amount`) / NULLIF(MEASURE(`Total Claims`), 0)
```

Rule: ALWAYS backtick-quote measure names inside `MEASURE()` — even single-word names are safe to quote.

**6. `wait_timeout` bounds: 5s–50s only**

Values outside (e.g., `"60s"`) cause `INVALID_PARAMETER_VALUE`. Use `"50s"` as standard.

**6. Every column referenced in measures/fields MUST exist in the source table**

The template's Gate 2b validates this: it extracts column identifiers from every `expr` and checks them against `DESCRIBE TABLE` results. Missing columns halt with an explicit error BEFORE the CREATE VIEW is attempted. This prevents `UNRESOLVED_COLUMN` errors at deployment time.

Common failure mode: the LLM writes `COUNT(DISTINCT clm_dtl_member_nbr_sk)` in a measure, but the source table has a different column name (e.g., `member_nbr_sk` or `mbr_member_sk`). Gate 2b catches this before compilation.

**7. Single-source preferred for greenfield synthetic data**

Avoids fact-to-fact fanout from synthetic FK distributions. Add joins only after stability test passes.

**7. Column prefix rules depend on joins**

No joins → bare column names. With joins → MUST prefix `source.` or `<join_name>.` on ALL references.

**8. `format` MUST be a structured object — NEVER a simple string**

Using `format: "#,##0"` or `format: "$#,##0.00"` causes `METRIC_VIEW_INVALID_VIEW_DEFINITION: Failed to parse YAML: Could not resolve subtype of [simple`. The YAML parser uses polymorphic deserialization on `format` and requires a `type` discriminator.

```yaml
# WRONG — causes parse failure:
  - name: Total Paid Amount
    expr: SUM(paid_amt)
    format: "$#,##0.00"           # ← simple string = CRASH

# WRONG — causes parse failure:
  - name: Denial Rate
    expr: SUM(denied) / NULLIF(COUNT(*), 0)
    format: "0.00%"               # ← simple string = CRASH

# CORRECT — structured object:
  - name: Total Paid Amount
    expr: SUM(paid_amt)
    format:
      type: currency
      currency_code: USD
      decimal_places:
        type: exact
        places: 2

# CORRECT — percentage:
  - name: Denial Rate
    expr: SUM(denied) / NULLIF(COUNT(*), 0)
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 2

# CORRECT — integer count:
  - name: Total Claims
    expr: COUNT(DISTINCT claim_id)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0

# CORRECT — decimal ratio:
  - name: Lines per Claim
    expr: COUNT(*) / NULLIF(COUNT(DISTINCT claim_id), 0)
    format:
      type: number
      decimal_places:
        type: exact
        places: 2

# CORRECT — date dimension (ALL sub-properties are MANDATORY):
  - name: Service Date
    expr: service_date
    format:
      type: date
      date_format: year_month_day    # REQUIRED: locale_short_month | locale_long_month | year_month_day | locale_number_month | year_week

# CORRECT — date_time dimension (BOTH sub-properties are MANDATORY):
  - name: Created At
    expr: created_timestamp
    format:
      type: date_time
      date_format: locale_short_month  # REQUIRED
      time_format: locale_hour_minute  # REQUIRED: no_time | locale_hour_minute | locale_hour_minute_second

# WRONG — missing date_format causes CRASH:
  - name: Service Date
    expr: service_date
    format:
      type: date                       # ← Missing date_format = METRIC_VIEW_INVALID_VIEW_DEFINITION

# SAFEST for date/timestamp dimensions — just OMIT format entirely:
  - name: Service Date
    expr: service_date
    comment: "Date of service"         # No format block — dashboard auto-formats dates correctly
```

Valid `format.type` values: `number` | `currency` | `percentage` | `date` | `date_time` | `byte`. Omit `format` entirely if no specific formatting is needed. **For date/timestamp dimensions, omitting `format` is strongly recommended** — dashboards auto-detect and format date columns correctly.

---
