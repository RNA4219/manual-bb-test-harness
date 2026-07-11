#!/usr/bin/env python3
"""Compatibility wrapper for bb_harness.tools.validate_release_bundle."""
# ruff: noqa: F403, I001
from bb_harness.tools.validate_release_bundle import *
from bb_harness.tools.validate_release_bundle import main

if __name__ == "__main__":
    raise SystemExit(main())
