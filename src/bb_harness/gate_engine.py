"""Package-native Gate 2.0 evaluation engine."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bb_harness import __version__
from bb_harness.schema_validation import SchemaValidationError, validate_artifact

GATE_THRESHOLDS = {
    "strict": {
        "coverage_scope": "changed_code",
        "auto_coverage": 80,
        "p0_pass": 100,
        "p1_pass": 100,
        "high_risk_obs": 100,
        "critical": 0,
        "hotspot": 100,
    },
    "standard": {
        "coverage_scope": "changed_code",
        "auto_coverage": 75,
        "p0_pass": 100,
        "p1_pass": 95,
        "high_risk_obs": 95,
        "critical": 0,
        "hotspot": None,
    },
    "lean": {
        "coverage_scope": "impacted_module",
        "auto_coverage": 60,
        "p0_pass": 100,
        "p1_pass": 80,
        "high_risk_obs": 80,
        # Critical automation findings are never waivable, even for lean.
        "critical": 0,
        "hotspot": None,
    },
}


class GateInputError(ValueError):
    """Gate input is missing, ambiguous, or invalid."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateInputError(f"Cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateInputError(f"Expected JSON object: {path}")
    return value


def load_evidence_files(path: Path) -> list[dict[str, Any]]:
    if path.is_file():
        return [load_json(path)]
    if not path.is_dir():
        raise GateInputError(f"Path not found: {path}")
    evidence = []
    for candidate in sorted(path.rglob("*.json")):
        value = load_json(candidate)
        if {"run_id", "result", "tc_id", "charter_id"} & value.keys():
            value["_source_path"] = str(candidate)
            evidence.append(value)
    return evidence


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


def validate_and_select_evidence(
    evidence: list[dict[str, Any]], feature_id: str, build_id: str | None
) -> tuple[list[dict[str, Any]], str]:
    matching = []
    builds: set[str] = set()
    for index, item in enumerate(evidence):
        source = str(item.get("_source_path", f"evidence[{index}]"))
        if bool(item.get("tc_id")) == bool(item.get("charter_id")):
            raise GateInputError(f"Exactly one of tc_id or charter_id required: {source}")
        if item.get("feature_id") != feature_id:
            raise GateInputError(f"Evidence feature_id mismatch: {source}")
        current_build = item.get("build_id")
        if not isinstance(current_build, str) or not current_build:
            raise GateInputError(f"build_id required: {source}")
        if build_id is not None and current_build != build_id:
            raise GateInputError(f"Evidence build_id mismatch: {source}")
        parse_timestamp(item.get("timestamp"), source)
        builds.add(current_build)
        matching.append(item)

    if build_id is None:
        if len(builds) != 1:
            raise GateInputError("--build-id required when evidence has zero or multiple builds")
        build_id = next(iter(builds))
    matching = [item for item in matching if item["build_id"] == build_id]
    if not matching:
        raise GateInputError(f"No evidence for feature={feature_id}, build={build_id}")

    latest: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for item in matching:
        case_id = str(item.get("tc_id") or item.get("charter_id"))
        stamp = parse_timestamp(item["timestamp"], str(item.get("_source_path", case_id)))
        previous = latest.get(case_id)
        if previous and previous[0] == stamp:
            raise GateInputError(f"Ambiguous duplicate evidence: {case_id} at {item['timestamp']}")
        if previous is None or stamp > previous[0]:
            latest[case_id] = (stamp, item)
    return [entry[1] for entry in latest.values()], build_id


def extract_case_results(
    evidence_list: list[dict[str, Any]], manual_cases: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for case in manual_cases.get("manual_cases", []):
        results[str(case.get("tc_id", ""))] = {
            "priority": case.get("priority", "P2"),
            "trace_to": case.get("trace_to", []),
            "type": "scripted",
            "result": "untested",
            "run_id": "",
            "defect_stub": None,
        }
    for charter in manual_cases.get("exploratory_charters", []):
        results[str(charter.get("id", ""))] = {
            "priority": charter.get("priority", "P2"),
            "trace_to": charter.get("trace_to", []),
            "type": "exploratory",
            "result": "untested",
            "run_id": "",
            "defect_stub": None,
        }
    for evidence in evidence_list:
        case_id = str(evidence.get("tc_id") or evidence.get("charter_id") or "")
        if case_id in results:
            results[case_id].update(
                result=str(evidence.get("result", "unknown")).lower(),
                run_id=evidence.get("run_id", ""),
                defect_stub=evidence.get("defect_stub"),
                timestamp=evidence.get("timestamp"),
            )
    return {key: value for key, value in results.items() if key}


def count_results_by_priority(results: dict[str, dict[str, Any]]) -> dict[str, dict[str, int]]:
    names = ("pass", "fail", "skip", "blocked", "unknown", "untested")
    counts = {
        priority: {**{name: 0 for name in names}, "total": 0}
        for priority in ("P0", "P1", "P2", "P3")
    }
    for item in results.values():
        priority = str(item.get("priority", "P2"))
        priority = priority if priority in counts else "P2"
        outcome = str(item.get("result", "unknown")).lower()
        outcome = outcome if outcome in names else "unknown"
        counts[priority]["total"] += 1
        counts[priority][outcome] += 1
        if outcome not in ("pass", "fail", "skip"):
            counts[priority]["skip"] += 1
    return counts


def extract_open_defects(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    defects = []
    for item in evidence:
        defect = item.get("defect_stub")
        if (
            isinstance(defect, dict)
            and defect.get("status", "open") == "open"
        ):
            defects.append(
                {
                    "tc_id": item.get("tc_id", item.get("charter_id", "")),
                    "title": defect.get("title", "Untitled defect"),
                    "severity": defect.get("severity", "unknown"),
                    "status": "open",
                }
            )
    return defects


def assess_residual_risks(
    risk_register: dict[str, Any], results: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str]]:
    reverse: dict[str, list[str]] = {}
    for case_id, item in results.items():
        for ref in item.get("trace_to", []):
            reverse.setdefault(str(ref), []).append(case_id)
    residual, blocking = [], []
    for risk in risk_register.get("risks", []):
        risk_id = str(risk.get("id", ""))
        cases = list(reverse.get(risk_id, []))
        cases.extend(str(ref) for ref in risk.get("trace_to", []) if str(ref) in results)
        cases = list(dict.fromkeys(cases))
        passed = bool(cases) and all(results[case].get("result") == "pass" for case in cases)
        if risk.get("priority") in ("P0", "P1") and not passed:
            blocking.append(risk_id)
        elif risk.get("priority") in ("P2", "P3") and not passed:
            residual.append(f"{risk_id}: {risk.get('scenario', '')}")
    return residual, blocking


def pass_rate(count: dict[str, int]) -> float:
    return 100.0 if count["total"] == 0 else count["pass"] / count["total"] * 100


def determine_gate_status(
    counts: dict[str, dict[str, int]],
    defects: list[dict[str, Any]],
    blocking_risks: list[str],
    profile: str = "standard",
) -> tuple[str, list[str], list[Any]]:
    """Compatibility helper for the historical public function."""
    thresholds = GATE_THRESHOLDS.get(profile, GATE_THRESHOLDS["standard"])
    severe = [
        defect
        for defect in defects
        if defect.get("severity") in ("blocker", "critical", "high")
        and defect.get("status", "open") == "open"
    ]
    if severe:
        return "no_go", [f"Blocker/critical/high defects: {len(severe)}"], []
    if counts["P0"]["total"] == 0:
        return "no_go", ["P0 evidence is missing"], []
    for priority, key in (("P0", "p0_pass"), ("P1", "p1_pass")):
        rate = pass_rate(counts[priority])
        if rate < thresholds[key]:
            return (
                "no_go",
                [f"{priority} pass rate: {rate:.1f}% (required: {thresholds[key]}%)"],
                [],
            )
    if blocking_risks:
        return "no_go", [f"Blocking risks unresolved: {len(blocking_risks)}"], []
    reasons = [
        f"P0 pass rate: {pass_rate(counts['P0']):.1f}% "
        f"({counts['P0']['pass']}/{counts['P0']['total']})"
    ]
    if counts["P1"]["total"]:
        reasons.append(
            f"P1 pass rate: {pass_rate(counts['P1']):.1f}% "
            f"({counts['P1']['pass']}/{counts['P1']['total']})"
        )
    return "go", reasons, []


def critical_open_assumptions(feature_spec: dict[str, Any] | None) -> list[str]:
    if not feature_spec:
        return []
    return [
        str(item.get("id", "UNKNOWN"))
        for item in feature_spec.get("assumptions", [])
        if item.get("severity") == "critical" and item.get("resolution_status", "open") == "open"
    ]


def automation_failures(
    automation: dict[str, Any] | None, profile: str, feature_id: str, build_id: str
) -> list[str]:
    if automation is None:
        return ["automation evidence missing"]
    if automation.get("feature_id") != feature_id or automation.get("build_id") != build_id:
        return ["automation evidence feature/build mismatch"]
    limits = GATE_THRESHOLDS[profile]
    failures = []
    if automation.get("coverage_scope") != limits["coverage_scope"]:
        failures.append(f"coverage_scope must be {limits['coverage_scope']}")
    if float(automation.get("coverage_percent", -1)) < limits["auto_coverage"]:
        failures.append(f"automation coverage below {limits['auto_coverage']}%")
    issues = automation.get("new_issues", {})
    if int(issues.get("blocker", 0)) > 0:
        failures.append("new blocker issues exist")
    if limits["critical"] is not None and int(issues.get("critical", 0)) > limits["critical"]:
        failures.append("new critical issues exist")
    if (
        limits["hotspot"] is not None
        and float(automation.get("hotspot_review_percent", -1)) < limits["hotspot"]
    ):
        failures.append(f"hotspot review below {limits['hotspot']}%")
    return failures


def observation_rate(
    observations: dict[str, Any] | None, results: dict[str, dict[str, Any]]
) -> float:
    if not observations:
        return 0.0
    required = {
        str(item.get("id"))
        for item in observations.get("observations", [])
        if item.get("mandatory") is True
    }
    if not required:
        return 100.0
    executed: set[str] = set()
    for result in results.values():
        if result.get("result") in ("pass", "fail"):
            executed.update(str(ref) for ref in result.get("trace_to", []))
    return len(required & executed) / len(required) * 100


def valid_waivers(
    waiver_set: dict[str, Any] | None, feature_id: str, build_id: str
) -> list[dict[str, Any]]:
    if not waiver_set:
        return []
    validate_schema(waiver_set, "waiver_set.schema.json")
    if waiver_set.get("feature_id") != feature_id or waiver_set.get("build_id") != build_id:
        raise GateInputError("waiver feature/build mismatch")
    for waiver in waiver_set.get("waivers", []):
        if parse_timestamp(waiver["expires_at"], str(waiver["id"])) <= datetime.now(timezone.utc):
            raise GateInputError(f"Expired waiver: {waiver['id']}")
    return list(waiver_set["waivers"])


def risk_ids_for_case(
    case_id: str, results: dict[str, dict[str, Any]], risk_register: dict[str, Any]
) -> set[str]:
    """Return risk IDs directly or reversely traced to a case/charter."""
    references = {str(ref) for ref in results[case_id].get("trace_to", [])}
    risk_ids = set()
    for risk in risk_register.get("risks", []):
        risk_id = str(risk.get("id", ""))
        risk_refs = {str(ref) for ref in risk.get("trace_to", [])}
        if risk_id and (risk_id in references or case_id in risk_refs):
            risk_ids.add(risk_id)
    return risk_ids


def missing_mandatory_observations(
    observations: dict[str, Any] | None, results: dict[str, dict[str, Any]]
) -> set[str]:
    """Return mandatory observation IDs not exercised by a pass or fail."""
    if not observations:
        return set()
    required = {
        str(item.get("id"))
        for item in observations.get("observations", [])
        if item.get("mandatory") is True
    }
    executed = {
        str(reference)
        for result in results.values()
        if result.get("result") in ("pass", "fail")
        for reference in result.get("trace_to", [])
    }
    return required - executed


def derive_waivable_conditions(
    *,
    profile: str,
    p1_rate: float,
    observation_rate_value: float,
    limits: dict[str, Any],
    results: dict[str, dict[str, Any]],
    observations: dict[str, Any] | None,
    risk_register: dict[str, Any],
    blocking_risks: list[str],
    residual_risks: list[str],
) -> tuple[dict[str, set[str]], list[str]]:
    """Derive risk-linked waiver conditions and fail-closed mapping errors."""
    conditions: dict[str, set[str]] = {}
    hard_failures: list[str] = []
    priorities = {
        str(risk.get("id")): str(risk.get("priority"))
        for risk in risk_register.get("risks", [])
    }

    if p1_rate < limits["p1_pass"]:
        failed_cases = [
            case_id
            for case_id, result in results.items()
            if result.get("priority") == "P1" and result.get("result") != "pass"
        ]
        risk_ids = set().union(
            *(risk_ids_for_case(case_id, results, risk_register) for case_id in failed_cases)
        ) if failed_cases else set()
        if risk_ids:
            conditions[
                f"P1 pass rate {p1_rate:.1f}% < {limits['p1_pass']}%"
            ] = risk_ids
        else:
            hard_failures.append("P1 failure has no traceable risk for a waiver")

    missing_observations = missing_mandatory_observations(observations, results)
    if observation_rate_value < limits["high_risk_obs"]:
        risk_ids = set()
        unmapped = []
        for observation_id in sorted(missing_observations):
            case_ids = [
                case_id
                for case_id, result in results.items()
                if observation_id in {str(ref) for ref in result.get("trace_to", [])}
            ]
            observation_risks = set().union(
                *(risk_ids_for_case(case_id, results, risk_register) for case_id in case_ids)
            ) if case_ids else set()
            if observation_risks:
                risk_ids.update(observation_risks)
            else:
                unmapped.append(observation_id)
        if unmapped:
            hard_failures.append(
                "mandatory observations lack traceable risks: " + ", ".join(unmapped)
            )
        elif risk_ids:
            conditions[
                f"mandatory observation execution {observation_rate_value:.1f}% "
                f"< {limits['high_risk_obs']}%"
            ] = risk_ids

    p0_blocking = [
        risk_id for risk_id in blocking_risks if priorities.get(risk_id) == "P0"
    ]
    if p0_blocking:
        hard_failures.append("P0 blocking risks unresolved: " + ", ".join(p0_blocking))

    p1_blocking = {
        risk_id for risk_id in blocking_risks if priorities.get(risk_id) == "P1"
    }
    unknown_blocking = {
        risk_id for risk_id in blocking_risks if priorities.get(risk_id) not in ("P0", "P1")
    }
    if unknown_blocking:
        hard_failures.append(
            "blocking risks have no waivable priority: " + ", ".join(sorted(unknown_blocking))
        )
    if p1_blocking:
        conditions["P1 blocking risks unresolved"] = p1_blocking

    if profile in ("strict", "standard") and residual_risks:
        conditions[f"residual risks exceed {profile} profile"] = {
            risk.split(":", 1)[0] for risk in residual_risks
        }
    return conditions, hard_failures


def applied_waivers(
    waivers: list[dict[str, Any]], required_risk_ids: set[str]
) -> tuple[list[dict[str, Any]], set[str]]:
    """Return only waivers that cover a currently waivable risk."""
    applied = [
        waiver
        for waiver in waivers
        if required_risk_ids & {str(risk) for risk in waiver["risk_ids"]}
    ]
    covered = {
        str(risk) for waiver in applied for risk in waiver["risk_ids"]
    } & required_risk_ids
    return applied, covered


def evaluate_gate(
    *,
    feature_id: str,
    build_id: str,
    profile: str,
    counts: dict[str, dict[str, int]],
    defects: list[dict[str, Any]],
    blocking_risks: list[str],
    feature_spec: dict[str, Any] | None,
    observations: dict[str, Any] | None,
    automation: dict[str, Any] | None,
    waiver_set: dict[str, Any] | None,
    results: dict[str, dict[str, Any]],
    residual_risks: list[str] | None = None,
    risk_register: dict[str, Any] | None = None,
) -> tuple[str, list[str], list[dict[str, Any]], list[str], float]:
    """Evaluate hard failures and risk-linked waivable release conditions."""
    limits = GATE_THRESHOLDS[profile]
    p0_rate, p1_rate = pass_rate(counts["P0"]), pass_rate(counts["P1"])
    severe = [
        defect
        for defect in defects
        if defect.get("severity") in ("blocker", "critical", "high")
        and defect.get("status", "open") == "open"
    ]
    assumptions = critical_open_assumptions(feature_spec)
    obs_rate = observation_rate(observations, results)
    waivers = valid_waivers(waiver_set, feature_id, build_id)

    hard_failures = []
    if counts["P0"]["total"] == 0:
        hard_failures.append("P0 evidence is missing")
    if p0_rate < limits["p0_pass"]:
        hard_failures.append(f"P0 pass rate {p0_rate:.1f}% < {limits['p0_pass']}%")
    if severe:
        hard_failures.append(f"open blocker/critical/high defects: {len(severe)}")
    if assumptions:
        hard_failures.append(f"critical assumptions unresolved: {', '.join(assumptions)}")
    hard_failures.extend(automation_failures(automation, profile, feature_id, build_id))

    conditions, mapping_failures = derive_waivable_conditions(
        profile=profile,
        p1_rate=p1_rate,
        observation_rate_value=obs_rate,
        limits=limits,
        results=results,
        observations=observations,
        risk_register=risk_register or {},
        blocking_risks=blocking_risks,
        residual_risks=residual_risks or [],
    )
    hard_failures.extend(mapping_failures)
    required_risk_ids = set().union(*conditions.values()) if conditions else set()
    applied, covered_risk_ids = applied_waivers(waivers, required_risk_ids)
    uncovered_risk_ids = sorted(required_risk_ids - covered_risk_ids)

    unmet = [*hard_failures, *conditions]
    if uncovered_risk_ids:
        unmet.append("waiver missing for risks: " + ", ".join(uncovered_risk_ids))

    if hard_failures or uncovered_risk_ids:
        status = "no_go"
        reasons = unmet
    elif conditions:
        status = "conditional_go"
        reasons = list(conditions)
    else:
        status = "go"
        reasons = [
            f"P0 pass rate: {p0_rate:.1f}%",
            f"P1 pass rate: {p1_rate:.1f}%",
            f"mandatory observation execution: {obs_rate:.1f}%",
            "automation evidence meets profile thresholds",
        ]
    return status, reasons, applied, unmet, obs_rate


def generate_gate_decision(
    feature_id: str,
    status: str,
    profile: str,
    reasons: list[str],
    blocking_risks: list[str],
    waivers: list[Any],
    residual_risks: list[str],
    defects: list[dict[str, Any]],
    *,
    build_id: str | None = None,
    evidence_summary: dict[str, Any] | None = None,
    unmet_conditions: list[str] | None = None,
) -> dict[str, Any]:
    gate: dict[str, Any] = {
        "feature_id": feature_id,
        "status": status,
        "profile": profile,
        "reasons": reasons or ["Gate evaluation produced no supporting reason"],
    }
    optional = {
        "build_id": build_id,
        "evidence_summary": evidence_summary,
        "blocking_risks": blocking_risks or None,
        "waivers": waivers or None,
        "residual_risks": residual_risks or None,
        "unmet_conditions": unmet_conditions or None,
    }
    gate.update({key: value for key, value in optional.items() if value is not None})
    follow_up = [
        f"Monitor {defect.get('title', 'defect')} post-release"
        for defect in defects
        if defect.get("severity") in ("medium", "low")
    ]
    if residual_risks:
        follow_up.append("Review residual risks in next sprint")
    if follow_up:
        gate["required_follow_up"] = follow_up
    return gate


def validate_schema(value: dict[str, Any], schema_name: str) -> None:
    """Raise a GateInputError when a package artifact violates its schema."""
    try:
        validate_artifact(value, schema_name)
    except SchemaValidationError as exc:
        raise GateInputError(str(exc)) from exc


def first_matching(directory: Path, patterns: tuple[str, ...]) -> Path | None:
    for pattern in patterns:
        match = next(iter(sorted(directory.glob(pattern))), None)
        if match:
            return match
    return None


def matching_gate_pair(directory: Path) -> tuple[Path, Path]:
    """Find the only risk/case pair sharing a feature_id."""
    risks = sorted(set(directory.glob("*risk*.json")))
    cases = sorted(set(directory.glob("*case*.json")))
    pairs = []
    for risk_path in risks:
        risk_feature = load_json(risk_path).get("feature_id")
        for case_path in cases:
            if risk_feature and load_json(case_path).get("feature_id") == risk_feature:
                pairs.append((risk_path, case_path))
    if len(pairs) != 1:
        raise GateInputError(f"Expected one matching risk/case feature pair, found {len(pairs)}")
    return pairs[0]


def artifact_for_feature(
    directory: Path, patterns: tuple[str, ...], feature_id: str
) -> Path | None:
    """Find at most one artifact of the requested type for feature_id."""
    candidates = sorted({path for pattern in patterns for path in directory.glob(pattern)})
    matches = [path for path in candidates if load_json(path).get("feature_id") == feature_id]
    if len(matches) > 1:
        raise GateInputError(
            f"Multiple artifacts for feature={feature_id}: "
            + ", ".join(path.name for path in matches)
        )
    return matches[0] if matches else None


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Gate 2.0 release readiness")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--risk", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--feature", type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--automation", type=Path)
    parser.add_argument("--waivers", type=Path)
    parser.add_argument("--build-id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=list(GATE_THRESHOLDS), default="standard")
    parser.add_argument("--version", action="version", version=f"evaluate-gate {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        evidence_path, risk_path, cases_path = args.evidence, args.risk, args.cases
        feature_path, observations_path = args.feature, args.observations
        automation_path, waivers_path = args.automation, args.waivers
        directory: Path | None = None
        if args.input:
            directory = args.input
            evidence_path = evidence_path or directory
            if risk_path is None and cases_path is None:
                risk_path, cases_path = matching_gate_pair(directory)
            else:
                risk_path = risk_path or first_matching(directory, ("*risk*.json",))
                cases_path = cases_path or first_matching(directory, ("*case*.json",))
        if evidence_path is None:
            raise GateInputError("--evidence or --input required")
        if risk_path is None or not risk_path.exists():
            raise GateInputError("Risk register file required")
        if cases_path is None or not cases_path.exists():
            raise GateInputError("Manual case set file required")

        risks, cases = load_json(risk_path), load_json(cases_path)
        validate_schema(risks, "risk_register.schema.json")
        validate_schema(cases, "manual_case_set.schema.json")
        feature_id = str(cases.get("feature_id") or risks.get("feature_id") or "")
        if not feature_id or risks.get("feature_id") != feature_id:
            raise GateInputError("risk/case feature_id mismatch")
        if directory is not None:
            feature_path = feature_path or artifact_for_feature(
                directory, ("*feature_spec*.json",), feature_id
            )
            observations_path = observations_path or artifact_for_feature(
                directory, ("*observation*.json",), feature_id
            )
            automation_path = automation_path or artifact_for_feature(
                directory, ("*automation*.json",), feature_id
            )
            waivers_path = waivers_path or artifact_for_feature(
                directory, ("*waiver*.json",), feature_id
            )
        feature = load_json(feature_path) if feature_path else None
        observations = load_json(observations_path) if observations_path else None
        automation = load_json(automation_path) if automation_path else None
        waiver_set = load_json(waivers_path) if waivers_path else None
        for artifact, schema_name, label in (
            (feature, "feature_spec.schema.json", "feature"),
            (observations, "observation_set.schema.json", "observations"),
            (automation, "automation_evidence.schema.json", "automation"),
            (waiver_set, "waiver_set.schema.json", "waivers"),
        ):
            if artifact is not None:
                validate_schema(artifact, schema_name)
                if artifact.get("feature_id") != feature_id:
                    raise GateInputError(f"{label} feature_id mismatch")

        raw_evidence = load_evidence_files(evidence_path)
        for item in raw_evidence:
            validate_schema(
                {key: value for key, value in item.items() if key != "_source_path"},
                "execution_evidence.schema.json",
            )
        evidence, build_id = validate_and_select_evidence(
            raw_evidence, feature_id, args.build_id
        )
        results = extract_case_results(evidence, cases)
        counts = count_results_by_priority(results)
        defects = extract_open_defects(evidence)
        residual, blocking = assess_residual_risks(risks, results)
        status, reasons, waivers, unmet, obs_rate = evaluate_gate(
            feature_id=feature_id,
            build_id=build_id,
            profile=args.profile,
            counts=counts,
            defects=defects,
            blocking_risks=blocking,
            residual_risks=residual,
            feature_spec=feature,
            risk_register=risks,
            observations=observations,
            automation=automation,
            waiver_set=waiver_set,
            results=results,
        )
        gate = generate_gate_decision(
            feature_id,
            status,
            args.profile,
            reasons,
            blocking,
            waivers,
            residual,
            defects,
            build_id=build_id,
            evidence_summary={
                "manual_by_priority": counts,
                "mandatory_observation_rate": obs_rate,
            },
            unmet_conditions=unmet,
        )
        validate_schema(gate, "gate_decision.schema.json")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Generated: {args.output}")
        print(f"  Status: {status}")
        print(f"  Feature: {feature_id}")
        print(f"  Build: {build_id}")
        print(f"  P0: {counts['P0']['pass']}/{counts['P0']['total']} passed")
        print(f"  P1: {counts['P1']['pass']}/{counts['P1']['total']} passed")
        return 0
    except (GateInputError, OSError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
