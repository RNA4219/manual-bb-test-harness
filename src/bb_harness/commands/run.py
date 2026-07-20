"""Run forward-test and local-model design workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.local_pipeline import LocalDesignPipeline
from bb_harness.local_runtime import LocalRuntimeError, load_profiles, resolve_config


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add run subparser with forward-test subcommand."""
    parser = subparsers.add_parser(
        "run",
        help="Run tests or evaluations",
        description="Run forward-test or other evaluation workflows",
    )

    run_subparsers = parser.add_subparsers(
        title="run targets",
        dest="run_target",
        help="Run target",
    )

    # forward-test
    ft_parser = run_subparsers.add_parser(
        "forward-test",
        help="Run forward-test to evaluate Skill output quality",
        description=(
            "Run the Skill against a golden input and evaluate output quality. "
            "See skills/manual-bb-test-harness/references/forward-test.md for details."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  bb-harness run forward-test \\\n"
            "    --skill skills/manual-bb-test-harness \\\n"
            "    --input goldens/order-cancel.input.md\n\n"
            "This prints the prompt template for manual execution.\n"
            "Automated execution requires a Skill runner (not bundled)."
        ),
    )
    ft_parser.add_argument(
        "--skill",
        type=Path,
        default=Path("skills/manual-bb-test-harness"),
        help="Path to Skill directory (default: skills/manual-bb-test-harness)",
    )
    ft_parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to golden input file (e.g., goldens/order-cancel.input.md)",
    )
    ft_parser.add_argument(
        "--expected",
        type=Path,
        help="Path to expected output file (for comparison)",
    )

    local_parser = run_subparsers.add_parser(
        "local-design",
        help="Run manual black-box design in Local Mode",
        description=(
            "Use an OpenAI-compatible local model as a staged candidate generator, then "
            "validate and "
            "normalize artifacts deterministically."
        ),
    )
    local_parser.add_argument("--input", type=Path, required=True, help="Input Markdown spec")
    local_parser.add_argument("--output", type=Path, required=True, help="Output directory")
    local_parser.add_argument(
        "--profile",
        choices=sorted(load_profiles()),
        default="generic",
        help="Local model profile",
    )
    local_parser.add_argument("--base-url", help="OpenAI-compatible /v1 base URL")
    local_parser.add_argument("--model", help="Model ID; omit only when /models has one item")
    local_parser.add_argument("--timeout", type=float, help="Per-request timeout in seconds")
    local_parser.add_argument(
        "--max-repairs",
        type=int,
        choices=[1],
        default=1,
        help="Maximum repair attempts per artifact (fixed to 1 for fail-closed operation)",
    )
    local_parser.add_argument("--evidence", type=Path, help="Execution evidence file/directory")
    local_parser.add_argument(
        "--build-id", default="local-design-unexecuted", help="Build identifier for Gate"
    )
    local_parser.add_argument(
        "--gate-profile", choices=["strict", "standard", "lean"], default="standard"
    )
    local_parser.add_argument(
        "--allow-non-loopback",
        action="store_true",
        help="Allow a trusted non-loopback endpoint (disabled by default)",
    )


def run(args: argparse.Namespace) -> int:
    """Run command dispatcher."""
    target = getattr(args, "run_target", None)
    if target is None:
        print("Error: run target required (forward-test)", file=sys.stderr)
        return 1

    if target == "forward-test":
        return _run_forward_test(args)

    if target == "local-design":
        return _run_local_design(args)

    print(f"Error: Unknown run target: {target}", file=sys.stderr)
    return 1


def _run_forward_test(args: argparse.Namespace) -> int:
    """Print forward-test prompt template and validate paths."""
    skill_path: Path = args.skill
    input_path: Path = args.input

    if not skill_path.exists():
        print(f"Error: Skill path not found: {skill_path}", file=sys.stderr)
        return 1

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    if getattr(args, "verbose", False):
        print(f"[verbose] Skill: {skill_path}", file=sys.stderr)
        print(f"[verbose] Input: {input_path}", file=sys.stderr)

    # Print the prompt template for manual execution
    print("=" * 60)
    print("Forward Test Prompt")
    print("=" * 60)
    print()
    print(
        f"Use $manual-bb-test-harness at {skill_path} to create a "
        f"manual black-box test design for {input_path}."
    )
    print()
    print("Return:")
    print("1. intake status")
    print("2. coverage model")
    print("3. observations")
    print("4. risks")
    print("5. manual cases")
    print("6. exploratory charters")
    print("7. effort")
    print("8. gate decision")
    print("9. Go/No-Go brief")
    print()

    if args.expected:
        if not args.expected.exists():
            print(f"Warning: Expected file not found: {args.expected}", file=sys.stderr)
        else:
            print(f"Compare output against: {args.expected}")
            print()

    print("Scoring: Use docs/evaluation-rubric.md to evaluate output quality.")
    print("Recording: Use docs/notion-report-guide.md or docs/forward-test-report-template.md")

    return 0


def _run_local_design(args: argparse.Namespace) -> int:
    """OpenAI互換ローカルモデルで段階的にテスト設計する。"""
    if not args.input.is_file():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    if args.evidence is not None and not args.evidence.exists():
        print(f"Error: Evidence path not found: {args.evidence}", file=sys.stderr)
        return 1
    try:
        config = resolve_config(
            args.profile,
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=args.timeout,
            allow_non_loopback=args.allow_non_loopback,
        )
        pipeline = LocalDesignPipeline(config)
        manifest = pipeline.run(
            args.input,
            args.output,
            evidence_path=args.evidence,
            build_id=args.build_id,
            gate_profile=args.gate_profile,
        )
    except (LocalRuntimeError, OSError, TypeError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Generated Local Mode design: {args.output}")
    print(f"  Model: {manifest['model']}")
    print(f"  Elapsed: {manifest['elapsed_seconds']} seconds")
    print(f"  Manifest: {args.output / 'run_manifest.json'}")
    return 0
