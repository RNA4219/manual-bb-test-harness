"""環境差・欠陥の状態・自動テスト成否による誤ったGoの回帰契約。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bb_harness.gate_engine import (
    GateInputError,
    automation_failures,
    extract_case_results,
    main,
    validate_and_select_evidence,
)

FEATURE, BUILD = "EVIDENCE-LIFECYCLE", "build-1"


def suite(**overrides):
    return {
        "suite_id": "required-regression",
        "status": "passed",
        "total": 2,
        "passed": 2,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "source_refs": [{"id": "CI-RUN-1", "kind": "auto_test"}],
        **overrides,
    }


def inputs():
    source = [{"id": "AC-1", "kind": "ac"}]
    return {
        "feature": {
            "feature_id": FEATURE,
            "revision": "spec-rev-1",
            "title": "保存",
            "acceptance_criteria": ["保存できる"],
            "source_refs": source,
        },
        "model": {
            "feature_id": FEATURE,
            "coverage_items": [{
                "id": "COV-FLOW-SAVE", "dimension": "flow", "technique": "use_case",
                "applicability": "applicable", "mandatory": True,
                "coverage_criterion": "each_item", "source_refs": source,
            }],
            "flows": ["save"], "data_partitions": [], "rule_columns": [],
            "states": [], "role_matrix": [], "regression_edges": [],
        },
        "observations": {
            "feature_id": FEATURE,
            "observations": [
                {
                    "id": "OBS-SAVE-1",
                    "title": "保存結果",
                    "view": "black",
                    "coverage_item_id": "COV-FLOW-SAVE",
                    "mandatory": True,
                    "techniques": ["use_case"],
                    "source_refs": source,
                }
            ],
        },
        "risk": {
            "feature_id": FEATURE,
            "risks": [
                {
                    "id": "RISK-1",
                    "scenario": "保存失敗",
                    "impact": 5,
                    "likelihood": 3,
                    "priority": "P0",
                    "trace_to": ["TC-1"],
                }
            ],
        },
        "cases": {
            "feature_id": FEATURE,
            "spec_revision": "spec-rev-1",
            "manual_cases": [
                {
                    "tc_id": "TC-1",
                    "revision": "case-rev-1",
                    "content_hash": "sha256:evidence-lifecycle-tc-1",
                    "oracle_revision": "oracle-rev-1",
                    "title": "保存",
                    "priority": "P0",
                    "primary_view": "black",
                    "steps": ["保存する"],
                    "expected_results": ["保存される"],
                    "oracle": {"type": "specified", "refs": ["AC-1"]},
                    "trace_to": ["RISK-1", "OBS-SAVE-1"],
                }
            ],
        },
        "automation": {
            "feature_id": FEATURE,
            "build_id": BUILD,
            "coverage_scope": "changed_code",
            "coverage_percent": 100,
            "hotspot_review_percent": 100,
            "new_issues": {"blocker": 0, "critical": 0},
            "source_refs": [{"id": "CI-1", "kind": "auto_test"}],
            "test_suites": [suite()],
        },
    }


def evidence(**overrides):
    return {
        "feature_id": FEATURE,
        "build_id": BUILD,
        "case_revision": "case-rev-1",
        "spec_revision": "spec-rev-1",
        "oracle_revision": "oracle-rev-1",
        "case_content_hash": "sha256:evidence-lifecycle-tc-1",
        "oracle_refs": ["AC-1"],
        "run_id": "RUN-PASS",
        "tc_id": "TC-1",
        "timestamp": "2026-09-12T11:00:00Z",
        "result": "pass",
        **overrides,
    }


def run_gate(tmp_path, artifacts, executions, *, register=None):
    argv = ["--output", str(tmp_path / "gate.json"), "--profile", "strict"]
    for name, value in artifacts.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        argv.extend([f"--{name}", str(path)])
    directory = tmp_path / "evidence"
    directory.mkdir(exist_ok=True)
    for index, item in enumerate(executions):
        (directory / f"{index}.json").write_text(json.dumps(item), encoding="utf-8")
    argv.extend(["--evidence", str(directory)])
    if register is not None:
        path = tmp_path / "defect_register.json"
        path.write_text(json.dumps(register), encoding="utf-8")
        argv.extend(["--defects", str(path)])
    code = main(argv)
    output = tmp_path / "gate.json"
    return code, json.loads(output.read_text(encoding="utf-8")) if code == 0 else None


def plan(artifacts):
    artifacts["cases"]["execution_configurations"] = [
        {"id": "android", "env": "Android"},
        {"id": "ios", "env": "iOS"},
    ]


@pytest.mark.parametrize("same_time", [True, False])
def test_distinct_environments_preserve_failure_and_allow_equal_timestamps(same_time):
    failed = evidence(
        result="fail", env="Android", run_id="RUN-FAIL", timestamp="2026-09-12T10:00:00Z"
    )
    passed = evidence(
        env="iOS", timestamp=failed["timestamp"] if same_time else "2026-09-12T11:00:00Z"
    )
    selected, _ = validate_and_select_evidence([failed, passed], FEATURE, BUILD)
    assert len(selected) == 2
    results = extract_case_results(selected, inputs()["cases"])
    assert results["TC-1"]["result"] == "fail"


def test_reexecution_replaces_only_the_same_configuration():
    selected, _ = validate_and_select_evidence(
        [
            evidence(env="Android", result="fail", timestamp="2026-09-12T09:00:00Z"),
            evidence(env="Android"),
            evidence(env="iOS", result="fail", timestamp="2026-09-12T10:00:00Z"),
        ],
        FEATURE,
        BUILD,
    )
    assert {(item["env"], item["result"]) for item in selected} == {
        ("Android", "pass"),
        ("iOS", "fail"),
    }


@pytest.mark.parametrize("field", ["device", "network_profile"])
def test_legacy_execution_context_components_are_distinct(field):
    selected, _ = validate_and_select_evidence(
        [
            evidence(**{field: "first"}, result="fail", timestamp="2026-09-12T09:00:00Z"),
            evidence(**{field: "second"}),
        ],
        FEATURE,
        BUILD,
    )
    assert len(selected) == 2


@pytest.mark.parametrize("complete", [False, True])
def test_planned_configurations_require_all_executions(tmp_path, complete):
    artifacts = inputs()
    plan(artifacts)
    runs = [evidence(configuration_id="android", env="Android")]
    if complete:
        runs.append(evidence(configuration_id="ios", env="iOS", run_id="RUN-IOS"))
    code, gate = run_gate(tmp_path, artifacts, runs)
    assert code == 0
    assert gate["status"] == ("go" if complete else "no_go")
    details = gate["evidence_summary"]["manual_execution_results"]
    assert {(item["configuration_id"], item["result"]) for item in details} == {
        ("android", "pass"),
        ("ios", "pass" if complete else "untested"),
    }
    assert gate["evidence_summary"]["mandatory_observation_rate"] == (100 if complete else 0)


def test_case_can_select_a_subset_of_configurations(tmp_path):
    artifacts = inputs()
    plan(artifacts)
    artifacts["cases"]["manual_cases"][0]["configuration_ids"] = ["android"]
    code, gate = run_gate(
        tmp_path, artifacts, [evidence(configuration_id="android", env="Android")]
    )
    assert code == 0 and gate["status"] == "go"


@pytest.mark.parametrize(
    "mutation",
    ["duplicate_plan", "unknown_reference", "unknown_evidence", "missing_id", "wrong_environment"],
)
def test_invalid_configuration_contract_preserves_output(tmp_path, mutation):
    artifacts = inputs()
    plan(artifacts)
    run = evidence(configuration_id="android", env="Android")
    if mutation == "duplicate_plan":
        artifacts["cases"]["execution_configurations"].append({"id": "android", "env": "Android"})
    elif mutation == "unknown_reference":
        artifacts["cases"]["manual_cases"][0]["configuration_ids"] = ["unknown"]
    elif mutation == "unknown_evidence":
        run["configuration_id"] = "unknown"
    elif mutation == "missing_id":
        run.pop("configuration_id")
    else:
        run["env"] = "iOS"
    output = tmp_path / "gate.json"
    output.write_bytes(b"previous gate")
    code, _ = run_gate(tmp_path, artifacts, [run])
    assert code == 1
    assert output.read_bytes() == b"previous gate"


def test_same_configuration_id_cannot_change_meaning():
    with pytest.raises(GateInputError):
        validate_and_select_evidence(
            [
                evidence(
                    configuration_id="mobile", env="Android", timestamp="2026-09-12T09:00:00Z"
                ),
                evidence(configuration_id="mobile", env="iOS"),
            ],
            FEATURE,
            BUILD,
        )


def defect(**overrides):
    return {
        "defect_id": "BUG-1",
        "title": "保存データ消失",
        "severity": "high",
        "status": "open",
        **overrides,
    }


def register_record(**overrides):
    return {
        **defect(),
        "updated_at": "2026-09-12T12:00:00Z",
        "source_refs": [{"id": "BUG-1", "kind": "bug"}],
        **overrides,
    }


def register(*records):
    return {"feature_id": FEATURE, "build_id": BUILD, "defects": list(records)}


def test_pass_does_not_close_legacy_unresolved_defect(tmp_path):
    old_defect = defect()
    old_defect.pop("defect_id")
    code, gate = run_gate(
        tmp_path,
        inputs(),
        [
            evidence(
                run_id="RUN-FAIL",
                timestamp="2026-09-12T10:00:00Z",
                result="fail",
                defect_stub=old_defect,
            ),
            evidence(),
        ],
    )
    assert code == 0 and gate["status"] == "no_go"
    assert any("open blocker/critical/high defects: 1" in reason for reason in gate["reasons"])


@pytest.mark.parametrize(
    "status", ["open", "in_progress", "fixed", "pending_confirmation", "reopened"]
)
def test_unresolved_defect_states_block_after_pass(tmp_path, status):
    code, gate = run_gate(
        tmp_path, inputs(), [evidence()], register=register(register_record(status=status))
    )
    assert code == 0 and gate["status"] == "no_go"
    assert gate["evidence_summary"]["open_defects"][0]["defect_id"] == "BUG-1"


def test_verified_explicit_resolution_releases_gate(tmp_path):
    runs = [
        evidence(
            run_id="RUN-FAIL", timestamp="2026-09-12T10:00:00Z", result="fail", defect_stub=defect()
        ),
        evidence(),
    ]
    code, gate = run_gate(
        tmp_path,
        inputs(),
        runs,
        register=register(register_record(status="resolved", confirmation_run_ids=["RUN-PASS"])),
    )
    assert code == 0 and gate["status"] == "go"
    assert gate["evidence_summary"]["open_defects"] == []


@pytest.mark.parametrize(
    "failure", ["missing", "unknown_run", "failed_run", "stale_pass", "future_confirmation"]
)
def test_resolution_requires_current_passing_confirmation(tmp_path, failure):
    closed = register_record(status="resolved", confirmation_run_ids=["RUN-PASS"])
    runs = [
        evidence(
            run_id="RUN-FAIL", timestamp="2026-09-12T10:00:00Z", result="fail", defect_stub=defect()
        ),
        evidence(),
    ]
    if failure == "missing":
        closed.pop("confirmation_run_ids")
    elif failure == "unknown_run":
        closed["confirmation_run_ids"] = ["MISSING"]
    elif failure == "failed_run":
        runs[-1]["result"] = "fail"
    elif failure == "stale_pass":
        runs[-1]["timestamp"] = "2026-09-12T09:00:00Z"
    else:
        closed["updated_at"] = "2026-09-12T10:30:00Z"
    output = tmp_path / "gate.json"
    output.write_bytes(b"previous gate")
    code, _ = run_gate(tmp_path, inputs(), runs, register=register(closed))
    assert code == 1 and output.read_bytes() == b"previous gate"


def test_reopened_defect_overrides_older_resolution(tmp_path):
    runs = [evidence(defect_stub=defect(status="reopened"))]
    closed = register_record(
        status="resolved", updated_at="2026-09-12T10:00:00Z", confirmation_run_ids=["OLD-PASS"]
    )
    code, gate = run_gate(tmp_path, inputs(), runs, register=register(closed))
    assert code == 0 and gate["status"] == "no_go"


def test_same_defect_referenced_by_multiple_cases_is_counted_once(tmp_path):
    artifacts = inputs()
    second = copy.deepcopy(artifacts["cases"]["manual_cases"][0])
    second["tc_id"] = "TC-2"
    artifacts["cases"]["manual_cases"].append(second)
    runs = [evidence(defect_stub=defect()), evidence(tc_id="TC-2", defect_stub=defect())]
    code, gate = run_gate(tmp_path, artifacts, runs)
    assert code == 0 and gate["status"] == "no_go"
    assert len(gate["evidence_summary"]["open_defects"]) == 1


@pytest.mark.parametrize("profile", ["strict", "standard", "lean"])
@pytest.mark.parametrize("status", ["failed", "error", "cancelled", "not_run"])
def test_unsuccessful_automation_suite_blocks_every_profile(profile, status):
    auto = inputs()["automation"]
    auto["coverage_scope"] = "impacted_module" if profile == "lean" else "changed_code"
    auto["test_suites"] = [suite(status=status)]
    assert automation_failures(auto, profile, FEATURE, BUILD)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "empty",
        "zero_tests",
        "skipped",
        "failed_count",
        "error_count",
        "mismatched_total",
        "duplicate_id",
    ],
)
def test_automation_cannot_pass_with_missing_or_inconsistent_execution(change):
    auto = inputs()["automation"]
    auto["test_suites"] = [suite()]
    if change == "missing":
        auto.pop("test_suites")
    elif change == "empty":
        auto["test_suites"] = []
    elif change == "duplicate_id":
        auto["test_suites"].append(suite())
    else:
        auto["test_suites"] = [
            suite(
                **{
                    "zero_tests": {"total": 0, "passed": 0},
                    "skipped": {"passed": 1, "skipped": 1},
                    "failed_count": {"passed": 1, "failed": 1},
                    "error_count": {"passed": 1, "errors": 1},
                    "mismatched_total": {"total": 3},
                }[change]
            )
        ]
    assert automation_failures(auto, "strict", FEATURE, BUILD)


def test_successful_automation_suites_allow_gate(tmp_path):
    artifacts = inputs()
    artifacts["automation"]["test_suites"] = [suite(), suite(suite_id="integration")]
    code, gate = run_gate(tmp_path, artifacts, [evidence()])
    assert code == 0 and gate["status"] == "go"


def test_automation_suite_failure_is_not_waivable(tmp_path):
    artifacts = inputs()
    artifacts["automation"]["test_suites"] = [suite(status="failed", passed=1, failed=1)]
    artifacts["waivers"] = {
        "feature_id": FEATURE,
        "build_id": BUILD,
        "waivers": [
            {
                "id": "W-1",
                "risk_ids": ["RISK-1"],
                "reason": "監視",
                "owner": "QA",
                "approver": "release-lead",
                "approved_at": "2026-09-12T12:00:00Z",
                "approval_ref": "DECISION-W-1",
                "expires_at": "2099-01-01T00:00:00Z",
                "containment": "監視",
                "rollback": "切戻し",
            }
        ],
    }
    code, gate = run_gate(tmp_path, artifacts, [evidence()])
    assert code == 0 and gate["status"] == "no_go"
    assert any("suite" in reason for reason in gate["reasons"])


@pytest.mark.parametrize("provider", ["testrail", "xray"])
def test_import_preserves_each_defect_identifier(provider):
    if provider == "testrail":
        from bb_harness.tools.import_testrail import convert_to_execution_evidence

        item = convert_to_execution_evidence(
            {"id": 1, "case_id": 1, "status_id": 5}, {"defects": ["BUG-1", "BUG-2"]}, "QA", 1
        )
    else:
        from bb_harness.tools.import_xray import convert_to_execution_evidence

        item = convert_to_execution_evidence(
            {"status": "FAIL", "defects": ["BUG-1", "BUG-2"]}, "EXEC-1", "TEST-1"
        )
    assert item["defect_stub"]["defect_id"] == "BUG-1"
    assert {entry["defect_id"] for entry in item["defects"]} == {"BUG-1", "BUG-2"}


def test_resolving_one_imported_defect_does_not_close_another(tmp_path):
    failed = evidence(
        result="fail",
        timestamp="2026-09-12T10:00:00Z",
        run_id="RUN-FAIL",
        defects=[defect(), defect(defect_id="BUG-2")],
    )
    code, gate = run_gate(
        tmp_path,
        inputs(),
        [failed, evidence()],
        register=register(register_record(status="resolved", confirmation_run_ids=["RUN-PASS"])),
    )
    assert code == 0 and gate["status"] == "no_go"
    assert [entry["defect_id"] for entry in gate["evidence_summary"]["open_defects"]] == ["BUG-2"]


@pytest.mark.parametrize("field", ["feature_id", "build_id"])
def test_defect_register_must_match_release_identity(tmp_path, field):
    ledger = register(register_record())
    ledger[field] = "OTHER"
    code, _ = run_gate(tmp_path, inputs(), [evidence()], register=ledger)
    assert code == 1


def test_confirmation_in_another_environment_cannot_close_defect(tmp_path):
    runs = [
        evidence(
            env="Android",
            result="fail",
            defect_stub=defect(),
            run_id="ANDROID-FAIL",
            timestamp="2026-09-12T10:00:00Z",
        ),
        evidence(env="iOS", run_id="IOS-PASS"),
    ]
    code, _ = run_gate(
        tmp_path,
        inputs(),
        runs,
        register=register(register_record(status="resolved", confirmation_run_ids=["IOS-PASS"])),
    )
    assert code == 1


def test_confirmation_requires_every_affected_configuration(tmp_path):
    runs = [
        evidence(
            env="Android",
            result="fail",
            defect_stub=defect(),
            run_id="A-FAIL",
            timestamp="2026-09-12T10:00:00Z",
        ),
        evidence(
            env="iOS",
            result="fail",
            defect_stub=defect(),
            run_id="I-FAIL",
            timestamp="2026-09-12T10:00:00Z",
        ),
        evidence(env="Android", run_id="A-PASS"),
        evidence(env="iOS", run_id="I-PASS"),
    ]
    code, gate = run_gate(
        tmp_path,
        inputs(),
        runs,
        register=register(
            register_record(status="resolved", confirmation_run_ids=["A-PASS", "I-PASS"])
        ),
    )
    assert code == 0 and gate["status"] == "go"


def test_same_timestamp_conflicting_defect_states_are_rejected(tmp_path):
    ledger = register(
        register_record(), register_record(status="resolved", confirmation_run_ids=["RUN-PASS"])
    )
    code, _ = run_gate(tmp_path, inputs(), [evidence()], register=ledger)
    assert code == 1


def test_resolved_report_without_register_cannot_close_defect(tmp_path):
    runs = [
        evidence(
            result="fail", defect_stub=defect(), run_id="RUN-FAIL", timestamp="2026-09-12T10:00:00Z"
        ),
        evidence(defect_stub=defect(status="resolved")),
    ]
    code, gate = run_gate(tmp_path, inputs(), runs)
    assert code == 0 and gate["status"] == "no_go"


def test_legacy_automation_missing_execution_preserves_output(tmp_path):
    artifacts = inputs()
    artifacts["automation"].pop("test_suites")
    output = tmp_path / "gate.json"
    output.write_bytes(b"previous gate")
    code, _ = run_gate(tmp_path, artifacts, [evidence()])
    assert code == 1 and output.read_bytes() == b"previous gate"


def test_resolved_defect_stays_closed_after_later_success(tmp_path):
    runs = [
        evidence(
            result="fail", defect_stub=defect(), run_id="RUN-FAIL", timestamp="2026-09-12T10:00:00Z"
        ),
        evidence(),
        evidence(run_id="LATER-PASS", timestamp="2026-09-12T13:00:00Z"),
    ]
    code, gate = run_gate(
        tmp_path,
        inputs(),
        runs,
        register=register(register_record(status="resolved", confirmation_run_ids=["RUN-PASS"])),
    )
    assert code == 0 and gate["status"] == "go"


def test_reused_confirmation_run_id_is_ambiguous(tmp_path):
    runs = [evidence(), evidence(timestamp="2026-09-12T13:00:00Z")]
    closed = register_record(
        status="resolved", updated_at="2026-09-12T14:00:00Z", confirmation_run_ids=["RUN-PASS"]
    )
    code, _ = run_gate(tmp_path, inputs(), runs, register=register(closed))
    assert code == 1


def test_documented_lifecycle_scenario(tmp_path):
    from bb_harness.cli import main as cli_main

    output = tmp_path / "gate.json"
    sample = Path(__file__).resolve().parents[1] / "examples/evidence-lifecycle"
    assert (
        cli_main(
            [
                "gate",
                "--input",
                str(sample),
                "--defects",
                str(sample / "lifecycle.defect_register.json"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    gate = json.loads(output.read_text(encoding="utf-8"))
    assert gate["status"] == "no_go"
    summary = gate["evidence_summary"]
    assert summary["manual_by_priority"]["P0"]["untested"] == 1
    assert summary["mandatory_observation_rate"] == 0
    assert summary["open_defects"][0]["defect_id"] == "BUG-1"
    assert summary["open_defects"][0]["status"] == "fixed"
    assert summary["automation_test_suites"][0]["status"] == "failed"
