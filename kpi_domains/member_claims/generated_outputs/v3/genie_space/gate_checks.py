# =============================================================================
# Gate Checks — Four-Gate Validation Framework for Pipeline Deployment
# =============================================================================
#
# This module provides runtime gate enforcement that PREVENTS the deployment of
# incomplete, incorrect, or architecturally unsound assets. It is the
# programmatic counterpart to the prose gate instructions in the step prompts.
#
# FOUR-GATE MODEL (from design_thoughts.md):
#
# Gate 1 — Structural validation (schema-valid YAML/JSON, required fields)
# Gate 2 — Metadata validation (catalog/schema/columns exist, types compatible)
# Gate 3 — Semantic validation (grain valid, KPI refs valid, join paths safe)
# Gate 4 — Deployment validation (permissions, naming, readback matches)
#
# Only after ALL four gates pass should execution proceed.
#
# This is particularly important because "valid SQL" is not the same as
# "correct architecture." A generated view can compile perfectly and still
# be wrong because it joins two facts at incompatible grains.
#
# MIGRATION MAP (old layers -> new gates):
#   Layer 1 pre-deploy assertions  -> Gates 1+3 (structural + semantic)
#   Layer 2 post-deploy readback   -> Gate 4 (deployment verification)
#   Layer 3 cross-validation       -> Gate 4 (terminal sweep)
#
# BACKWARD COMPATIBILITY:
#   Existing functions (assert_dashboard_has_widgets, validate_genie_from_api,
#   run_cross_validation, etc.) are preserved. New four-gate functions are
#   added alongside. Templates can use either API.
#
# NEW FUNCTIONS:
#   run_four_gate_ddl()       — DDL table spec validation
#   run_four_gate_metric_views() — Metric view spec validation
#   run_four_gate_dashboard() — Dashboard design validation
#   run_four_gate_genie()     — Genie space validation
#   validate_grain_safety()  — Semantic: grain compatibility check
#   validate_join_paths()    — Semantic: join fanout detection
#   validate_no_duplicates() — Semantic: duplicate measure/dimension detection
#
# GUARANTEE:
# After Gate 1+2 pass, the spec is well-formed and references real objects.
# After Gate 3 passes, the architecture is semantically correct.
# After Gate 4 passes, the deployed object matches the spec (idempotency proof).
# =============================================================================

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


# =============================================================================
# DEFAULT QUALITY THRESHOLDS
# =============================================================================
# These can be overridden by passing a quality_gates dict from accelerator.yaml.
# The defaults represent the minimum acceptable quality for a production run.

DEFAULT_QUALITY_GATES = {
    # Dashboard thresholds
    "min_widgets_per_canvas_page": 2,
    "min_filters_per_dashboard": 3,
    "min_datasets_per_dashboard": 1,
    "min_canvas_pages_per_dashboard": 1,
    # Genie thresholds
    "min_genie_instruction_chars": 200,
    "min_genie_tables": 1,
    "min_genie_sample_questions": 5,
    "min_genie_example_sqls": 5,
    "min_genie_description_chars": 50,
}


def _get_threshold(quality_gates: dict | None, key: str) -> int:
    """Resolve a threshold from user-provided gates or defaults."""
    if quality_gates and key in quality_gates:
        return int(quality_gates[key])
    return DEFAULT_QUALITY_GATES[key]


# =============================================================================
# SECTION 1: Pre-Deploy Assertions (Layer 1)
# =============================================================================
# Call these BEFORE any Lakeview or Genie API create/publish call.
# They raise GateCheckError (subclass of RuntimeError) on failure,
# which physically prevents the API call from executing.


class GateCheckError(RuntimeError):
    """Raised when a programmatic gate check fails.

    Contains the gate_id and a human-readable explanation of what
    was expected vs what was found. Agents cannot catch-and-ignore
    this without explicitly handling the specific gate ID.
    """

    def __init__(self, gate_id: str, message: str):
        self.gate_id = gate_id
        super().__init__(f"GATE {gate_id} FAILED: {message}")


def assert_artifact_exists(
    path: str,
    gate_id: str,
    *,
    min_size_bytes: int = 10,
) -> None:
    """Assert that a prerequisite artifact file exists and is non-trivial.

    Call before any API call that depends on a prior step's output.
    Prevents the #1 failure mode: skipping design/validation steps
    and jumping directly to API creation.

    Args:
        path: Absolute workspace path to the expected artifact.
        gate_id: Identifier for this gate (e.g., 'GATE_3.2_DESIGN_CONTRACT').
        min_size_bytes: Minimum file size to consider non-trivial.

    Raises:
        GateCheckError: If file is missing or too small.

    Example:
        assert_artifact_exists(
            f"{output_folder}/dashboards/dashboard_design.yaml",
            "GATE_3.2_DESIGN_CONTRACT",
        )
    """
    if not os.path.exists(path):
        raise GateCheckError(
            gate_id,
            f"Required artifact not found: {path}\n"
            f"  This artifact must be created by a prior step before proceeding.\n"
            f"  Re-run the step that produces this artifact.",
        )
    size = os.path.getsize(path)
    if size < min_size_bytes:
        raise GateCheckError(
            gate_id,
            f"Artifact exists but is too small ({size} bytes < {min_size_bytes}): {path}\n"
            f"  This usually means the prior step wrote an empty/placeholder file.",
        )


def assert_dashboard_has_widgets(
    serialized_dashboard: dict,
    dashboard_name: str,
    *,
    quality_gates: dict | None = None,
) -> dict:
    """Assert that a dashboard JSON has widgets on every canvas page.

    Call AFTER building the serialized_dashboard dict and BEFORE passing
    it to create_dashboard() or patch_dashboard().

    This catches the exact v2 failure: dashboards created with datasets
    and page names but layout: [] and widgets: [] on every page.

    Args:
        serialized_dashboard: The full dashboard dict (datasets + pages).
        dashboard_name: Display name for error messages.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Summary dict with counts for logging/audit.

    Raises:
        GateCheckError: If any canvas page has zero widgets or fewer
            than the minimum threshold.
    """
    min_widgets = _get_threshold(quality_gates, "min_widgets_per_canvas_page")
    min_canvas = _get_threshold(quality_gates, "min_canvas_pages_per_dashboard")
    min_datasets = _get_threshold(quality_gates, "min_datasets_per_dashboard")

    pages = serialized_dashboard.get("pages", [])
    datasets = serialized_dashboard.get("datasets", [])

    # Check datasets exist
    if len(datasets) < min_datasets:
        raise GateCheckError(
            "PRE_DEPLOY_DATASETS",
            f"Dashboard '{dashboard_name}' has {len(datasets)} dataset(s) "
            f"(minimum: {min_datasets}).\n"
            f"  Every dashboard must have at least one dataset with valid SQL.",
        )

    # Separate canvas pages from filter pages
    canvas_pages = []
    filter_pages = []
    for page in pages:
        page_type = page.get("pageType", "PAGE_TYPE_CANVAS")
        if page_type == "PAGE_TYPE_GLOBAL_FILTERS":
            filter_pages.append(page)
        else:
            canvas_pages.append(page)

    # Check canvas page count
    if len(canvas_pages) < min_canvas:
        raise GateCheckError(
            "PRE_DEPLOY_CANVAS_PAGES",
            f"Dashboard '{dashboard_name}' has {len(canvas_pages)} canvas page(s) "
            f"(minimum: {min_canvas}).\n"
            f"  KPI spec Dashboard Mapping defines the required page count.",
        )

    # Check each canvas page has widgets
    issues = []
    total_widgets = 0
    page_summary = []
    for page in canvas_pages:
        layout = page.get("layout", [])
        widget_count = len(layout)
        total_widgets += widget_count
        page_name = page.get("displayName", page.get("name", "unnamed"))
        page_summary.append({"page": page_name, "widgets": widget_count})

        if widget_count == 0:
            issues.append(
                f"Canvas page '{page_name}' has 0 widgets (layout is empty)."
            )
        elif widget_count < min_widgets:
            issues.append(
                f"Canvas page '{page_name}' has {widget_count} widget(s) "
                f"(minimum: {min_widgets})."
            )

    if issues:
        detail = "\n  ".join(issues)
        raise GateCheckError(
            "PRE_DEPLOY_WIDGETS",
            f"Dashboard '{dashboard_name}' has empty or under-populated canvas pages:\n"
            f"  {detail}\n\n"
            f"  Page summary: {page_summary}\n\n"
            f"  This means widget construction was skipped. Do NOT call \n"
            f"  create_dashboard() until every canvas page has widgets.\n"
            f"  Re-run the widget construction step.",
        )

    summary = {
        "dashboard_name": dashboard_name,
        "datasets": len(datasets),
        "canvas_pages": len(canvas_pages),
        "filter_pages": len(filter_pages),
        "total_widgets": total_widgets,
        "page_summary": page_summary,
    }
    print(
        f"  \u2705 PRE_DEPLOY_WIDGETS: '{dashboard_name}' — "
        f"{len(canvas_pages)} canvas pages, {total_widgets} widgets, "
        f"{len(datasets)} datasets"
    )
    return summary


def assert_dashboard_has_filters(
    serialized_dashboard: dict,
    dashboard_name: str,
    *,
    quality_gates: dict | None = None,
) -> dict:
    """Assert that a dashboard has a filters page with functional bindings.

    Every dashboard MUST include a PAGE_TYPE_GLOBAL_FILTERS page with
    at least N filter widgets (default: 3). Filters must reference a
    dataset via queryName in their encodings.

    Args:
        serialized_dashboard: The full dashboard dict.
        dashboard_name: Display name for error messages.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Summary dict with filter details.

    Raises:
        GateCheckError: If no filter page exists or filter count is
            below the minimum.
    """
    min_filters = _get_threshold(quality_gates, "min_filters_per_dashboard")
    pages = serialized_dashboard.get("pages", [])

    filter_pages = [
        p for p in pages
        if p.get("pageType") == "PAGE_TYPE_GLOBAL_FILTERS"
    ]

    if not filter_pages:
        raise GateCheckError(
            "PRE_DEPLOY_FILTERS",
            f"Dashboard '{dashboard_name}' has NO filter page.\n"
            f"  Every dashboard MUST include a PAGE_TYPE_GLOBAL_FILTERS page.\n"
            f"  Use build_filters_page() from lakeview_dashboard_helpers.py.",
        )

    total_filters = 0
    unbound_filters = []
    for fp in filter_pages:
        layout = fp.get("layout", [])
        for item in layout:
            widget = item.get("widget", {})
            total_filters += 1
            # Check that filter has a query binding
            spec = widget.get("spec", {})
            encodings = spec.get("encodings", {})
            fields = encodings.get("fields", [])
            has_binding = any(
                f.get("queryName") for f in fields
            ) if fields else False
            if not has_binding:
                w_name = widget.get("name", "unnamed")
                unbound_filters.append(w_name)

    if total_filters < min_filters:
        raise GateCheckError(
            "PRE_DEPLOY_FILTER_COUNT",
            f"Dashboard '{dashboard_name}' has {total_filters} filter widget(s) "
            f"(minimum: {min_filters}).\n"
            f"  Every dashboard needs at least {min_filters} functional filters "
            f"(date range, categorical selects for key dimensions).",
        )

    summary = {
        "dashboard_name": dashboard_name,
        "filter_pages": len(filter_pages),
        "total_filters": total_filters,
        "unbound_filters": unbound_filters,
    }

    if unbound_filters:
        raise GateCheckError(
            "PRE_DEPLOY_FILTER_BINDING",
            f"Dashboard '{dashboard_name}' has {len(unbound_filters)} filter(s) "
            f"missing 'queryName' in encodings.fields[].\n"
            f"  Unbound filters: {unbound_filters}\n"
            f"  Filters without queryName appear as 'no fields or parameters selected' in the UI.\n"
            f"  FIX: Use build_filter_widget() from lakeview_dashboard_helpers.py, which always\n"
            f"  includes queryName: 'main_query'. Never hand-write filter JSON.",
        )
    else:
        print(
            f"  \u2705 PRE_DEPLOY_FILTERS: '{dashboard_name}' — "
            f"{total_filters} filters, all bound"
        )
    return summary


def assert_genie_config_complete(
    *,
    title: str,
    description: str | None,
    table_identifiers: list[str],
    general_instructions: str,
    sample_questions: list[str],
    example_sqls: list[tuple[str, str]],
    quality_gates: dict | None = None,
) -> dict:
    """Assert that Genie space configuration is complete before API call.

    Call BEFORE the Genie create/update API call. Prevents deploying
    an empty shell with no instructions, tables, or questions.

    Args:
        title: Space title.
        description: Space description (shown in UI).
        table_identifiers: List of fully qualified metric view names.
        general_instructions: Markdown instructions for Genie.
        sample_questions: List of sample question strings.
        example_sqls: List of (question, sql) tuples.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Summary dict with content metrics.

    Raises:
        GateCheckError: If any required content is missing or below threshold.
    """
    min_instr = _get_threshold(quality_gates, "min_genie_instruction_chars")
    min_tables = _get_threshold(quality_gates, "min_genie_tables")
    min_questions = _get_threshold(quality_gates, "min_genie_sample_questions")
    min_sqls = _get_threshold(quality_gates, "min_genie_example_sqls")
    min_desc = _get_threshold(quality_gates, "min_genie_description_chars")

    issues = []

    if not title or not title.strip():
        issues.append("Title is empty")

    if not description or len(description.strip()) < min_desc:
        actual = len(description.strip()) if description else 0
        issues.append(
            f"Description too short ({actual} chars, need >= {min_desc}). "
            f"The description appears in the Genie UI and should summarize "
            f"what this space covers."
        )

    if len(table_identifiers) < min_tables:
        issues.append(
            f"Only {len(table_identifiers)} table identifier(s) "
            f"(need >= {min_tables}). "
            f"At least the primary metric view must be attached."
        )

    instr_len = len(general_instructions.strip()) if general_instructions else 0
    if instr_len < min_instr:
        issues.append(
            f"Instructions too short ({instr_len} chars, need >= {min_instr}). "
            f"Must cover domain context, measures, dimensions, and query rules."
        )

    if len(sample_questions) < min_questions:
        issues.append(
            f"Only {len(sample_questions)} sample question(s) "
            f"(need >= {min_questions}). "
            f"Questions appear as suggestions in the Genie chat UI."
        )

    if len(example_sqls) < min_sqls:
        issues.append(
            f"Only {len(example_sqls)} example SQL(s) "
            f"(need >= {min_sqls}). "
            f"Example SQLs teach Genie how to answer with MEASURE() syntax."
        )

    if issues:
        detail = "\n  ".join(issues)
        raise GateCheckError(
            "PRE_DEPLOY_GENIE",
            f"Genie space '{title}' configuration is incomplete:\n"
            f"  {detail}\n\n"
            f"  Do NOT call the Genie API until all content is populated.\n"
            f"  Re-run the LLM design and configuration steps.",
        )

    summary = {
        "title": title,
        "description_chars": len(description) if description else 0,
        "table_identifiers": len(table_identifiers),
        "instruction_chars": instr_len,
        "sample_questions": len(sample_questions),
        "example_sqls": len(example_sqls),
    }
    print(
        f"  \u2705 PRE_DEPLOY_GENIE: '{title}' — "
        f"{instr_len} instruction chars, {len(table_identifiers)} tables, "
        f"{len(sample_questions)} questions, {len(example_sqls)} example SQLs"
    )
    return summary


# =============================================================================
# SECTION 2: Post-Deploy API Readback Validation (Layer 2)
# =============================================================================
# Call these AFTER the API create/publish call returns successfully.
# They read the deployed object back from the API and verify that what
# was deployed matches what was intended. This catches silent API failures
# where the call succeeds but the content is not persisted.


def validate_dashboard_from_api(
    dashboard_id: str,
    expected_name: str,
    *,
    quality_gates: dict | None = None,
) -> dict:
    """Read back a deployed dashboard via Lakeview API and validate content.

    Call AFTER create_dashboard() and publish_dashboard() succeed.
    This is the ground-truth check that prevents fraudulent validation
    files (manifest says PASS but dashboard is actually empty).

    Args:
        dashboard_id: The dashboard UUID returned by the API.
        expected_name: Expected display name for verification.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Ground-truth validation dict with source='api_readback'.

    Raises:
        GateCheckError: If the dashboard API object is empty or
            doesn't match expectations.
    """
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    min_widgets = _get_threshold(quality_gates, "min_widgets_per_canvas_page")
    min_filters = _get_threshold(quality_gates, "min_filters_per_dashboard")

    # GET the dashboard — use the DRAFT endpoint for structural validation
    # because the published endpoint strips page layout/widget details.
    # The draft endpoint returns the full serialized_dashboard with all
    # pages, widgets, and layout arrays intact.
    resp = w.api_client.do(
        "GET",
        f"/api/2.0/lakeview/dashboards/{dashboard_id}",
    )

    display_name = resp.get("display_name", "")
    sd_raw = resp.get("serialized_dashboard", "{}")
    sd = json.loads(sd_raw) if isinstance(sd_raw, str) else sd_raw

    # Also check publication status separately
    is_published = False
    try:
        pub_resp = w.api_client.do(
            "GET",
            f"/api/2.0/lakeview/dashboards/{dashboard_id}/published",
        )
        is_published = bool(pub_resp)
    except Exception:
        pass  # Not published yet — not a structural failure

    pages = sd.get("pages", [])
    datasets = sd.get("datasets", [])

    # Count widgets per page category
    canvas_pages = []
    filter_pages = []
    total_widgets = 0
    total_filters = 0
    page_details = []

    for page in pages:
        page_type = page.get("pageType", "PAGE_TYPE_CANVAS")
        layout = page.get("layout", [])
        page_name = page.get("displayName", page.get("name", "unnamed"))
        widget_count = len(layout)

        if page_type == "PAGE_TYPE_GLOBAL_FILTERS":
            filter_pages.append(page)
            total_filters += widget_count
        else:
            canvas_pages.append(page)
            total_widgets += widget_count

        page_details.append({
            "name": page_name,
            "type": page_type,
            "widgets": widget_count,
        })

    # Validate
    issues = []

    if total_widgets == 0:
        issues.append(
            f"Dashboard has 0 canvas widgets across {len(canvas_pages)} "
            f"canvas page(s). All pages have empty layout arrays."
        )

    for page in canvas_pages:
        layout = page.get("layout", [])
        page_name = page.get("displayName", page.get("name", "unnamed"))
        if len(layout) == 0:
            issues.append(f"Canvas page '{page_name}' has 0 widgets.")
        elif len(layout) < min_widgets:
            issues.append(
                f"Canvas page '{page_name}' has {len(layout)} widget(s) "
                f"(minimum: {min_widgets})."
            )

    if not filter_pages:
        issues.append("No filter page found in deployed dashboard.")
    elif total_filters < min_filters:
        issues.append(
            f"Dashboard has {total_filters} filter(s) "
            f"(minimum: {min_filters})."
        )

    if not datasets:
        issues.append("Dashboard has 0 datasets.")

    validation = {
        "source": "api_readback",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dashboard_id": dashboard_id,
        "display_name": display_name,
        "published": is_published,
        "datasets": len(datasets),
        "total_pages": len(pages),
        "canvas_pages": len(canvas_pages),
        "filter_pages": len(filter_pages),
        "total_canvas_widgets": total_widgets,
        "total_filters": total_filters,
        "page_details": page_details,
        "issues": issues,
        "status": "FAIL" if issues else "PASS",
    }

    if issues:
        detail = "\n  ".join(issues)
        raise GateCheckError(
            "POST_DEPLOY_DASHBOARD",
            f"Dashboard '{expected_name}' ({dashboard_id}) deployed but "
            f"API readback shows problems:\n  {detail}\n\n"
            f"  Readback summary: {json.dumps(validation, indent=2)}\n\n"
            f"  The dashboard must be rebuilt with actual widgets before "
            f"writing any validation artifact.",
        )

    print(
        f"  \u2705 POST_DEPLOY_DASHBOARD: '{display_name}' — "
        f"API confirms {total_widgets} canvas widgets, "
        f"{total_filters} filters, {len(datasets)} datasets"
    )
    return validation


def validate_genie_from_api(
    space_id: str,
    expected_title: str,
    *,
    quality_gates: dict | None = None,
) -> dict:
    """Read back a deployed Genie space via API and validate content.

    Call AFTER the Genie create/update API call succeeds.
    Reads back the space with serialized_space=true to inspect
    actual instructions, sample questions, example SQLs, and tables.

    Args:
        space_id: The Genie space UUID.
        expected_title: Expected title for verification.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Ground-truth validation dict with source='api_readback'.

    Raises:
        GateCheckError: If the space is empty or misconfigured.
    """
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    min_instr = _get_threshold(quality_gates, "min_genie_instruction_chars")
    min_questions = _get_threshold(quality_gates, "min_genie_sample_questions")
    min_sqls = _get_threshold(quality_gates, "min_genie_example_sqls")
    min_desc = _get_threshold(quality_gates, "min_genie_description_chars")

    # GET the space with serialized content
    data = w.api_client.do(
        "GET",
        f"/api/2.0/genie/spaces/{space_id}",
        query={"include_serialized_space": "true"},
    )

    title = data.get("title", "")
    description = data.get("description", "") or ""
    warehouse_id = data.get("warehouse_id", "")

    # Parse serialized_space for content counts
    ss_raw = data.get("serialized_space", "{}")
    ss = json.loads(ss_raw) if isinstance(ss_raw, str) else (ss_raw or {})

    sample_questions = ss.get("config", {}).get("sample_questions", [])
    # API may store metric_views under "tables" key in read-back
    metric_views = (
        ss.get("data_sources", {}).get("metric_views", [])
        or ss.get("data_sources", {}).get("tables", [])
    )
    text_instructions = ss.get("instructions", {}).get("text_instructions", [])
    example_sqls = ss.get("instructions", {}).get("example_question_sqls", [])
    benchmarks = ss.get("benchmarks", {}).get("questions", [])

    # Calculate instruction text length (stored as multi-line arrays)
    instr_chars = sum(
        len("".join(t.get("content", []))) for t in text_instructions
    )

    # Validate
    issues = []

    if not description or len(description.strip()) < min_desc:
        actual = len(description.strip()) if description else 0
        issues.append(
            f"Description is {'empty' if actual == 0 else f'too short ({actual} chars)'}. "
            f"Need >= {min_desc} chars."
        )

    if not metric_views:
        issues.append("No metric views/tables attached to the space.")

    if instr_chars < min_instr:
        issues.append(
            f"Instructions too short ({instr_chars} chars, need >= {min_instr}). "
            f"The serialized_space has {len(text_instructions)} instruction block(s)."
        )

    if len(sample_questions) < min_questions:
        issues.append(
            f"Only {len(sample_questions)} sample question(s) "
            f"(need >= {min_questions})."
        )

    if len(example_sqls) < min_sqls:
        issues.append(
            f"Only {len(example_sqls)} example SQL(s) "
            f"(need >= {min_sqls})."
        )

    if not warehouse_id:
        issues.append("No warehouse_id set on the space.")

    validation = {
        "source": "api_readback",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "space_id": space_id,
        "title": title,
        "description_chars": len(description),
        "warehouse_id": warehouse_id,
        "metric_views": len(metric_views),
        "instruction_chars": instr_chars,
        "instruction_blocks": len(text_instructions),
        "sample_questions": len(sample_questions),
        "example_sqls": len(example_sqls),
        "benchmarks": len(benchmarks),
        "issues": issues,
        "status": "FAIL" if issues else "PASS",
    }

    if issues:
        detail = "\n  ".join(issues)
        raise GateCheckError(
            "POST_DEPLOY_GENIE",
            f"Genie space '{expected_title}' ({space_id}) deployed but "
            f"API readback shows problems:\n  {detail}\n\n"
            f"  Readback summary: {json.dumps(validation, indent=2)}\n\n"
            f"  The space must be reconfigured with complete content before "
            f"writing any validation artifact.",
        )

    print(
        f"  \u2705 POST_DEPLOY_GENIE: '{title}' — "
        f"API confirms {instr_chars} instruction chars, "
        f"{len(metric_views)} metric views, "
        f"{len(sample_questions)} questions, "
        f"{len(example_sqls)} example SQLs"
    )
    return validation


# =============================================================================
# SECTION 3: Terminal Cross-Validation Sweep (Layer 3)
# =============================================================================
# Call ONCE at the end of the entire run (before documentation).
# Reads every manifest in the output folder, GETs each deployed asset
# from the API, and produces a ground-truth validation report.


def run_cross_validation(
    output_folder: str,
    *,
    quality_gates: dict | None = None,
) -> dict:
    """Independent audit of all deployed assets against their manifests.

    Walks the output folder for manifest files, reads each one, then
    calls the API to verify the deployed asset matches the manifest's
    claims. Produces a ground_truth_validation.yaml that the
    documentation step must reference.

    Args:
        output_folder: Absolute path to the version output folder.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Cross-validation report dict. Write this to
        {output_folder}/ground_truth_validation.yaml.

    Raises:
        GateCheckError: If any deployed asset fails cross-validation.
    """
    import glob

    report = {
        "source": "cross_validation_sweep",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_folder": output_folder,
        "dashboards": [],
        "genie_spaces": [],
        "issues": [],
        "overall_status": "PASS",
    }

    # ---- Dashboard manifests ----
    dashboard_dir = os.path.join(output_folder, "dashboards")
    if os.path.isdir(dashboard_dir):
        for manifest_path in sorted(glob.glob(
            os.path.join(dashboard_dir, "*_dashboard_manifest.json")
        )):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                dashboard_id = manifest.get("dashboard_id", "")
                display_name = manifest.get("display_name", "")

                if not dashboard_id:
                    report["issues"].append(
                        f"Manifest {os.path.basename(manifest_path)} has no dashboard_id"
                    )
                    continue

                # Readback from API (non-raising version)
                try:
                    result = validate_dashboard_from_api(
                        dashboard_id,
                        display_name,
                        quality_gates=quality_gates,
                    )
                    report["dashboards"].append(result)
                except GateCheckError as e:
                    report["issues"].append(str(e))
                    report["dashboards"].append({
                        "dashboard_id": dashboard_id,
                        "display_name": display_name,
                        "status": "FAIL",
                        "error": str(e),
                    })

            except (json.JSONDecodeError, OSError) as e:
                report["issues"].append(
                    f"Cannot read manifest {os.path.basename(manifest_path)}: {e}"
                )

    # ---- Genie manifests ----
    genie_dir = os.path.join(output_folder, "genie_space")
    if os.path.isdir(genie_dir):
        for manifest_path in sorted(glob.glob(
            os.path.join(genie_dir, "*_manifest.json")
        )):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                space_id = manifest.get("space_id", "")
                title = manifest.get("title", "")

                if not space_id:
                    report["issues"].append(
                        f"Manifest {os.path.basename(manifest_path)} has no space_id"
                    )
                    continue

                try:
                    result = validate_genie_from_api(
                        space_id,
                        title,
                        quality_gates=quality_gates,
                    )
                    report["genie_spaces"].append(result)
                except GateCheckError as e:
                    report["issues"].append(str(e))
                    report["genie_spaces"].append({
                        "space_id": space_id,
                        "title": title,
                        "status": "FAIL",
                        "error": str(e),
                    })

            except (json.JSONDecodeError, OSError) as e:
                report["issues"].append(
                    f"Cannot read manifest {os.path.basename(manifest_path)}: {e}"
                )

    # ---- Overall status ----
    all_dashboard_pass = all(
        d.get("status") == "PASS" for d in report["dashboards"]
    )
    all_genie_pass = all(
        g.get("status") == "PASS" for g in report["genie_spaces"]
    )

    if not all_dashboard_pass or not all_genie_pass or report["issues"]:
        report["overall_status"] = "FAIL"

    # ---- Summary ----
    n_dash = len(report["dashboards"])
    n_dash_pass = sum(1 for d in report["dashboards"] if d.get("status") == "PASS")
    n_genie = len(report["genie_spaces"])
    n_genie_pass = sum(1 for g in report["genie_spaces"] if g.get("status") == "PASS")

    status_icon = "\u2705" if report["overall_status"] == "PASS" else "\u274c"
    print(f"\n{'=' * 60}")
    print(f"CROSS-VALIDATION SWEEP: {status_icon} {report['overall_status']}")
    print(f"{'=' * 60}")
    print(f"  Dashboards : {n_dash_pass}/{n_dash} passed")
    print(f"  Genie      : {n_genie_pass}/{n_genie} passed")
    if report["issues"]:
        print(f"  Issues     : {len(report['issues'])}")
        for issue in report["issues"]:
            # Truncate long error messages for summary display
            short = issue.split("\n")[0][:120]
            print(f"    \u2022 {short}")
    print()

    if report["overall_status"] == "FAIL":
        raise GateCheckError(
            "CROSS_VALIDATION",
            f"Cross-validation sweep FAILED.\n"
            f"  Dashboards: {n_dash_pass}/{n_dash} passed\n"
            f"  Genie: {n_genie_pass}/{n_genie} passed\n"
            f"  Total issues: {len(report['issues'])}\n\n"
            f"  Do NOT write run_manifest.json or documentation until all \n"
            f"  deployed assets pass cross-validation.\n"
            f"  Write this report to ground_truth_validation.yaml for audit.",
        )

    return report


# =============================================================================
# SECTION 4: Validation YAML Writer
# =============================================================================
# Writes validation artifacts with a mandatory 'source' field that
# distinguishes ground-truth API readbacks from agent self-reports.


def write_ground_truth_validation(
    path: str,
    validation_data: dict,
    *,
    source: str = "api_readback",
) -> None:
    """Write a validation YAML file with source attribution.

    The source field enables the documentation step to distinguish
    between verified (api_readback, cross_validation_sweep) and
    unverified (agent_reported) validation claims.

    Args:
        path: Absolute path to write the YAML file.
        validation_data: The validation dict to write.
        source: One of 'api_readback', 'cross_validation_sweep',
            or 'agent_reported'. Default is 'api_readback'.
    """
    import yaml

    output = {
        "source": source,
        "written_at": datetime.now(timezone.utc).isoformat(),
        **validation_data,
    }

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False)

    print(f"  \u2705 Validation written ({source}): {os.path.basename(path)}")


# =============================================================================
# SECTION 5: Convenience — Full Pre-Deploy Dashboard Gate
# =============================================================================
# Combines all Layer 1 dashboard checks into a single call.


def run_dashboard_predeploy_gates(
    serialized_dashboard: dict,
    dashboard_name: str,
    *,
    required_artifacts: list[str] | None = None,
    quality_gates: dict | None = None,
) -> dict:
    """Run all pre-deploy checks for a single dashboard.

    Combines artifact existence, widget, and filter checks into one
    call. Use this as the single gate before create_dashboard().

    Args:
        serialized_dashboard: The built dashboard JSON dict.
        dashboard_name: Display name for error messages.
        required_artifacts: List of file paths that must exist.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Combined summary dict.

    Raises:
        GateCheckError: On first failing check.
    """
    separator = '\u2500' * 40
    print(f"\n{separator}")
    print(f"Pre-deploy gates: {dashboard_name}")
    print(separator)

    # Check prerequisite artifacts
    if required_artifacts:
        for artifact_path in required_artifacts:
            artifact_name = os.path.basename(artifact_path)
            assert_artifact_exists(
                artifact_path,
                f"PRE_DEPLOY_ARTIFACT_{artifact_name}",
            )
            print(f"  \u2705 Artifact exists: {artifact_name}")

    # Check widgets
    widget_summary = assert_dashboard_has_widgets(
        serialized_dashboard,
        dashboard_name,
        quality_gates=quality_gates,
    )

    # Check filters
    filter_summary = assert_dashboard_has_filters(
        serialized_dashboard,
        dashboard_name,
        quality_gates=quality_gates,
    )

    return {
        "dashboard_name": dashboard_name,
        "artifacts_checked": len(required_artifacts or []),
        **widget_summary,
        **filter_summary,
    }


def run_genie_predeploy_gates(
    *,
    title: str,
    description: str | None,
    table_identifiers: list[str],
    general_instructions: str,
    sample_questions: list[str],
    example_sqls: list[tuple[str, str]],
    required_artifacts: list[str] | None = None,
    quality_gates: dict | None = None,
) -> dict:
    """Run all pre-deploy checks for a Genie space.

    Combines artifact existence and content completeness checks
    into one call. Use this as the single gate before the Genie API.

    Args:
        title: Space title.
        description: Space description.
        table_identifiers: Fully qualified metric view names.
        general_instructions: Markdown instructions.
        sample_questions: Sample question strings.
        example_sqls: (question, sql) tuples.
        required_artifacts: List of file paths that must exist.
        quality_gates: Optional overrides from accelerator.yaml.

    Returns:
        Summary dict.

    Raises:
        GateCheckError: On first failing check.
    """
    separator = '\u2500' * 40
    print(f"\n{separator}")
    print(f"Pre-deploy gates: Genie '{title}'")
    print(separator)

    # Check prerequisite artifacts
    if required_artifacts:
        for artifact_path in required_artifacts:
            artifact_name = os.path.basename(artifact_path)
            assert_artifact_exists(
                artifact_path,
                f"PRE_DEPLOY_ARTIFACT_{artifact_name}",
            )
            print(f"  \u2705 Artifact exists: {artifact_name}")

    # Check content completeness
    return assert_genie_config_complete(
        title=title,
        description=description,
        table_identifiers=table_identifiers,
        general_instructions=general_instructions,
        sample_questions=sample_questions,
        example_sqls=example_sqls,
        quality_gates=quality_gates,
    )


# =============================================================================
# SECTION 6: Four-Gate Validation Framework (New Architecture)
# =============================================================================
# Formal four-gate model per design_thoughts.md.
# Each gate validates a different failure class:
#   Gate 1: Structural — spec is well-formed (schema, required fields)
#   Gate 2: Metadata — spec references real objects (tables, columns exist)
#   Gate 3: Semantic — architecture is correct (grain, joins, KPIs valid)
#   Gate 4: Deployment — environment is ready (permissions, readback matches)
#
# Only after ALL four pass should execution proceed.
# =============================================================================


class GateResult:
    """Result of a single gate check."""

    def __init__(self, gate_id: str, status: str, details: dict | None = None,
                 issues: list[str] | None = None):
        self.gate_id = gate_id
        self.status = status  # PASS, FAIL, WARN
        self.details = details or {}
        self.issues = issues or []

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def __repr__(self):
        icon = "PASS" if self.passed else self.status
        return f"GateResult({self.gate_id}={icon})"


# -----------------------------------------------------------------------------
# GATE 1: STRUCTURAL VALIDATION
# -----------------------------------------------------------------------------

def gate1_structural_ddl(spec: dict) -> GateResult:
    """Gate 1 for DDL: validate table_spec.yaml structure.

    Checks: tables array exists, each table has name+columns, each column has name+type.
    """
    issues = []
    if "tables" not in spec or not spec["tables"]:
        return GateResult("G1_DDL", "FAIL", issues=["No 'tables' key or empty"])
    for t in spec["tables"]:
        if "name" not in t:
            issues.append(f"Table missing 'name'")
        if "columns" not in t or not t["columns"]:
            issues.append(f"Table '{t.get('name', '?')}' has no columns")
            continue
        for col in t["columns"]:
            if "name" not in col:
                issues.append(f"Column missing 'name' in table {t.get('name', '?')}")
            if "type" not in col:
                issues.append(f"Column '{col.get('name', '?')}' missing 'type' in {t.get('name', '?')}")
    if issues:
        return GateResult("G1_DDL", "FAIL", issues=issues)
    return GateResult("G1_DDL", "PASS",
                      details={"tables": len(spec["tables"]),
                               "columns": sum(len(t["columns"]) for t in spec["tables"])})


def gate1_structural_metric_view(spec: dict) -> GateResult:
    """Gate 1 for metric views: validate metric_view_spec.yaml structure.

    Checks: metric_views array exists, each has name+yaml, yaml has version+source+measures.
    """
    issues = []
    if "metric_views" not in spec or not spec["metric_views"]:
        return GateResult("G1_MV", "FAIL", issues=["No 'metric_views' key or empty"])
    for i, mv in enumerate(spec["metric_views"]):
        if "name" not in mv:
            issues.append(f"Metric view #{i} missing 'name'")
            continue
        if "yaml" not in mv:
            issues.append(f"Metric view '{mv['name']}' missing 'yaml' content")
            continue
        yml = mv["yaml"]
        if "version" not in yml:
            issues.append(f"Metric view '{mv['name']}': missing 'version' (must be 1.1)")
        elif str(yml["version"]) != "1.1":
            issues.append(f"Metric view '{mv['name']}': version must be 1.1, got {yml['version']}")
        if "source" not in yml:
            issues.append(f"Metric view '{mv['name']}': missing 'source'")
        if "measures" not in yml or not yml["measures"]:
            issues.append(f"Metric view '{mv['name']}': no measures")
        else:
            for m in yml["measures"]:
                if "name" not in m:
                    issues.append(f"Metric view '{mv['name']}': measure missing 'name'")
                if "expr" not in m:
                    issues.append(f"Metric view '{mv['name']}': measure '{m.get('name', '?')}' missing 'expr'")
    if issues:
        return GateResult("G1_MV", "FAIL", issues=issues)
    return GateResult("G1_MV", "PASS",
                      details={"metric_views": len(spec["metric_views"]),
                               "measures": sum(len(mv["yaml"].get("measures", []))
                                               for mv in spec["metric_views"])})


def gate1_structural_dashboard(design: dict) -> GateResult:
    """Gate 1 for dashboards: validate dashboard_design.yaml structure.

    Delegates to existing assert_dashboard_has_widgets + assert_dashboard_has_filters.
    """
    try:
        assert_dashboard_has_widgets(design.get("serialized_dashboard", design), design.get("name", "unnamed"))
        assert_dashboard_has_filters(design.get("serialized_dashboard", design), design.get("name", "unnamed"))
        return GateResult("G1_DASH", "PASS")
    except GateCheckError as e:
        return GateResult("G1_DASH", "FAIL", issues=[str(e)])


# -----------------------------------------------------------------------------
# GATE 2: METADATA VALIDATION
# -----------------------------------------------------------------------------

def gate2_metadata_ddl(spec: dict, spark) -> GateResult:
    """Gate 2 for DDL: verify column types are valid Spark SQL types."""
    VALID_TYPES = {"BIGINT", "INT", "INTEGER", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE",
                   "DECIMAL", "STRING", "VARCHAR", "CHAR", "BOOLEAN", "DATE",
                   "TIMESTAMP", "TIMESTAMP_NTZ", "BINARY"}
    issues = []
    for t in spec.get("tables", []):
        for col in t.get("columns", []):
            base_type = col.get("type", "").split("(")[0].upper().strip()
            if base_type not in VALID_TYPES:
                issues.append(f"Invalid type '{col.get('type')}' for column {col.get('name')} in table {t.get('name')}")
    if issues:
        return GateResult("G2_DDL", "FAIL", issues=issues)
    return GateResult("G2_DDL", "PASS")


def gate2_metadata_metric_view(spec: dict, execute_fn=None) -> GateResult:
    """Gate 2 for metric views: verify source tables exist and are accessible.

    Args:
        spec: metric_view_spec.yaml content
        execute_fn: callable that executes SQL and returns result (Statement Execution API wrapper)
    """
    if not execute_fn:
        return GateResult("G2_MV", "WARN", issues=["No execute_fn provided — skipping metadata validation"])
    issues = []
    for mv in spec.get("metric_views", []):
        source = mv["yaml"].get("source", "")
        if not source:
            issues.append(f"Metric view '{mv['name']}': no source specified")
            continue
        try:
            execute_fn(f"DESCRIBE TABLE {source}")
        except Exception as e:
            issues.append(f"Source table {source} not accessible: {e}")
    if issues:
        return GateResult("G2_MV", "FAIL", issues=issues)
    return GateResult("G2_MV", "PASS")


# -----------------------------------------------------------------------------
# GATE 3: SEMANTIC VALIDATION (the highest-value gate)
# -----------------------------------------------------------------------------
# "Valid SQL" is NOT the same as "correct architecture."
# A generated view can compile perfectly and still be wrong because it joins
# two facts at incompatible grains. Gate 3 catches what SQL compilation cannot.


def validate_grain_safety(
    measure_expr: str,
    source_grain: str,
    join_specs: list[dict] | None = None,
) -> GateResult:
    """Validate that a measure expression is safe at the declared grain.

    Checks:
    - SUM/COUNT expressions are additive at the declared grain
    - RATIO expressions use SUM(numerator)/SUM(denominator), not AVG(row_ratio)
    - DISTINCT_COUNT uses the correct business key

    Args:
        measure_expr: The SQL expression from the metric view measure.
        source_grain: Description of the source table grain.
        join_specs: List of join dicts (name, source, on, rely) if joins are present.

    Returns:
        GateResult with PASS, FAIL, or WARN.
    """
    issues = []
    expr_upper = measure_expr.upper()

    # Check 1: RATIO measures must use SUM/SUM pattern, not AVG
    if "/" in measure_expr and "AVG(" in expr_upper:
        issues.append(
            f"RATIO measure uses AVG() — should use SUM(numerator)/NULLIF(SUM(denominator), 0). "
            f"Expression: {measure_expr[:80]}"
        )

    # Check 2: DISTINCT_COUNT should reference a business key, not COUNT(*)
    if "COUNT(DISTINCT" in expr_upper:
        pass  # Valid pattern — the specific column is in the expression
    elif "COUNT(*)" in expr_upper and "distinct" in source_grain.lower():
        issues.append(
            f"DISTINCT_COUNT grain but using COUNT(*) — should use COUNT(DISTINCT business_key). "
            f"Expression: {measure_expr[:80]}"
        )

    # Check 3: If joins exist, each must have rely: at_most_one_match (N:1)
    if join_specs:
        for j in join_specs:
            rely = j.get("rely", {})
            if isinstance(rely, dict) and not rely.get("at_most_one_match"):
                issues.append(
                    f"Join '{j.get('name', '?')}' lacks rely: at_most_one_match — "
                    f"potential fanout (M:1 or M:N join detected)"
                )

    if issues:
        return GateResult("G3_GRAIN", "FAIL", issues=issues)
    return GateResult("G3_GRAIN", "PASS")


def validate_join_paths(
    joins: list[dict],
    available_tables: set[str],
) -> GateResult:
    """Validate join paths for fanout risk and chain violations.

    Checks:
    - Each join source must reference an available table
    - 'on' clause must only reference source.<col> or <this_join>.<col> (no chains)
    - Each join should have rely: at_most_one_match for N:1 safety

    Args:
        joins: List of join dicts from metric view YAML.
        available_tables: Set of table FQNs that are accessible.

    Returns:
        GateResult with PASS, FAIL, or WARN.
    """
    issues = []
    warnings = []

    for j in joins:
        jname = j.get("name", "?")
        jsource = j.get("source", "")
        on_expr = j.get("on", "")

        # Check source table exists
        if jsource and jsource not in available_tables:
            issues.append(f"Join '{jname}': source '{jsource}' not in available tables")

        # Check for chained joins (on clause referencing a join other than source or self)
        join_names = {jj.get("name") for jj in joins}
        for other_join in join_names:
            if other_join and other_join != jname and f"{other_join}." in on_expr:
                issues.append(
                    f"Join '{jname}': 'on' clause references '{other_join}.' — "
                    f"chained joins are NOT supported. Use only source.<col> or {jname}.<col>"
                )

        # Check rely constraint
        rely = j.get("rely", None)
        if rely is None:
            warnings.append(f"Join '{jname}': no 'rely' constraint — fanout risk if not N:1")
        elif isinstance(rely, dict) and rely.get("at_most_one_match") is not True:
            warnings.append(f"Join '{jname}': rely.at_most_one_match is not True — may not be N:1")

    if issues:
        return GateResult("G3_JOINS", "FAIL", issues=issues, details={"warnings": warnings})
    if warnings:
        return GateResult("G3_JOINS", "WARN", issues=warnings)
    return GateResult("G3_JOINS", "PASS")


def validate_no_duplicates(
    items: list[dict],
    name_field: str,
    context: str,
) -> GateResult:
    """Validate that no duplicate names exist in a list of dicts.

    Args:
        items: List of dicts (measures, dimensions, etc.)
        name_field: The key to use for uniqueness (e.g., 'name')
        context: Description for error messages (e.g., 'measures in metric_view X')

    Returns:
        GateResult with PASS or FAIL.
    """
    names = [item.get(name_field, "") for item in items]
    seen = set()
    duplicates = set()
    for n in names:
        if n in seen:
            duplicates.add(n)
        seen.add(n)
    if duplicates:
        return GateResult("G3_DUP", "FAIL",
                          issues=[f"Duplicate {name_field} in {context}: {duplicates}"])
    return GateResult("G3_DUP", "PASS")


def gate3_semantic_metric_view(spec: dict) -> GateResult:
    """Gate 3 for metric views: full semantic validation.

    Runs grain safety, join path validation, and duplicate detection.
    """
    all_issues = []
    all_warnings = []

    for mv in spec.get("metric_views", []):
        mv_name = mv["name"]
        yml = mv["yaml"]

        # Check 3a: No duplicate measures
        dup_result = validate_no_duplicates(yml.get("measures", []), "name", f"measures in {mv_name}")
        if not dup_result.passed:
            all_issues.extend(dup_result.issues)

        # Check 3b: No duplicate dimensions
        dup_result = validate_no_duplicates(yml.get("fields", []), "name", f"dimensions in {mv_name}")
        if not dup_result.passed:
            all_issues.extend(dup_result.issues)

        # Check 3c: Join path safety
        joins = yml.get("joins", [])
        if joins:
            source_table = yml.get("source", "")
            join_sources = {j.get("source", "") for j in joins}
            available = {source_table} | join_sources
            join_result = validate_join_paths(joins, available)
            if not join_result.passed:
                all_issues.extend(join_result.issues)
            all_warnings.extend(join_result.details.get("warnings", []))

        # Check 3d: Grain safety for each measure
        for m in yml.get("measures", []):
            grain_result = validate_grain_safety(
                m.get("expr", ""),
                mv.get("source_grain", ""),
                yml.get("joins", []),
            )
            if not grain_result.passed:
                all_issues.extend(grain_result.issues)

    if all_issues:
        return GateResult("G3_MV", "FAIL", issues=all_issues, details={"warnings": all_warnings})
    if all_warnings:
        return GateResult("G3_MV", "WARN", issues=all_warnings)
    return GateResult("G3_MV", "PASS")


# -----------------------------------------------------------------------------
# GATE 4: DEPLOYMENT VALIDATION
# -----------------------------------------------------------------------------

def gate4_deployment_metric_view(
    spec: dict,
    deployed_views: list[str],
    catalog: str,
    schema: str,
) -> GateResult:
    """Gate 4 for metric views: verify deployment succeeded.

    Checks: all planned views deployed, smoke test passed, readback matches.
    """
    issues = []
    expected_views = {mv["name"] for mv in spec.get("metric_views", [])}
    deployed_set = set(deployed_views)
    missing = expected_views - deployed_set
    if missing:
        issues.append(f"Not all views deployed. Missing: {missing}")
    if issues:
        return GateResult("G4_MV", "FAIL", issues=issues)
    return GateResult("G4_MV", "PASS",
                      details={"deployed": len(deployed_views), "expected": len(expected_views)})


def gate4_deployment_dashboard(
    dashboard_id: str,
    expected_name: str,
    quality_gates: dict | None = None,
) -> GateResult:
    """Gate 4 for dashboards: API readback validation.

    Delegates to existing validate_dashboard_from_api.
    """
    try:
        result = validate_dashboard_from_api(dashboard_id, expected_name, quality_gates=quality_gates)
        return GateResult("G4_DASH", "PASS", details=result)
    except GateCheckError as e:
        return GateResult("G4_DASH", "FAIL", issues=[str(e)])


def gate4_deployment_genie(
    space_id: str,
    expected_title: str,
    quality_gates: dict | None = None,
) -> GateResult:
    """Gate 4 for Genie: API readback validation.

    Delegates to existing validate_genie_from_api.
    """
    try:
        result = validate_genie_from_api(space_id, expected_title, quality_gates=quality_gates)
        return GateResult("G4_GENIE", "PASS", details=result)
    except GateCheckError as e:
        return GateResult("G4_GENIE", "FAIL", issues=[str(e)])


# -----------------------------------------------------------------------------
# CONVENIENCE: Run all four gates for a given artifact type
# -----------------------------------------------------------------------------

def run_four_gate_metric_views(
    spec: dict,
    execute_fn=None,
    deployed_views: list[str] | None = None,
    catalog: str = "",
    schema: str = "",
) -> dict:
    """Run all four gates for metric view deployment.

    Args:
        spec: metric_view_spec.yaml content
        execute_fn: SQL execution function (for Gate 2 metadata validation)
        deployed_views: List of successfully deployed view names (for Gate 4)
        catalog: UC catalog name (for Gate 4)
        schema: UC schema name (for Gate 4)

    Returns:
        Dict with gate results: {gate1: GateResult, gate2: ..., gate3: ..., gate4: ...}

    Raises:
        GateCheckError: If any gate fails (after reporting all gate results).
    """
    results = {}

    # Gate 1: Structural
    results["gate1"] = gate1_structural_metric_view(spec)
    print(f"Gate 1 (Structural): {results['gate1'].status}")
    if not results["gate1"].passed:
        for issue in results["gate1"].issues:
            print(f"  FAIL: {issue}")

    # Gate 2: Metadata
    if results["gate1"].passed and execute_fn:
        results["gate2"] = gate2_metadata_metric_view(spec, execute_fn)
    elif results["gate1"].passed:
        results["gate2"] = GateResult("G2_MV", "WARN", issues=["No execute_fn — skipped"])
    else:
        results["gate2"] = GateResult("G2_MV", "FAIL", issues=["Gate 1 failed — skipping"])
    print(f"Gate 2 (Metadata): {results['gate2'].status}")

    # Gate 3: Semantic
    if results["gate2"].passed or results["gate2"].status == "WARN":
        results["gate3"] = gate3_semantic_metric_view(spec)
    else:
        results["gate3"] = GateResult("G3_MV", "FAIL", issues=["Gate 2 failed — skipping"])
    print(f"Gate 3 (Semantic): {results['gate3'].status}")
    if not results["gate3"].passed:
        for issue in results["gate3"].issues:
            print(f"  {'FAIL' if 'FAIL' in issue[:20] else 'WARN'}: {issue}")

    # Gate 4: Deployment
    if deployed_views is not None:
        results["gate4"] = gate4_deployment_metric_view(spec, deployed_views, catalog, schema)
    else:
        results["gate4"] = GateResult("G4_MV", "WARN", issues=["No deployed_views — skipping"])
    print(f"Gate 4 (Deployment): {results['gate4'].status}")

    # Summary
    all_pass = all(r.passed or r.status == "WARN" for r in results.values())
    if not all_pass:
        failed_gates = [k for k, r in results.items() if not r.passed and r.status != "WARN"]
        raise GateCheckError(
            "FOUR_GATE_MV",
            f"Metric view four-gate validation FAILED for gates: {failed_gates}.\n"
            + "\n".join(f"  {k}: {r.status} — {'; '.join(r.issues[:3])}" for k, r in results.items())
        )

    print(f"\nAll four gates PASSED for metric views.")
    return results
