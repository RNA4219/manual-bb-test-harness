"""Synchronize workflow-cookbook counts and review metadata."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def synchronize(repo: Path, *, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    workflow = repo / "docs" / "workflow-cookbook"
    index_path = workflow / "index.json"
    hot_path = workflow / "hot.json"
    index = read_json(index_path)
    hot = read_json(hot_path)
    counts = {
        "nodes": len(index.get("nodes", [])),
        "edges": len(index.get("edges", [])),
        "capsules": len(list((workflow / "caps").glob("*.json"))),
    }
    stamp = datetime.now(timezone.utc).isoformat()
    index["generated_at"] = stamp
    index.setdefault("metadata", {}).update(
        {
            "last_updated": today.isoformat(),
            "total_nodes": counts["nodes"],
            "total_edges": counts["edges"],
            "total_capsules": counts["capsules"],
        }
    )
    hot["generated_at"] = stamp
    hot.setdefault("project_status", {}).update(
        {
            "last_updated": today.isoformat(),
            "total_capsules": counts["capsules"],
        }
    )
    readme_path = repo / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    updated, replacements = re.subn(
        r"\(\d+ nodes,\s*\d+ edges\)",
        f"({counts['nodes']} nodes, {counts['edges']} edges)",
        readme,
        count=1,
    )
    if replacements != 1:
        raise ValueError("README knowledge-map count marker not found")
    test_count_match = re.search(r"検証済みテスト:\s*\*\*(\d+)件\*\*", updated)
    if not test_count_match:
        raise ValueError("README test-count marker not found")
    hot.setdefault("project_status", {})["test_count"] = int(test_count_match.group(1))
    write_json(index_path, index)
    write_json(hot_path, hot)
    readme_path.write_text(updated, encoding="utf-8")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    counts = synchronize(args.repo.resolve())
    print(
        f"Synchronized: {counts['nodes']} nodes, {counts['edges']} edges, "
        f"{counts['capsules']} capsules"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
