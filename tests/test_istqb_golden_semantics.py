"""ISTQBレビューで検出した評価資産の意味不整合に対する回帰テスト。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_artifact(name: str) -> dict[str, object]:
    return json.loads((ROOT / "examples" / "artifacts" / name).read_text(encoding="utf-8"))


def test_admin_role_artifacts_share_one_feature_and_role_vocabulary() -> None:
    feature = load_artifact("admin-role-change.feature_spec.json")
    model = load_artifact("admin-role-change.test_model.json")
    cases = load_artifact("admin-role-change.manual_case_set.json")

    assert feature["feature_id"] == model["feature_id"] == cases["feature_id"]
    assert {"owner", "admin", "editor", "viewer", "member"}.issubset(set(feature["actors"]))
    assert "super_admin" not in json.dumps(feature, ensure_ascii=False)
    assert "super_admin" not in json.dumps(model, ensure_ascii=False)


def test_admin_cases_use_oracles_that_support_the_expected_behavior() -> None:
    cases = load_artifact("admin-role-change.manual_case_set.json")["manual_cases"]
    by_id = {case["tc_id"]: case for case in cases}

    assert by_id["TC-ADMIN-005"]["oracle"]["refs"] == ["BR-2"]
    assert by_id["TC-ADMIN-006"]["oracle"]["refs"] == ["BR-3"]
    assert by_id["TC-ADMIN-006"]["primary_view"] == "black"


def test_self_demotion_rule_is_exercised_without_last_owner_masking() -> None:
    case_set = load_artifact("admin-role-change.manual_case_set.json")
    cases = case_set["manual_cases"]
    candidates = [
        case
        for case in cases
        if "BR-1" in case["oracle"]["refs"]
        and "owner_count=2" in case.get("preconditions", [])
    ]

    assert len(candidates) == 1
    assert "自分自身" in " ".join(candidates[0]["steps"])


def test_admin_golden_requires_the_unmasked_self_demotion_observation() -> None:
    expected = (ROOT / "goldens" / "admin-role-change.expected.md").read_text(
        encoding="utf-8"
    )

    assert "複数 owner のときも自分自身の owner 降格は禁止" in expected
