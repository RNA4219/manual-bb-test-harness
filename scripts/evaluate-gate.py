"""Compatibility wrapper for the package-native Gate engine."""

from bb_harness.gate_engine import *  # noqa: F403
from bb_harness.gate_engine import main

if __name__ == "__main__":
    raise SystemExit(main())
