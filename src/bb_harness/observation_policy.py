"""Policies for merging independently derived manual-test observations."""

from __future__ import annotations

import copy
from typing import Any


def merge_observation_runs(runs: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Merge observations while treating support count only as confidence evidence."""
    merged: dict[str, dict[str, Any]] = {}
    support: dict[str, int] = {}
    for run in runs:
        seen_in_run: set[str] = set()
        for item in run:
            identifier = str(item.get("id", ""))
            if not identifier:
                raise ValueError("observation id required")
            if identifier not in merged:
                merged[identifier] = copy.deepcopy(item)
            else:
                current = merged[identifier]
                current["mandatory"] = bool(current.get("mandatory")) or bool(
                    item.get("mandatory")
                )
                if current.get("priority") != "P0" and item.get("priority") == "P0":
                    current["priority"] = "P0"
            if identifier not in seen_in_run:
                support[identifier] = support.get(identifier, 0) + 1
                seen_in_run.add(identifier)
    for identifier, item in merged.items():
        item["support_count"] = support[identifier]
        item["run_count"] = len(runs)
    return list(merged.values())
