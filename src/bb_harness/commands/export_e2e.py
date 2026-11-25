"""Explicitly reviewed scenario export CLI (no LLM inference)."""

from __future__ import annotations

import argparse

from bb_harness.e2e_export import E2EExportError, export_e2e


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "export-e2e", help="Export approved cases to Lakda replay inputs"
    )
    parser.add_argument("--feature-spec", required=True)
    parser.add_argument("--manual-case-set", required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument(
        "--approved-binding-sha256", help="SHA-256 of the reviewed binding bytes for native export"
    )
    parser.add_argument("--out", required=True)


def run(args: argparse.Namespace) -> int:
    try:
        ids = export_e2e(
            args.feature_spec,
            args.manual_case_set,
            args.binding,
            args.out,
            approved_binding_sha256=args.approved_binding_sha256,
        )
    except (OSError, E2EExportError) as exc:
        print("E2E export refused:", exc)
        return 2
    print("E2E scenarios exported:", ", ".join(ids))
    return 0
