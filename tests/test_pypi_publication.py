"""公開後検証の改変拒否、限定retry、証跡保存をネットワークなしで確認する。"""

import copy
import hashlib
import json
import urllib.error

import pytest

from tools.ci import verify_pypi_publication as publication


def sample(tmp_path):
    source = tmp_path / "expected"
    source.mkdir()
    for name in ("bb_harness-4.0.1-py3-none-any.whl", "bb_harness-4.0.1.tar.gz"):
        (source / name).write_bytes(name.encode())
    version, expected = publication.expected_files(source, "v4.0.1")
    metadata = {
        "info": {"name": "bb-harness", "version": version},
        "urls": [
            {
                "filename": name,
                "size": item["size"],
                "digests": {"sha256": item["sha256"]},
                "yanked": False,
                "url": "https://files.pythonhosted.org/" + name,
            }
            for name, item in expected.items()
        ],
    }
    return source, expected, metadata


@pytest.mark.parametrize(
    "damage", ["hash", "size", "version", "name", "extra", "duplicate", "yanked", "host"]
)
def test_reject_mismatched_publication(tmp_path, damage):
    _, expected, metadata = sample(tmp_path)
    item = metadata["urls"][0]
    if damage == "hash":
        item["digests"]["sha256"] = "0" * 64
    elif damage == "size":
        item["size"] += 1
    elif damage in {"version", "name"}:
        metadata["info"][damage] = "wrong"
    elif damage == "extra":
        item["filename"] = "unexpected.whl"
    elif damage == "duplicate":
        metadata["urls"].append(copy.deepcopy(item))
    elif damage == "yanked":
        item["yanked"] = True
    else:
        item["url"] = "http://files.pythonhosted.org/file"
    with pytest.raises(ValueError):
        publication.check_metadata(metadata, "4.0.1", expected)


def test_missing_files_are_pending_but_tampering_still_fails(tmp_path):
    _, expected, metadata = sample(tmp_path)
    metadata["urls"].pop()
    with pytest.raises(publication.PublicationPending):
        publication.check_metadata(metadata, "4.0.1", expected)
    metadata["urls"][0]["digests"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        publication.check_metadata(metadata, "4.0.1", expected)


@pytest.mark.parametrize("status,attempts", [(404, 6), (429, 6), (503, 6), (403, 1)])
def test_publication_retry_is_bounded_and_only_for_transient_errors(
    tmp_path, monkeypatch, status, attempts
):
    _, expected, _ = sample(tmp_path)
    calls, waits = [], []

    def fetch(*args, **kwargs):
        calls.append(args)
        raise urllib.error.HTTPError("https://pypi.org", status, "test", {}, None)

    monkeypatch.setattr(publication, "fetch", fetch)
    monkeypatch.setattr(publication.time, "sleep", waits.append)
    with pytest.raises((RuntimeError, urllib.error.HTTPError)):
        publication.download_publication("4.0.1", expected, tmp_path)
    assert len(calls) == attempts
    assert waits == [10] * (attempts - 1)


@pytest.mark.parametrize("tampered", [False, True])
def test_download_verifies_actual_bytes(tmp_path, monkeypatch, tampered):
    source, expected, metadata = sample(tmp_path)
    output = tmp_path / "downloads"
    output.mkdir()

    def fetch(url, **kwargs):
        if url.endswith("/json"):
            return json.dumps(metadata).encode()
        content = (source / url.rsplit("/", 1)[1]).read_bytes()
        return content + b"changed" if tampered else content

    monkeypatch.setattr(publication, "fetch", fetch)
    if tampered:
        with pytest.raises(ValueError):
            publication.download_publication("4.0.1", expected, output)
        assert list(output.iterdir()) == []
    else:
        result = publication.download_publication("4.0.1", expected, output)
        assert len(result) == 2
        assert all(
            hashlib.sha256((output / name).read_bytes()).hexdigest() == item["sha256"]
            for name, item in expected.items()
        )


@pytest.mark.parametrize("damage", [None, "version", "hash", "host", "duplicate"])
def test_installed_package_must_match_expected_wheel(tmp_path, damage):
    _, expected, _ = sample(tmp_path)
    digest = expected["bb_harness-4.0.1-py3-none-any.whl"]["sha256"]
    item = {
        "metadata": {"name": "bb-harness", "version": "4.0.1"},
        "download_info": {
            "url": "https://files.pythonhosted.org/wheel",
            "archive_info": {"hashes": {"sha256": digest}},
        },
    }
    report = {"install": [item]}
    if damage == "version":
        item["metadata"]["version"] = "4.0.0"
    elif damage == "hash":
        item["download_info"]["archive_info"]["hashes"]["sha256"] = "0" * 64
    elif damage == "host":
        item["download_info"]["url"] = "file:///wheel"
    elif damage == "duplicate":
        report["install"].append(copy.deepcopy(item))
    if damage:
        with pytest.raises(ValueError):
            publication.check_install_report(report, "4.0.1", expected)
    else:
        publication.check_install_report(report, "4.0.1", expected)


def test_failure_evidence_and_existing_output_protection(tmp_path, monkeypatch):
    source, _, _ = sample(tmp_path)
    output = tmp_path / "result"
    monkeypatch.setattr(publication, "download_publication", lambda *args: [])

    def failed_install(*args):
        raise ValueError("install failed")

    monkeypatch.setattr(publication, "install_and_smoke", failed_install)
    args = ["--tag", "v4.0.1", "--expected", str(source), "--output", str(output)]
    with pytest.raises(ValueError, match="install failed"):
        publication.main(args)
    record = output / "verification.json"
    original = record.read_bytes()
    assert json.loads(original)["status"] == "failed"
    with pytest.raises(FileExistsError):
        publication.main(args)
    assert record.read_bytes() == original


@pytest.mark.parametrize("tag", ["4.0.1", "v4.0.1rc1", "v04.0.1", "../v4.0.1"])
def test_publication_input_rejects_non_release_tags(tmp_path, tag):
    with pytest.raises(ValueError):
        publication.expected_files(tmp_path, tag)
