"""Generate Mermaid stateDiagram from test_model.json.

Usage:
    python scripts/state-diagram.py --input <test_model.json> --output <output.mmd>

Example:
    python scripts/state-diagram.py \
        --input examples/artifacts/order-cancel.test_model.json \
        --output examples/artifacts/order-cancel.states.mmd
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

__version__ = "0.2.0"


def load_test_model(path: Path) -> dict:
    """Load and parse test_model.json."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def extract_states(test_model: dict) -> list[str]:
    """Extract states from test_model."""
    states: list[str] = test_model.get("states", [])
    if not states:
        # Infer states from transitions if not explicitly defined
        transitions = test_model.get("valid_transitions", [])
        for t in transitions:
            parts = t.split("->")
            for p in parts:
                state = p.strip()
                if state and state not in states:
                    states.append(state)
    return states


def extract_transitions(test_model: dict) -> tuple[list[str], list[str]]:
    """Extract valid and invalid transitions from test_model."""
    valid: list[str] = test_model.get("valid_transitions", [])
    invalid: list[str] = test_model.get("invalid_transitions", [])
    return valid, invalid


def parse_transition(transition_str: str) -> tuple[str, str]:
    """Parse 'from -> to' transition string."""
    parts = transition_str.split("->")
    if len(parts) != 2:
        raise ValueError(f"Invalid transition format: {transition_str}")
    return parts[0].strip(), parts[1].strip()


def generate_mermaid(
    states: list[str],
    valid_transitions: list[str],
    invalid_transitions: list[str],
    flows: list[str] | None = None,
) -> str:
    """Generate Mermaid stateDiagram-v2 from states and transitions."""
    lines: list[str] = ["stateDiagram-v2"]

    # Add initial state if we have a natural entry point
    # Convention: first valid transition's source is initial
    if valid_transitions:
        first_transition = valid_transitions[0]
        from_state, _ = parse_transition(first_transition)
        lines.append(f"  [*] --> {from_state}")

    # Add valid transitions (solid arrows)
    for t in valid_transitions:
        from_state, to_state = parse_transition(t)
        lines.append(f"  {from_state} --> {to_state}")

    # Add invalid transitions (dashed arrows with note)
    for t in invalid_transitions:
        from_state, to_state = parse_transition(t)
        lines.append(f"  {from_state} -.-> {to_state}: invalid")

    # Add flow descriptions as notes (if provided)
    if flows:
        for i, flow in enumerate(flows):
            lines.append(f"  note right of [*] : Flow {i+1}: {flow}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Mermaid stateDiagram from test_model.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to test_model.json file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output Mermaid file (.mmd)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"state-diagram {__version__}",
    )

    args = parser.parse_args()

    try:
        # Load test model
        test_model = load_test_model(args.input)

        # Extract data
        states = extract_states(test_model)
        valid, invalid = extract_transitions(test_model)
        flows = test_model.get("flows")

        # Generate Mermaid
        mermaid_content = generate_mermaid(states, valid, invalid, flows)

        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(mermaid_content, encoding="utf-8")

        print(f"Generated: {args.output}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())