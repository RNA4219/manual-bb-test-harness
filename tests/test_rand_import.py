"""RanD取り込みの境界・原文保存・回帰範囲・CLI副作用を検証する。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from bb_harness import rand_import
from bb_harness.cli import main
from bb_harness.rand_contracts import MAX_INPUT_BYTES, content_hash
from bb_harness.rand_import import build_intake, publish, render_prompt
from bb_harness.schema_validation import validate_artifact
from bb_harness.tools.validate_artifact import validate_artifact as validate_file

ROOT = Path(__file__).resolve().parents[1]


def envelope(kind, **fields):
    return {
        "schema_version": "2.0",
        "id": "rand:example",
        "type": kind,
        "producer": {"name": "RanD", "version": "0.3.0"},
        "created_at": "2026-09-12T00:00:00Z",
        "input_refs": [],
        "source_refs": [],
        "status": "ok",
        "assumptions": [],
        "limitations": [],
        "review_required": True,
        "downstream_allowed_uses": ["review", "test_design"],
        **fields,
    }


def document(entries=None):
    entries = (
        entries if entries is not None else [("REQ-1", "結果を保存する", ["JSONが生成される"])]
    )
    rows = []
    path = "/spec/requirements.md"
    for index, (rid, statement, criteria) in enumerate(entries, 1):
        row = {
            "requirement_id": "rand:req:sample:" + rid,
            "external_id": rid,
            "identity_basis": "explicit",
            "statement": statement,
            "acceptance_criteria": criteria,
            "section_path": ["要求"],
            "source": {
                "path": path,
                "uri": f"file://{path}#L{index}-L{index}",
                "line_start": index,
                "line_end": index,
                "excerpt": f"- {rid}: {statement}",
            },
        }
        row["content_hash"] = content_hash(row)
        rows.append(row)
    raw = "\n".join(row["source"]["excerpt"] for row in rows)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return envelope(
        "requirements_document",
        document_id="rand:document:sample",
        parser_version="1",
        id="rand:document-snapshot:sample:" + digest[:20],
        source={"path": path, "uri": f"file://{path}", "sha256": digest, "line_count": len(rows)},
        requirements=rows,
        extraction_diagnostics=[],
    )


def packet(kind="requirements_packet"):
    item = {
        "requirement_id": "rand:REQ-1",
        "statement": "結果を保存する",
        "acceptance_criteria": ["JSONが生成される"],
        "confidence": 0.9,
        "bias_note": "肯定的な反応への偏り",
        "kill_condition": "利用されない",
        "gate_verdict": "go",
        "evidence_refs": ["EV-1"],
        "risks": ["保存失敗"],
    }
    if kind == "requirements_audit_packet":
        item["original_text"] = item.pop("statement")
    return envelope(
        kind, packet_id="rand:packet-demo", document_id="rand:document:sample", requirements=[item]
    )


def save(tmp_path, data, name="input.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def delta_pair():
    before = document(
        [
            ("REQ-1", "保存する", ["結果が生成される"]),
            ("REQ-2", "表示する", ["結果が表示される"]),
            ("REQ-3", "履歴を保存する", ["履歴が生成される"]),
        ]
    )
    current = document(
        [
            ("REQ-1", "即時に保存する", ["結果が保存される"]),
            ("REQ-2", "表示する", ["結果が表示される"]),
            ("REQ-4", "通知する", ["通知が表示される"]),
        ]
    )
    previous = {r["external_id"]: r for r in before["requirements"]}
    present = {r["external_id"]: r for r in current["requirements"]}
    candidates = []
    for row, action in [
        (present["REQ-1"], "review_new_or_changed"),
        (present["REQ-4"], "review_new_or_changed"),
        (previous["REQ-3"], "review_retirement"),
    ]:
        candidates.append(
            {
                "test_id": row["requirement_id"] + ":test:draft",
                "requirement_id": row["requirement_id"],
                "status": "draft",
                "action": action,
                "focus": ["原文を確認する"],
                "acceptance_criteria": row["acceptance_criteria"],
                "source_refs": [row["source"]["uri"]],
                "review_required": True,
            }
        )
    delta = envelope(
        "requirements_diff",
        id="rand:diff:sample",
        document_id=current["document_id"],
        parser_version="1",
        current_ref=current["id"],
        baseline_ref=before["id"],
        current_source_sha256=current["source"]["sha256"],
        baseline_source_sha256=before["source"]["sha256"],
        added=[present["REQ-4"]],
        removed=[previous["REQ-3"]],
        modified=[
            {
                "requirement_id": present["REQ-1"]["requirement_id"],
                "before": previous["REQ-1"],
                "after": present["REQ-1"],
                "changed_fields": ["statement", "acceptance_criteria"],
            }
        ],
        unchanged=[present["REQ-2"]["requirement_id"]],
        summary={"added": 1, "removed": 1, "modified": 1, "unchanged": 1},
        test_candidates=candidates,
    )
    return current, deepcopy(delta)


@pytest.mark.parametrize(
    "kind",
    [
        "requirements_packet",
        "requirements_audit_packet",
        "requirements_document",
        "discovery_handoff",
        "audit_handoff",
    ],
)
def test_supported_input_preserves_source_and_raw_payload(tmp_path, kind):
    if kind == "requirements_document":
        data = document()
    elif kind.endswith("handoff"):
        section_type = (
            "manual_test_model_seed"
            if kind == "discovery_handoff"
            else "requirements_audit_testability"
        )
        data = envelope(
            "downstream_handoff",
            manual_bb_test_harness={
                "artifact_type": section_type,
                "requirements": packet()["requirements"],
            },
        )
    else:
        data = packet(kind)
    path = save(tmp_path, data)
    intake, feature = build_intake(path)
    assert feature is not None
    assert intake["inputs"][0]["payload"] == data
    assert intake["inputs"][0]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    row = intake["requirements"][0]
    assert row["statement"] == "結果を保存する"
    assert row["acceptance_criteria"] == ["JSONが生成される"]
    if kind == "requirements_document":
        assert row["source_refs"][0]["url"] == data["requirements"][0]["source"]["uri"]
        assert row["source_refs"][0]["excerpt"] == data["requirements"][0]["source"]["excerpt"]
    assert feature["acceptance_criteria"] == row["acceptance_criteria"]
    assert "gate_decision" not in intake
    validate_artifact(intake, "rand_intake.schema.json")
    validate_artifact(feature, "feature_spec.schema.json")
    assert "rand_research" not in sys.modules


def test_research_candidates_never_become_approved_oracles(tmp_path):
    original = packet()
    intake, feature = build_intake(save(tmp_path, original))
    assert intake["requirements"][0]["oracle_status"] == "candidate"
    assert intake["requirements"][0]["upstream"] == original["requirements"][0]
    assert all(ref["kind"] == "memo" for ref in feature["source_refs"])
    assert any(
        a["severity"] == "critical" and a["resolution_status"] == "open"
        for a in feature["assumptions"]
    )
    assert intake["intake_status"] == "degraded"


@pytest.mark.parametrize(
    "entries,expected",
    [
        ([], "blocked"),
        ([("REQ-1", "保存する", [])], "blocked"),
        ([("REQ-1", "保存する", []), ("REQ-2", "表示する", ["表示される"])], "degraded"),
    ],
)
def test_missing_acceptance_is_not_invented(tmp_path, entries, expected):
    intake, feature = build_intake(save(tmp_path, document(entries)))
    assert intake["intake_status"] == expected
    if expected == "blocked":
        assert feature is None
    else:
        assert feature["acceptance_criteria"] == ["表示される"]
        assert any(a["severity"] == "critical" for a in feature["assumptions"])
    output = tmp_path / "output"
    publish(output, intake, feature, render_prompt(intake, feature))
    assert (output / "feature_spec.json").exists() == (feature is not None)
    assert not (output / "gate_decision.json").exists()


def test_stable_feature_and_ac_identity_across_reorder(tmp_path):
    data = document(
        [("REQ-1", "保存する", ["保存される", "表示される"]), ("REQ-2", "表示する", ["表示される"])]
    )
    first, _ = build_intake(save(tmp_path, data))
    data["requirements"].reverse()
    data["requirements"][1]["acceptance_criteria"].reverse()
    second, _ = build_intake(save(tmp_path, data, "reordered.json"))
    assert first["feature_id"] == second["feature_id"]
    assert first["revision"] != second["revision"]
    assert {r["id"] for r in first["source_refs"]} == {r["id"] for r in second["source_refs"]}


def test_delta_retains_whole_surface_and_retirement(tmp_path):
    current, delta = delta_pair()
    intake, feature = build_intake(
        save(tmp_path, current), diff_path=save(tmp_path, delta, "diff.json")
    )
    assert len(intake["requirements"]) == 3
    assert intake["focus_requirement_ids"] == ["rand:req:sample:REQ-1", "rand:req:sample:REQ-4"]
    assert intake["regression_requirement_ids"] == ["rand:req:sample:REQ-2"]
    assert intake["retired_requirements"][0]["requirement_id"] == "rand:req:sample:REQ-3"
    assert "履歴が生成される" not in feature["acceptance_criteria"]
    assert intake["inputs"][1]["payload"] == delta
    prompt = render_prompt(intake, feature)
    for term in ["unchanged", "removed", "境界値", "再試行", "実行証跡", "自動retireしない"]:
        assert term in prompt


@pytest.mark.parametrize(
    "fault",
    [
        "version",
        "type",
        "id",
        "duplicate",
        "criteria_type",
        "blank",
        "source_uri",
        "source_lines",
        "content_hash",
        "requirement_id",
        "document_hash_id",
        "parser",
        "not_object",
        "exponent",
    ],
)
def test_invalid_primary_rejected_before_output(tmp_path, capsys, fault):
    data = document()
    row = data["requirements"][0]
    if fault == "version":
        data["schema_version"] = "1.0"
    elif fault == "type":
        data["type"] = "gate"
    elif fault == "id":
        data["id"] = "foreign"
    elif fault == "duplicate":
        data["requirements"].append(deepcopy(row))
    elif fault == "criteria_type":
        row["acceptance_criteria"] = "保存される"
    elif fault == "blank":
        row["statement"] = " "
    elif fault == "source_uri":
        row["source"]["uri"] = "file:///other.md#L1-L1"
    elif fault == "source_lines":
        row["source"]["line_end"] = 4
    elif fault == "content_hash":
        row["content_hash"] = "0" * 64
    elif fault == "requirement_id":
        row["requirement_id"] = "rand:req:sample:REQ-OTHER"
    elif fault == "document_hash_id":
        data["source"]["sha256"] = "a" * 64
    elif fault == "parser":
        data["parser_version"] = "2"
    elif fault == "not_object":
        data = []
    elif fault == "exponent":
        data["unexpected"] = float("inf")
    path = save(tmp_path, data)
    output = tmp_path / "new"
    assert main(["import", "rand", "--input", str(path), "--output", str(output)]) == 1
    assert json.loads(capsys.readouterr().err)["status"] == "failed"
    assert not output.exists()


@pytest.mark.parametrize(
    "raw", [b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}', b'{"x":1e999}', b"\xff", b"{"]
)
def test_invalid_json_rejected(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises((ValueError, UnicodeError)):
        build_intake(path)


def test_bounded_input_and_bom(tmp_path):
    path = save(tmp_path, packet())
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert build_intake(path)[1] is not None
    path.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
    with pytest.raises(ValueError, match="16 MiB"):
        build_intake(path)


@pytest.mark.parametrize(
    "fault",
    [
        "foreign",
        "current_ref",
        "source_hash",
        "baseline_ref",
        "summary",
        "overlap",
        "missing_unchanged",
        "after",
        "before_hash",
        "changed_fields",
        "candidate_missing",
        "candidate_action",
        "candidate_ac",
    ],
)
def test_inconsistent_diff_rejected(tmp_path, fault):
    current, delta = delta_pair()
    if fault == "foreign":
        delta["document_id"] = "rand:document:other"
    elif fault == "current_ref":
        delta["current_ref"] = "rand:other"
    elif fault == "source_hash":
        delta["current_source_sha256"] = "0" * 64
    elif fault == "baseline_ref":
        delta["baseline_ref"] = "rand:other"
    elif fault == "summary":
        delta["summary"]["modified"] = 2
    elif fault == "overlap":
        delta["unchanged"].append(delta["added"][0]["requirement_id"])
    elif fault == "missing_unchanged":
        delta["unchanged"] = []
    elif fault == "after":
        delta["modified"][0]["after"]["source"]["excerpt"] = "別の原文"
    elif fault == "before_hash":
        delta["modified"][0]["before"]["content_hash"] = "0" * 64
    elif fault == "changed_fields":
        delta["modified"][0]["changed_fields"] = ["statement"]
    elif fault == "candidate_missing":
        delta["test_candidates"].pop()
    elif fault == "candidate_action":
        delta["test_candidates"][0]["action"] = "review_retirement"
    elif fault == "candidate_ac":
        delta["test_candidates"][0]["acceptance_criteria"] = ["捏造した期待値"]
    with pytest.raises(ValueError):
        build_intake(save(tmp_path, current), diff_path=save(tmp_path, delta, "diff.json"))


def test_diff_requires_full_normalized_document(tmp_path):
    _, delta = delta_pair()
    with pytest.raises(ValueError, match="requirements_document"):
        build_intake(save(tmp_path, packet()), diff_path=save(tmp_path, delta, "diff.json"))


def defects():
    entries = []
    for i, status in enumerate(["open", "fixed", "resolved"], 1):
        entry = {
            "defect_id": f"BUG-{i}",
            "title": "再試行で結果が欠落する",
            "severity": "high",
            "status": status,
            "updated_at": "2026-09-12T00:00:00Z",
            "source_refs": [{"id": "TC-1", "kind": "bug"}],
        }
        if status == "resolved":
            entry["confirmation_run_ids"] = ["RUN-3"]
        entries.append(entry)
    return {"feature_id": "F-1", "build_id": "build-original", "defects": entries}


def test_defect_feedback_preserves_history_without_closing(tmp_path):
    register = defects()
    path = save(tmp_path, register, "defects.json")
    before = path.read_bytes()
    intake, feature = build_intake(save(tmp_path, packet()), feature_id="F-1", defects_path=path)
    assert intake["follow_up_defect_ids"] == ["BUG-1", "BUG-2"]
    assert intake["inputs"][-1]["payload"] == register
    assert path.read_bytes() == before
    prompt = render_prompt(intake, feature)
    assert "confirmation_run_ids" in prompt and "resolvedも回帰" in prompt
    assert "関連は推測しない" in " ".join(intake["notes"])


@pytest.mark.parametrize("fault", ["feature", "duplicate", "resolved_without_confirmation"])
def test_invalid_feedback_rejected(tmp_path, fault):
    register = defects()
    if fault == "feature":
        register["feature_id"] = "F-OTHER"
    elif fault == "duplicate":
        register["defects"].append(register["defects"][0])
    else:
        register["defects"][-1].pop("confirmation_run_ids")
    with pytest.raises(ValueError):
        build_intake(
            save(tmp_path, packet()),
            feature_id="F-1",
            defects_path=save(tmp_path, register, "defects.json"),
        )


@pytest.mark.parametrize("flag_position", ["global", "local"])
def test_dry_run_writes_nothing(tmp_path, capsys, flag_position):
    path = save(tmp_path, packet())
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    args = ["import", "rand", "--input", str(path), "--output", str(tmp_path / "missing" / "out")]
    args.insert(0 if flag_position == "global" else len(args), "--dry-run")
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["artifacts"] == {} and result["intake"]["requirements"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("kind", ["directory", "file", "input"])
def test_existing_output_unchanged(tmp_path, kind):
    path = save(tmp_path, packet())
    intake, feature = build_intake(path)
    output = path if kind == "input" else tmp_path / "output"
    if kind == "directory":
        output.mkdir()
        (output / "sentinel").write_text("keep")
    elif kind == "file":
        output.write_text("keep")
    with pytest.raises(ValueError, match="上書き"):
        publish(output, intake, feature, "prompt")
    assert path.exists()
    if kind == "directory":
        assert (output / "sentinel").read_text() == "keep"
    elif kind == "file":
        assert output.read_text() == "keep"


@pytest.mark.parametrize("failure", ["write", "rename"])
def test_publish_failure_cleans_owned_stage_and_lock(tmp_path, monkeypatch, failure):
    intake, feature = build_intake(save(tmp_path, packet()))
    output = tmp_path / "out"

    def fail(*args, **kwargs):
        raise OSError("injected")

    if failure == "write":
        monkeypatch.setattr(Path, "write_text", fail)
    else:
        monkeypatch.setattr(rand_import.os, "rename", fail)
    with pytest.raises(OSError, match="injected"):
        publish(output, intake, feature, "prompt")
    assert not output.exists()
    assert not list(tmp_path.glob(".rand-import-*"))
    assert not list(tmp_path.glob("*.lock"))


def test_lock_contention_leaves_other_writer_untouched(tmp_path):
    intake, feature = build_intake(save(tmp_path, packet()))
    lock = tmp_path / ".out.rand-import.lock"
    lock.write_text("another writer")
    with pytest.raises(FileExistsError):
        publish(tmp_path / "out", intake, feature, "prompt")
    assert lock.read_text() == "another writer"


def test_post_publication_cleanup_warning_retains_references(tmp_path, monkeypatch, capsys):
    path = save(tmp_path, packet())
    output = tmp_path / "out"
    unlink = Path.unlink

    def fail_lock(self, *args, **kwargs):
        if self.name.endswith(".rand-import.lock"):
            raise OSError("injected")
        return unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_lock)
    assert main(["import", "rand", "--input", str(path), "--output", str(output)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "degraded"
    assert all(Path(p).is_file() for p in result["artifacts"].values())


def test_native_cli_output_validates_and_input_is_frozen(tmp_path):
    path = save(tmp_path, document())
    original = path.read_bytes()
    output = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "bb_harness.cli",
            "import",
            "rand",
            "--input",
            str(path),
            "--output",
            str(output),
        ],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    for filename in ["rand_intake.json", "feature_spec.json"]:
        assert validate_file(output / filename)["valid"]
    assert path.read_bytes() == original
    intake = json.loads((output / "rand_intake.json").read_text(encoding="utf-8"))
    path.unlink()
    assert intake["requirements"][0]["upstream"]["source"]["excerpt"] == "- REQ-1: 結果を保存する"


@pytest.mark.parametrize(
    "name", ["rand_intake", "rand_requirements_document", "rand_requirements_diff"]
)
def test_package_schema_is_identical(name):
    filename = name + ".schema.json"
    assert (ROOT / "schemas" / filename).read_bytes() == (
        ROOT / "src/bb_harness/schemas" / filename
    ).read_bytes()


def test_upstream_reference_urls_survive_without_document_source(tmp_path):
    data = packet("requirements_audit_packet")
    data["requirements"][0]["source_refs"] = ["https://example.test/spec"]
    data["requirements"][0]["evidence"] = [
        {"source_ref": "fixture://user-reaction", "summary": "再試行時に保存結果が消える"}
    ]
    intake, feature = build_intake(save(tmp_path, data))
    refs = feature["source_refs"]
    assert any(r.get("url") == "https://example.test/spec" for r in refs)
    assert any(
        r.get("url") == "fixture://user-reaction"
        and r.get("excerpt") == "再試行時に保存結果が消える"
        for r in refs
    )
    assert any(r.get("excerpt") == "EV-1" for r in refs)
    assert intake["requirements"][0]["upstream"] == data["requirements"][0]
