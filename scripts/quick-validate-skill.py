"""Compatibility wrapper for the package-native implementation."""
# ruff: noqa: F403, I001

from bb_harness.tools.quick_validate_skill import *
from bb_harness.tools.quick_validate_skill import main


if __name__ == "__main__":
    raise SystemExit(main())
