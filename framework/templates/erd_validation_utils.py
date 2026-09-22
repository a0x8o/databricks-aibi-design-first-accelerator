# =============================================================================
# ERD Validation Utilities — Deterministic Data Type Validation
# =============================================================================
#
# This module provides deterministic validation and safe normalization of data types
# extracted by the vision model during ERD image parsing (Step 2).
#
# PURPOSE:
# Vision models may truncate data type definitions when processing ERD images.
# Precision, scale, and length are schema intent. Strict validation remains the
# default. A separate, explicitly invoked resolver can repair datatype-only
# defects for greenfield synthetic targets and returns structured provenance for
# schema_assumptions.yaml. It is never used for source/live schema authority.
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
_SIMPLE_TYPE_ALIASES = {'integer': 'int', 'long': 'bigint'}


def validate_datatype(dtype: Any) -> str | None:
    """Return an error for an incomplete/unsupported Databricks SQL datatype."""
    if not isinstance(dtype, str) or not dtype.strip():
        return "empty datatype; authoritative ERD evidence is required"

    value = dtype.strip()
    lower = value.lower()
    if lower in _SIMPLE_TYPES:
        return None

    decimal_match = re.fullmatch(
        r'(decimal|dec|numeric)(?:\s*\(\s*(\d+)(?:\s*,\s*(\d+))?\s*\))?',
        lower,
    )
    if decimal_match:
        # Databricks documents DECIMAL as DECIMAL[(p[,s])], with defaults
        # p=10 and s=0. Expanding those defaults is canonicalization, not
        # application inference.
        precision = int(decimal_match.group(2) or 10)
        scale = int(decimal_match.group(3) or 0)
        if not 1 <= precision <= 38:
            return f"decimal precision {precision} is outside 1..38"
        if not 0 <= scale <= precision:
            return f"decimal scale {scale} is outside 0..{precision}"
        return None

    if re.match(r'^(decimal|dec|numeric)\b', lower):
        return f"decimal/numeric value {value!r} is malformed or truncated"

    length_match = re.fullmatch(r'(varchar|char|nvarchar)\s*\(\s*(\d+)\s*\)', lower)
    if length_match:
        if int(length_match.group(2)) < 1:
            return "character length must be a positive integer"
        return None

    if re.match(r'^(varchar|char|nvarchar)\b', lower):
        return "varchar/char/nvarchar must include a complete positive length"

    return f"unsupported or malformed datatype '{value}'"


def canonicalize_datatype(dtype: Any) -> str:
    """Canonicalize representation and documented Databricks defaults."""
    error = validate_datatype(dtype)
    if error:
        raise ValueError(error)
    value = re.sub(r'\s+', '', dtype).lower()
    value = _SIMPLE_TYPE_ALIASES.get(value, value)
    if value in _SIMPLE_TYPES or value in _SIMPLE_TYPE_ALIASES.values():
        return value
    decimal_match = re.fullmatch(
        r'(decimal|dec|numeric)(?:\((\d+)(?:,(\d+))?\))?', value
    )
    if decimal_match:
        precision = int(decimal_match.group(2) or 10)
        scale = int(decimal_match.group(3) or 0)
        return f"decimal({precision},{scale})"
    length_match = re.fullmatch(r'(varchar|char|nvarchar)\((\d+)\)', value)
    if length_match:
        return f"{length_match.group(1)}({int(length_match.group(2))})"
    raise ValueError(f"unsupported or malformed datatype {dtype!r}")


# =============================================================================
# SECTION 2A: Governed Resolution for Greenfield Synthetic Targets
# =============================================================================

DATATYPE_RESOLUTION_POLICY_ID = "GREENFIELD_SYNTHETIC_DATATYPE_RESOLUTION_V1"

_SEMANTIC_TOKENS = {
    "MONETARY": {
        "amt", "amount", "allowed", "balance", "billed", "charge", "coinsurance",
        "copay", "cost", "deduct", "expense", "fee", "net", "paid", "payment",
        "premium", "price", "revenue",
    },
    "RATIO": {"factor", "pct", "percent", "percentage", "rate", "ratio"},
    "MEASUREMENT": {
        "dose", "dosage", "duration", "height", "measurement", "qty", "quantity",
        "volume", "weight",
    },
    "COUNT": {"count", "cnt", "nbr", "num", "number", "rank", "seq", "sequence"},
}
_DECIMAL_DEFAULTS = {
    "MONETARY": (38, 4),
    "RATIO": (38, 6),
    "MEASUREMENT": (38, 4),
    "COUNT": (38, 0),
    "GENERIC": (38, 18),
}
_TYPE_SYNONYMS = {
    "bit": "boolean",
    "bool": "boolean",
    "byte": "tinyint",
    "datetime": "timestamp",
    "datetime2": "timestamp",
    "int16": "smallint",
    "int32": "int",
    "int64": "bigint",
    "json": "string",
    "real": "float",
    "short": "smallint",
    "text": "string",
    "uuid": "string",
    "xml": "string",
}


def _semantic_family(column_name: Any) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", str(column_name or "").lower()))
    for family in ("MONETARY", "RATIO", "MEASUREMENT", "COUNT"):
        if tokens & _SEMANTIC_TOKENS[family]:
            return family
    return "GENERIC"


def _strict_decimal_parts(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"\s*(?:decimal|dec|numeric)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    precision, scale = int(match.group(1)), int(match.group(2))
    if 1 <= precision <= 38 and 0 <= scale <= precision:
        return precision, scale
    return None


def _strict_majority(values: list[int]) -> int | None:
    if not values:
        return None
    counts = {value: values.count(value) for value in set(values)}
    scale, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return scale if count * 2 > len(values) else None


def _peer_scale(
    tables: list[dict], table_name: str, column_name: str, family: str
) -> tuple[int | None, str | None, list[str]]:
    same_table = []
    global_values = []
    for table in tables:
        for column in table.get("observed", {}).get("columns", []):
            if table.get("name") == table_name and column.get("name") == column_name:
                continue
            if _semantic_family(column.get("name")) != family:
                continue
            parts = _strict_decimal_parts(column.get("datatype"))
            if parts is None:
                continue
            global_values.append(parts[1])
            if table.get("name") == table_name:
                same_table.append(parts[1])
    scale = _strict_majority(same_table)
    if scale is not None:
        return scale, "SAME_TABLE_SEMANTIC_PEER_MODE", [f"peer_scales={same_table!r}"]
    scale = _strict_majority(global_values)
    if scale is not None:
        return scale, "GLOBAL_SEMANTIC_PEER_MODE", [f"peer_scales={global_values!r}"]
    return None, None, []


def _fallback_from_column_name(column_name: Any) -> tuple[str, str, list[str]]:
    name = str(column_name or "").lower()
    tokens = set(re.findall(r"[a-z0-9]+", name))
    family = _semantic_family(name)
    if family != "GENERIC":
        precision, scale = _DECIMAL_DEFAULTS[family]
        return f"decimal({precision},{scale})", "SEMANTIC_NUMERIC_POLICY", [f"family={family}"]
    if tokens & {"date", "dob"} or name.endswith("_dt"):
        return "date", "SEMANTIC_DATE_POLICY", ["date-like column name"]
    if tokens & {"timestamp", "datetime", "dttm"} or name.endswith(("_ts", "_at")):
        return "timestamp", "SEMANTIC_TIMESTAMP_POLICY", ["timestamp-like column name"]
    if name.startswith(("is_", "has_")) or tokens & {"bool", "boolean", "flag", "ind", "indicator"}:
        return "boolean", "SEMANTIC_BOOLEAN_POLICY", ["boolean-like column name"]
    return "string", "SAFE_STRING_FALLBACK", ["no reliable numeric or temporal semantic evidence"]


def resolve_greenfield_synthetic_datatypes(
    tables: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Make datatype defects total for generated synthetic schemas.

    The caller owns the scope check. This function must be called only after
    authoritative reparse attempts are exhausted and only for a generated
    greenfield target with synthetic data enabled. It never changes table or
    column identity. Resolution priority is exact syntax, recoverable syntax,
    semantic peer evidence, release-pinned semantic defaults, then STRING.
    """
    if not isinstance(tables, list) or not tables:
        raise ValueError("structural ERD defect: non-empty tables list is required")
    decisions = []
    for table in tables:
        if not isinstance(table, dict):
            raise ValueError("structural ERD defect: table entry is not a mapping")
        table_name = table.get("name", "unknown")
        observed = table.get("observed")
        columns = observed.get("columns") if isinstance(observed, dict) else None
        if not isinstance(columns, list) or not columns:
            raise ValueError(f"structural ERD defect: {table_name} has no observed columns")
        for column in columns:
            if not isinstance(column, dict):
                raise ValueError(
                    f"structural ERD defect: {table_name} contains a non-mapping column"
                )
            column_name = column.get("name", "unknown")
            raw = column.get("datatype")
            raw_text = raw.strip() if isinstance(raw, str) else ""
            try:
                resolved = canonicalize_datatype(raw_text)
                compact = re.sub(r"\s+", "", raw_text).lower()
                if re.fullmatch(r"(?:decimal|dec|numeric)(?:\(\d+\))?", compact):
                    decisions.append({
                        "table": table_name,
                        "column": column_name,
                        "raw_datatype": raw,
                        "resolved_datatype": resolved,
                        "resolution_source": "DATABRICKS_DEFAULT_EXPANSION",
                        "confidence": "HIGH",
                        "semantic_family": _semantic_family(column_name),
                        "inference": False,
                        "observed": True,
                        "evidence": ["documented DECIMAL default precision=10 and scale=0"],
                    })
                column["datatype"] = resolved
                continue
            except ValueError:
                pass

            compact = re.sub(r"\s+", "", raw_text).lower()
            family = _semantic_family(column_name)
            source = None
            evidence = []
            confidence = "MEDIUM"

            if re.match(r"^(decimal|dec|numeric|number)\b", compact):
                numbers = [int(value) for value in re.findall(r"\d+", compact)]
                observed_precision = numbers[0] if numbers else None
                observed_scale = numbers[1] if len(numbers) > 1 else None
                if observed_scale is not None:
                    scale = min(max(observed_scale, 0), 37)
                    precision = min(max(observed_precision or 38, scale + 1), 38)
                    source = "DECIMAL_SYNTAX_RECOVERY"
                    evidence = [
                        f"visible_precision={observed_precision}",
                        f"visible_scale={observed_scale}",
                    ]
                    confidence = "HIGH"
                else:
                    scale, source, evidence = _peer_scale(
                        tables, table_name, column_name, family
                    )
                    if scale is None:
                        _, scale = _DECIMAL_DEFAULTS[family]
                        source = "SEMANTIC_DECIMAL_POLICY"
                        evidence = [f"family={family}"]
                    precision = (
                        observed_precision
                        if observed_precision and observed_precision > 0
                        else _DECIMAL_DEFAULTS[family][0]
                    )
                    precision = min(max(precision, scale + (1 if scale else 0)), 38)
                    scale = min(scale, precision)
                resolved = f"decimal({precision},{scale})"
            elif re.match(r"^(varchar|char|nvarchar)\b", compact):
                resolved = "string"
                source = "NON_TRUNCATING_STRING_FALLBACK"
                evidence = ["character length was unavailable or invalid"]
                confidence = "HIGH"
            elif compact in _TYPE_SYNONYMS:
                resolved = _TYPE_SYNONYMS[compact]
                source = "DATABRICKS_TYPE_SYNONYM"
                evidence = [f"source_type={raw_text!r}"]
                confidence = "HIGH"
            else:
                resolved, source, evidence = _fallback_from_column_name(column_name)
                confidence = "LOW"

            column["datatype"] = resolved
            decisions.append({
                "table": table_name,
                "column": column_name,
                "raw_datatype": raw,
                "resolved_datatype": resolved,
                "resolution_source": source,
                "confidence": confidence,
                "semantic_family": family,
                "inference": True,
                "observed": False,
                "evidence": evidence,
            })
    return tables, decisions


def validate_table_spec_projection(erd_tables: list[dict], table_spec: dict) -> dict:
    """Prove table_spec is an exact physical projection of validated ERD tables.

    The function is intentionally read-only. It compares ordered table and column
    identities plus canonical datatypes, while preserving precision, scale, and
    length. It never fills, repairs, or adopts a datatype from the other input.
    """
    errors = []
    erd_datatype_errors = []
    table_spec_datatype_errors = []
    if not isinstance(erd_tables, list) or not erd_tables:
        errors.append("erd_parsed.yaml has no non-empty tables list")
        erd_tables = []
    spec_tables = table_spec.get('tables') if isinstance(table_spec, dict) else None
    if not isinstance(spec_tables, list) or not spec_tables:
        errors.append("table_spec.yaml has no non-empty tables list")
        spec_tables = []

    erd_names = [table.get('name') for table in erd_tables if isinstance(table, dict)]
    spec_names = [table.get('name') for table in spec_tables if isinstance(table, dict)]
    if len(erd_names) != len(set(erd_names)):
        errors.append("erd_parsed.yaml contains duplicate table names")
    if len(spec_names) != len(set(spec_names)):
        errors.append("table_spec.yaml contains duplicate table names")
    if erd_names != spec_names:
        errors.append(
            f"table inventory/order mismatch: ERD={erd_names!r}, table_spec={spec_names!r}"
        )

    spec_by_name = {
        table.get('name'): table
        for table in spec_tables
        if isinstance(table, dict) and isinstance(table.get('name'), str)
    }
    for erd_table in erd_tables:
        if not isinstance(erd_table, dict):
            errors.append("erd_parsed.yaml contains a non-mapping table entry")
            continue
        table_name = erd_table.get('name')
        spec_table = spec_by_name.get(table_name)
        if spec_table is None:
            continue
        erd_columns = erd_table.get('observed', {}).get('columns', [])
        spec_columns = spec_table.get('columns', [])
        if not isinstance(erd_columns, list) or not isinstance(spec_columns, list):
            errors.append(f"{table_name}: columns must be lists in both artifacts")
            continue
        erd_column_names = [column.get('name') for column in erd_columns]
        spec_column_names = [column.get('name') for column in spec_columns]
        if len(erd_column_names) != len(set(erd_column_names)):
            errors.append(f"{table_name}: erd_parsed.yaml contains duplicate column names")
        if len(spec_column_names) != len(set(spec_column_names)):
            errors.append(f"{table_name}: table_spec.yaml contains duplicate column names")
        if erd_column_names != spec_column_names:
            errors.append(
                f"{table_name}: column inventory/order mismatch: "
                f"ERD={erd_column_names!r}, table_spec={spec_column_names!r}"
            )
            continue
        for erd_column, spec_column in zip(erd_columns, spec_columns):
            column_name = erd_column.get('name')
            erd_type = erd_column.get('datatype')
            spec_type = spec_column.get('type')
            try:
                canonical_erd_type = canonicalize_datatype(erd_type)
            except ValueError as exc:
                message = f"{table_name}.{column_name}: invalid ERD datatype: {exc}"
                errors.append(message)
                erd_datatype_errors.append(message)
                continue
            try:
                canonical_spec_type = canonicalize_datatype(spec_type)
            except ValueError as exc:
                message = f"{table_name}.{column_name}: invalid table-spec datatype: {exc}"
                errors.append(message)
                table_spec_datatype_errors.append(message)
                continue
            if canonical_erd_type != canonical_spec_type:
                errors.append(
                    f"{table_name}.{column_name}: datatype mismatch: "
                    f"ERD={erd_type!r}, table_spec={spec_type!r}"
                )

    failure_code = None
    if errors:
        failure_code = "ERD_EXTRACTION_ERROR" if erd_datatype_errors else "SCHEMA_CONTRACT_ERROR"
    return {
        "status": "PASS" if not errors else "FAIL",
        "failure_code": failure_code,
        "errors": errors,
        "erd_datatype_errors": erd_datatype_errors,
        "table_spec_datatype_errors": table_spec_datatype_errors,
    }


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

    seen_table_names = set()
    for table in tables:
        table_name = table.get('name')
        if not isinstance(table_name, str) or not table_name:
            errors.append("Table found with no name")
            continue
        if (len(table_name) > 255 or any(
                c in '. /`' or ord(c) < 32 or ord(c) == 127 for c in table_name)):
            errors.append(f"GENERATED_IDENTIFIER_ERROR: {table_name!r} is not a single UC table name; resolve its source label before DDL")
        if table_name.lower() in seen_table_names:
            errors.append(f"GENERATED_IDENTIFIER_ERROR: case-insensitive table-name collision: {table_name}")
        seen_table_names.add(table_name.lower())

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
