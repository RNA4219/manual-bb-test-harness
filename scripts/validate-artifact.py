"""Validate artifact JSON against schema.

Usage:
    python scripts/validate-artifact.py --artifact <file.json> --type <artifact_type>
    python scripts/validate-artifact.py --all <directory>
    python scripts/validate-artifact.py --version

Example:
    python scripts/validate-artifact.py \
        --artifact examples/artifacts/order-cancel.feature_spec.json \
        --type feature_spec

    python scripts/validate-artifact.py --all examples/artifacts/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

__version__ = "0.1.0"

SCHEMA_DIR = Path("schemas")

# Mapping artifact type to schema
ARTifact_SCHEMA_MAP = {
    "feature_spec": "feature_spec.schema.json",
    "test_model": "test_model.schema.json",
    "observation_set": "observation_set.schema.json",
    "risk_register": "risk_register.schema.json",
    "manual_case_set": "manual_case_set.schema.json",
    "effort_plan": "effort_plan.schema.json",
    "gate_decision": "gate_decision.schema.json",
    "release_brief": "release_brief.schema.json",
    "execution_evidence": "execution_evidence.schema.json",
    "forward_test_report": "forward_test_report.schema.json",
}

# Try to import jsonschema
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def load_json(path: Path) -> dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def resolve_schema_refs(schema: dict[str, Any], schema_dir: Path) -> dict[str, Any]:
    """Resolve $ref references in schema by inlining shared_defs."""
    # Load shared_defs
    shared_defs_path = schema_dir / "shared_defs.schema.json"
    shared_defs: dict[str, Any] = {}
    if shared_defs_path.exists():
        shared_defs = load_json(shared_defs_path).get("$defs", {})

    # Initialize $defs in schema
    if "$defs" not in schema:
        schema["$defs"] = {}

    # Merge shared_defs into schema's $defs
    for key, value in shared_defs.items():
        schema["$defs"][key] = value

    # Now resolve $refs that reference shared_defs
    # The $refs like "shared_defs.schema.json#/$defs/SourceRef" become "#/$defs/SourceRef"
    def fix_refs(obj: Any) -> Any:
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            for k, v in obj.items():
                if k == "$ref" and isinstance(v, str):
                    # Convert external ref to internal ref
                    if "shared_defs.schema.json" in v:
                        # Extract the definition name
                        parts = v.split("$defs/")
                        if len(parts) == 2:
                            def_name = parts[1]
                            result[k] = f"#/$defs/{def_name}"
                        else:
                            result[k] = v
                    else:
                        result[k] = v
                else:
                    result[k] = fix_refs(v)
            return result
        elif isinstance(obj, list):
            return [fix_refs(item) for item in obj]
        else:
            return obj

    schema = fix_refs(schema)
    return schema


def detect_artifact_type(path: Path) -> str:
    """Detect artifact type from filename."""
    name_lower = path.name.lower()
    for artifact_type, schema_file in ARTifact_SCHEMA_MAP.items():
        if artifact_type in name_lower:
            return artifact_type
    return ""


def validate_artifact_basic(artifact: dict[str, Any], schema_type: str) -> list[str]:
    """Basic validation without jsonschema library."""
    errors: list[str] = []

    # Check required fields based on type
    required_fields: dict[str, list[str]] = {
        "feature_spec": ["feature_id"],
        "test_model": ["feature_id", "flows"],
        "observation_set": ["feature_id", "observations"],
        "risk_register": ["feature_id", "risks"],
        "manual_case_set": ["feature_id", "manual_cases"],
        "effort_plan": ["feature_id", "phases", "total_estimate_hours"],
        "gate_decision": ["feature_id", "status", "reasons"],
        "release_brief": ["feature_id", "decision", "summary"],
        "execution_evidence": ["run_id", "result"],
    }

    required = required_fields.get(schema_type, [])
    for field in required:
        if field not in artifact:
            errors.append(f"Missing required field: '{field}'")

    return errors


def validate_artifact_jsonschema(
    artifact: dict[str, Any],
    schema: dict[str, Any]
) -> list[str]:
    """Validate using jsonschema library."""
    errors: list[str] = []

    try:
        validator = jsonschema.Draft202012Validator(schema)
        for error in validator.iter_errors(artifact):
            path = "/" + "/".join(str(p) for p in error.path) if error.path else "/"
            errors.append(f"{path}: {error.message}")
    except Exception as e:
        errors.append(f"Validation error: {e}")

    return errors


def validate_artifact(artifact_path: Path, schema_type: str | None = None) -> dict[str, Any]:
    """Validate single artifact file."""
    artifact = load_json(artifact_path)

    # Detect type if not specified
    if not schema_type:
        schema_type = detect_artifact_type(artifact_path)

    if not schema_type:
        return {
            "valid": False,
            "artifact": str(artifact_path),
            "errors": ["Cannot detect artifact type from filename"],
        }

    schema_file = ARTifact_SCHEMA_MAP.get(schema_type)
    if not schema_file:
        return {
            "valid": False,
            "artifact": str(artifact_path),
            "type": schema_type,
            "errors": [f"Unknown artifact type: {schema_type}"],
        }

    schema_path = SCHEMA_DIR / schema_file
    if not schema_path.exists():
        return {
            "valid": False,
            "artifact": str(artifact_path),
            "type": schema_type,
            "errors": [f"Schema file not found: {schema_path}"],
        }

    # Load and resolve schema
    schema = load_json(schema_path)
    schema = resolve_schema_refs(schema, SCHEMA_DIR)

    # Validate
    if HAS_JSONSCHEMA:
        errors = validate_artifact_jsonschema(artifact, schema)
    else:
        errors = validate_artifact_basic(artifact, schema_type)

    return {
        "valid": len(errors) == 0,
        "artifact": str(artifact_path),
        "type": schema_type,
        "errors": errors,
    }


def validate_all(directory: Path) -> list[dict[str, Any]]:
    """Validate all JSON artifacts in directory."""
    results: list[dict[str, Any]] = []

    for f in directory.glob("*.json"):
        if f.name in ["validation-report.json"]:
            continue  # Skip non-artifact files

        result = validate_artifact(f)
        results.append(result)

    return results


def print_report(results: list[dict[str, Any]]) -> int:
    """Print validation report."""
    print("=" * 60)
    print("ARTIFACT VALIDATION REPORT")
    print("=" * 60)

    total_valid = 0
    total_invalid = 0

    for result in results:
        status = "[OK]" if result["valid"] else "[FAIL]"
        print(f"\n{status} {Path(result['artifact']).name}")
        print(f"    Type: {result.get('type', 'unknown')}")

        if not result["valid"]:
            for error in result.get("errors", []):
                print(f"    Error: {error}")
            total_invalid += 1
        else:
            total_valid += 1

    print("\n" + "=" * 60)
    print(f"TOTAL: {total_valid} valid, {total_invalid} invalid")
    if not HAS_JSONSCHEMA:
        print("NOTE: jsonschema library not installed - using basic validation")
        print("      Install: pip install jsonschema")
    print("=" * 60)

    return 0 if total_invalid == 0 else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate artifact JSON against schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        help="Path to artifact JSON file",
    )
    parser.add_argument(
        "--type",
        choices=list(ARTifact_SCHEMA_MAP.keys()),
        help="Artifact type (auto-detected if not specified)",
    )
    parser.add_argument(
        "--all",
        type=Path,
        help="Validate all artifacts in directory",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if any invalid",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"validate-artifact {__version__}",
    )

    args = parser.parse_args()

    try:
        results: list[dict[str, Any]] = []

        if args.all:
            results = validate_all(args.all)
        elif args.artifact:
            result = validate_artifact(args.artifact, args.type)
            results.append(result)
        else:
            print("Error: --artifact or --all required", file=sys.stderr)
            return 1

        exit_code = print_report(results)
        return exit_code if args.strict else 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())