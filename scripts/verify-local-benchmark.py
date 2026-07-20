#!/usr/bin/env python3
"""Compatibility wrapper for bb_harness.tools.verify_local_benchmark."""
# ruff: noqa: I001

from bb_harness.tools.verify_local_benchmark import main


if __name__ == "__main__":
    raise SystemExit(main())
