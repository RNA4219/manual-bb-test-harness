"""Compatibility wrapper for the package-native implementation."""
# ruff: noqa: F403, I001

from bb_harness.tools.risk_heatmap import *
from bb_harness.tools.risk_heatmap import main


if __name__ == "__main__":
    raise SystemExit(main())
