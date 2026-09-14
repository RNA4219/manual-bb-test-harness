"""RanD成果物をローカルのテスト設計入力として取り込むCLI。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bb_harness.rand_import import build_intake, publish, render_prompt


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rand", help="RanDのR&D成果物をテスト設計へ取り込む")
    parser.add_argument("--input", type=Path, required=True, help="RanD schema 2.0 JSON")
    parser.add_argument("--diff", type=Path, help="文書入力に対応するrequirements_diff JSON")
    parser.add_argument("--output", type=Path, required=True, help="新規出力directory")
    parser.add_argument("--feature-id", help="欠陥台帳や既存テストと共通のfeature ID")
    parser.add_argument("--title", help="設計対象の表示名")
    parser.add_argument("--defects", type=Path, help="同じfeatureのdefect_register JSON")
    parser.add_argument("--dry-run", action="store_true", help="JSONを表示し、保存しない")


def run(args: argparse.Namespace) -> int:
    try:
        intake, feature = build_intake(
            args.input,
            diff_path=args.diff,
            feature_id=args.feature_id,
            title=args.title,
            defects_path=args.defects,
        )
        prompt = render_prompt(intake, feature)
        result = {
            "status": "ok",
            "intake_status": intake["intake_status"],
            "feature_id": intake["feature_id"],
            "artifacts": {},
        }
        if args.dry_run:
            result.update({"intake": intake, "feature_spec": feature, "test_design_prompt": prompt})
        else:
            result.update(publish(args.output, intake, feature, prompt))
            if "warning" in result:
                result["status"] = "degraded"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result["status"] == "degraded" else 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(
            json.dumps(
                {"status": "failed", "error": str(exc), "artifacts": {}}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        return 1
