"""Compatibility wrapper for the package-native implementation."""
# ruff: noqa: F403, I001

from bb_harness.tools.state_diagram import *
from bb_harness.tools.state_diagram import main


if __name__ == "__main__":
    raise SystemExit(main())
