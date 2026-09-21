# =============================================================================
# ERD Validation Utilities — Deterministic Data Type Validation
# =============================================================================
#
# This module provides deterministic validation and safe normalization of data types
# extracted by the vision model during ERD image parsing (Step 2).
#
# PURPOSE:
# Vision models may truncate data type definitions when processing ERD images.
# Precision, scale, and length are schema intent, so this utility never guesses
# missing values. It rejects incomplete or invalid types before erd_parsed.yaml
# is written and routes the caller back to authoritative ERD evidence.
#
# USAGE:
# Call validate_and_fix_datatypes() on the parsed tables list AFTER vision model
# returns and BEFORE writing erd_parsed.yaml:
#
#   tables, normalizations = validate_and_fix_datatypes(parsed_tables)
#   # Only whitespace is normalized; semantic type components are never inferred.
#
# GUARANTEE:
# A PASS guarantees that every column datatype is complete and valid. An
# incomplete datatype remains unchanged and is returned as a validation error.
# =============================================================================

import re
from typing import Any


# =============================================================================
# SECTION 1: Core Validation & Fix
# =============================================================================

def validate_and_fix_datatypes(tables: list[dict]) -> tuple[list[dict], list[str]]:
    """Apply only semantics-preserving whitespace normalization.

    The public function name is retained for compatibility with existing
    authenticated callers. It MUST NOT invent a datatype, precision, scale,
    length, or parenthesis. Completeness is enforced by
    :func:`validate_schema_for_ddl`.

    Args:
        tables: List of table dicts from ERD parsing. Expected structure:
            [{"name": "table_name", "observed": {"columns": [{"name": "col", "datatype": "..."}]}}]

    Returns:
        Tuple of (tables, safe_normalizations). Only leading/trailing
        whitespace is removed.
    """
    normalizations = []

    for table in tables:
        table_name = table.get('name', 'unknown')
        columns = table.get('observed', {}).get('columns', [])

        for col in columns:
            col_name = col.get('name', 'unknown')
            dtype = col.get('datatype', '').strip()
            original = col.get('datatype', '')
            if isinstance(original, str) and original != dtype:
                col['datatype'] = dtype
                normalizations.append(
                    f"{table_name}.{col_name}: trimmed surrounding datatype whitespace"
                )

    # Report
    if normalizations:
        print(f"ERD Data Type Validation: {len(normalizations)} safe normalization(s):")
        for item in normalizations[:20]:
            print(f"    • {item}")
        if len(normalizations) > 20:
            print(f"    ... and {len(normalizations) - 20} more")
    else:
        print("✓ ERD Data Type Validation: no datatype normalization required")

    return tables, normalizations


# =============================================================================
# SECTION 2: Strict Type Validation
# =============================================================================

_SIMPLE_TYPES = {
    'bigint', 'int', 'integer', 'smallint', 'tinyint', 'long',
    'double', 'float', 'boolean', 'string', 'binary',
    'date', 'timestamp', 'timestamp_ntz',
}


def validate_datatype(dtype: Any) -> str | None:
    """Return an error for an incomplete/unsupported Databricks SQL datatype."""
    if not isinstance(dtype, str) or not dtype.strip():
        return "empty datatype; authoritative ERD evidence is required"

    value = dtype.strip()
    lower = value.lower()
    if lower in _SIMPLE_TYPES:
        return None

    decimal_match = re.fullmatch(
        r'(decimal|numeric)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)',
        lower,
    )
    if decimal_match:
        precision = int(decimal_match.group(2))
        scale = int(decimal_match.group(3))
        if not 1 <= precision <= 38:
            return f"decimal precision {precision} is outside 1..38"
        if not 0 <= scale <= precision:
            return f"decimal scale {scale} is outside 0..{precision}"
        return None

    if re.match(r'^(decimal|numeric)\b', lower):
        return "decimal/numeric must include complete precision and scale as (p,s)"

    length_match = re.fullmatch(r'(varchar|char|nvarchar)\s*\(\s*(\d+)\s*\)', lower)
    if length_match:
        if int(length_match.group(2)) < 1:
            return "character length must be a positive integer"
        return None

    if re.match(r'^(varchar|char|nvarchar)\b', lower):
        return "varchar/char/nvarchar must include a complete positive length"

    return f"unsupported or malformed datatype '{value}'"


# =============================================================================
# SECTION 3: Full Schema Validation (DDL-ready check)
# =============================================================================

def validate_schema_for_ddl(tables: list[dict]) -> dict:
    """Comprehensive schema validation before DDL generation.

    Checks beyond data types:
    - Every table has a name
    - Every table has at least one column
    - Every column has a name and datatype
    - No duplicate column names within a table
    - At least one PK identified per table
    - Data types are syntactically valid for Databricks SQL

    Returns:
        {"status": "PASS"|"FAIL", "errors": [...], "warnings": [...]}
    """
    errors = []
    warnings = []

    for table in tables:
        table_name = table.get('name')
        if not table_name:
            errors.append("Table found with no name")
            continue

        columns = table.get('observed', {}).get('columns', [])
        if not columns:
            errors.append(f"{table_name}: no columns defined")
            continue

        col_names = []
        has_pk = False

        for col in columns:
            col_name = col.get('name', '')
            dtype = col.get('datatype', '')
            key_marker = col.get('key_marker', '')

            if not col_name:
                errors.append(f"{table_name}: column with empty name")
                continue

            if col_name in col_names:
                errors.append(f"{table_name}: duplicate column '{col_name}'")
            col_names.append(col_name)

            datatype_error = validate_datatype(dtype)
            if datatype_error:
                errors.append(f"{table_name}.{col_name}: {datatype_error}")

            if key_marker == 'PK':
                has_pk = True

        if not has_pk:
            warnings.append(f"{table_name}: no PK marker found (will be inferred)")

    status = "PASS" if not errors else "FAIL"

    if errors:
        print(f"❌ Schema validation FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"    • {e}")
    else:
        print(f"✓ Schema validation PASSED")

    if warnings:
        print(f"  ⚠️  {len(warnings)} warning(s):")
        for w in warnings[:10]:
            print(f"    • {w}")

    return {"status": status, "errors": errors, "warnings": warnings}


# =============================================================================
# SECTION 4: Convenience — Combined Validation Pipeline
# =============================================================================

def validate_erd_output(tables: list[dict]) -> tuple[list[dict], dict]:
    """Run the FULL validation pipeline on ERD-parsed tables.

    This is the ONE function the orchestrating agent should call after
    vision model parsing. It:
    1. Applies only semantics-preserving whitespace normalization
    2. Validates the full schema is DDL-ready
    3. Returns the fixed tables + validation report

    Usage:
        tables, report = validate_erd_output(parsed_tables)
        assert report['status'] == 'PASS', f"ERD validation failed: {report['errors']}"
        # Now safe to write erd_parsed.yaml and generate DDL
    """
    print("═" * 60)
    print("ERD OUTPUT VALIDATION PIPELINE")
    print("═" * 60)

    # Step 1: Apply safe normalization only. Missing type components are never guessed.
    print("\n[1/2] Data type normalization check...")
    tables, normalizations = validate_and_fix_datatypes(tables)

    # Step 2: Full schema validation
    print("\n[2/2] Schema structure validation...")
    report = validate_schema_for_ddl(tables)
    report['datatype_fixes'] = []
    report['datatype_fixes_count'] = 0
    report['safe_normalizations'] = normalizations
    report['safe_normalizations_count'] = len(normalizations)

    print("\n" + "═" * 60)
    if report['status'] == 'PASS':
        print(f"✅ ERD VALIDATION PASSED — {len(tables)} tables, no datatype components inferred")
    else:
        print(f"❌ ERD VALIDATION FAILED — {len(report['errors'])} errors must be resolved")
    print("═" * 60)

    return tables, report
