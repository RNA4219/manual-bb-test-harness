#!/usr/bin/env python3
"""Compatibility wrapper for bb_harness.tools.check_utf8."""
# ruff: noqa: F403, I001
from bb_harness.tools.check_utf8 import *
from bb_harness.tools.check_utf8 import main

if __name__ == "__main__":
    raise SystemExit(main())
