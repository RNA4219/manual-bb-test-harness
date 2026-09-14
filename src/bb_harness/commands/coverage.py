"""被覆検証と非破壊artifact移行のCLI。"""

import argparse
import json
import sys
from pathlib import Path

from bb_harness.artifact_migration import migrate_artifact
from bb_harness.coverage_engine import build_coverage_report, build_technique_plan
from bb_harness.evidence_revisions import bind_case_set
from bb_harness.gate_engine import load_evidence_files
from bb_harness.tools.validate_artifact import ARTIFACT_SCHEMA_MAP


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("coverage", help="型付きモデルの設計・実施被覆を検証する")
    for name in ("feature", "test-model", "observations", "risk", "cases"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--build-id", default="unexecuted")
    parser.add_argument("--output", type=Path, required=True, help="新規出力ディレクトリ")
    parser = subparsers.add_parser("migrate", help="artifactを別ファイルへ非破壊移行する")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--type", choices=sorted(ARTIFACT_SCHEMA_MAP), required=True)
    parser.add_argument("--artifact-version", choices=["legacy", "enhanced"], default="enhanced")
    parser = subparsers.add_parser(
        "bind-cases", help="現在のケースとモデルの版を別ファイルへ固定する"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--test-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def run(args: argparse.Namespace) -> int:
    try:
        if args.command == "bind-cases":
            if args.output.resolve() in {args.input.resolve(), args.test_model.resolve()}:
                raise ValueError("入力ファイルの上書きは禁止")
            _write(args.output, bind_case_set(_read(args.input), _read(args.test_model)))
        elif args.command == "migrate":
            if args.input.resolve() == args.output.resolve():
                raise ValueError("移行元の上書きは禁止")
            result = migrate_artifact(
                _read(args.input), args.type, artifact_version=args.artifact_version
            )
            _write(args.output, result)
        else:
            feature, model, observations, risks, cases = (
                _read(path)
                for path in (
                    args.feature,
                    args.test_model,
                    args.observations,
                    args.risk,
                    args.cases,
                )
            )
            plan = build_technique_plan(feature, model, observations, risks)
            report = build_coverage_report(
                model,
                plan,
                cases,
                load_evidence_files(args.evidence) if args.evidence else [],
                build_id=args.build_id,
            )
            if args.output.exists():
                raise ValueError("被覆出力には未存在のディレクトリを指定する")
            _write(args.output / "technique_plan.json", plan)
            _write(args.output / "coverage_report.json", report)
        print(f"Generated: {args.output}")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
