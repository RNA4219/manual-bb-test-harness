"""初回証跡を保持して、前提修正と不具合の対照試験を外部CLIで実施する。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def run(repo: Path, lab: Path) -> None:
    repo, lab = repo.resolve(), lab.resolve()
    work = lab / "work"
    followup = work / "followup"
    followup.mkdir(exist_ok=False)
    sut = lab / "installed/venv/Scripts/bb-harness.exe"
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    commands, results, requests = [], [], []

    def read(path):
        return json.loads((work / path).read_text(encoding="utf-8"))

    def write(path, value):
        target = work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
        return path

    def call(name, args):
        started = time.monotonic()
        response = subprocess.run([str(sut), *map(str, args)], cwd=work, env=env,
                                  capture_output=True, encoding="utf-8", timeout=60)
        commands.append({"name": name, "args": list(map(str, args)), "code": response.returncode,
                         "stdout": response.stdout, "stderr": response.stderr,
                         "elapsed_seconds": round(time.monotonic() - started, 3)})
        return response

    def check(identifier, operation):
        try:
            detail = operation()
            result, error = "pass", None
        except AssertionError as exc:
            result, error, detail = "fail", str(exc), None
        results.append({"id": identifier, "result": result, "error": error, "details": detail})
        print(identifier, result, error or "", flush=True)

    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    def resolved():
        report = read("probes/closed/requirements_confidence.json")
        require(report["score"] == 100 and report["counts"]["open_confirmations"] == 0,
                "公開reportのissue_idで解決後は100点・未解決0件")
        return {"score": report["score"], "counts": report["counts"]}

    def rebound():
        report = read("probes/coverage/coverage_report.json")
        require(bool(report["errors"]) and report["design"]["covered_by_cases"] == 3,
                "正規rebind後も不正手順参照を加算せず設計3/4")
        return {"design": report["design"], "errors": report["errors"]}

    check("BB-14-corrected", resolved)
    check("BB-35-corrected", rebound)

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
    base = ["run", "local-design", "--profile", "generic", "--model", "self-bb-model",
            "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--generation-mode", "batched"]
    try:
        body = (work / "probes/ascii-minimal.md").read_text(encoding="utf-8")
        for name, path in (("ascii", "followup/ascii.md"),
                           ("japanese-directory", "followup/日本語ディレクトリ/ascii.md"),
                           ("mixed-filename", "followup/日本語-ascii.md"),
                           ("japanese-filename", "followup/日本語.md")):
            write(path, body)

            def estimate(name=name, path=path):
                before = len(requests)
                output = "followup/estimate-" + name
                response = call(name, base + ["--input", path, "--output", output, "--estimate-only"])
                require(len(requests) == before, "見積もりでHTTP呼出があった")
                require(not (work / output).exists(), "見積もりが出力を作成した")
                require(response.returncode == 0, response.stderr)
                return {"http_requests": [], "output_created": False}

            check("LOCAL-" + name, estimate)

        def budget():
            before = len(requests)
            response = call("ascii-budget", base + ["--input", "followup/ascii.md",
                            "--output", "followup/budget", "--token-budget", "1"])
            actual_requests = requests[before:]
            manifest = read("followup/budget/run_manifest.json")
            require(response.returncode == 1, "予算停止は終了1")
            require(not any(item.startswith("POST") for item in actual_requests), "予算停止前に生成を呼んだ")
            require(manifest["status"] == "failed" and "budget" in manifest["stop_reason"],
                    json.dumps(manifest, ensure_ascii=False))
            return {"requests": actual_requests, "stop_reason": manifest["stop_reason"],
                    "usage_summary": manifest["usage_summary"]}

        check("BB-32-ascii-control", budget)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    artifacts = repo / "examples/artifacts"
    for kind in ("feature_spec", "risk_register", "manual_case_set"):
        write(f"followup/gate-input/order-cancel.{kind}.json",
              (artifacts / f"order-cancel.{kind}.json").read_text(encoding="utf-8"))

    def empty_gate():
        output = "followup/gate-empty.json"
        response = call("gate-input-empty", ["gate", "--input", "followup/gate-input",
                         "--build-id", "self-bb-4.1.0", "--output", output])
        require(response.returncode == 0 and (work / output).is_file(), response.stderr)
        report = read(output)
        require(report["status"] == "no_go", "実施なしはno_go")
        return report

    check("BB-38-corrected-empty", empty_gate)

    # SUTに与える合成blocked証跡。manual-bb自身の実測結果ではない。
    cases = read("followup/gate-input/order-cancel.manual_case_set.json")
    write("followup/gate-input/blocked.execution_evidence.json", {
        "run_id": "SYNTHETIC-CONTROL-ONLY", "feature_id": cases["feature_id"],
        "build_id": "self-bb-4.1.0", "tc_id": cases["manual_cases"][0]["tc_id"],
        "timestamp": "2026-09-11T17:00:00+09:00", "result": "blocked",
        "tester": "Codex synthetic SUT input", "actual": ["合成の未実施状態"],
    })

    def partial_gate():
        output = "followup/gate-blocked.json"
        response = call("gate-partial-blocked", ["gate", "--input", "followup/gate-input",
                         "--build-id", "self-bb-4.1.0", "--output", output])
        require(response.returncode == 0, response.stderr)
        report = read(output)
        require(report["status"] == "no_go", "blockedと証跡なしのケースはno_go")
        counts = report["evidence_summary"]["manual_by_priority"]
        require(sum(row["pass"] for row in counts.values()) == 0, "証跡なしをpassに加算した")
        return report

    check("GATE-partial-blocked", partial_gate)
    value = {"target": "bb-harness 4.1.0 from PyPI", "results": results,
             "commands": commands, "http_requests": requests,
             "note": "初回results.jsonとtriage-probes.jsonは変更していない"}
    with (lab / "followup-results.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--lab", required=True, type=Path)
    args = parser.parse_args()
    run(args.repo, args.lab)
