"""要件定義の信頼度を通信なしで評価するCLI。"""

import argparse
import json
import sys
from pathlib import Path

from bb_harness.requirements_confidence import (
    evaluate_requirements,
    load_input,
    render_markdown,
    review_template,
)


def _threshold(text: str) -> float:
    value = float(text)
    if not 0 <= value <= 100:
        raise argparse.ArgumentTypeError("閾値は0から100を指定してください")
    return value


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("evaluate", help="要件定義の信頼度を評価する")
    commands = parser.add_subparsers(dest="evaluation", required=True)
    requirements = commands.add_parser("requirements", help="要確認・重大度・レビュー率を採点")
    requirements.add_argument("--input", type=Path, required=True)
    requirements.add_argument("--phase-contract", type=Path)
    requirements.add_argument("--review", type=Path)
    requirements.add_argument("--output", type=Path, required=True, help="新規出力ディレクトリ")
    requirements.add_argument("--fail-under", type=_threshold)
    requirements.add_argument("--dry-run", action="store_true")


def run(args: argparse.Namespace) -> int:
    try:
        feature, markers = load_input(args.input)
        phase = (
            json.loads(args.phase_contract.read_text(encoding="utf-8"))
            if args.phase_contract
            else None
        )
        review = json.loads(args.review.read_text(encoding="utf-8")) if args.review else None
        report = evaluate_requirements(feature, phase=phase, review=review, markers=markers)
        if not args.dry_run:
            args.output.mkdir(parents=True, exist_ok=False)
            for filename, value in (
                ("requirements_confidence.json", report),
                ("requirements_review.template.json", review_template(report)),
            ):
                with (args.output / filename).open("x", encoding="utf-8") as handle:
                    json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
                    handle.write("\n")
            with (args.output / "requirements-confidence.md").open("x", encoding="utf-8") as handle:
                handle.write(render_markdown(report))
        score_text = "評価不能" if report["score"] is None else f"{report['score']} / 100"
        coverage = report["metrics"]["review_coverage_percent"]
        coverage_text = "未算出" if coverage is None else f"{coverage}%"
        print(f"要件定義信頼度: {score_text} ({report['band']}, {report['status']})")
        print(
            f"要確認: {report['counts']['open_confirmations']}件 / レビュー済み率: {coverage_text}"
        )
        if not args.dry_run:
            print(f"出力: {args.output}")
        if args.fail_under is not None and (
            report["score"] is None or report["score"] < args.fail_under
        ):
            return 2
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
