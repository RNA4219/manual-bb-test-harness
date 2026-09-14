"""Comprehensive tests for scripts/evaluate-gate.py.

Tests all major branches and functions:
- load_evidence_files (file/directory loading)
- extract_case_results (test case result extraction)
- count_results_by_priority (P0/P1/P2/P3 counting)
- extract_open_defects (defect extraction)
- assess_residual_risks (residual/blocking risk assessment)
- determine_gate_status (go/conditional_go/no_go decision)
- generate_gate_decision (gate_decision.json generation)
- main (CLI execution with various inputs)

# TRACE: scripts/evaluate-gate.py (role: operations)
# TRACE: skills/manual-bb-test-harness/references/risk-and-gate-policy.md (role: reference)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from bb_harness import gate_engine

REPO_ROOT = Path(__file__).parent.parent


def load_evaluate_gate_module() -> object:
    """配布される package 正本を検証する。"""
    return gate_engine


class TestLoadEvidenceFiles:
    """Tests for load_evidence_files function.

    # TRACE: scripts/evaluate-gate.py:64-93 (role: file_loading)
    """

    def test_load_single_evidence_file(self, tmp_path: Path) -> None:
        """Load execution evidence from single file."""
        module = load_evaluate_gate_module()
        evidence_file = tmp_path / "TC-001.json"
        evidence_file.write_text(
            json.dumps({"tc_id": "TC-001", "result": "pass"}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = module.load_evidence_files(evidence_file)
        assert len(result) == 1
        assert result[0]["tc_id"] == "TC-001"

    def test_load_evidence_directory(self, tmp_path: Path) -> None:
        """Load execution evidence from directory."""
        module = load_evaluate_gate_module()

        # Create multiple evidence files
        (tmp_path / "execution_001.json").write_text(
            json.dumps({"tc_id": "TC-001", "result": "pass"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (tmp_path / "TC-002.json").write_text(
            json.dumps({"tc_id": "TC-002", "result": "fail"}, ensure_ascii=False),
            encoding="utf-8",
        )
        # Non-evidence file (should be skipped unless has tc_id)
        (tmp_path / "other.json").write_text(
            json.dumps({"other": "data"}, ensure_ascii=False),
            encoding="utf-8",
        )
        # Evidence file with tc_id field
        (tmp_path / "charter.json").write_text(
            json.dumps({"tc_id": "CHARTER-001", "result": "pass"}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = module.load_evidence_files(tmp_path)
        # Should load execution_, TC-*, and files with tc_id field
        assert len(result) >= 2

    def test_load_evidence_file_not_found(self, tmp_path: Path) -> None:
        """Load evidence from non-existent path raises error."""
        module = load_evaluate_gate_module()
        non_existent = tmp_path / "nonexistent.json"

        with pytest.raises(ValueError, match="Path not found"):
            module.load_evidence_files(non_existent)


class TestExtractCaseResults:
    """Tests for extract_case_results function.

    # TRACE: scripts/evaluate-gate.py:96-141 (role: result_extraction)
    """

    def test_extract_scripted_case_results(self, tmp_path: Path) -> None:
        """Extract results for scripted test cases."""
        module = load_evaluate_gate_module()

        evidence_list = [
            {"tc_id": "TC-001", "result": "pass"},
            {"tc_id": "TC-002", "result": "fail"},
        ]
        manual_cases = {
            "manual_cases": [
                {"tc_id": "TC-001", "priority": "P0", "trace_to": ["RISK-001"]},
                {"tc_id": "TC-002", "priority": "P1", "trace_to": ["RISK-002"]},
            ]
        }

        result = module.extract_case_results(evidence_list, manual_cases)
        assert "TC-001" in result
        assert result["TC-001"]["result"] == "pass"
        assert result["TC-001"]["priority"] == "P0"
        assert result["TC-002"]["result"] == "fail"

    def test_extract_exploratory_charter_results(self, tmp_path: Path) -> None:
        """Extract results for exploratory charters."""
        module = load_evaluate_gate_module()

        evidence_list = [
            {"charter_id": "CHARTER-001", "result": "pass"},
        ]
        manual_cases = {
            "exploratory_charters": [
                {"id": "CHARTER-001", "priority": "P2", "trace_to": ["RISK-003"]}
            ]
        }

        result = module.extract_case_results(evidence_list, manual_cases)
        assert "CHARTER-001" in result
        assert result["CHARTER-001"]["type"] == "exploratory"

    def test_extract_with_defect_stub(self, tmp_path: Path) -> None:
        """Extract results with defect stub."""
        module = load_evaluate_gate_module()

        evidence_list = [
            {
                "tc_id": "TC-001",
                "result": "fail",
                "defect_stub": {"title": "Login fails", "severity": "high"},
            }
        ]
        manual_cases = {
            "manual_cases": [{"tc_id": "TC-001", "priority": "P0", "trace_to": []}]
        }

        result = module.extract_case_results(evidence_list, manual_cases)
        assert result["TC-001"]["defect_stub"]["title"] == "Login fails"

    def test_extract_retired_case_without_evidence(self, tmp_path: Path) -> None:
        """Retired cases are represented separately from missing evidence."""
        module = load_evaluate_gate_module()

        manual_cases = {
            "manual_cases": [
                {
                    "tc_id": "TC-RET-001",
                    "priority": "P1",
                    "trace_to": ["RISK-RET-001"],
                    "status": "retired",
                    "retired_reason": "自動テストへ移管済み",
                    "replacement_refs": ["hate:AETE-001"],
                    "placement_change_ref": "qeg:PLC-001",
                }
            ]
        }

        result = module.extract_case_results([], manual_cases)

        assert result["TC-RET-001"]["result"] == "retired"
        assert result["TC-RET-001"]["replacement_refs"] == ["hate:AETE-001"]


class TestCountResultsByPriority:
    """Tests for count_results_by_priority function.

    # TRACE: scripts/evaluate-gate.py:144-166 (role: counting)
    """

    def test_count_all_priorities(self, tmp_path: Path) -> None:
        """Count pass/fail/skip by priority."""
        module = load_evaluate_gate_module()

        case_results = {
            "TC-001": {"result": "pass", "priority": "P0"},
            "TC-002": {"result": "fail", "priority": "P0"},
            "TC-003": {"result": "pass", "priority": "P1"},
            "TC-004": {"result": "skip", "priority": "P2"},
            "TC-005": {"result": "pass", "priority": "P3"},
        }

        counts = module.count_results_by_priority(case_results)
        assert counts["P0"]["pass"] == 1
        assert counts["P0"]["fail"] == 1
        assert counts["P0"]["total"] == 2
        assert counts["P1"]["pass"] == 1
        assert counts["P2"]["skip"] == 1

    def test_count_unknown_priority_defaults_to_p2(self, tmp_path: Path) -> None:
        """Unknown priority defaults to P2."""
        module = load_evaluate_gate_module()

        case_results = {
            "TC-001": {"result": "pass", "priority": "UNKNOWN"},
        }

        counts = module.count_results_by_priority(case_results)
        assert counts["P2"]["pass"] == 1

    def test_retired_case_excluded_from_priority_counts(self, tmp_path: Path) -> None:
        """Retired cases do not count as skipped or failed manual evidence."""
        module = load_evaluate_gate_module()

        case_results = {
            "TC-RET-001": {"result": "retired", "priority": "P1"},
            "TC-001": {"result": "pass", "priority": "P1"},
        }

        counts = module.count_results_by_priority(case_results)

        assert counts["P1"]["total"] == 1
        assert counts["P1"]["pass"] == 1


class TestExtractOpenDefects:
    """Tests for extract_open_defects function.

    # TRACE: scripts/evaluate-gate.py:169-185 (role: defect_extraction)
    """

    def test_extract_defects_from_failed_cases(self, tmp_path: Path) -> None:
        """Extract defects from failed test cases."""
        module = load_evaluate_gate_module()

        evidence_list = [
            {
                "tc_id": "TC-001",
                "result": "fail",
                "defect_stub": {"title": "Bug 1", "severity": "high"},
            },
            {
                "tc_id": "TC-002",
                "result": "fail",
                "defect_stub": {"title": "Bug 2", "severity": "critical"},
            },
            {"tc_id": "TC-003", "result": "pass"},
        ]

        defects = module.extract_open_defects(evidence_list)
        assert len(defects) == 2
        assert defects[0]["title"] == "Bug 1"

    def test_extract_defects_no_defect_stub(self, tmp_path: Path) -> None:
        """Failed case without defect_stub is skipped."""
        module = load_evaluate_gate_module()

        evidence_list = [
            {"tc_id": "TC-001", "result": "fail"},
        ]

        defects = module.extract_open_defects(evidence_list)
        assert len(defects) == 0


class TestAssessResidualRisks:
    """Tests for assess_residual_risks function.

    # TRACE: scripts/evaluate-gate.py:188-233 (role: risk_assessment)
    """

    def test_assess_blocking_risks_p0_untested(self, tmp_path: Path) -> None:
        """P0 risk without test cases is blocking."""
        module = load_evaluate_gate_module()

        risk_register = {
            "risks": [
                {"id": "RISK-001", "priority": "P0", "scenario": "Critical risk"},
            ]
        }
        case_results = {}  # No tests

        residual, blocking = module.assess_residual_risks(risk_register, case_results)
        assert "RISK-001" in blocking
        assert len(residual) == 0

    def test_assess_blocking_risks_p0_failed(self, tmp_path: Path) -> None:
        """P0 risk with failed test is blocking."""
        module = load_evaluate_gate_module()

        risk_register = {
            "risks": [
                {"id": "RISK-001", "priority": "P0", "scenario": "Critical risk"},
            ]
        }
        case_results = {
            "TC-001": {"result": "fail", "priority": "P0", "trace_to": ["RISK-001"]}
        }

        residual, blocking = module.assess_residual_risks(risk_register, case_results)
        assert "RISK-001" in blocking

    def test_assess_residual_risks_p2_untested(self, tmp_path: Path) -> None:
        """P2/P3 risk without test cases is residual."""
        module = load_evaluate_gate_module()

        risk_register = {
            "risks": [
                {"id": "RISK-002", "priority": "P2", "scenario": "Low risk scenario"},
            ]
        }
        case_results = {}

        residual, blocking = module.assess_residual_risks(risk_register, case_results)
        assert len(residual) == 1
        assert "RISK-002" in residual[0]
        assert len(blocking) == 0

    def test_assess_risk_trace_to_field(self, tmp_path: Path) -> None:
        """Risk's trace_to field is also checked."""
        module = load_evaluate_gate_module()

        risk_register = {
            "risks": [
                {"id": "RISK-001", "priority": "P0", "scenario": "Risk", "trace_to": ["TC-001"]}
            ]
        }
        case_results = {
            "TC-001": {"result": "pass", "priority": "P0", "trace_to": []}
        }

        residual, blocking = module.assess_residual_risks(risk_register, case_results)
        # Risk is tested via risk.trace_to, should not be blocking
        assert len(blocking) == 0

    def test_retired_case_does_not_block_p1_risk(self, tmp_path: Path) -> None:
        """Retired replacement coverage is not treated as missing manual execution."""
        module = load_evaluate_gate_module()

        risk_register = {
            "risks": [
                {
                    "id": "RISK-RET-001",
                    "priority": "P1",
                    "scenario": "Moved to automated evidence",
                    "trace_to": ["TC-RET-001"],
                }
            ]
        }
        case_results = {
            "TC-RET-001": {
                "result": "retired",
                "priority": "P1",
                "trace_to": ["RISK-RET-001"],
            }
        }

        residual, blocking = module.assess_residual_risks(risk_register, case_results)

        assert residual == []
        assert blocking == []


class TestDetermineGateStatus:
    """Tests for determine_gate_status function.

    # TRACE: scripts/evaluate-gate.py:236-287 (role: gate_decision)
    """

    def test_gate_no_go_blocker_defects(self, tmp_path: Path) -> None:
        """Blocker/critical/high defects cause no_go."""
        module = load_evaluate_gate_module()

        counts = {
            "P0": {"pass": 2, "fail": 0, "skip": 0, "total": 2},
            "P1": {"pass": 1, "fail": 0, "skip": 0, "total": 1},
            "P2": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
            "P3": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        }
        defects = [{"title": "Critical bug", "severity": "critical"}]
        blocking_risks = []

        status, reasons, waivers = module.determine_gate_status(
            counts, defects, blocking_risks, "standard"
        )
        assert status == "no_go"
        assert "Blocker" in reasons[0] or "critical" in reasons[0]

    def test_gate_no_go_p0_fail(self, tmp_path: Path) -> None:
        """P0 pass rate below 100% causes no_go."""
        module = load_evaluate_gate_module()

        counts = {
            "P0": {"pass": 1, "fail": 1, "skip": 0, "total": 2},
            "P1": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
            "P2": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
            "P3": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        }
        defects = []
        blocking_risks = []

        status, reasons, waivers = module.determine_gate_status(
            counts, defects, blocking_risks, "standard"
        )
        assert status == "no_go"
        assert "P0" in reasons[0]

    def test_gate_no_go_blocking_risks(self, tmp_path: Path) -> None:
        """Unresolved blocking risks cause no_go."""
        module = load_evaluate_gate_module()

        counts = {
            "P0": {"pass": 2, "fail": 0, "skip": 0, "total": 2},
            "P1": {"pass": 1, "fail": 0, "skip": 0, "total": 1},
            "P2": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
            "P3": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        }
        defects = []
        blocking_risks = ["RISK-001"]

        status, reasons, waivers = module.determine_gate_status(
            counts, defects, blocking_risks, "standard"
        )
        assert status == "no_go"
        assert "Blocking" in reasons[0]

    def test_gate_go_all_pass(self, tmp_path: Path) -> None:
        """All P0/P1 pass with no defects/blocking risks is go."""
        module = load_evaluate_gate_module()

        counts = {
            "P0": {"pass": 2, "fail": 0, "skip": 0, "total": 2},
            "P1": {"pass": 1, "fail": 0, "skip": 0, "total": 1},
            "P2": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
            "P3": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        }
        defects = []
        blocking_risks = []

        status, reasons, waivers = module.determine_gate_status(
            counts, defects, blocking_risks, "standard"
        )
        assert status == "go"
        assert len(waivers) == 0

    def test_gate_no_implicit_waiver_lean_profile(self, tmp_path: Path) -> None:
        """閾値未達を lean 指定だけで自動承認しない。"""
        module = load_evaluate_gate_module()

        counts = {
            "P0": {"pass": 2, "fail": 0, "skip": 0, "total": 2},
            "P1": {"pass": 1, "fail": 1, "skip": 0, "total": 2},  # 50% pass
            "P2": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
            "P3": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        }
        defects = []
        blocking_risks = []

        status, reasons, waivers = module.determine_gate_status(
            counts, defects, blocking_risks, "lean"
        )
        assert status == "no_go"
        assert waivers == []

    def test_gate_no_go_p1_fail_standard(self, tmp_path: Path) -> None:
        """P1 below 95% in standard profile causes no_go."""
        module = load_evaluate_gate_module()

        counts = {
            "P0": {"pass": 2, "fail": 0, "skip": 0, "total": 2},
            "P1": {"pass": 1, "fail": 1, "skip": 0, "total": 2},  # 50% pass
            "P2": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
            "P3": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        }
        defects = []
        blocking_risks = []

        status, reasons, waivers = module.determine_gate_status(
            counts, defects, blocking_risks, "standard"
        )
        assert status == "no_go"


class TestGenerateGateDecision:
    """Tests for generate_gate_decision function.

    # TRACE: scripts/evaluate-gate.py:290-327 (role: output_generation)
    """

    def test_generate_gate_decision_go(self, tmp_path: Path) -> None:
        """Generate go gate decision."""
        module = load_evaluate_gate_module()

        gate = module.generate_gate_decision(
            "FEATURE-001",
            "go",
            "standard",
            ["P0 pass rate: 100%"],
            [],
            [],
            [],
            [],
            build_id="build-test",
            evidence_summary={"manual_by_priority": {}, "mandatory_observation_rate": 100},
        )
        module.validate_schema(gate, "gate_decision.schema.json")

        assert gate["feature_id"] == "FEATURE-001"
        assert gate["status"] == "go"
        assert gate["profile"] == "standard"
        assert "blocking_risks" not in gate

    def test_generate_gate_decision_with_waivers(self, tmp_path: Path) -> None:
        """Generate conditional_go with waivers."""
        module = load_evaluate_gate_module()

        gate = module.generate_gate_decision(
            "FEATURE-001",
            "conditional_go",
            "lean",
            ["P0 pass rate: 100%", "P1 pass rate: 80%"],
            [],
            [{"id": "WAIVER-001", "risk_ids": ["RISK-001"],
              "reason": "限定公開で影響を制限", "owner": "release-owner",
              "approver": "release-lead", "approved_at": "2026-09-12T12:00:00Z",
              "approval_ref": "DECISION-001",
              "expires_at": "2099-01-01T00:00:00Z",
              "containment": "対象機能を限定公開", "rollback": "機能フラグを戻す"}],
            [],
            [],
            build_id="build-test",
            evidence_summary={"manual_by_priority": {}, "mandatory_observation_rate": 100},
        )
        module.validate_schema(gate, "gate_decision.schema.json")

        assert gate["status"] == "conditional_go"
        assert len(gate["waivers"]) == 1

    def test_generate_gate_decision_with_residual_risks(self, tmp_path: Path) -> None:
        """Generate gate decision with residual risks."""
        module = load_evaluate_gate_module()

        gate = module.generate_gate_decision(
            "FEATURE-001",
            "go",
            "standard",
            ["P0 pass rate: 100%"],
            [],
            [],
            ["RISK-002: Low priority risk"],
            [],
            build_id="build-test",
            evidence_summary={"manual_by_priority": {}, "mandatory_observation_rate": 100},
        )
        module.validate_schema(gate, "gate_decision.schema.json")

        assert len(gate["residual_risks"]) == 1
        assert "Review residual risks in next sprint" in gate["required_follow_up"]

    def test_generate_gate_decision_with_defects(self, tmp_path: Path) -> None:
        """Generate gate decision with medium defects."""
        module = load_evaluate_gate_module()

        gate = module.generate_gate_decision(
            "FEATURE-001",
            "go",
            "standard",
            ["P0 pass rate: 100%"],
            [],
            [],
            [],
            [{"title": "Minor bug", "severity": "medium"}],
            build_id="build-test",
            evidence_summary={"manual_by_priority": {}, "mandatory_observation_rate": 100},
        )
        module.validate_schema(gate, "gate_decision.schema.json")

        assert "Monitor" in gate["required_follow_up"][0]

    def test_generate_gate_decision_with_retired_cases(self, tmp_path: Path) -> None:
        """Generate gate decision preserves retired case metadata."""
        module = load_evaluate_gate_module()

        gate = module.generate_gate_decision(
            "FEATURE-001",
            "go",
            "standard",
            ["P0 pass rate: 100%"],
            [],
            [],
            [],
            [],
            retired_cases=[
                {
                    "id": "TC-RET-001",
                    "priority": "P1",
                    "replacement_refs": ["hate:AETE-001"],
                    "placement_change_ref": "qeg:PLC-001",
                    "retired_reason": "自動テストへ移管済み",
                }
            ],
            build_id="build-test",
            evidence_summary={"manual_by_priority": {}, "mandatory_observation_rate": 100},
        )
        module.validate_schema(gate, "gate_decision.schema.json")

        assert gate["retired_cases"][0]["id"] == "TC-RET-001"
        assert gate["retired_cases"][0]["replacement_refs"] == ["hate:AETE-001"]
        assert any("Retired cases excluded" in reason for reason in gate["reasons"])


def write_gate_inputs(directory: Path, *, profile: str = "standard") -> dict[str, Path]:
    """成功シナリオは全入力を正規スキーマに適合させる。"""
    directory.mkdir(parents=True, exist_ok=True)
    feature = "TEST-GATE"
    source = [{"id": "AC-1", "kind": "ac"}]
    artifacts = {
        "risk_register": {"feature_id": feature, "risks": [{
            "id": "RISK-001", "scenario": "正常操作の失敗", "priority": "P0",
            "impact": 5, "likelihood": 3, "trace_to": ["TC-001"],
        }]},
        "manual_case_set": {"feature_id": feature, "spec_revision": "spec-rev-1", "manual_cases": [{
            "tc_id": "TC-001", "revision": "case-rev-1",
            "content_hash": "sha256:tc-001", "oracle_revision": "oracle-rev-1",
            "title": "正常操作", "priority": "P0",
            "primary_view": "black", "steps": ["操作する"],
            "expected_results": ["完了を確認できる"],
            "oracle": {"type": "specified", "refs": ["AC-1"]},
            "trace_to": ["RISK-001", "OBS-STATE-01"],
        }]},
        "feature_spec": {"feature_id": feature, "revision": "spec-rev-1", "title": "対象機能",
                         "acceptance_criteria": ["AC-1: 操作が完了する"], "source_refs": source},
        "test_model": {"feature_id": feature, "coverage_items": [{
            "id": "COV-STATE-NORMAL", "dimension": "state",
            "technique": "state_transition", "applicability": "applicable",
            "mandatory": True, "coverage_criterion": "each_transition",
            "source_refs": source,
        }], "flows": ["normal"], "data_partitions": [], "rule_columns": [],
            "states": ["ready", "done"], "role_matrix": [], "regression_edges": []},
        "observation_set": {"feature_id": feature, "observations": [{
            "id": "OBS-STATE-01", "title": "正常完了", "view": "black", "mandatory": True,
            "coverage_item_id": "COV-STATE-NORMAL",
            "techniques": ["state_transition"], "source_refs": source,
        }]},
        "automation_evidence": {"feature_id": feature, "build_id": "build-test",
            "coverage_scope": "impacted_module" if profile == "lean" else "changed_code",
            "coverage_percent": 100, "hotspot_review_percent": 100,
            "test_suites": [{"suite_id": "regression", "status": "passed", "total": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0, "source_refs": [{"id": "CI-1", "kind": "auto_test"}]}],
            "new_issues": {"blocker": 0, "critical": 0},
            "source_refs": [{"id": "CI-1", "kind": "auto_test"}]},
        "execution_evidence": {"feature_id": feature, "build_id": "build-test", "run_id": "RUN-1",
            "timestamp": "2026-09-12T00:00:00Z", "tc_id": "TC-001", "result": "pass",
            "case_revision": "case-rev-1", "spec_revision": "spec-rev-1",
            "oracle_revision": "oracle-rev-1", "case_content_hash": "sha256:tc-001",
            "oracle_refs": ["AC-1"]},
    }
    paths = {}
    for kind, value in artifacts.items():
        gate_engine.validate_schema(value, f"{kind}.schema.json")
        path = directory / f"test.{kind}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        paths[kind] = path
    return paths


def run_gate_cli(args: list[str]) -> int:
    import subprocess

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/evaluate-gate.py"), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.returncode


class TestEvaluateGateMain:
    """CLI / native の両方で完全な入力から同じ Gate 2.0 artifact を作る。"""

    def test_main_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as caught:
            gate_engine.main(["--version"])
        assert caught.value.code == 0
        assert "evaluate-gate" in capsys.readouterr().out

    @pytest.mark.parametrize("runner", [gate_engine.main, run_gate_cli])
    @pytest.mark.parametrize("profile", ["standard", "strict"])
    def test_main_with_input_directory(self, tmp_path: Path, runner, profile: str) -> None:
        directory = tmp_path / "artifacts"
        write_gate_inputs(directory, profile=profile)
        output = tmp_path / "gate.json"
        assert runner(["--input", str(directory), "--output", str(output), "--profile", profile]) == 0
        gate = json.loads(output.read_text(encoding="utf-8"))
        gate_engine.validate_schema(gate, "gate_decision.schema.json")
        assert gate["status"] == "go"
        assert gate["profile"] == profile
        assert gate["build_id"] == "build-test"
        assert gate["evidence_summary"]["mandatory_observation_rate"] == 100

    @pytest.mark.parametrize("runner", [gate_engine.main, run_gate_cli])
    def test_main_with_separate_inputs(self, tmp_path: Path, runner) -> None:
        inputs = write_gate_inputs(tmp_path / "artifacts")
        output = tmp_path / "gate.json"
        args = ["--output", str(output)]
        for option, kind in [("risk", "risk_register"), ("cases", "manual_case_set"),
                             ("evidence", "execution_evidence"), ("feature", "feature_spec"),
                             ("model", "test_model"),
                             ("observations", "observation_set"), ("automation", "automation_evidence")]:
            args.extend([f"--{option}", str(inputs[kind])])
        assert runner(args) == 0
        gate = json.loads(output.read_text(encoding="utf-8"))
        gate_engine.validate_schema(gate, "gate_decision.schema.json")
        assert gate["status"] == "go"

    @pytest.mark.parametrize("kind,name", [("risk_register", "project-risk-register.json"),
                                           ("manual_case_set", "test-cases.json")])
    def test_main_with_alternative_filename(self, tmp_path: Path, kind: str, name: str) -> None:
        directory = tmp_path / "artifacts"
        inputs = write_gate_inputs(directory)
        inputs[kind].rename(directory / name)
        output = tmp_path / "gate.json"
        assert gate_engine.main(["--input", str(directory), "--output", str(output)]) == 0
        assert json.loads(output.read_text(encoding="utf-8"))["status"] == "go"

    @pytest.mark.parametrize("kind", ["risk_register", "manual_case_set"])
    def test_main_missing_required_artifact(self, tmp_path: Path, kind: str) -> None:
        directory = tmp_path / "artifacts"
        inputs = write_gate_inputs(directory)
        inputs[kind].unlink()
        output = tmp_path / "gate.json"
        assert gate_engine.main(["--input", str(directory), "--output", str(output)]) == 1
        assert not output.exists()

    @pytest.mark.parametrize("kind", ["risk_register", "manual_case_set", "execution_evidence"])
    def test_main_rejects_incomplete_artifact(self, tmp_path: Path, kind: str) -> None:
        directory = tmp_path / "artifacts"
        inputs = write_gate_inputs(directory)
        inputs[kind].write_text(json.dumps({"feature_id": "TEST-GATE"}), encoding="utf-8")
        output = tmp_path / "gate.json"
        assert gate_engine.main(["--input", str(directory), "--output", str(output)]) == 1
        assert not output.exists()

    @pytest.mark.parametrize("runner", [gate_engine.main, run_gate_cli])
    def test_main_missing_input(self, tmp_path: Path, runner) -> None:
        output = tmp_path / "gate.json"
        assert runner(["--output", str(output)]) == 1
        assert not output.exists()


class TestGateThresholds:
    def test_thresholds_exist(self) -> None:
        thresholds = gate_engine.GATE_THRESHOLDS
        assert thresholds["strict"]["p0_pass"] == 100
        assert thresholds["standard"]["p1_pass"] == 95
        assert thresholds["lean"]["p1_pass"] == 80


def test_compat_helper_allows_unplanned_p0() -> None:
    """互換公開関数でもP0が計画にない集計をN/Aとして扱う。"""
    module = load_evaluate_gate_module()
    counts = {
        priority: {"pass": 0, "fail": 0, "skip": 0, "blocked": 0, "unknown": 0, "untested": 0, "total": 0}
        for priority in ("P0", "P1", "P2", "P3")
    }
    counts["P2"] = {**counts["P2"], "pass": 1, "total": 1}

    status, reasons, _ = module.determine_gate_status(counts, [], [], "standard")

    assert status == "go", reasons
