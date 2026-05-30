"""Common utilities for import scripts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def lazy_import_requests() -> Any:
    """Lazily import requests library.

    Returns:
        requests module

    Raises:
        ValueError: If requests is not installed
    """
    try:
        import requests

        return requests
    except ImportError:
        raise ValueError("requests library required: pip install requests") from None


def create_import_stats(source: str, **extra_fields: Any) -> dict[str, Any]:
    """Create base import statistics dictionary.

    Args:
        source: Import source identifier (e.g., "testrail", "xray")
        **extra_fields: Additional fields to include in stats

    Returns:
        Statistics dictionary with common fields
    """
    stats: dict[str, Any] = {
        "source": source,
        "imported_count": 0,
        "pass_count": 0,
        "fail_count": 0,
        "skip_count": 0,
        "blocked_count": 0,
        "import_timestamp": datetime.now().isoformat(),
    }
    stats.update(extra_fields)
    return stats


def write_evidence_files(results: list[dict[str, Any]], output_dir: Path) -> None:
    """Write evidence JSON files to output directory.

    Args:
        results: List of evidence dictionaries
        output_dir: Output directory path
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for evidence in results:
        filename = f"{evidence['tc_id']}.json"
        file_path = output_dir / filename
        file_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write summary
    summary_path = output_dir / "summary.json"
    stats = {
        "imported_count": len(results),
        "pass_count": sum(1 for r in results if r.get("result") == "pass"),
        "fail_count": sum(1 for r in results if r.get("result") == "fail"),
        "skip_count": sum(1 for r in results if r.get("result") in ("skip", "blocked")),
    }
    summary_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")


def print_dry_run_summary(
    source_label: str, stats: dict[str, Any], results: list[dict[str, Any]]
) -> None:
    """Print dry-run summary to stdout.

    Args:
        source_label: Human-readable source label (e.g., "Project: 12, Run: 1234")
        stats: Statistics dictionary
        results: List of evidence dictionaries
    """
    print("=== DRY RUN ===")
    print(source_label)
    print(f"Stats: {json.dumps(stats, indent=2)}")
    print(f"Results: {len(results)} tests")
    for r in results[:5]:
        print(f"  - {r['tc_id']}: {r['result']}")


def print_import_summary(output_dir: Path, stats: dict[str, Any]) -> None:
    """Print import summary to stdout.

    Args:
        output_dir: Output directory path
        stats: Statistics dictionary
    """
    print(f"Imported: {output_dir}")
    print(f"  Total: {stats['imported_count']} tests")
    print(f"  Pass: {stats['pass_count']}, Fail: {stats['fail_count']}")
    print(f"  Skip: {stats['skip_count']}, Blocked: {stats['blocked_count']}")
