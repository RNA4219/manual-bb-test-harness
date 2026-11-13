"""設計書の手計算を、通信なしで検算するCLI。"""

import argparse
import json
import sys
from pathlib import Path

from bb_harness.markdown_risk_check import check_risk_tables, render_text


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("check", help="設計書の計算を検算する")
    commands = parser.add_subparsers(dest="check_target", required=True)
    risk = commands.add_parser(
        "risk",
        help="Markdownのリスク表の点数と優先度を式で検算する",
        description=(
            "I・L・補正（D/C/X/P/A）から点数と優先度を計算し直し、表の値と比べる。"
            "全行一致で0、不一致・検算できない行・リスク表なしで2、入力エラーで1を返す。"
        ),
    )
    risk.add_argument("--input", type=Path, required=True, help="検算するMarkdownファイル")
    risk.add_argument("--format", choices=["text", "json"], default="text", help="出力形式")


def run(args: argparse.Namespace) -> int:
    try:
        text = args.input.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    report = check_risk_tables(text)
    if args.format == "json":
        payload = {"input": str(args.input), **report}
        print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        print(render_text(report, str(args.input)), end="")
    return 0 if report["status"] == "ok" else 2
