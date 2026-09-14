"""実pytest → HATE/v1 → QEG 0.2 のCI専用境界。外部LLMは呼び出さない。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HATE_REVISION = "f76f1b90772bc609094ca568cd44ca161593349f"
QEG_REVISION = "d957fc25907e1b678add65eb47f92853dd093d32"
COVERAGE_FLOOR = 85
RAW_FILES = ("github-context.json", "junit.xml", "lcov.info", "coverage.json")
STATUS = {"passed": "pass", "failed": "fail", "error": "fail", "skipped": "skipped"}
NOT_EVALUATED = [
    "リリース承認",
    "手動受入",
    "実LLM・外部サービスの受入",
    "RanD・Code-to-gateの全producer連携",
    "変更行と個別testの対応",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def head(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def coverage_metrics(coverage: dict, floor: float) -> dict:
    """表示用合算値を信用せず、実測件数から行率・分岐率を計算する。"""
    require(type(floor) in (int, float) and math.isfinite(floor) and 0 <= floor <= 100,
            "coverage閾値が不正です")
    require(coverage["meta"]["branch_coverage"] is True, "branch coverageの実測値が必要です")
    totals = coverage["totals"]
    names = ("covered_lines", "missing_lines", "num_statements",
             "covered_branches", "missing_branches", "num_branches")
    require(all(type(totals[name]) is int and totals[name] >= 0 for name in names),
            "coverage件数は非負整数が必要です")
    lines, branches = totals["num_statements"], totals["num_branches"]
    covered_lines, covered_branches = totals["covered_lines"], totals["covered_branches"]
    require(lines > 0 and branches > 0, "coverage分母は正の整数が必要です")
    require(covered_lines + totals["missing_lines"] == lines
            and covered_branches + totals["missing_branches"] == branches,
            "coverage件数の合計が一致しません")
    return {
        "metric": "branch", "floor": floor,
        "covered_branches": covered_branches, "num_branches": branches,
        "covered_lines": covered_lines, "num_statements": lines,
        "branch_percent": 100 * covered_branches / branches,
        "line_percent": 100 * covered_lines / lines,
        "combined_percent": 100 * (covered_lines + covered_branches) / (lines + branches),
        "passed": covered_branches * 100 >= floor * branches,
    }


def capture(out: Path, repo: Path) -> int:
    """収集先を新規作成し、実際のpytest終了コードも保存する。"""
    out.mkdir(parents=True, exist_ok=False)
    raw = out / "raw"
    raw.mkdir()
    revision = head(repo)
    require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)), "HEADが不正です")
    context = {
        "repository": os.environ.get("GITHUB_REPOSITORY", "local/manual-bb-test-harness"),
        "workflow": os.environ.get("GITHUB_WORKFLOW", "local-validation"),
        "job": "coverage",
        "run_id": os.environ.get("GITHUB_RUN_ID", "local-" + now().replace(":", "-")),
        "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        "commit_sha": revision,
        "started_at": now(),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "actor": os.environ.get("GITHUB_ACTOR", "local"),
        "ref": os.environ.get("GITHUB_REF", "local"),
    }
    # ローカル実行をGitHub Actionsとして記録しない。
    context["ci_provider"] = "github-actions" if os.environ.get("GITHUB_ACTIONS") else "generic-ci"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--cov=src/bb_harness",
        "--cov=scripts",
        "--cov-branch",
        "--cov-report=term",
        f"--cov-report=lcov:{raw / 'lcov.info'}",
        f"--cov-report=json:{raw / 'coverage.json'}",
        f"--junitxml={raw / 'junit.xml'}",
        f"--cov-fail-under={COVERAGE_FLOOR}",
        "--durations=20",
    ]
    result = subprocess.run(command, cwd=repo, check=False)
    coverage_export = subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "json",
            "--show-contexts",
            "--fail-under=0",
            "-o",
            str(raw / "coverage.json"),
        ],
        cwd=repo,
        check=False,
    )
    context["finished_at"] = now()
    write(raw / "github-context.json", context)
    try:
        metrics = coverage_metrics(read(raw / "coverage.json"), COVERAGE_FLOOR)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        metrics = {"metric": "branch", "passed": False, "error": str(exc)}
    print(json.dumps(metrics, ensure_ascii=False))
    write(
        out / "collection.json",
        {
            "version": "manual-bb-ci/v2",
            "command": command,
            "pytest_exit_code": result.returncode,
            "coverage_export_exit_code": coverage_export.returncode,
            "coverage_floor": COVERAGE_FLOOR,
            "coverage_metric": "branch",
            "coverage_metrics": metrics,
            "hashes": {name: digest(raw / name) for name in RAW_FILES if (raw / name).is_file()},
        },
    )
    return result.returncode or coverage_export.returncode or int(not metrics["passed"])


def verify_collection(root: Path, revision: str, run_id: str, attempt: int) -> tuple[dict, dict]:
    collection = read(root / "collection.json")
    require(collection["version"] == "manual-bb-ci/v2", "未知の収集契約です")
    require(collection["coverage_metric"] == "branch", "coverage指標が分岐率ではありません")
    require(collection["coverage_floor"] == COVERAGE_FLOOR, "coverage閾値が変更されています")
    require(type(collection["pytest_exit_code"]) is int, "pytest終了コードが不正です")
    require(collection["coverage_export_exit_code"] == 0, "coverageのexportが失敗しています")
    for name in RAW_FILES:
        require(
            collection["hashes"].get(name) == digest(root / "raw" / name),
            f"元証跡が欠落・改変されています: {name}",
        )
    context = read(root / "raw/github-context.json")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)), "期待するHEADが不正です")
    require(
        (context["commit_sha"], context["run_id"], context["run_attempt"])
        == (revision, run_id, attempt),
        "コミット/run/attemptが一致しません",
    )
    require(type(context["run_attempt"]) is int and attempt > 0, "attemptが不正です")
    start = datetime.fromisoformat(context["started_at"].replace("Z", "+00:00"))
    finish = datetime.fromisoformat(context["finished_at"].replace("Z", "+00:00"))
    require(
        start.tzinfo is not None and finish.tzinfo is not None and start <= finish,
        "実行時刻が不正です",
    )
    return collection, context


def junit_results(path: Path) -> dict[tuple[str, str], str]:
    root = ET.parse(path).getroot()
    require(root.tag in {"testsuite", "testsuites"}, "JUnit rootが不正です")
    results = {}
    for case in root.iter("testcase"):
        key = (case.get("classname", ""), case.get("name", ""))
        require(all(key) and key not in results, "JUnit test identityが空または重複しています")
        results[key] = next(
            (
                status
                for tag, status in (
                    ("failure", "failed"),
                    ("error", "error"),
                    ("skipped", "skipped"),
                )
                if case.find(tag) is not None
            ),
            "passed",
        )
    require(bool(results), "実テスト結果が0件です")
    return results


def normalized_results(root: Path, context: dict) -> list[dict]:
    expected = junit_results(root / "raw/junit.xml")
    records = [
        json.loads(line)
        for line in (root / "hate/p0a/HATE-test-results.ndjson")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    actual = {}
    canonical_ids = set()
    for record in records:
        require(record["schema_version"] == "HATE/v1", "未知のHATE契約です")
        require(record["source_version"] == HATE_REVISION, "HATEの実装版が一致しません")
        require(
            all(record[k] == context[k] for k in ("commit_sha", "run_id", "run_attempt")),
            "HATE実行証跡の版が一致しません",
        )
        payload = record["payload"]
        identity = payload["identity_components"]
        key = (identity["classname"], identity["name"])
        require(
            key not in actual and payload["canonical_test_id"] not in canonical_ids,
            "HATE test identityが重複しています",
        )
        require(payload["status"] in STATUS, "未知のHATE test statusです")
        actual[key] = payload["status"]
        canonical_ids.add(payload["canonical_test_id"])
    require(actual == expected, "JUnitとHATEの件数・identity・statusが一致しません")
    return records


def run_hate(root: Path) -> None:
    require(not (root / "hate").exists(), "HATE出力先が既に存在します")
    source = root / "hate/input"
    source.mkdir(parents=True)
    for name in ("github-context.json", "junit.xml", "coverage.json"):
        shutil.copyfile(root / "raw" / name, source / name)
    for args in (
        [
            "p0a",
            "--input",
            str(source),
            "--out",
            str(root / "hate/p0a"),
            "--source-version",
            HATE_REVISION,
        ],
        ["export", "qeg", "--fixture", str(root / "hate"), "--out", str(root / "hate/export")],
    ):
        subprocess.run([sys.executable, "-m", "hate", *args], check=True)


def build_qeg(root: Path, revision: str, run_id: str, attempt: int) -> Path:
    collection, context = verify_collection(root, revision, run_id, attempt)
    records = normalized_results(root, context)
    decision = read(root / "hate/p0a/precheck-decision.json")
    require(decision["payload"]["qeg_export_allowed"] is True, "HATEがexportを拒否しました")
    bundle = read(root / "hate/export/qeg-bundle.json")
    meta = bundle["metadata"]
    require(
        meta["qegVersion"] == "HATE/v1" and not meta.get("debugOnly"),
        "未知またはdebug用HATE exportです",
    )
    require(
        (meta["commitSha"], meta["runId"], meta["runAttempt"]) == (revision, run_id, attempt),
        "HATE exportの版が一致しません",
    )
    report = read(root / "hate/export/qeg-export-report.json")
    require(report["qeg_schema_compatibility"]["valid"] is True, "HATE export schemaが不正です")
    exported = [node["data"] for node in bundle["nodes"] if node["kind"] == "test"]
    require(
        len(exported) == len(records)
        and {item["canonical_test_id"]: item["status"] for item in exported}
        == {
            record["payload"]["canonical_test_id"]: record["payload"]["status"]
            for record in records
        },
        "HATE exportでtest identity・statusが変化しました",
    )
    completeness = bundle["completeness"]
    require(
        completeness["partial"] is False
        and not completeness["parserFailures"]
        and not completeness["unsupportedClaims"],
        "HATE exportの証跡が不完全です",
    )
    coverage = read(root / "raw/coverage.json")
    metrics = coverage_metrics(coverage, COVERAGE_FLOOR)
    percent = metrics["branch_percent"]

    out = root / "qeg"
    out.mkdir(exist_ok=False)
    shutil.copytree(root / "raw", out / "evidence/raw")
    shutil.copytree(root / "hate", out / "evidence/hate")
    shutil.copyfile(root / "collection.json", out / "evidence/collection.json")
    spec = Path(__file__).resolve().parents[2] / "docs/specs/spec-08-hate-qeg-ci.md"
    shutil.copyfile(spec, out / "evidence/spec.md")
    artifacts = []

    def ref(path: str, *, adapter="qeg-native", kind="quality_evidence_record") -> dict:
        item = {
            "id": "qeg:artifact-" + hashlib.sha256(path.encode()).hexdigest()[:20],
            "adapter": adapter,
            "kind": kind,
            "path": path,
            "contentHash": digest(out / path),
            "revision": revision,
        }
        artifacts.append(item)
        return {key: item[key] for key in ("id", "path", "contentHash", "revision")}

    raw_refs = [
        ref("evidence/raw/" + name, adapter=adapter, kind=kind)
        for name, adapter, kind in (
            ("junit.xml", "junit", "junit"),
            ("lcov.info", "coverage", "coverage"),
            ("coverage.json", "coverage", "coverage"),
            ("github-context.json", "qeg-native", "quality_evidence_record"),
        )
    ]
    for path in sorted((out / "evidence/hate").rglob("*")):
        if path.is_file():
            raw_refs.append(ref(path.relative_to(out).as_posix()))
    raw_refs.extend([ref("evidence/collection.json"), ref("evidence/spec.md")])
    sources = [{"id": item["id"], "path": item["path"], "revision": revision} for item in raw_refs]
    trace = {
        "sourceRefs": sources,
        "assumptions": [
            "pytest自身は実行済み。テスト内で代替されたLLM・サービスの実環境受入は未評価。"
        ],
        "confidence": "high",
    }
    target = {
        "projectId": context["repository"],
        "buildId": f"{run_id}:{attempt}:coverage",
        "revision": revision,
        "environmentId": context["ci_provider"] + ":coverage",
    }
    write(out / "execution/build.json", {"bindingVersion": "qeg-build/v1", "target": target})
    binding = ref("execution/build.json")
    nodes, edges, selected = [], [], []

    def add_test(case_id: str, status: str, producer: str, source_version: str) -> None:
        suffix = hashlib.sha256((producer + case_id).encode()).hexdigest()[:24]
        test_id, execution_id = "hate:test-" + suffix, "hate:execution-" + suffix
        identity = {
            "producer": producer,
            "projectId": target["projectId"],
            "featureId": "repository-ci",
            "caseId": case_id,
        }
        base = {"sourceArtifactIds": [r["id"] for r in raw_refs], "traceability": trace}
        nodes.append(
            {
                **base,
                "id": test_id,
                "kind": "test",
                "title": case_id,
                "layer": "unit",
                "existing": True,
                "testExecutionMode": "real",
                "executionIdentity": identity,
            }
        )
        detail = {
            "executionVersion": "qeg-execution/v1",
            "testId": test_id,
            "identity": identity,
            "producerVersion": source_version,
            "runId": "qeg:" + target["buildId"],
            "target": target,
            "completedAt": context["finished_at"],
            "status": status,
            "executionMode": "real",
        }
        path = f"execution/{suffix}.json"
        write(out / path, detail)
        execution_ref = ref(path)
        nodes.append(
            {
                **base,
                "id": execution_id,
                "kind": "execution_evidence",
                "title": case_id,
                "execution": {**detail, "rawArtifactRef": execution_ref},
                "evidenceRefs": [
                    {
                        **execution_ref,
                        "evidenceKind": "test_result",
                        "capturedAt": context["finished_at"],
                    }
                ],
            }
        )
        edges.append(
            {
                "id": "hate:edge-" + suffix,
                "kind": "evidenced_by",
                "from": test_id,
                "to": execution_id,
                "traceability": trace,
            }
        )
        selected.append(test_id)

    for record in records:
        payload = record["payload"]
        add_test(
            payload["canonical_test_id"],
            STATUS[payload["status"]],
            "harness-auto-test-evidence",
            record["source_version"],
        )
    add_test(
        "pytest-exit-and-branch-coverage-85",
        "pass" if collection["pytest_exit_code"] == 0 and metrics["passed"] else "fail",
        "manual-bb-ci-checker",
        revision,
    )
    policy = {
        "policyId": "qeg:manual-bb-ci-v1",
        "policyHash": digest(out / "evidence/spec.md"),
        "profile": "standard",
        "effectiveDate": "2026-09-10T15:00:00Z",
        "approver": "repository-maintainer:CI-policy",
        "sourceRefs": sources[-1:],
        "dqScope": [f"DQ-{i:02}" for i in range(1, 18)],
        "exitCodePolicy": {"go": 0, "conditional_go": 2, "no_go": 2, "disqualified": 2},
        "inputContract": {
            "mode": "native_graph",
            "requiredArtifacts": [
                {"adapter": "junit", "kind": "junit"},
                {"adapter": "coverage", "kind": "coverage"},
                {"adapter": "qeg-native", "kind": "quality_evidence_record"},
            ],
            "evaluationScope": {
                "kind": "real_environment",
                "target": target["buildId"],
                "notEvaluated": NOT_EVALUATED,
            },
            "requireExecutedTests": True,
            "sourceRefs": sources[-1:],
        },
        "executionPolicy": {
            "target": target,
            "maxEvidenceAgeHours": 24,
            "buildBindingRef": binding,
            "sourceRefs": sources[-1:],
        },
    }
    metadata = {
        "qegVersion": "0.2",
        "runId": "qeg:" + target["buildId"],
        "createdAt": now(),
        "headRef": revision,
        "profile": "standard",
        "inputArtifacts": artifacts,
        "requiredConnectorStatus": {
            "qeg-native": "success",
            "junit": "success",
            "coverage": "success",
        },
    }
    obligation = {
        "id": "qeg:ci-obligation",
        "changedCodeIds": [],
        "riskIds": [],
        "requirementIds": [],
        "failureModeIds": [],
        "priority": "P1",
        "riskPriorityIndex": 0,
        "gateRelevance": "blocking",
        "traceability": trace,
    }
    placement = {
        "id": "qeg:ci-placement",
        "kind": "test_placement",
        "title": "全pytest結果の検証",
        "obligationId": obligation["id"],
        "primaryLayer": "unit",
        "disposition": "reuse",
        "gateRelevance": "blocking",
        "candidateScores": [],
        "selectedTestIds": selected,
        "traceability": trace,
        "sourceArtifactIds": [],
    }
    write(
        out / "gate-input.json",
        {
            "metadata": metadata,
            "policy": policy,
            "graph": {
                "metadata": metadata,
                "nodes": nodes,
                "edges": edges,
                "completeness": {"partial": False, "parserFailures": [], "unsupportedClaims": []},
            },
            "placementPlan": {
                "metadata": metadata,
                "obligations": [obligation],
                "placements": [placement],
            },
        },
    )
    write(
        out / "conversion-summary.json",
        {
            "version": "manual-bb-hate-qeg/v2",
            "revision": revision,
            "run_id": run_id,
            "run_attempt": attempt,
            "hate_revision": HATE_REVISION,
            "qeg_revision": QEG_REVISION,
            "test_count": len(records),
            "coverage_percent": percent,
            "coverage_metric": "branch",
            "coverage_metrics": metrics,
            "pytest_exit_code": collection["pytest_exit_code"],
            "not_evaluated": NOT_EVALUATED,
            "hate_completeness": bundle["completeness"],
        },
    )
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "convert", "check-coverage"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--floor", type=float, default=COVERAGE_FLOOR)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    try:
        if args.mode == "check-coverage":
            require(args.input is not None, "--input required")
            metrics = coverage_metrics(read(args.input), args.floor)
            print(json.dumps(metrics, ensure_ascii=False))
            return int(not metrics["passed"])
        require(args.out is not None, "--out required")
        root = args.out.resolve()
        if args.mode == "capture":
            return capture(root, repo)
        context = read(root / "raw/github-context.json")
        run_id = os.environ.get("GITHUB_RUN_ID", context["run_id"])
        attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", context["run_attempt"]))
        revision = head(repo)
        verify_collection(root, revision, run_id, attempt)
        run_hate(root)
        build_qeg(root, revision, run_id, attempt)
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ET.ParseError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"CI証跡の生成失敗: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
