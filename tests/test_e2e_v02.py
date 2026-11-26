import hashlib
import json
import os
import runpy
import subprocess
from pathlib import Path

import pytest

inputs = runpy.run_path(str(Path(__file__).with_name("test_e2e_export.py")))["inputs"]

ROOT = Path(__file__).resolve().parents[1]
BIN = (
    ROOT
    / "src/bb_harness/native/e2e_export/target/debug"
    / ("bb-export-e2e.exe" if os.name == "nt" else "bb-export-e2e")
)


@pytest.fixture(scope="module", autouse=True)
def build_exporter():
    subprocess.run(
        [
            "cargo",
            "build",
            "--locked",
            "--manifest-path",
            str(ROOT / "src/bb_harness/native/e2e_export/Cargo.toml"),
        ],
        check=True,
    )


def run(tmp_path, check):
    paths, binding = inputs(tmp_path)
    binding["cases"][0]["checks"] = [check]
    data = json.dumps(binding).encode()
    paths[2].write_bytes(data)
    out = tmp_path / "out"
    result = subprocess.run(
        [
            str(BIN),
            "--feature-spec",
            str(paths[0]),
            "--manual-case-set",
            str(paths[1]),
            "--binding",
            str(paths[2]),
            "--approved-binding-sha256",
            hashlib.sha256(data).hexdigest(),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    return result, out


def base():
    return {
        "text": "Confirmation is visible",
        "kind": "countDelta",
        "locator": {"testId": "list"},
        "itemLocator": {"testId": "row"},
        "value": 1,
        "afterActionId": "confirm",
        "acceptanceRef": "AC-1",
    }


def test_delta_export(tmp_path):
    result, out = run(tmp_path, base())
    assert result.returncode == 0, result.stderr
    folder = out / "TC-001"
    config = json.loads((folder / "lakda.config.json").read_text())
    assert config["reviewedOracleVersion"] == 2
    assert config["obligations"][0]["countDelta"]["value"] == 1
    script = (folder / "scenario.spec.ts").read_text(encoding="utf-8")
    assert (
        script.index("before[0] =")
        < script.index(".click()")
        < script.index("record.observed = await readCount")
    )
    assert "reviewed-observations.json" in script
    assert "type Locator" in script and "const before:" in script
    assert "const amount =" not in script


@pytest.mark.parametrize(
    "change",
    [
        {"acceptanceRef": "AC-X"},
        {"afterActionId": "unknown"},
        {"value": 9007199254740992},
        {"itemLocator": {"selector": "div"}},
    ],
)
def test_invalid_delta_is_rejected(tmp_path, change):
    check = base()
    check.update(change)
    result, out = run(tmp_path, check)
    assert result.returncode != 0
    assert not out.exists()


@pytest.mark.parametrize(
    "currency,fmt,minor", [("JPY", "jpy-yen-suffix", 900), ("USD", "usd-dollar-prefix", -900)]
)
def test_amount_export(tmp_path, currency, fmt, minor):
    check = {
        "text": "Confirmation is visible",
        "kind": "amountEquals",
        "locator": {"testId": "total"},
        "currency": currency,
        "format": fmt,
        "minorUnits": minor,
        "acceptanceRef": "AC-1",
    }
    result, out = run(tmp_path, check)
    assert result.returncode == 0, result.stderr
    config = json.loads((out / "TC-001" / "lakda.config.json").read_text())
    assert config["obligations"][0]["amountEquals"]["minorUnits"] == minor
    script = (out / "TC-001" / "scenario.spec.ts").read_text(encoding="utf-8")
    assert "Number.isSafeInteger" in script and "timeout: 5000" in script
    assert "const amount =" in script
    assert all(unused not in script for unused in ("const before:", "readCount", "type Locator"))


def test_invalid_currency_format_is_rejected(tmp_path):
    check = {
        "text": "Confirmation is visible",
        "kind": "amountEquals",
        "locator": {"testId": "total"},
        "currency": "USD",
        "format": "jpy-yen-suffix",
        "minorUnits": 900,
        "acceptanceRef": "AC-1",
    }
    result, out = run(tmp_path, check)
    assert result.returncode != 0 and not out.exists()


def test_python_fallback_rejects_v02(tmp_path, monkeypatch):
    from bb_harness.e2e_export import E2EExportError, export_e2e

    monkeypatch.setattr("bb_harness.e2e_export.native_command", lambda *_: None)
    paths, binding = inputs(tmp_path)
    binding["cases"][0]["checks"] = [base()]
    data = json.dumps(binding).encode()
    paths[2].write_bytes(data)
    with pytest.raises(E2EExportError, match="unsupported expected result"):
        export_e2e(
            *paths, tmp_path / "out", approved_binding_sha256=hashlib.sha256(data).hexdigest()
        )
    assert not (tmp_path / "out").exists()


def test_intermediate_legacy_check_requires_acceptance_ref(tmp_path):
    check = {
        "text": "Confirmation is visible",
        "kind": "visible",
        "locator": {"testId": "confirmation"},
        "afterActionId": "confirm",
    }
    result, out = run(tmp_path, check)
    assert result.returncode != 0 and "acceptanceRef" in result.stderr
    assert not out.exists()


@pytest.mark.parametrize("timing", [{}, {"afterActionId": "confirm"}])
def test_visible_with_acceptance_reference_exports_v2_config(tmp_path, timing, monkeypatch):
    from bb_harness.cli import main

    check = {
        "text": "Confirmation is visible",
        "kind": "visible",
        "locator": {"testId": "confirmation"},
        "acceptanceRef": "AC-1",
        **timing,
    }
    paths, binding = inputs(tmp_path)
    binding["cases"][0]["checks"] = [check]
    reviewed = json.dumps(binding).encode("utf-8")
    paths[2].write_bytes(reviewed)
    monkeypatch.setenv("PATH", str(BIN.parent) + os.pathsep + os.environ["PATH"])
    out = tmp_path / "export"
    args = ["export-e2e", "--feature-spec", str(paths[0]), "--manual-case-set", str(paths[1]),
            "--binding", str(paths[2]), "--out", str(out), "--approved-binding-sha256"]
    assert main([*args, "0" * 64]) == 2 and not out.exists()
    assert main([*args, hashlib.sha256(reviewed).hexdigest()]) == 0
    config = json.loads((out / "TC-001" / "lakda.config.json").read_text(encoding="utf-8"))
    assert config["reviewedOracleVersion"] == 2
    assert config["obligations"] == [
        {"visible": check["locator"], "acceptanceRef": "AC-1", **timing}
    ]


@pytest.fixture
def shipping_export(tmp_path, monkeypatch):
    from bb_harness.cli import main

    sample = ROOT / "examples/artifacts/shipping-details"
    out = tmp_path / "export"
    monkeypatch.setenv("PATH", str(BIN.parent) + os.pathsep + os.environ["PATH"])

    def export(binding):
        return main([
            "export-e2e", "--feature-spec", str(sample / "feature_spec.json"),
            "--manual-case-set", str(sample / "manual_case_set.json"),
            "--binding", str(binding), "--out", str(out),
            "--approved-binding-sha256", hashlib.sha256(binding.read_bytes()).hexdigest(),
        ])

    return export, sample / "e2e-binding.json", out


def test_shipping_details_close_exports_ordered_checks(shipping_export):
    export, binding, out = shipping_export
    assert export(binding) == 0
    folder = out / "TC-SHIPPING-CLOSE"
    config = json.loads((folder / "lakda.config.json").read_text(encoding="utf-8"))
    answer = {"testId": "shipping-answer"}
    assert config["reviewedOracleVersion"] == 2
    assert config["obligations"] == [
        {"visible": answer, "afterActionId": "open", "acceptanceRef": "AC-SHIPPING-OPEN"},
        {"hidden": answer, "afterActionId": "close", "acceptanceRef": "AC-SHIPPING-CLOSE"},
    ]
    script = (folder / "scenario.spec.ts").read_text(encoding="utf-8")
    click = 'page.getByTestId("shipping-question").click()'
    opened, closed = script.index(click), script.rindex(click)
    assert opened < script.index(".toBeVisible(") < closed < script.index(".toBeHidden(")
    assert all(unused not in script for unused in ("const before:", "const amount =", "readCount", "type Locator"))


def test_count_equals_only_needs_the_count_helper(tmp_path):
    check = {**base(), "kind": "countEquals"}
    del check["afterActionId"]
    result, out = run(tmp_path, check)
    assert result.returncode == 0, result.stderr
    script = (out / "TC-001/scenario.spec.ts").read_text(encoding="utf-8")
    assert "type Locator" in script and "const readCount =" in script
    assert "const before:" not in script and "const amount =" not in script


def test_mixed_amount_and_delta_generate_both_helpers(shipping_export, tmp_path):
    export, binding, out = shipping_export
    data = json.loads(binding.read_text(encoding="utf-8"))
    amount, delta = data["cases"][0]["checks"]
    amount.update(kind="amountEquals", currency="JPY", format="jpy-yen-suffix", minorUnits=900)
    delta.update(kind="countDelta", itemLocator={"testId": "row"}, value=1)
    mixed = tmp_path / "mixed.json"
    mixed.write_text(json.dumps(data), encoding="utf-8")
    assert export(mixed) == 0
    script = (out / "TC-SHIPPING-CLOSE/scenario.spec.ts").read_text(encoding="utf-8")
    for needed in ("const amount =", "const readCount =", "const before:", "type Locator"):
        assert script.count(needed) == 1


@pytest.mark.parametrize("with_reference", [True, False])
def test_final_hidden_check_requires_acceptance_ref(shipping_export, tmp_path, with_reference):
    export, binding, out = shipping_export
    data = json.loads(binding.read_text(encoding="utf-8"))
    check = data["cases"][0]["checks"][1]
    del check["afterActionId"]
    if not with_reference:
        del check["acceptanceRef"]
    final_binding = tmp_path / "final-binding.json"
    final_binding.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if with_reference:
        assert export(final_binding) == 0
        config = json.loads((out / "TC-SHIPPING-CLOSE/lakda.config.json").read_text(encoding="utf-8"))
        assert config["obligations"][1] == {
            "hidden": {"testId": "shipping-answer"}, "acceptanceRef": "AC-SHIPPING-CLOSE",
        }
    else:
        assert export(final_binding) == 2
        assert not out.exists()


def test_count_checks_recheck_container_around_measurement(tmp_path):
    result, out = run(tmp_path, base())
    assert result.returncode == 0, result.stderr
    script = (out / "TC-001" / "scenario.spec.ts").read_text(encoding="utf-8")
    assert script.count("await container.count()") == 2
    assert script.count("await readCount(") == 2
    assert "toHaveCount(1" not in script
