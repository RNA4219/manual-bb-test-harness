"""被覆エンジン共通の式評価・有限モデル制約。"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from decimal import Decimal, InvalidOperation
from typing import Any

LIMIT = 10000


class ModelError(ValueError):
    """不足・矛盾・未対応を網羅済みに変換しないためのエラー。"""


def canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ModelError("boolean is not numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ModelError(f"invalid numeric value: {value}") from exc
    if not result.is_finite() or abs(result.adjusted()) > 100:
        raise ModelError("numeric value out of supported range")
    return result


def evaluate(node: dict[str, Any], data: dict[str, Any], depth: int = 0) -> Any:
    """許可されたASTだけを評価する。Python式や動的な関数名は受け付けない。"""
    if depth > 24 or not isinstance(node, dict):
        raise ModelError("invalid expression or expression depth exceeded")
    if set(node) == {"var"}:
        if node["var"] not in data:
            raise ModelError(f"unknown variable: {node['var']}")
        return data[node["var"]]
    if set(node) == {"const"}:
        value = node["const"]
        return (
            decimal(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else value
        )
    if set(node) != {"op", "args"} or not isinstance(node["args"], list):
        raise ModelError("invalid expression shape")
    op, args = node["op"], node["args"]
    if op not in {
        "and",
        "or",
        "not",
        "eq",
        "neq",
        "lt",
        "lte",
        "gt",
        "gte",
        "add",
        "sub",
        "mul",
        "div",
    }:
        raise ModelError(f"unsupported expression operator: {op}")
    if (
        len(args) > 16
        or len(args) < 1
        or (op == "not" and len(args) != 1)
        or (op not in {"and", "or", "not"} and len(args) != 2)
    ):
        raise ModelError(f"invalid expression arity: {op}")
    values = [evaluate(arg, data, depth + 1) for arg in args]
    if op in {"and", "or", "not"}:
        if any(type(value) is not bool for value in values):
            raise ModelError("boolean expression required")
        return all(values) if op == "and" else any(values) if op == "or" else not values[0]
    left, right = values
    if op in {"eq", "neq"}:
        equal = left == right and not (isinstance(left, bool) != isinstance(right, bool))
        return equal if op == "eq" else not equal
    left, right = decimal(left), decimal(right)
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "add":
        return decimal(left + right)
    if op == "sub":
        return decimal(left - right)
    if op == "mul":
        return decimal(left * right)
    if right == 0:
        raise ModelError("division by zero")
    return decimal(left / right)


def holds(constraints: list[dict], data: dict) -> bool:
    values = [evaluate(expr, data) for expr in constraints]
    if any(type(value) is not bool for value in values):
        raise ModelError("constraint must be boolean")
    return all(values)


def indexed(items: list[dict], label: str) -> dict[str, dict]:
    result = {item["id"]: item for item in items}
    if len(result) != len(items):
        raise ModelError(f"duplicate {label} IDs")
    return result


def typed_data(data: dict, parameters: dict[str, dict]) -> dict:
    result = {}
    for key, value in data.items():
        if key not in parameters:
            raise ModelError(f"unknown parameter: {key}")
        param = parameters[key]
        kind = param["type"]
        if kind in {"integer", "decimal", "number"}:
            value = decimal(value)
            if kind == "integer" and value != value.to_integral_value():
                raise ModelError(f"integer required: {key}")
            if "step" in param:
                step = decimal(param["step"])
                if step <= 0 or value % step != 0:
                    raise ModelError(f"precision/step mismatch: {key}")
            if "precision" in param:
                precision = param["precision"]
                if precision > 100 or value * (Decimal(10) ** precision) % 1 != 0:
                    raise ModelError(f"decimal precision mismatch: {key}")
            if "minimum" in param and value < decimal(param["minimum"]):
                raise ModelError(f"below minimum: {key}")
            if "maximum" in param and value > decimal(param["maximum"]):
                raise ModelError(f"above maximum: {key}")
        elif kind == "boolean" and type(value) is not bool:
            raise ModelError(f"boolean required: {key}")
        elif kind in {"string", "date", "datetime"} and not isinstance(value, str):
            raise ModelError(f"string required: {key}")
        if "values" in param and not any(
            value == (decimal(item) if kind in {"integer", "decimal", "number"} else item)
            and isinstance(value, bool) == isinstance(item, bool)
            for item in param["values"]
        ):
            raise ModelError(f"value outside declared domain: {key}")
        result[key] = value
    return result


def configurations(model: dict, parameters: dict[str, dict]) -> list[dict]:
    ids = model["parameter_ids"]
    if len(set(ids)) != len(ids) or not ids:
        raise ModelError("parameter IDs must be nonempty and unique")
    if any(key not in parameters or not parameters[key].get("values") for key in ids):
        raise ModelError("explicit finite parameter values required")
    choices = [parameters[key]["values"] for key in ids]
    if math.prod(map(len, choices)) > LIMIT:
        raise ModelError(f"finite configuration limit exceeded: {LIMIT}")
    if any(len({canonical(value) for value in values}) != len(values) for values in choices):
        raise ModelError("duplicate parameter values")
    result = []
    for values in itertools.product(*choices):
        row = dict(zip(ids, values, strict=True))
        if holds(model.get("constraints", []), typed_data(row, parameters)):
            result.append(row)
    if not result:
        raise ModelError("no feasible configuration")
    return result


def obligation(
    model: dict, key: str, selector: dict, *, feasibility: str = "feasible", reason: str = ""
) -> dict:
    result = {
        "id": f"COV-{model['id']}-{digest(selector)[:20]}",
        "technique_key": key,
        "model_ref": model["id"],
        "criterion": model["coverage_criterion"],
        "selector": selector,
        "required": model.get("required", True),
        "feasibility": feasibility,
        "observation_ids": model.get("observation_ids", []),
        "risk_ids": model.get("risk_ids", []),
        "source_refs": model.get("source_refs", []),
    }
    if reason:
        result["reason"] = reason
    return result
