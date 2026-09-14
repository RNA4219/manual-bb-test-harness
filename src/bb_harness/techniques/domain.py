"""明示的な軸・anchorを用いた線形borderのDomain Coverage。"""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .common import ModelError, decimal, evaluate, holds, indexed, obligation, typed_data

OPS = {"<": "lt", "<=": "lte", "=": "eq", "!=": "neq", ">=": "gte", ">": "gt"}


def linear(node: dict, axis: str, anchor: dict) -> tuple[Decimal, Decimal]:
    """軸に対する係数と定数を求め、非線形式を明示的に拒否する。"""
    if node.get("var") == axis:
        return Decimal(1), Decimal(0)
    if "var" in node or "const" in node:
        return Decimal(0), decimal(evaluate(node, anchor))
    op, args = node.get("op"), node.get("args", [])
    if op not in {"add", "sub", "mul", "div"} or len(args) != 2:
        raise ModelError("domain border requires linear arithmetic")
    a, b = linear(args[0], axis, anchor)
    c, d = linear(args[1], axis, anchor)
    if op == "add":
        return a + c, b + d
    if op == "sub":
        return a - c, b - d
    if op == "mul" and not (a and c):
        return a * d + b * c, b * d
    if op == "div" and not c and d:
        return a / d, b / d
    raise ModelError("nonlinear or undefined domain border")


def enumerate_domain(model: dict, parameters: dict) -> list[dict]:
    if model["coverage_criterion"] not in {"simplified_domain", "reliable_domain"}:
        raise ModelError("unsupported domain criterion")
    indexed(model["borders"], "border")
    result = []
    for border in model["borders"]:
        axis, anchor, expr = border["axis"], border["anchor"], border["predicate"]
        if (
            axis not in parameters
            or axis not in model["variable_ids"]
            or "step" not in parameters[axis]
        ):
            raise ModelError("domain axis requires an explicit parameter and step")
        if set(anchor) != set(model["variable_ids"]):
            raise ModelError("anchor must bind every domain variable")
        if parameters[axis]["type"] not in {"integer", "decimal", "number"}:
            raise ModelError("only numeric domain axes are supported")
        anchor_values = typed_data(anchor, parameters)
        step = decimal(parameters[axis]["step"])
        if step <= 0:
            raise ModelError("domain step must be positive")
        if expr.get("op") != OPS[border["operator"]] or len(expr.get("args", [])) != 2:
            raise ModelError("border operator/predicate mismatch")
        if "closed" in border and border["closed"] != (border["operator"] in {"<=", "=", ">="}):
            raise ModelError("border open/closed mismatch")
        a, b = linear({"op": "sub", "args": expr["args"]}, axis, anchor_values)
        if not a:
            raise ModelError("domain axis does not cross this border")
        root = -b / a
        lo = (root / step).to_integral_value(rounding=ROUND_FLOOR) * step
        hi = (root / step).to_integral_value(rounding=ROUND_CEILING) * step
        op = border["operator"]
        points = {}
        if op in {"=", "!="}:
            if lo != hi:
                raise ModelError("equality border is not representable at this precision")
            center, side = ("ON", "OFF") if op == "=" else ("OFF", "ON")
            points = {center: root, side + "-LOW": root - step, side + "-HIGH": root + step}
        else:
            candidates = sorted({lo - step, lo, hi, hi + step})
            inside = [x for x in candidates if evaluate(expr, {**anchor_values, axis: x})]
            outside = [x for x in candidates if not evaluate(expr, {**anchor_values, axis: x})]
            on = min(inside, key=lambda x: abs(x - root))
            off = min(outside, key=lambda x: abs(x - root))
            points = {"ON": on, "OFF": off}
            if model["coverage_criterion"] == "reliable_domain":
                direction = Decimal(1) if on > off else Decimal(-1)
                points.update(IN=on + direction * step * 2, OUT=off - direction * step * 2)
        for role, x in points.items():
            values = {**anchor, axis: int(x) if x == int(x) else str(x)}
            feasible, reason = "feasible", ""
            try:
                typed = typed_data(values, parameters)
                constraints = holds(model.get("constraints", []), typed)
                others = [other for other in model["borders"] if other["id"] != border["id"]]
                isolated = all(evaluate(other["predicate"], typed) for other in others)
                # 他のborderの隣接点・交点に当たるanchorは独立した被覆としない。
                for other in others:
                    other_axis = other["axis"]
                    delta = decimal(parameters[other_axis]["step"])
                    isolated = isolated and all(
                        evaluate(
                            other["predicate"],
                            {**typed, other_axis: typed[other_axis] + sign * delta},
                        )
                        for sign in (-1, 1)
                    )
                expected_inside = role.startswith("ON") or role == "IN"
                if (
                    not constraints
                    or not isolated
                    or evaluate(model["partition_predicate"], typed) != expected_inside
                ):
                    feasible, reason = (
                        "unknown",
                        "anchorの制約・他境界による遮蔽を解決する必要がある",
                    )
            except ModelError as exc:
                feasible, reason = "unknown", str(exc)
            result.append(
                obligation(
                    model,
                    "domain_testing",
                    {"border_id": border["id"], "point_role": role, "data": values},
                    feasibility=feasible,
                    reason=reason,
                )
            )
    return result
