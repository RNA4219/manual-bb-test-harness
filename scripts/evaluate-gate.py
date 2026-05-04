"""Evaluate gate decision from execution evidence, risk register, and manual case set.

Applies gate policy to determine go/conditional_go/no_go status.

Usage:
    python scripts/evaluate-gate.py --evidence <dir_or_file> --risk <risk_register.json> --cases <manual_case_set.json> --output <gate_decision.json>
    python scripts/evaluate-gate.py --input <dir> --output <gate_decision.json>
    python scripts/evaluate-gate.py --version

Example:
    python scripts/evaluate-gate.py \
        --evidence examples/artifacts/execution_evidence/ \
        --risk examples/artifacts/order-cancel.risk_register.json \
        --cases examples/artifacts/order-cancel.manual_case_set.json \
        --output examples/artifacts/order-cancel.gate_decision.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

__version__ = "0.1.0"


# Gate policy thresholds (from risk-and-gate-policy.md)
GATE_THRESHOLDS = {
    "strict": {
        "auto_coverage": 80,
        "new_issues_blocker": 0,
        "new_issues_critical": 0,
        "p0_pass": 100,
        "p1_pass": 100,
        "high_risk_obs": 100,
        "unresolved_high_risk": 0,
    },
    "standard": {
        "auto_coverage": 75,
        "new_issues_blocker": 0,
        "new_issues_critical": 0,
        "p0_pass": 100,
        "p1_pass": 95,
        "high_risk_obs": 95,
        "unresolved_high_risk": 0,
    },
    "lean": {
        "auto_coverage": 60,
        "new_issues_blocker": 0,
        "p0_pass": 100,
        "p1_pass": 80,
        "high_risk_obs": 80,
        "unresolved_high_risk": None,  # Can be waived
    },
}


def load_json_file(path: Path) -> dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def load_evidence_files(path: Path) -> list[dict[str, Any]]:
    """Load execution evidence from file or directory."""
    evidence_list: list[dict[str, Any]] = []

    if path.is_file():
        evidence_list.append(load_json_file(path))
    elif path.is_dir():
        # Look for execution evidence files
        # Accept: execution_*.json, *_evidence.json, TC-*.json (test case results)
        for f in path.glob("*.json"):
            name_lower = f.name.lower()
            if "execution" in name_lower or "evidence" in name_lower or f.name.startswith("TC-") or f.name.startswith("tc-"):
                evidence_list.append(load_json_file(f))
            # Also check if file has tc_id field (execution evidence marker)
            else:
                try:
                    data = load_json_file(f)
                    if "tc_id" in data and "result" in data:
                        evidence_list.append(data)
                except Exception:
                    pass  # Skip non-evidence JSON files
    else:
        raise ValueError(f"Path not found: {path}")

    return evidence_list


def extract_case_results(
    evidence_list: list[dict[str, Any]],
    manual_cases: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Extract pass/fail results for each test case and charter from evidence."""
    results: dict[str, dict[str, Any]] = {}

    # Build lookup from manual_cases (scripted test cases)
    case_lookup: dict[str, dict[str, Any]] = {}
    for case in manual_cases.get("manual_cases", []):
        tc_id = case.get("tc_id", "")
        case_lookup[tc_id] = {
            "priority": case.get("priority", "P2"),
            "trace_to": case.get("trace_to", []),
            "type": "scripted",
        }

    # Build lookup from exploratory_charters
    for charter in manual_cases.get("exploratory_charters", []):
        charter_id = charter.get("id", "")
        case_lookup[charter_id] = {
            "priority": charter.get("priority", "P2"),
            "trace_to": charter.get("trace_to", []),
            "type": "exploratory",
        }

    # Process evidence
    for evidence in evidence_list:
        tc_id = evidence.get("tc_id", "")
        charter_id = evidence.get("charter_id", "")
        # Check both tc_id and charter_id
        lookup_key = tc_id if tc_id in case_lookup else charter_id

        if lookup_key in case_lookup:
            result = evidence.get("result", "unknown")
            case_info = case_lookup[lookup_key]

            results[lookup_key] = {
                "result": result,
                "priority": case_info["priority"],
                "trace_to": case_info["trace_to"],
                "type": case_info["type"],
                "run_id": evidence.get("run_id", ""),
                "defect_stub": evidence.get("defect_stub"),
            }

    return results


def count_results_by_priority(
    case_results: dict[str, dict[str, Any]]
) -> dict[str, dict[str, int]]:
    """Count pass/fail/skip by priority."""
    counts: dict[str, dict[str, int]] = {
        "P0": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        "P1": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        "P2": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
        "P3": {"pass": 0, "fail": 0, "skip": 0, "total": 0},
    }

    for tc_id, data in case_results.items():
        priority = data.get("priority", "P2")
        if priority not in counts:
            priority = "P2"
        counts[priority]["total"] += 1
        result = data.get("result", "unknown").lower()
        if result == "pass":
            counts[priority]["pass"] += 1
        elif result == "fail":
            counts[priority]["fail"] += 1
        else:
            counts[priority]["skip"] += 1

    return counts


def extract_open_defects(
    evidence_list: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Extract open defects from execution evidence."""
    defects: list[dict[str, Any]] = []

    for evidence in evidence_list:
        if evidence.get("result") == "fail":
            defect_stub = evidence.get("defect_stub")
            if defect_stub:
                defects.append({
                    "tc_id": evidence.get("tc_id", ""),
                    "title": defect_stub.get("title", "Untitled defect"),
                    "severity": defect_stub.get("severity", "unknown"),
                })

    return defects


def assess_residual_risks(
    risk_register: dict[str, Any],
    case_results: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str]]:
    """Assess residual and blocking risks based on test results."""
    residual: list[str] = []
    blocking: list[str] = []

    risks = risk_register.get("risks", [])

    # Build reverse mapping: risk_id -> list of case_ids that trace to it (case -> risk)
    risk_to_cases: dict[str, list[str]] = {}
    for case_id, data in case_results.items():
        for ref in data.get("trace_to", []):
            if ref not in risk_to_cases:
                risk_to_cases[ref] = []
            risk_to_cases[ref].append(case_id)

    for risk in risks:
        risk_id = risk.get("id", "")
        priority = risk.get("priority", "P3")
        scenario = risk.get("scenario", "")

        # Check both directions:
        # 1. Cases that trace TO this risk (case.trace_to contains risk_id)
        # 2. Risk's trace_to references (risk.trace_to contains case_id)
        tracing_cases = risk_to_cases.get(risk_id, [])

        # Also check risk's own trace_to field (risk -> case/charters)
        risk_trace_to = risk.get("trace_to", [])
        for traced_item in risk_trace_to:
            if traced_item in case_results:
                tracing_cases.append(traced_item)

        tested = len(tracing_cases) > 0
        passed = all(
            case_results.get(case_id, {}).get("result") == "pass"
            for case_id in tracing_cases
        )

        if priority in ["P0", "P1"] and not tested:
            blocking.append(risk_id)
        elif priority in ["P0", "P1"] and tested and not passed:
            blocking.append(risk_id)
        elif priority in ["P2", "P3"] and not tested:
            residual.append(f"{risk_id}: {scenario}")

    return residual, blocking


def determine_gate_status(
    counts: dict[str, dict[str, int]],
    defects: list[dict[str, Any]],
    blocking_risks: list[str],
    profile: str = "standard"
) -> tuple[str, list[str], list[str]]:
    """Determine gate status based on policy thresholds."""
    thresholds = GATE_THRESHOLDS.get(profile, GATE_THRESHOLDS["standard"])
    reasons: list[str] = []
    waivers: list[str] = []

    # Check blocker/high defects
    blocker_count = sum(1 for d in defects if d.get("severity") in ["blocker", "critical", "high"])
    if blocker_count > 0:
        return "no_go", [f"Blocker/critical/high defects: {blocker_count}"], []

    # Check P0 pass rate
    p0_total = counts["P0"]["total"]
    p0_pass = counts["P0"]["pass"]
    if p0_total > 0:
        p0_rate = (p0_pass / p0_total) * 100
        if p0_rate < thresholds["p0_pass"]:
            return "no_go", [f"P0 pass rate: {p0_rate:.1f}% (required: {thresholds['p0_pass']}%)"], []
        reasons.append(f"P0 pass rate: {p0_rate:.1f}% ({p0_pass}/{p0_total})")

    # Check P1 pass rate
    p1_total = counts["P1"]["total"]
    p1_pass = counts["P1"]["pass"]
    if p1_total > 0:
        p1_rate = (p1_pass / p1_total) * 100
        required_p1 = thresholds["p1_pass"]
        if p1_rate < required_p1:
            if profile == "lean":
                waivers.append(f"P1 pass rate {p1_rate:.1f}% below {required_p1}% (waived for lean profile)")
            else:
                return "no_go", [f"P1 pass rate: {p1_rate:.1f}% (required: {required_p1}%)"], []
        reasons.append(f"P1 pass rate: {p1_rate:.1f}% ({p1_pass}/{p1_total})")

    # Check blocking risks
    if blocking_risks:
        return "no_go", [f"Blocking risks unresolved: {len(blocking_risks)}"], []

    # Determine status
    if waivers:
        return "conditional_go", reasons, waivers
    return "go", reasons, []


def generate_gate_decision(
    feature_id: str,
    status: str,
    profile: str,
    reasons: list[str],
    blocking_risks: list[str],
    waivers: list[str],
    residual_risks: list[str],
    defects: list[dict[str, Any]]
) -> dict[str, Any]:
    """Generate gate_decision.json structure."""
    gate: dict[str, Any] = {
        "feature_id": feature_id,
        "status": status,
        "profile": profile,
        "reasons": reasons,
    }

    if blocking_risks:
        gate["blocking_risks"] = blocking_risks

    if waivers:
        gate["waivers"] = waivers

    if residual_risks:
        gate["residual_risks"] = residual_risks

    # Add follow-up based on defects
    follow_up: list[str] = []
    for d in defects:
        if d.get("severity") in ["medium", "low"]:
            follow_up.append(f"Monitor {d.get('title', 'defect')} post-release")
    if residual_risks:
        follow_up.append("Review residual risks in next sprint")
    if follow_up:
        gate["required_follow_up"] = follow_up

    return gate


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate gate decision from execution evidence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Execution evidence file or directory",
    )
    parser.add_argument(
        "--risk",
        type=Path,
        help="Risk register JSON file",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        help="Manual case set JSON file",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input directory containing all artifacts",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output gate_decision.json file",
    )
    parser.add_argument(
        "--profile",
        choices=["strict", "standard", "lean"],
        default="standard",
        help="Gate quality profile (default: standard)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"evaluate-gate {__version__}",
    )

    args = parser.parse_args()

    try:
        # Determine input paths
        evidence_path: Path | None = args.evidence
        risk_path: Path | None = args.risk
        cases_path: Path | None = args.cases

        if args.input:
            input_dir = args.input
            if not evidence_path:
                evidence_path = input_dir
            if not risk_path:
                risk_path = input_dir / "risk_register.json"
                # Try alternative names
                if not risk_path.exists():
                    for f in input_dir.glob("*risk*.json"):
                        risk_path = f
                        break
            if not cases_path:
                cases_path = input_dir / "manual_case_set.json"
                # Try alternative names
                if not cases_path.exists():
                    for f in input_dir.glob("*case*.json"):
                        cases_path = f
                        break

        # Validate required inputs
        if not evidence_path:
            print("Error: --evidence or --input required", file=sys.stderr)
            return 1
        if not risk_path or not risk_path.exists():
            print("Error: Risk register file required", file=sys.stderr)
            return 1
        if not cases_path or not cases_path.exists():
            print("Error: Manual case set file required", file=sys.stderr)
            return 1

        # Load data
        evidence_list = load_evidence_files(evidence_path)
        risk_register = load_json_file(risk_path)
        manual_cases = load_json_file(cases_path)

        # Get feature_id
        feature_id = manual_cases.get("feature_id", risk_register.get("feature_id", "UNKNOWN"))

        # Extract results
        case_results = extract_case_results(evidence_list, manual_cases)
        counts = count_results_by_priority(case_results)
        defects = extract_open_defects(evidence_list)

        # Assess risks
        residual_risks, blocking_risks = assess_residual_risks(risk_register, case_results)

        # Determine gate
        status, reasons, waivers = determine_gate_status(
            counts, defects, blocking_risks, args.profile
        )

        # Generate output
        gate = generate_gate_decision(
            feature_id, status, args.profile, reasons,
            blocking_risks, waivers, residual_risks, defects
        )

        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(gate, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"Generated: {args.output}")
        print(f"  Status: {status}")
        print(f"  Feature: {feature_id}")
        print(f"  P0: {counts['P0']['pass']}/{counts['P0']['total']} passed")
        print(f"  P1: {counts['P1']['pass']}/{counts['P1']['total']} passed")
        print(f"  Defects: {len(defects)} open")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())