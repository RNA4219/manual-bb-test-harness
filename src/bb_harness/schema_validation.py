"""Package-resource JSON Schema validation helpers."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


def build_format_checker() -> FormatChecker:
    """Return a checker with strict timezone-aware ISO 8601 date-times."""
    checker = FormatChecker()

    @checker.checks("date-time", raises=(TypeError, ValueError))
    def is_date_time(value: object) -> bool:
        if not isinstance(value, str) or not value:
            return False
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    return checker


class SchemaValidationError(ValueError):
    """Raised when an artifact does not conform to its JSON Schema."""


def validate_finite_numbers(value: Any, path: str = "$") -> None:
    """JSON の数値として不正な NaN/Infinity を入れ子も含めて拒否する。"""
    if isinstance(value, float) and not math.isfinite(value):
        raise SchemaValidationError(f"Non-finite JSON number at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            validate_finite_numbers(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_finite_numbers(item, f"{path}[{index}]")


def schema_directory() -> Path:
    """Return packaged runtime schemas, falling back to a source checkout."""
    packaged = Path(__file__).resolve().parent / "schemas"
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[2] / "schemas"


def load_schema(schema_name: str) -> tuple[dict[str, Any], Registry]:
    """Load one schema and a registry for local package-resource references."""
    directory = schema_directory()
    schema: dict[str, Any] | None = None
    resources: list[tuple[str, Resource[Any]]] = []
    for path in directory.glob("*.schema.json"):
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SchemaValidationError(f"Cannot load schema {path.name}: {exc}") from exc
        identifier = candidate.get("$id")
        if isinstance(identifier, str):
            resources.append(
                (
                    identifier,
                    Resource.from_contents(
                        candidate,
                        default_specification=DRAFT202012,
                    ),
                )
            )
        if path.name == schema_name:
            schema = candidate

    if schema is None:
        raise SchemaValidationError(f"Schema not found: {schema_name}")
    return schema, Registry().with_resources(resources)


def validate_artifact(value: dict[str, Any], schema_name: str) -> None:
    """Validate one artifact with local $ref and date-time format support."""
    validate_finite_numbers(value)
    schema, registry = load_schema(schema_name)
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=build_format_checker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
            for error in errors[:5]
        )
        raise SchemaValidationError(f"Schema validation failed ({schema_name}): {detail}")
    from bb_harness.evidence_policy import artifact_contract_errors

    contract_errors = artifact_contract_errors(value, schema_name.removesuffix(".schema.json"))
    if contract_errors:
        raise SchemaValidationError("; ".join(contract_errors))
