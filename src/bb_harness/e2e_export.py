"""Deterministic, review-bound export of manual cases to Lakda replay inputs.

Only explicitly reviewed action bindings and machine-checkable final obligations
are exported. No LLM inference, browser launch, network request or Gate decision.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit


class E2EExportError(ValueError):
    """The supplied approval/binding cannot prove a runnable scenario."""


CASE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
SECRET = re.compile(r"(?:bearer\s+\S+|sk-[A-Za-z0-9]{16,}|password\s*[:=]\s*\S+)", re.I)
ACTION_KINDS = {"navigate", "goto", "click", "fill", "check", "select", "press"}
LOCATOR_ROLES = {"button", "link", "textbox", "checkbox", "combobox", "option", "menuitem", "tab"}


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EExportError(message)


def _read(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise E2EExportError("invalid input JSON") from exc
    _require(isinstance(data, dict), "input must be object")
    return data


def _text(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), label + " is required")
    _require(not SECRET.search(value), label + " contains a possible secret")
    return value


def _action(raw: object, case_id: str, index: int) -> dict:
    _require(isinstance(raw, dict), "action must be object")
    allowed = {"id", "kind", "path", "locator", "inputProfileId", "key", "mutates"}
    _require(not (set(raw) - allowed), "unsafe action fields")
    kind = raw.get("kind")
    _require(kind in ACTION_KINDS, "unsupported action kind")
    _text(raw.get("id"), "action id")
    if kind in {"navigate", "goto"}:
        path = _text(raw.get("path"), "navigation path")
        _require(path.startswith("/") and not path.startswith("//") and "\\" not in path,
                 "navigation must use a local absolute path")
        _require(raw.get("locator") is None, "navigation cannot have locator")
    else:
        locator = raw.get("locator")
        _require(isinstance(locator, dict), "action locator is required")
        _require(not set(locator) - {"testId", "role", "name"}, "unsupported locator")
        if "testId" in locator:
            _text(locator["testId"], "testId")
            _require(not ("role" in locator or "name" in locator), "ambiguous locator")
        else:
            _require(locator.get("role") in LOCATOR_ROLES, "invalid locator role")
            _text(locator.get("name"), "locator name")
    if kind in {"fill", "select"}:
        input_profile_id = _text(raw.get("inputProfileId"), "input profile ID")
        _require(bool(CASE_ID.fullmatch(input_profile_id)), "invalid input profile ID")
    else:
        _require("inputProfileId" not in raw, "unexpected input profile")
    if kind == "press":
        _require(raw.get("key") in {"Enter", "Escape", "Space", "Tab"}, "invalid key")
    else:
        _require("key" not in raw, "unexpected key")
    _require(not raw.get("mutates", False), "mutation requires separate approved reset policy")
    return dict(raw)


def _check(raw: object, expected: str, base_url: str) -> tuple[dict, dict]:
    _require(isinstance(raw, dict), "expected result binding must be object")
    _require(raw.get("text") == expected, "expected result text changed after review")
    kind = raw.get("kind")
    if kind == "url":
        _require(set(raw) == {"text", "kind", "value"}, "invalid URL oracle binding")
        target = _text(raw.get("value"), "expected URL")
        resolved = urljoin(base_url, target)
        _require(urlsplit(resolved).netloc == urlsplit(base_url).netloc
                 and urlsplit(resolved).scheme == urlsplit(base_url).scheme,
                 "expected URL must remain on approved target")
        return {"expectedUrl": resolved}, {"kind": "url", "value": resolved}
    if kind == "visible":
        _require(set(raw) == {"text", "kind", "locator"}, "invalid visibility binding")
        locator = raw.get("locator")
        _require(isinstance(locator, dict) and not set(locator) - {"testId", "role", "name"},
                 "invalid visibility locator")
        if "testId" in locator:
            _text(locator["testId"], "testId")
            _require(len(locator) == 1, "ambiguous visibility locator")
        else:
            _require(set(locator) == {"role", "name"} and locator["role"] in LOCATOR_ROLES,
                     "invalid visibility locator")
            _text(locator["name"], "locator name")
        return {"visible": locator}, {"kind": "visible", "locator": locator}
    raise E2EExportError("unsupported expected result: no mechanical oracle")


def _playwright_script(actions: list[dict], checks: list[dict], base_url: str) -> str:
    def q(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)
    lines = [
        'import { test, expect } from "@playwright/test";',
        "",
        'test("reviewed scenario (generated; do not hand-edit)", async ({ page }) => {',
    ]
    for action in actions:
        kind = action["kind"]
        if kind in {"navigate", "goto"}:
            lines.append("  await page.goto(" + q(urljoin(base_url, action["path"])) + ");")
            continue
        loc = action["locator"]
        target = ("page.getByTestId(" + q(loc["testId"]) + ")") if "testId" in loc else (
            "page.getByRole(" + q(loc["role"]) + ", { name: " + q(loc["name"]) + ", exact: true })"
        )
        if kind == "click":
            lines.append("  await " + target + ".click();")
        elif kind == "check":
            lines.append("  await " + target + ".check();")
        elif kind == "press":
            lines.append("  await " + target + ".press(" + q(action["key"]) + ");")
        else:
            # Input values are supplied from the consuming product's environment, not generated.
            name = "E2E_INPUT_" + action["inputProfileId"].upper().replace("-", "_")
            lines.append("  {")
            lines.append("  const value = process.env[" + q(name) + "];")
            lines.append("  if (value === undefined) throw new Error(" + q("missing input profile: " + name) + ");")
            lines.append("  await " + target + (".fill(value);" if kind == "fill" else ".selectOption(value);"))
            lines.append("  }")
    for check in checks:
        if check["kind"] == "url":
            lines.append("  await expect(page).toHaveURL(" + q(check["value"]) + ");")
        else:
            loc = check["locator"]
            target = ("page.getByTestId(" + q(loc["testId"]) + ")") if "testId" in loc else (
                "page.getByRole(" + q(loc["role"]) + ", { name: " + q(loc["name"]) + ", exact: true })"
            )
            lines.append("  await expect(" + target + ").toBeVisible();")
    return "\n".join(lines + ["});", ""])


def export_e2e(feature_spec: str | Path, case_set: str | Path, binding_path: str | Path,
               output: str | Path) -> list[str]:
    """Export reviewed, active scripted cases to new-only deterministic directories."""
    feature = _read(feature_spec)
    cases = _read(case_set)
    binding = _read(binding_path)
    _require(binding.get("schemaVersion") == "manual-bb/e2e-binding/v1", "unsupported binding schema")
    _require(isinstance(feature.get("acceptance_criteria"), list)
             and len(feature["acceptance_criteria"]) > 0 and isinstance(feature.get("source_refs"), list)
             and len(feature["source_refs"]) > 0, "source acceptance criteria are required")
    _require(feature.get("feature_id") == cases.get("feature_id") == binding.get("featureId"),
             "feature mismatch")
    _require(feature.get("revision") == cases.get("spec_revision") == binding.get("specRevision"),
             "spec revision mismatch")
    base_url = _text(binding.get("baseUrl"), "baseUrl")
    url = urlsplit(base_url)
    _require(url.scheme in {"http", "https"} and bool(url.hostname) and not url.username
             and not url.password and not url.query and not url.fragment, "invalid target URL")
    _require(binding.get("seed") is not None and type(binding["seed"]) is int
             and 0 <= binding["seed"] < 2**32, "invalid seed")
    _require(binding.get("featureSha256") == _digest(feature), "feature input hash mismatch")
    _require(binding.get("caseSetSha256") == _digest(cases), "case set input hash mismatch")
    entries = binding.get("cases")
    _require(isinstance(entries, list) and len(entries) > 0, "empty bindings")
    by_id: dict[str, dict] = {}
    for case in cases.get("manual_cases", []):
        _require(isinstance(case, dict), "invalid case")
        case_id = _text(case.get("tc_id"), "case ID")
        _require(bool(CASE_ID.fullmatch(case_id)) and case_id not in by_id,
                 "unsafe or duplicate case ID")
        by_id[case_id] = case
    _require(len(entries) == len({entry.get("caseId") for entry in entries if isinstance(entry, dict)}),
             "duplicate binding case")
    prepared: list[tuple[str, dict[str, str]]] = []
    for entry in entries:
        _require(isinstance(entry, dict), "invalid binding")
        case_id = _text(entry.get("caseId"), "binding case ID")
        _require(case_id in by_id, "unknown case")
        case = by_id[case_id]
        _require(case.get("status", "active") == "active", "retired case cannot be automated")
        _require(case.get("oracle", {}).get("type") == "specified"
                 and bool(case.get("oracle", {}).get("refs")), "unapproved or unsupported oracle")
        _require(case.get("revision") == entry.get("revision")
                 and case.get("content_hash") == entry.get("contentHash")
                 and case.get("oracle_revision") == entry.get("oracleRevision"),
                 "case/oracle revision mismatch")
        _text(entry.get("reviewRef"), "review reference")
        _text(entry.get("reviewedBy"), "reviewer")
        _text(case.get("title"), "case title")
        _require(isinstance(case.get("steps"), list) and len(case["steps"]) > 0, "missing steps")
        _require(isinstance(case.get("expected_results"), list)
                 and len(case["expected_results"]) > 0, "missing expected results")
        for raw_text in [*case["steps"], *case["expected_results"]]:
            _text(raw_text, "case content")
        _require(isinstance(entry.get("actions"), list)
                 and len(entry["actions"]) == len(case["steps"]), "step bindings must be complete")
        _require(isinstance(entry.get("checks"), list)
                 and len(entry["checks"]) == len(case["expected_results"]),
                 "expectation bindings must be complete")
        actions = [_action(a, case_id, i) for i, a in enumerate(entry["actions"])]
        _require(len({a["id"] for a in actions}) == len(actions), "duplicate action ID")
        mapped = [_check(ch, text, base_url) for ch, text in zip(entry["checks"], case["expected_results"], strict=True)]
        obligations = [p[0] for p in mapped]
        checks = [p[1] for p in mapped]
        plan = {"schemaVersion": "lakda/action-plan/v1", "mode": "regression-replay",
                "seed": binding["seed"], "baseUrl": base_url, "actions": actions}
        config = {"schemaVersion": "lakda/v1", "browser": "chromium", "seed": binding["seed"],
                  "persona": "guest", "workers": 1,
                  "actionCatalog": actions,
                  "obligations": obligations, "safety": {"allowHosts": [url.hostname]}}
        review = {"schemaVersion": "manual-bb/e2e-scenario/v1", "featureId": feature["feature_id"],
                  "specRevision": feature["revision"], "caseId": case_id,
                  "caseRevision": case["revision"], "caseContentHash": case["content_hash"],
                  "oracleRevision": case["oracle_revision"], "oracleRefs": case["oracle"]["refs"],
                  "reviewRef": entry["reviewRef"], "reviewedBy": entry["reviewedBy"],
                  "steps": case["steps"], "expectedResults": case["expected_results"],
                  "machineChecks": checks, "sourceFeatureSha256": _digest(feature),
                  "sourceCaseSetSha256": _digest(cases)}
        markdown = ("# " + case["title"] + "\n\n" +
                    "Case: " + case_id + " / Review: " + entry["reviewRef"] + "\n\n" +
                    "## Steps\n" + "".join("- " + s + "\n" for s in case["steps"]) +
                    "\n## Expected\n" + "".join("- " + s + "\n" for s in case["expected_results"]))
        artifacts = {
            "scenario.json": json.dumps(review, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            "action-sequence.json": json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            "lakda.config.json": json.dumps(config, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            "scenario.md": markdown,
            "scenario.spec.ts": _playwright_script(actions, checks, base_url),
        }
        files = {name: hashlib.sha256(data.encode("utf-8")).hexdigest() for name, data in artifacts.items()}
        artifacts["manifest.json"] = json.dumps({
            "schemaVersion": "manual-bb/e2e-export/v1", "caseId": case_id,
            "sourceFeatureSha256": _digest(feature), "sourceCaseSetSha256": _digest(cases),
            "filesSha256": files,
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        prepared.append((case_id, artifacts))
    destination = Path(output)
    _require(not destination.exists(), "output directory already exists")
    destination.mkdir(parents=True, exist_ok=False)
    for case_id, artifacts in prepared:
        folder = destination / case_id
        folder.mkdir()
        for name, data in artifacts.items():
            (folder / name).write_bytes(data.encode("utf-8"))
    return [case_id for case_id, _ in prepared]
