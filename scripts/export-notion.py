"""Compatibility wrapper for the package-native implementation."""
# ruff: noqa: F403, I001

from bb_harness.tools.export_notion import *
from bb_harness.tools.export_notion import main


if __name__ == "__main__":
    raise SystemExit(main())
