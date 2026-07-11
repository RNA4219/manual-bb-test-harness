#!/usr/bin/env python3
"""Compatibility wrapper for bb_harness.tools.validate_spec."""
# ruff: noqa: F403, I001
from bb_harness.tools.validate_spec import *
from bb_harness.tools.validate_spec import main

if __name__ == "__main__":
    raise SystemExit(main())
