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

import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).parent.parent


def load_evaluate_gate_module() -> object:
    """Load evaluate-gate.py module dynamically."""
    spec = importlib.util.spec_from_file_location(
        "evaluate_gate", REPO_ROOT / "scripts" / "evaluate-gate.py"
    )
    if spec is None or spec.loader is None:
        pytest.skip("Cannot load evaluate-gate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["evaluate_gate"] = module
    spec.loader.exec_module(module)
    return module


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

    def test_gate_conditional_go_lean_profile(self, tmp_path: Path) -> None:
        """Lean profile with P1 below threshold gives conditional_go."""
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
        assert status == "conditional_go"
        assert len(waivers) > 0
        assert "waived" in waivers[0]

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
        )

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
            ["P1 pass rate waived for lean profile"],
            [],
            [],
        )

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
        )

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
        )

        assert "Monitor" in gate["required_follow_up"][0]


class TestEvaluateGateMain:
    """Tests for main function (CLI execution).

    # TRACE: scripts/evaluate-gate.py:330-459 (role: cli_entry)
    """

    def test_main_version(self, tmp_path: Path) -> None:
        """Version flag works."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "evaluate-gate.py"), "--version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "evaluate-gate" in result.stdout

    def test_main_missing_input(self, tmp_path: Path) -> None:
        """Missing input arguments returns error."""
        import subprocess

        output_file = tmp_path / "gate.json"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "evaluate-gate.py"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_main_with_input_directory(self, tmp_path: Path) -> None:
        """Main with --input directory works."""
        import subprocess

        # Create test artifacts
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Risk register
        (artifacts_dir / "risk_register.json").write_text(
            json.dumps(
                {
                    "feature_id": "TEST-001",
                    "risks": [
                        {"id": "RISK-001", "priority": "P2", "scenario": "Low risk"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # Manual case set
        (artifacts_dir / "manual_case_set.json").write_text(
            json.dumps(
                {
                    "feature_id": "TEST-001",
                    "manual_cases": [
                        {"tc_id": "TC-001", "priority": "P0", "trace_to": []},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # Execution evidence
        (artifacts_dir / "execution_001.json").write_text(
            json.dumps({"tc_id": "TC-001", "result": "pass"}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "evaluate-gate.py"),
                "--input",
                str(artifacts_dir),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert output_file.exists()

        gate = json.loads(output_file.read_text(encoding="utf-8"))
        assert gate["status"] in ["go", "conditional_go", "no_go"]

    def test_main_with_separate_inputs(self, tmp_path: Path) -> None:
        """Main with separate --evidence, --risk, --cases works."""
        import subprocess

        # Create separate files
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "TC-001.json").write_text(
            json.dumps({"tc_id": "TC-001", "result": "pass"}, ensure_ascii=False),
            encoding="utf-8",
        )

        risk_file = tmp_path / "risk.json"
        risk_file.write_text(
            json.dumps(
                {
                    "feature_id": "TEST-002",
                    "risks": [{"id": "RISK-001", "priority": "P2", "scenario": "Low risk"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        cases_file = tmp_path / "cases.json"
        cases_file.write_text(
            json.dumps(
                {
                    "feature_id": "TEST-002",
                    "manual_cases": [{"tc_id": "TC-001", "priority": "P0", "trace_to": []}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "evaluate-gate.py"),
                "--evidence",
                str(evidence_dir),
                "--risk",
                str(risk_file),
                "--cases",
                str(cases_file),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert output_file.exists()

    def test_main_profile_strict(self, tmp_path: Path) -> None:
        """Main with --profile strict."""
        import subprocess

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        (artifacts_dir / "risk_register.json").write_text(
            json.dumps(
                {"feature_id": "TEST-003", "risks": []},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        (artifacts_dir / "manual_case_set.json").write_text(
            json.dumps(
                {"feature_id": "TEST-003", "manual_cases": []},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "evaluate-gate.py"),
                "--input",
                str(artifacts_dir),
                "--output",
                str(output_file),
                "--profile",
                "strict",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0

        gate = json.loads(output_file.read_text(encoding="utf-8"))
        assert gate["profile"] == "strict"

    def test_main_missing_risk_file(self, tmp_path: Path) -> None:
        """Missing risk file returns error."""
        import subprocess

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Only create case set, no risk
        (artifacts_dir / "manual_case_set.json").write_text(
            json.dumps({"feature_id": "TEST", "manual_cases": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "evaluate-gate.py"),
                "--input",
                str(artifacts_dir),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 1


class TestGateThresholds:
    """Tests for GATE_THRESHOLDS constant.

    # TRACE: scripts/evaluate-gate.py:33-61 (role: thresholds)
    """

    def test_thresholds_exist(self) -> None:
        """Gate thresholds are defined."""
        module = load_evaluate_gate_module()
        thresholds = module.GATE_THRESHOLDS

        assert "strict" in thresholds
        assert "standard" in thresholds
        assert "lean" in thresholds

        # Check threshold values
        assert thresholds["strict"]["p0_pass"] == 100
        assert thresholds["standard"]["p1_pass"] == 95
        assert thresholds["lean"]["p1_pass"] == 80


class TestEvaluateGateMainDirect:
    """Tests for main function direct calls for coverage.

    # TRACE: scripts/evaluate-gate.py:330-459 (role: main_direct)
    """

    def test_main_direct_with_input(self, tmp_path: Path) -> None:
        """Direct main call with --input directory."""
        module = load_evaluate_gate_module()

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Create artifacts
        (artifacts_dir / "risk_register.json").write_text(
            json.dumps(
                {"feature_id": "TEST-DIRECT", "risks": []},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (artifacts_dir / "manual_case_set.json").write_text(
            json.dumps(
                {"feature_id": "TEST-DIRECT", "manual_cases": []},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "evaluate-gate",
                "--input",
                str(artifacts_dir),
                "--output",
                str(output_file),
            ],
        ):
            result = module.main()
            assert result == 0
            assert output_file.exists()

    def test_main_direct_missing_evidence(self, tmp_path: Path) -> None:
        """Direct main call without evidence returns error."""
        module = load_evaluate_gate_module()

        output_file = tmp_path / "gate.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "evaluate-gate",
                "--output",
                str(output_file),
            ],
        ):
            result = module.main()
            assert result == 1

    def test_main_direct_with_separate_inputs(self, tmp_path: Path) -> None:
        """Direct main call with separate --evidence, --risk, --cases."""
        module = load_evaluate_gate_module()

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "execution_001.json").write_text(
            json.dumps({"tc_id": "TC-001", "result": "pass"}, ensure_ascii=False),
            encoding="utf-8",
        )

        risk_file = tmp_path / "risk.json"
        risk_file.write_text(
            json.dumps({"feature_id": "TEST", "risks": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        cases_file = tmp_path / "cases.json"
        cases_file.write_text(
            json.dumps(
                {"feature_id": "TEST", "manual_cases": [{"tc_id": "TC-001", "priority": "P0", "trace_to": []}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "evaluate-gate",
                "--evidence",
                str(evidence_dir),
                "--risk",
                str(risk_file),
                "--cases",
                str(cases_file),
                "--output",
                str(output_file),
            ],
        ):
            result = module.main()
            assert result == 0

    def test_main_direct_with_alternative_risk_file(self, tmp_path: Path) -> None:
        """Direct main call finds alternative risk file names."""
        module = load_evaluate_gate_module()

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Use alternative name
        (artifacts_dir / "project-risk-register.json").write_text(
            json.dumps({"feature_id": "TEST", "risks": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        (artifacts_dir / "manual_case_set.json").write_text(
            json.dumps({"feature_id": "TEST", "manual_cases": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "evaluate-gate",
                "--input",
                str(artifacts_dir),
                "--output",
                str(output_file),
            ],
        ):
            result = module.main()
            assert result == 0

    def test_main_direct_with_alternative_cases_file(self, tmp_path: Path) -> None:
        """Direct main call finds alternative case file names."""
        module = load_evaluate_gate_module()

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        (artifacts_dir / "risk_register.json").write_text(
            json.dumps({"feature_id": "TEST", "risks": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        # Use alternative name
        (artifacts_dir / "test-cases.json").write_text(
            json.dumps({"feature_id": "TEST", "manual_cases": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "evaluate-gate",
                "--input",
                str(artifacts_dir),
                "--output",
                str(output_file),
            ],
        ):
            result = module.main()
            assert result == 0

    def test_main_direct_missing_cases(self, tmp_path: Path) -> None:
        """Direct main call without cases file returns error."""
        module = load_evaluate_gate_module()

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        (artifacts_dir / "risk_register.json").write_text(
            json.dumps({"feature_id": "TEST", "risks": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "gate.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "evaluate-gate",
                "--input",
                str(artifacts_dir),
                "--output",
                str(output_file),
            ],
        ):
            result = module.main()
            assert result == 1
