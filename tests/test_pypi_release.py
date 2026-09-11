"""公開前に改変・誤った版・不完全な配布物を拒否する。"""

import hashlib
import importlib.util
import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

CI_DIR = Path(__file__).resolve().parents[1] / "tools" / "ci"
sys.path.insert(0, str(CI_DIR))
spec = importlib.util.spec_from_file_location("prepare_pypi_release", CI_DIR / "prepare_pypi_release.py")
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
sys.path.pop(0)


def checksums(directory):
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(directory.iterdir()) if path.name != "SHA256SUMS.txt"
    ]
    (directory / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def bundle(directory, version="4.0.0", omit_license=False):
    metadata = f"Name: bb-harness\nVersion: {version}\n".encode()
    licenses = release.verify_license_documents.__globals__["LICENSE_DOCUMENTS"]
    docs = {} if omit_license else dict.fromkeys(licenses, b"license")
    with zipfile.ZipFile(directory / "bb_harness-4.0.0-py3-none-any.whl", "w") as archive:
        for name, content in {"bb_harness-4.0.0.dist-info/METADATA": metadata, **docs}.items():
            archive.writestr(name, content)
    with tarfile.open(directory / "bb_harness-4.0.0.tar.gz", "w:gz") as archive:
        for name, content in {"PKG-INFO": metadata, **docs}.items():
            member = tarfile.TarInfo(f"bb_harness-4.0.0/{name}")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    checksums(directory)


def test_valid_bundle(tmp_path):
    bundle(tmp_path)
    assert len(release.verify_bundle(tmp_path, "v4.0.0")) == 2


@pytest.mark.parametrize("tag", ["4.0.0", "v4.0.0rc1", "v04.0.0", "../v4.0.0"])
def test_invalid_tag(tmp_path, tag):
    with pytest.raises(ValueError, match="タグ"):
        release.verify_bundle(tmp_path, tag)


@pytest.mark.parametrize("kind", ["tampered", "missing", "version", "license", "duplicate", "extra"])
def test_reject_incomplete_or_changed_bundle(tmp_path, kind):
    bundle(tmp_path, version="3.0.0" if kind == "version" else "4.0.0", omit_license=kind == "license")
    wheel = tmp_path / "bb_harness-4.0.0-py3-none-any.whl"
    sums = tmp_path / "SHA256SUMS.txt"
    if kind == "tampered":
        wheel.write_bytes(wheel.read_bytes() + b"changed")
    elif kind == "missing":
        wheel.unlink()
    elif kind == "duplicate":
        sums.write_text(sums.read_text() * 2)
    elif kind == "extra":
        sums.write_text(sums.read_text() + "0" * 64 + "  other.whl\n")
    with pytest.raises((ValueError, RuntimeError)):
        release.verify_bundle(tmp_path, "v4.0.0")
