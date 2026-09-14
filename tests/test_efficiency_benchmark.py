"""比較コマンドが失敗・欠測を隠さず、同じ設定を順番に使うことを確認する。"""

import hashlib
import json

import pytest

from bb_harness import efficiency_benchmark as benchmark


@pytest.mark.parametrize("fail", [False, True])
def test_command_preserves_measurements_and_common_config(tmp_path, monkeypatch, fail):
    fixture = tmp_path / "input.md"
    fixture.write_text("# 比較用仕様\n", encoding="utf-8")
    configs = []

    class Pipeline:
        def __init__(self, config):
            self.config = config
            configs.append(config)

        def run(self, input_path, directory):
            assert input_path == fixture
            directory.mkdir()
            compact = self.config.generation_mode == "compact"
            token_count = 150 if compact else 200
            artifacts = {
                "run_manifest": {
                    "status": "failed" if fail else "succeeded",
                    "usage_summary": {"total_tokens": token_count},
                    "error": "generation stopped" if fail else None,
                    "artifacts": {"cases": {"schema_valid": True}},
                },
                "quality_report": {"automatic_fails": []},
                "coverage_report": {
                    "errors": [],
                    "unknown_ids": [],
                    "blocked_selections": [],
                    "design": {"required_feasible": 2, "covered_by_cases": 2, "rate": 100},
                },
            }
            for name, value in artifacts.items():
                (directory / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            if fail:
                raise RuntimeError("generation stopped")

    monkeypatch.setattr(benchmark, "LocalDesignPipeline", Pipeline)
    out = tmp_path / "out"
    code = benchmark.main(
        ["--input", str(fixture), "--output", str(out), "--token-budget", "100000"]
    )
    # 自己申告だけの不完全なbundleは、生成statusにかかわらず拒否する。
    assert code == 1
    result = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    assert result["token_reduction_percent"] is None
    assert result["input_sha256"] == hashlib.sha256(fixture.read_bytes()).hexdigest()
    assert [config.generation_mode for config in configs] == ["full", "compact"]
    assert configs[0].token_budget == configs[1].token_budget == 100000
    assert "api_key" not in result["common_config"]
    assert result["runs"]["full"]["usage"]["total_tokens"] == 200
    assert result["runs"]["full"]["schema_valid"] is False


@pytest.mark.parametrize("existing_input,existing_output", [(False, False), (True, True)])
def test_command_refuses_bad_paths_before_model_call(tmp_path, existing_input, existing_output):
    fixture = tmp_path / "spec.md"
    out = tmp_path / "out"
    if existing_input:
        fixture.write_text("spec", encoding="utf-8")
    if existing_output:
        out.mkdir()
    with pytest.raises(SystemExit):
        benchmark.main(["--input", str(fixture), "--output", str(out)])
