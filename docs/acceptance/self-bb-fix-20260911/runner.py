"""公開CLIのみを子プロセスから操作する4.1.0の自己BB試験。SUTのPython関数はimportしない。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, expected, actual=None):
    if not value:
        raise AssertionError(json.dumps({"expected": expected, "actual": actual}, ensure_ascii=False))


class Suite:
    def __init__(self, repo, lab):
        self.repo, self.lab = repo.resolve(), lab.resolve()
        self.work = self.lab / "work"
        self.work.mkdir(exist_ok=False)
        self.logs = self.lab / "commands"
        self.logs.mkdir(exist_ok=False)
        self.sut = self.lab / "installed/venv/Scripts/bb-harness.exe"
        self.python = self.lab / "installed/venv/Scripts/python.exe"
        self.env = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            self.env.pop(key, None)
        self.env["PYTHONUTF8"] = "1"
        self.calls, self.results, self.current = [], [], "SETUP"

    def write(self, path, value):
        target = self.work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        return path

    def read(self, path):
        return json.loads((self.work / path).read_text(encoding="utf-8"))

    def call(self, args, *, analysis=False):
        command = (
            [str(self.python), "-I", str(self.repo / "tools/analyze_requirements_outcomes.py")]
            if analysis else [str(self.sut)]
        ) + [str(arg) for arg in args]
        start = time.monotonic()
        result = subprocess.run(command, cwd=self.work, env=self.env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=90)
        record = {"number": len(self.calls) + 1, "case": self.current,
                  "entrypoint": "repo-analysis-tool" if analysis else "published-cli",
                  "args": list(map(str, args)), "returncode": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr,
                  "elapsed_seconds": round(time.monotonic() - start, 3)}
        self.calls.append(record)
        (self.logs / f"{record['number']:03d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    def case(self, identifier, operation):
        self.current = identifier
        first = len(self.calls)
        start = time.monotonic()
        try:
            details = operation()
            result, error = ("observed" if identifier.startswith("CH-") else "pass"), None
        except AssertionError as exc:
            result, error, details = "fail", str(exc), None
        except Exception as exc:
            result, error, details = "blocked", f"{type(exc).__name__}: {exc}", None
        row = {"id": identifier, "result": result, "error": error, "details": details,
               "commands": list(range(first + 1, len(self.calls) + 1)),
               "elapsed_seconds": round(time.monotonic() - start, 3)}
        self.results.append(row)
        print(identifier, result, error or "", flush=True)
        self.save()

    def save(self):
        (self.lab / "results.json").write_text(json.dumps({
            "target": "bb-harness 4.1.0 + self-BB fixes (local wheel, unreleased)", "runner_kind": "agent-operated black-box CLI",
            "results": self.results, "commands": len(self.calls),
            "counts": {key: sum(row["result"] == key for row in self.results)
                       for key in ("pass", "fail", "blocked", "observed")},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def evaluate(self, input_path, name, *, review=None, options=(), code=0):
        output = "outputs/" + name
        args = ["evaluate", "requirements", "--input", input_path, "--output", output]
        if review:
            args += ["--review", review]
        result = self.call(args + list(options))
        require(result.returncode == code, f"exit {code}",
                {"code": result.returncode, "stderr": result.stderr})
        if code == 1:
            require(not (self.work / output / "requirements_confidence.json").exists(),
                    "invalid input produces no successful report")
            return None
        return self.read(output + "/requirements_confidence.json")

    def seed(self, count):
        feature = {
            "feature_id": f"BB-N{count}", "title": "合成の保存仕様", "summary": "自己BB試験用",
            "actors": ["tester"],
            "acceptance_criteria": [f"値{i}を保存すると画面に値{i}が表示される" for i in range(count)],
            "business_rules": [], "changed_areas": ["display"], "devices": ["Web"],
            "source_refs": [{"id": f"AC-{i+1}", "kind": "ac",
                             "excerpt": f"値{i}を保存すると画面に値{i}が表示される"}
                            for i in range(count)], "assumptions": [],
        }
        source = self.write(f"fixtures/n{count}.json", feature)
        report = self.evaluate(source, f"seed-{count}")
        review = self.read(f"outputs/seed-{count}/requirements_review.template.json")
        review.update(reviewer="Codex synthetic-fixture reviewer", reviewed_at="2026-09-11T16:00:00+09:00")
        by_text = {ref["excerpt"]: ref["id"] for ref in feature["source_refs"]}
        by_id = {item["requirement_id"]: item["text"] for item in report["requirements"]}
        for item in review["requirements"]:
            text = by_id[item["requirement_id"]]
            item.update(reviewed=True, oracle=text, source_refs=[by_text[text]])
        return source, feature, review

    def reviewed(self, seed, name, *, change=None, options=(), code=0):
        review = copy.deepcopy(seed[2])
        if change:
            change(review)
        path = self.write(f"reviews/{name}.json", review)
        return self.evaluate(seed[0], name, review=path, options=options, code=code)


def run(repo, lab):
    s = Suite(repo, lab)
    one_md = s.write("fixtures/日本語 空白.md", "# 自己BB\n\n## Acceptance Criteria\n- AC-1: 保存後に完了と表示する。\n")
    empty_md = s.write("fixtures/empty.md", "")
    n1, n2, n10, n100 = [s.seed(count) for count in (1, 2, 10, 100)]

    def report_check(source, name, **expected):
        value = s.evaluate(source, name)
        for key, item in expected.items():
            actual = value["counts"][key[7:]] if key.startswith("counts_") else value[key]
            require(actual == item, {key: item}, actual)
        return {key: value[key] for key in ("score", "band", "status", "counts")}

    def version_help():
        version = s.call(["--version"])
        help_result = s.call(["--help"])
        require(version.returncode == help_result.returncode == 0, "version/help exit 0")
        require("4.1.0" in version.stdout and "evaluate" in help_result.stdout,
                "version 4.1.0 and evaluate command", version.stdout)
        return version.stdout.strip()

    s.case("BB-01", version_help)
    s.case("BB-02", lambda: report_check(empty_md, "empty", score=None, band="unknown", status="insufficient_data", counts_requirements=0))
    s.case("BB-03", lambda: report_check(one_md, "unreviewed", score=69, provisional=True, counts_unreviewed_requirements=1))

    def headings():
        reports = []
        for label, heading in (("en", "Acceptance Criteria"), ("ja", "要件")):
            path = s.write(f"fixtures/headings-{label}.md", f"# 試験\n\n## {heading}\n- AC-1: 保存できる。\n- AC-2: 削除できる。\n")
            reports.append(report_check(path, "heading-" + label, counts_requirements=2))
        return reports
    s.case("BB-04", headings)

    def duplicates():
        value = copy.deepcopy(n1[1])
        value["acceptance_criteria"] = ["AC-1: Save A", "ＡＣ－２：Ｓａｖｅ　Ａ"]
        value["business_rules"] = ["BR-9: Save  A"]
        return report_check(s.write("fixtures/duplicates.json", value), "duplicates", counts_requirements=1)
    s.case("BB-05", duplicates)
    tagged = s.write("fixtures/tagged.md", "# 試験\n\n## Acceptance Criteria\n- AC-1: 応答時間は[要確認][要確認] TBD TODO。\n")
    s.case("BB-06", lambda: report_check(tagged, "tagged", counts_open_confirmations=1))

    def checked_review(seed, name, score, status=None, change=None):
        report = s.reviewed(seed, name, change=change)
        require(report["score"] == score, {"score": score}, report["score"])
        if status:
            require(report["status"] == status, {"status": status}, report["status"])
        if name in {"reviewed-all", "reviewed-half"}:
            require(report["provisional"] == (name == "reviewed-half"), "provisional follows review completeness", report["provisional"])
        return {key: report[key] for key in ("score", "status", "provisional", "counts")}
    s.case("BB-07", lambda: checked_review(n2, "reviewed-all", 100, "reviewed"))

    def half(review):
        review["requirements"][0].update(reviewed=False, oracle="", source_refs=[])
    s.case("BB-08", lambda: checked_review(n2, "reviewed-half", 84, change=half))

    def finding(review, severity):
        first = review["requirements"][0]
        review["findings"] = [{"id": "F-1", "kind": "ambiguity", "severity": severity,
                               "text": "同時保存時の表示優先順位が未確定",
                               "requirement_ids": [first["requirement_id"]],
                               "source_refs": first["source_refs"]}]
    for number, severity, score in ((9, "low", 84), (10, "medium", 84), (11, "high", 69), (12, "critical", 39)):
        s.case(f"BB-{number:02d}", lambda severity=severity, score=score: checked_review(
            n10, "severity-" + severity, score, "blocked" if severity == "critical" else "needs_confirmation",
            lambda review: finding(review, severity)))
    s.case("BB-13", lambda: checked_review(n100, "critical-100", 39, "blocked", lambda review: finding(review, "critical")))

    def resolve(review):
        finding(review, "high")
        review["resolutions"] = [{"issue_id": "review:F-1", "decision": "この合成試験では先の保存を確定した後に次を保存する。",
                                  "source_refs": review["requirements"][0]["source_refs"]}]
    s.case("BB-14", lambda: checked_review(n2, "resolved", 100, "reviewed", resolve))

    def stale():
        feature = copy.deepcopy(n2[1])
        feature["acceptance_criteria"][0] += "更新後"
        source = s.write("fixtures/stale.json", feature)
        review = s.write("reviews/stale.json", n2[2])
        s.evaluate(source, "stale", review=review, code=1)
    s.case("BB-15", stale)
    invalid_reviews = {
        16: lambda r: r.update(feature_id="WRONG"),
        17: lambda r: r["requirements"][0].update(requirement_id="REQ-UNKNOWN"),
        18: lambda r: r["requirements"][0].update(oracle=""),
        19: lambda r: r.update(reviewed_at="2026-09-11T16:00:00"),
        20: lambda r: r["requirements"][0].update(source_refs=["UNKNOWN"]),
        21: lambda r: r["requirements"].append(copy.deepcopy(r["requirements"][0])),
    }
    for number, change in invalid_reviews.items():
        s.case(f"BB-{number:02d}", lambda number=number, change=change: s.reviewed(n2, f"invalid-{number}", change=change, code=1))
    for number, threshold, code in ((22, "68.9", 0), (23, "69", 0), (24, "69.1", 2)):
        s.case(f"BB-{number}", lambda number=number, threshold=threshold, code=code: s.evaluate(
            one_md, f"threshold-{number}", options=["--fail-under", threshold], code=code))
    s.case("BB-25", lambda: s.evaluate(empty_md, "empty-threshold", options=["--fail-under", "0"], code=2))

    def tree_hash(path):
        return {str(item.relative_to(path)): digest(item) for item in path.rglob("*") if item.is_file()}

    def existing_output():
        target = s.work / "outputs/unreviewed"
        before = tree_hash(target)
        response = s.call(["evaluate", "requirements", "--input", one_md, "--output", "outputs/unreviewed"])
        require(response.returncode == 1 and tree_hash(target) == before, "exit 1 and existing outputs unchanged", response.returncode)
    s.case("BB-26", existing_output)

    def containing_output():
        before = tree_hash(s.work / "fixtures")
        response = s.call(["evaluate", "requirements", "--input", one_md, "--output", "fixtures"])
        require(response.returncode == 1 and tree_hash(s.work / "fixtures") == before, "input directory unchanged", response.returncode)
    s.case("BB-27", containing_output)

    def dry_run():
        before = digest(s.work / one_md)
        response = s.call(["evaluate", "requirements", "--input", one_md, "--output", "outputs/dry", "--dry-run"])
        require(response.returncode == 0 and not (s.work / "outputs/dry").exists(), "dry-run: exit 0, no output", response.returncode)
        require(digest(s.work / one_md) == before, "input unchanged")
    s.case("BB-28", dry_run)

    def repeat():
        first, second = s.read("outputs/unreviewed/requirements_confidence.json"), s.evaluate(one_md, "repeat")
        for key in ("input_sha256", "score", "counts", "requirements", "issues"):
            require(key in first and key in second and first[key] == second[key], f"repeat preserves {key}")
    s.case("BB-29", repeat)
    broken = s.write("fixtures/broken.json", '{"feature_id":')
    s.case("BB-30", lambda: s.evaluate(broken, "broken", code=1))

    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append("GET " + self.path)
            body = b'{"data":[{"id":"self-bb-model"}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            requests.append("POST " + self.path)
            self.send_response(400)
            self.end_headers()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    local = ["run", "local-design", "--input", one_md, "--profile", "generic", "--model", "self-bb-model",
             "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--generation-mode", "batched"]
    try:
        def estimate():
            before = len(requests)
            response = s.call(local + ["--output", "outputs/estimate", "--estimate-only"])
            require(response.returncode == 0 and len(requests) == before, "estimate succeeds without HTTP", {"code": response.returncode, "requests": requests[before:]})
            require(not (s.work / "outputs/estimate").exists(), "estimate creates no outputs")
        s.case("BB-31", estimate)

        def budget():
            before = len(requests)
            response = s.call(local + ["--output", "outputs/budget", "--token-budget", "1"])
            require(response.returncode == 1, "budget stops with exit 1", response.returncode)
            require(not any(item.startswith("POST") for item in requests[before:]), "no generation POST", requests[before:])
            manifest = s.read("outputs/budget/run_manifest.json")
            require(manifest["status"] == "failed" and "budget" in manifest["stop_reason"], "failed budget manifest", manifest["stop_reason"])
            return {"requests": requests[before:], "usage": manifest["usage_summary"]}
        s.case("BB-32", budget)

        def local_existing():
            before, request_count = tree_hash(s.work / "outputs/unreviewed"), len(requests)
            response = s.call(local + ["--output", "outputs/unreviewed"])
            require(response.returncode != 0 and len(requests) == request_count, "existing output rejected before HTTP", requests[request_count:])
            require(tree_hash(s.work / "outputs/unreviewed") == before, "existing content unchanged")
        s.case("BB-33", local_existing)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    examples = s.repo / "examples/artifacts/techniques/discount-domain"
    for path in examples.glob("*.json"):
        s.write("fixtures/discount/" + path.name, path.read_text(encoding="utf-8"))
    coverage_args = ["coverage", "--feature", "fixtures/discount/discount.feature_spec.json",
                     "--test-model", "fixtures/discount/discount.test_model.json", "--observations", "fixtures/discount/discount.observation_set.json",
                     "--risk", "fixtures/discount/discount.risk_register.json"]
    def coverage(name, *, damaged=False, evidence=False):
        cases = "fixtures/discount/discount.manual_case_set.json"
        if damaged:
            value = s.read(cases)
            value["manual_cases"][0]["coverage_inputs"][0]["step_refs"] = [999]
            cases = s.write("fixtures/discount/damaged.json", value)
            binding = s.call(["bind-cases", "--input", cases, "--test-model", "fixtures/discount/discount.test_model.json", "--output", "fixtures/discount/rebound.json"])
            require(binding.returncode == 0, "modified case rebind succeeds", binding.stderr)
            cases = "fixtures/discount/rebound.json"
        args = coverage_args + ["--cases", cases, "--build-id", "demo-1", "--output", "outputs/" + name]
        if evidence:
            args += ["--evidence", str(s.repo / "examples/coverage-evidence/discount-domain")]
        response = s.call(args)
        require(response.returncode == 0, "coverage produces report", response.stderr)
        report = s.read("outputs/" + name + "/coverage_report.json")
        if damaged:
            require(report["errors"] and report["design"]["covered_by_cases"] < 4, "bad reference is not valid coverage", report)
        else:
            require(report["design"]["required_feasible"] == report["design"]["covered_by_cases"] == 4, "design 4/4", report["design"])
            required_execution = (3, 2) if evidence else (0, 0)
            actual = (report["execution"]["executed"], report["execution"]["passed"])
            require(actual == required_execution, required_execution, actual)
        return report
    s.case("BB-34", lambda: coverage("coverage"))
    s.case("BB-35", lambda: coverage("coverage-damaged", damaged=True))

    old_cases = s.repo / "examples/artifacts/order-cancel.manual_case_set.json"
    s.write("fixtures/old-cases.json", old_cases.read_text(encoding="utf-8"))
    def migrate():
        before = digest(s.work / "fixtures/old-cases.json")
        result = s.call(["migrate", "--input", "fixtures/old-cases.json", "--output", "outputs/migrated.json", "--type", "manual_case_set"])
        require(result.returncode == 0, "migrate succeeds", result.stderr)
        original, migrated = s.read("fixtures/old-cases.json"), s.read("outputs/migrated.json")
        keys = ("tc_id", "title", "steps", "expected_results")
        require([{k: c[k] for k in keys} for c in original["manual_cases"]] ==
                [{k: c[k] for k in keys} for c in migrated["manual_cases"]], "case ID and content preserved")
        require(digest(s.work / "fixtures/old-cases.json") == before, "input unchanged")
    s.case("BB-36", migrate)
    def migrate_existing():
        for output in ("outputs/migrated.json", "fixtures/old-cases.json"):
            before = digest(s.work / output)
            result = s.call(["migrate", "--input", "fixtures/old-cases.json", "--output", output, "--type", "manual_case_set"])
            require(result.returncode != 0 and digest(s.work / output) == before, "existing file preserved", result.returncode)
    s.case("BB-37", migrate_existing)
    def gate():
        base = s.repo / "examples/artifacts"
        (s.work / "fixtures/empty-evidence").mkdir()
        result = s.call(["gate", "--feature", str(base / "order-cancel.feature_spec.json"),
                         "--risk", str(base / "order-cancel.risk_register.json"), "--cases", "fixtures/old-cases.json",
                         "--evidence", "fixtures/empty-evidence", "--build-id", "self-bb-4.1.0", "--output", "outputs/gate.json"])
        require((s.work / "outputs/gate.json").is_file(), "gate report produced", result.stderr)
        report = s.read("outputs/gate.json")
        require(report["status"] == "no_go", "no evidence => no_go", report["status"])
        return report
    s.case("BB-38", gate)

    analysis_fixture = "fixtures/calibration"
    s.write(analysis_fixture + "/snapshot.json", s.read("outputs/reviewed-all/requirements_confidence.json"))
    snapshot_hash = digest(s.work / analysis_fixture / "snapshot.json")
    row = {"project_id": "synthetic-001", "split": "calibration", "evaluated_at": "2026-07-01",
           "window_end": "2026-07-31", "report_path": "snapshot.json", "report_sha256": snapshot_hash,
           "complete": False, "defects": None, "rework_hours": None}
    def analyze(name, data, *, rejected=False):
        input_path = s.write(f"{analysis_fixture}/{name}.json", data)
        result = s.call(["--input", input_path, "--output", "outputs/" + name], analysis=True)
        if rejected:
            require(result.returncode != 0 and not (s.work / "outputs" / name / "analysis.json").exists(), "invalid dataset rejected", result.returncode)
            return None
        require(result.returncode == 0, "analysis succeeds", result.stderr)
        report = s.read("outputs/" + name + "/analysis.json")
        require(report["candidate"] is None and report["policy_changed"] is False, "no automatic calibration", report["candidate"])
        return report
    def empty_data():
        report = analyze("cal-empty", {"data_kind": "real", "window_days": 30, "cases": []})
        require(report["status"] == "insufficient_data", "insufficient_data", report["status"])
        return report
    s.case("BB-39", empty_data)
    def incomplete():
        report = analyze("cal-incomplete", {"data_kind": "synthetic", "window_days": 30, "cases": [row]})
        require(report["excluded"]["incomplete_outcomes"] == 1 and report["groups"]["calibration"]["cases"] == 0, "incomplete outcome excluded", report)
        return report
    s.case("BB-40", incomplete)
    def tampered_snapshot():
        changed = s.read(analysis_fixture + "/snapshot.json")
        changed["score"] = 99
        s.write(analysis_fixture + "/tampered.json", changed)
        return analyze("cal-hash", {"data_kind": "synthetic", "window_days": 30,
                                    "cases": [{**row, "report_path": "tampered.json"}]}, rejected=True)
    s.case("BB-41", tampered_snapshot)
    s.case("BB-42", lambda: analyze("cal-duplicate", {"data_kind": "synthetic", "window_days": 30,
                                                      "cases": [row, {**row, "split": "holdout"}]}, rejected=True))
    def synthetic():
        report = analyze("cal-synthetic", {"data_kind": "synthetic", "window_days": 30,
                                            "cases": [{**row, "complete": True, "defects": 1, "rework_hours": 2}]})
        require(report["status"] == "synthetic_only", "synthetic_only", report["status"])
        return report
    s.case("BB-43", synthetic)
    s.case("BB-44", lambda: analyze("cal-future", {"data_kind": "synthetic", "window_days": 30,
        "cases": [{**row, "evaluated_at": date.today().isoformat(),
                   "window_end": (date.today()+timedelta(days=30)).isoformat(),
                   "complete": True, "defects": 0, "rework_hours": 0}]}, rejected=True))
    s.case("BB-45", lambda: coverage("coverage-executed", evidence=True))

    # 探索結果には生の観測を残し、仕様レビューを経ずに製品不具合と確定しない。
    for suffix, threshold in (("nan", "nan"), ("inf", "inf"), ("negative", "-1"), ("over", "101")):
        def threshold_probe(suffix=suffix, threshold=threshold):
            response = s.call(["evaluate", "requirements", "--input", one_md, "--output", "outputs/probe-"+suffix, "--fail-under", threshold])
            return {"returncode": response.returncode, "stdout": response.stdout, "stderr": response.stderr}
        s.case("CH-01-"+suffix, threshold_probe)
    bom = s.write("fixtures/bom.md", "\ufeff## 要件\n- AC-1: 保存後に完了と表示する。\n")
    s.case("CH-01-bom", lambda: report_check(bom, "bom", counts_requirements=1))
    shutil.copyfile(s.lab / "installed/verification.json", s.lab / "package-verification.json")
    s.save()
    return s


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--lab", type=Path, required=True)
    args = parser.parse_args()
    run(args.repo, args.lab)
