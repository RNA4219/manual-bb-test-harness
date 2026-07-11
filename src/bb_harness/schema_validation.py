"""Package-resource JSON Schema validation helpers."""

from __future__ import annotations

import json
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
    schema, registry = load_schema(schema_name)
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=build_format_checker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        detail = "; ".join(error.message for error in errors[:5])
        raise SchemaValidationError(f"Schema validation failed ({schema_name}): {detail}")
