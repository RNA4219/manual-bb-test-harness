from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "manual-bb-test-harness"
REQUIRED = {"schema_version", "record_type", "bridge_id", "original_command", "owner", "canonical_contract", "status", "input_refs", "expected_output_types", "sourceRefs"}

def test_hate_bridge_golden_request_matches_consumer_contract() -> None:
    fixture = json.loads((ROOT / "fixtures/hate-bridge/v1/golden-request.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "contracts/hate-bridge/v1/request.consumer.schema.json").read_text(encoding="utf-8"))
    assert REQUIRED <= fixture.keys()
    assert set(schema["required"]) == REQUIRED
    assert fixture["schema_version"] == "HATE-bridge/v1"
    assert fixture["record_type"] == "bridge_request"
    assert fixture["owner"] == OWNER == schema["properties"]["owner"]["const"]
    assert fixture["status"] == "handoff_required"
    assert fixture["expected_output_types"]
