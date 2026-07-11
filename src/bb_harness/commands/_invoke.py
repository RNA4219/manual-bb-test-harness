"""Invoke argparse-based packaged tools without spawning a subprocess."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable


def invoke_tool(
    main: Callable[[], int],
    argv: list[str],
    args: argparse.Namespace | None = None,
) -> int:
    effective = list(argv)
    if args is not None and getattr(args, "dry_run", False):
        effective.append("--dry-run")
    if args is not None and getattr(args, "verbose", False):
        command = " ".join(effective)
        print(f"[verbose] Running: {main.__module__} {command}", file=sys.stderr)
    previous = sys.argv
    sys.argv = [main.__module__, *effective]
    try:
        return main()
    finally:
        sys.argv = previous
