"""実行構成、欠陥の状態、自動テスト実績の契約。"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class GateInputError(ValueError):
    """Gate input is missing, ambiguous, or invalid."""


def parse_timestamp(value: Any, source: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise GateInputError(f"timestamp required: {source}")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateInputError(f"Invalid timestamp in {source}: {value}") from exc
    if timestamp.tzinfo is None:
        raise GateInputError(f"timestamp must include timezone: {source}")
    return timestamp


CONTEXT_FIELDS = ("env", "device", "network_profile")
UNRESOLVED_STATES = {"open", "in_progress", "fixed", "pending_confirmation", "reopened", "accepted"}


def configuration_key(item: dict[str, Any]) -> tuple[str, ...]:
    if item.get("configuration_id"):
        return ("id", str(item["configuration_id"]))
    return ("legacy", *(str(item.get(field, "")) for field in CONTEXT_FIELDS))


def execution_identity(item: dict[str, Any]) -> tuple[str, ...]:
    return (str(item.get("tc_id") or item.get("charter_id") or ""), *configuration_key(item))


def validate_evidence_identity(
    evidence: dict[str, Any],
    case_set: dict[str, Any],
    feature_spec: dict[str, Any],
) -> None:
    """Reject execution evidence bound to a different testware revision."""
    case_id = str(evidence.get("tc_id") or evidence.get("charter_id") or "")
    definitions = {
        str(item.get(id_field)): item
        for collection, id_field in (
            ("manual_cases", "tc_id"),
            ("exploratory_charters", "id"),
        )
        for item in case_set.get(collection, [])
    }
    definition = definitions.get(case_id)
    if definition is None:
        raise GateInputError(f"Evidence identity references unknown case: {case_id}")
    feature_revision = feature_spec.get("revision")
    case_spec_revision = case_set.get("spec_revision")
    if not feature_revision or not case_spec_revision:
        raise GateInputError("Definition testware identity missing: spec_revision")
    if case_spec_revision != feature_revision:
        raise GateInputError("Manual case set spec_revision does not match feature revision")
    expected_pairs = (
        ("case_revision", "revision", definition),
        ("case_content_hash", "content_hash", definition),
        ("oracle_revision", "oracle_revision", definition),
        ("spec_revision", "revision", feature_spec),
    )
    for evidence_field, definition_field, source in expected_pairs:
        expected = source.get(definition_field)
        actual = evidence.get(evidence_field)
        if expected is None:
            raise GateInputError(
                f"Definition testware identity missing for {case_id}: {definition_field}"
            )
        if not actual:
            raise GateInputError(
                f"Execution testware identity missing for {case_id}: {evidence_field}"
            )
        if actual != expected:
            raise GateInputError(
                f"Evidence testware identity mismatch for {case_id}: {evidence_field}"
            )
    if evidence.get("feature_id") != feature_spec.get("feature_id"):
        raise GateInputError(f"Evidence identity feature mismatch for {case_id}")


def configuration_plan(cases: dict[str, Any]) -> dict[str, dict[str, Any]]:
    configurations = cases.get("execution_configurations", [])
    if not isinstance(configurations, list):
        raise GateInputError("execution_configurations must be an array")
    if "execution_configurations" in cases and not configurations:
        raise GateInputError("execution_configurations must not be empty")
    plan: dict[str, dict[str, Any]] = {}
    for item in configurations:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
        ):
            raise GateInputError("configuration id required")
        if item["id"] in plan:
            raise GateInputError(f"Duplicate configuration id: {item['id']}")
        plan[item["id"]] = item
    for collection in ("manual_cases", "exploratory_charters"):
        for case in cases.get(collection, []):
            if not isinstance(case, dict):
                raise GateInputError("case definition must be an object")
            refs = case.get("configuration_ids")
            if refs is not None and (
                not isinstance(refs, list)
                or not refs
                or any(not isinstance(ref, str) or ref not in plan for ref in refs)
                or len(refs) != len(set(refs))
            ):
                raise GateInputError("configuration_ids must uniquely reference the execution plan")
    return plan


def validate_evidence_configurations(
    evidence: list[dict[str, Any]],
    cases: dict[str, Any] | None = None,
) -> None:
    plan = configuration_plan(cases) if cases is not None else {}
    bindings: dict[str, dict[str, Any]] = {}
    for item in evidence:
        identifier = item.get("configuration_id")
        if cases is not None and (plan or identifier) and identifier not in plan:
            raise GateInputError("Evidence configuration_id must reference the execution plan")
        if not identifier:
            continue
        binding = bindings.setdefault(identifier, {})
        for field in CONTEXT_FIELDS:
            if field not in item:
                continue
            expected = plan.get(identifier, {}).get(field, binding.get(field))
            if expected is not None and item[field] != expected:
                raise GateInputError(f"Configuration {identifier} has conflicting {field}")
            binding[field] = item[field]


def case_execution_results(
    evidence: list[dict[str, Any]],
    cases: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    validate_evidence_configurations(evidence, cases)
    plan = configuration_plan(cases)
    grouped: dict[str, dict[tuple[str, ...], dict[str, Any]]] = {}
    for item in evidence:
        case_id = str(item.get("tc_id") or item.get("charter_id") or "")
        entries = grouped.setdefault(case_id, {})
        key = configuration_key(item)
        if key in entries:
            raise GateInputError(f"Multiple selected executions for {case_id}, {key}")
        entries[key] = item
    output = {}
    for collection, id_field in (("manual_cases", "tc_id"), ("exploratory_charters", "id")):
        for definition in cases.get(collection, []):
            case_id = str(definition.get(id_field, ""))
            if definition.get("status") == "retired":
                continue
            observed = grouped.get(case_id, {})
            if plan:
                targets = [("id", ref) for ref in definition.get("configuration_ids", list(plan))]
                if set(observed) - set(targets):
                    raise GateInputError(f"Execution outside case configuration_ids: {case_id}")
            else:
                targets = sorted(observed) or [("legacy", "", "", "")]
            units = []
            for key in targets:
                item = observed.get(key, {})
                outcome = str(item.get("result", "untested")).lower()
                if outcome not in ("pass", "fail", "blocked", "unknown", "skip", "untested"):
                    outcome = "unknown"
                unit = {"case_id": case_id, "result": outcome, "run_id": item.get("run_id", "")}
                if key[0] == "id":
                    unit["configuration_id"] = key[1]
                    unit.update(
                        {
                            field: plan[key[1]][field]
                            for field in CONTEXT_FIELDS
                            if field in plan[key[1]]
                        }
                    )
                else:
                    unit.update(
                        {
                            field: value
                            for field, value in zip(CONTEXT_FIELDS, key[1:], strict=True)
                            if value
                        }
                    )
                unit.update({field: item[field] for field in CONTEXT_FIELDS if field in item})
                if "timestamp" in item:
                    unit["timestamp"] = item["timestamp"]
                units.append(unit)
            output[case_id] = units
    return output


def case_was_executed(result: dict[str, Any]) -> bool:
    units = result.get("execution_results")
    if units is not None:
        return bool(units) and all(unit["result"] in ("pass", "fail") for unit in units)
    return result.get("result") in ("pass", "fail")


def suite_failures(automation: dict[str, Any], *, require_success: bool = True) -> list[str]:
    suites = automation.get("test_suites")
    if not isinstance(suites, list) or not suites:
        return ["automation test_suites missing or empty"]
    failures = []
    identifiers: set[str] = set()
    for suite in suites:
        if not isinstance(suite, dict):
            failures.append("automation suite must be an object")
            continue
        identifier = suite.get("suite_id")
        if not isinstance(identifier, str) or not identifier.strip():
            failures.append("automation suite_id required")
        elif identifier in identifiers:
            failures.append(f"duplicate automation suite_id: {identifier}")
        else:
            identifiers.add(identifier)
        label = f"automation suite {identifier}"
        names = ("total", "passed", "failed", "errors", "skipped")
        if any(type(suite.get(name)) is not int or suite[name] < 0 for name in names):
            failures.append(f"{label} requires nonnegative integer execution counts")
            continue
        if suite["total"] != sum(suite[name] for name in names[1:]):
            failures.append(f"{label} execution counts do not sum to total")
        status = suite.get("status")
        if status not in ("passed", "failed", "error", "cancelled", "not_run"):
            failures.append(f"{label} has invalid execution status")
        if not suite.get("source_refs"):
            failures.append(f"{label} source_refs required")
        if require_success and (
            status != "passed"
            or suite["total"] == 0
            or suite["passed"] != suite["total"]
            or any(suite[name] for name in ("failed", "errors", "skipped"))
        ):
            failures.append(f"{label} did not pass every required test")
    return failures


def artifact_contract_errors(artifact: dict[str, Any], kind: str) -> list[str]:
    if kind == "test_model":
        errors: list[str] = []
        identifiers: set[str] = set()
        for index, item in enumerate(artifact.get("coverage_items", [])):
            identifier = str(item.get("id", ""))
            if identifier in identifiers:
                errors.append(f"coverage_items[{index}] duplicate id: {identifier}")
            identifiers.add(identifier)
            boundary = item.get("boundary_spec")
            if (
                isinstance(boundary, dict)
                and boundary.get("analysis_type") == "three_value"
                and len(boundary.get("selected_values", [])) != 3
            ):
                errors.append(
                    f"coverage_items[{index}] three_value requires boundary and both neighbors"
                )
        return errors
    if kind == "phase_contract":
        errors: list[str] = []
        readiness = artifact.get("readiness", {})
        expected_decision = {
            "ok": "ready",
            "degraded": "ready_with_conditions",
            "blocked": "not_ready",
        }.get(readiness.get("status"))
        if expected_decision and readiness.get("decision") != expected_decision:
            errors.append(
                "readiness status/decision mismatch: "
                f"{readiness.get('status')} requires {expected_decision}"
            )
        for index, question in enumerate(artifact.get("open_questions", [])):
            owner = question.get("owner")
            if not isinstance(owner, str) or not owner.strip():
                errors.append(f"open_questions[{index}] owner required")
            if (
                question.get("severity") == "critical"
                and question.get("blocks_ready") is True
                and readiness.get("decision") != "not_ready"
            ):
                errors.append(f"open_questions[{index}] critical blocker requires not_ready")
        return errors
    if kind == "manual_case_set":
        try:
            configuration_plan(artifact)
        except GateInputError as exc:
            return [str(exc)]
    if kind == "automation_evidence":
        return suite_failures(artifact, require_success=False)
    return []


def imported_defect_reports(value: Any) -> list[dict[str, str]]:
    """連携元が返す欠陥IDを個別に保持する。"""
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        raise GateInputError("Imported defects must be strings or an array of strings")
    if any(not isinstance(item, str) for item in values):
        raise GateInputError("Imported defect identifier must be a string")
    identifiers = dict.fromkeys(item.strip() for item in values if item.strip())
    return [
        {
            "defect_id": identifier,
            "title": f"Defect {identifier}",
            "severity": "high",
            "status": "open",
        }
        for identifier in identifiers
    ]


def extract_open_defects(
    evidence: list[dict[str, Any]],
    defect_register: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """ケースの最新結果と独立して欠陥履歴を保持し、明示的な解決を検証する。"""
    anonymous: dict[tuple[str, ...], dict[str, Any]] = {}
    events: dict[str, list[tuple[datetime, dict[str, Any], bool]]] = {}
    affected: dict[str, set[tuple[str, ...]]] = {}
    run_history: list[tuple[tuple[str, ...], datetime, dict[str, Any]]] = []
    for item in evidence:
        # 旧単体APIの匿名stubにはtimestampのない入力もある。
        stamp = (
            parse_timestamp(item["timestamp"], "defect evidence") if "timestamp" in item else None
        )
        identity = execution_identity(item)
        if stamp is not None:
            run_history.append((identity, stamp, item))
        reports = list(item.get("defects", []))
        if isinstance(item.get("defect_stub"), dict):
            reports.append(item["defect_stub"])
        for report in reports:
            if not isinstance(report, dict):
                raise GateInputError("defect report must be an object")
            status = report.get("status", "open")
            identifier = report.get("defect_id")
            if not identifier:
                if status in UNRESOLVED_STATES:
                    key = (
                        *identity,
                        str(report.get("title", "Untitled defect")),
                        str(report.get("severity", "unknown")),
                    )
                    anonymous[key] = {
                        "tc_id": identity[0],
                        "title": report.get("title", "Untitled defect"),
                        "severity": report.get("severity", "unknown"),
                        "status": status,
                    }
                continue
            if stamp is None:
                raise GateInputError("timestamp required for identified defect report")
            # 実行結果に添付されたstubだけでは欠陥をクローズしない。
            event = {
                **report,
                "status": status if status in UNRESOLVED_STATES else "pending_confirmation",
            }
            events.setdefault(identifier, []).append((stamp, event, False))
            affected.setdefault(identifier, set()).add(identity)

    for record in (defect_register or {}).get("defects", []):
        identifier = record.get("defect_id")
        if not identifier:
            raise GateInputError("defect_id required in defect_register")
        events.setdefault(identifier, []).append(
            (
                parse_timestamp(record.get("updated_at"), f"defect {identifier}"),
                record,
                True,
            )
        )

    unresolved = list(anonymous.values())
    for identifier, history in sorted(events.items()):
        last_time = max(event[0] for event in history)
        current = [event for event in history if event[0] == last_time]
        states = {
            (
                event[1].get("status"),
                event[1].get("severity"),
                tuple(sorted(event[1].get("confirmation_run_ids", []))),
            )
            for event in current
        }
        if len(states) != 1:
            raise GateInputError(f"Conflicting defect states at the same time: {identifier}")
        _, state, from_register = current[0]
        if state.get("status") == "resolved" and from_register:
            refs = state.get("confirmation_run_ids", [])
            if not refs or len(refs) != len(set(refs)):
                raise GateInputError(f"Resolved defect requires confirmation_run_ids: {identifier}")
            open_times = [
                stamp
                for stamp, record, _ in history
                if record.get("status") in UNRESOLVED_STATES and stamp <= last_time
            ]
            confirmed = set()
            for ref in refs:
                matches = [
                    (identity, stamp, item)
                    for identity, stamp, item in run_history
                    if item.get("run_id") == ref and stamp <= last_time
                ]
                if len(matches) != 1:
                    raise GateInputError(f"Missing or ambiguous confirmation run: {ref}")
                identity, stamp, item = matches[0]
                latest_at_resolution = max(
                    run_time
                    for run_identity, run_time, _ in run_history
                    if run_identity == identity and run_time <= last_time
                )
                if (
                    item.get("result") != "pass"
                    or stamp != latest_at_resolution
                    or (open_times and stamp < max(open_times))
                ):
                    raise GateInputError(f"Invalid confirmation for defect {identifier}: {ref}")
                confirmed.add(identity)
            if affected.get(identifier, set()) - confirmed:
                raise GateInputError(
                    f"Confirmation missing for affected case/configuration: {identifier}"
                )
            continue
        unresolved.append(
            {
                "defect_id": identifier,
                "title": state.get("title", "Untitled defect"),
                "severity": state.get("severity", "unknown"),
                "status": state.get("status", "open"),
            }
        )
    return unresolved
