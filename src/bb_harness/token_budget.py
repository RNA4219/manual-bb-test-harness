"""実測と推定を区別する、1 run内の呼出予算と消費記録。"""

from __future__ import annotations

import json
from typing import Any


class TokenBudgetExceeded(RuntimeError):
    """次の呼び出しを予約できない。モデルは呼び出していない。"""


def estimate_input(system: str, user: str, schema: dict) -> int:
    """モデル非依存の保守的な推定。tokenizerの実測ではない。"""
    return len((system + user + json.dumps(schema, ensure_ascii=False)).encode("utf-8")) + 256


def output_limit(config: Any, stage: str) -> int:
    stage = stage.removesuffix("_repair").split("__", 1)[0]
    value = config.stage_overrides.get(stage, {}).get("max_tokens", config.max_tokens)
    extra = dict(config.extra_body)
    extra.update(config.stage_overrides.get(stage, {}).get("extra_body", {}))
    value = extra.get("max_tokens", value)
    if type(value) is not int or value <= 0:
        raise ValueError("max_tokens must be a positive integer")
    return value


class TokenMeter:
    def __init__(self, budget: int | None = None):
        if budget is not None and (type(budget) is not int or budget <= 0):
            raise ValueError("token_budget must be a positive integer")
        self.budget = budget
        self.records: list[dict] = []

    def prepare(self, stage: str, system: str, user: str, schema: dict, maximum: int) -> dict:
        estimated = estimate_input(system, user, schema)
        record = {
            "stage": stage,
            "repair": stage.endswith("_repair"),
            "estimated_input_tokens": estimated,
            "max_output_tokens": maximum,
            "outcome": "pending",
            "elapsed_seconds": 0.0,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "usage_status": "unknown",
            "accounted_tokens": 0,
            "finish_reason": None,
            "model": None,
        }
        used = sum(item["accounted_tokens"] for item in self.records)
        if self.budget is not None and used + estimated + maximum > self.budget:
            record["outcome"] = "budget_blocked"
            self.records.append(record)
            raise TokenBudgetExceeded(
                f"{stage}: estimated reservation {estimated + maximum} exceeds "
                f"remaining token budget {max(0, self.budget - used)}"
            )
        self.records.append(record)
        return record

    def finish(self, record: dict, usage: dict, elapsed: float, outcome: str) -> None:
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        known = all(type(value) is int and value >= 0 for value in (prompt, completion))
        if known and "total_tokens" in usage:
            known = (
                type(usage["total_tokens"]) is int and usage["total_tokens"] == prompt + completion
            )
        record.update(elapsed_seconds=round(max(0.0, elapsed), 3), outcome=outcome)
        if known:
            record.update(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=prompt + completion,
                usage_status="reported",
                accounted_tokens=prompt + completion,
            )
        else:
            record["usage_status"] = "invalid" if usage else "unknown"
            record["accounted_tokens"] = (
                record["estimated_input_tokens"] + record["max_output_tokens"]
            )

    def summary(self) -> dict:
        calls = [item for item in self.records if item["outcome"] != "budget_blocked"]
        unknown = sum(item["usage_status"] != "reported" for item in calls)
        accounted = sum(item["accounted_tokens"] for item in calls)
        return {
            "calls": len(calls),
            "repair_calls": sum(item["repair"] for item in calls),
            "unreported_calls": unknown,
            "prompt_tokens": None if unknown else sum(item["prompt_tokens"] for item in calls),
            "completion_tokens": None
            if unknown
            else sum(item["completion_tokens"] for item in calls),
            "total_tokens": None if unknown else sum(item["total_tokens"] for item in calls),
            "reported_total_tokens": sum(item["total_tokens"] or 0 for item in calls),
            "accounted_tokens": accounted,
            "budget_tokens": self.budget,
            "remaining_tokens": None if self.budget is None else max(0, self.budget - accounted),
            "budget_exhausted": self.budget is not None
            and (
                accounted >= self.budget
                or any(item["outcome"] == "budget_blocked" for item in self.records)
            ),
            "estimation_method": "utf8_bytes_plus_256_v1",
        }
