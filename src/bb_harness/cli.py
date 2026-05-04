"""CLI entry point for bb-harness."""

from __future__ import annotations

import argparse
import sys

from bb_harness import __version__
from bb_harness.commands import (
    gate,
    heatmap,
    ingest,
    regression_graph,
    state_diagram,
    validate,
    export,
)


def create_parser() -> argparse.ArgumentParser:
    """Create main CLI parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="bb-harness",
        description="Manual black-box test harness CLI tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"bb-harness {__version__}",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes (for API operations)",
    )

    # Create subparsers
    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="command",
        help="Available commands",
    )

    # Add subcommands
    validate.add_subparser(subparsers)
    ingest.add_subparser(subparsers)
    state_diagram.add_subparser(subparsers)
    regression_graph.add_subparser(subparsers)
    heatmap.add_subparser(subparsers)
    gate.add_subparser(subparsers)
    export.add_subparser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    # Dispatch to subcommand
    dispatch_map = {
        "validate": validate.run,
        "ingest": ingest.run,
        "state-diagram": state_diagram.run,
        "regression-graph": regression_graph.run,
        "heatmap": heatmap.run,
        "gate": gate.run,
        "export": export.run,
    }

    handler = dispatch_map.get(args.command)
    if handler:
        return handler(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())