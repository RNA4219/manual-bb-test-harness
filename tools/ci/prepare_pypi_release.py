"""既存GitHub Releaseの2配布物を検証し、PyPI公開用ディレクトリへコピーする。"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import tarfile
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

from package_smoke import smoke_artifact, verify_classifiers, verify_license_documents


def verify_bundle(directory: Path, tag: str) -> list[Path]:
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag):
        raise ValueError("正式版タグvX.Y.Zが必要です")
    version = tag[1:]
    names = [f"bb_harness-{version}-py3-none-any.whl", f"bb_harness-{version}.tar.gz"]
    checksums = {}
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match[2] in checksums:
            raise ValueError("SHA256SUMS.txtの形式不正または重複")
        checksums[match[2]] = match[1]
    if set(checksums) != set(names):
        raise ValueError("checksum一覧が対象wheel・sdistと一致しません")

    artifacts = [directory / name for name in names]
    for artifact in artifacts:
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError(f"配布物が通常ファイルではありません: {artifact.name}")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != checksums[artifact.name]:
            raise ValueError(f"SHA-256不一致: {artifact.name}")
        if artifact.suffix == ".whl":
            member = f"bb_harness-{version}.dist-info/METADATA"
            with zipfile.ZipFile(artifact) as archive:
                if archive.namelist().count(member) != 1:
                    raise ValueError("wheelのMETADATAが欠落または重複")
                metadata = archive.read(member)
        else:
            member = f"bb_harness-{version}/PKG-INFO"
            with tarfile.open(artifact, "r:gz") as archive:
                if archive.getnames().count(member) != 1 or not archive.getmember(member).isfile():
                    raise ValueError("sdistのPKG-INFOが欠落・重複・通常ファイル以外")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("sdistのPKG-INFOを読めません")
                with stream:
                    metadata = stream.read()
        headers = BytesParser().parsebytes(metadata, headersonly=True)
        if headers.get_all("Name") != ["bb-harness"] or headers.get_all("Version") != [version]:
            raise ValueError(f"パッケージ名または版の不一致: {artifact.name}")
        verify_classifiers(headers.get_all("Classifier", []))
        verify_license_documents(artifact)
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("出力先は新規ディレクトリにしてください")
    artifacts = verify_bundle(args.input.resolve(), args.tag)
    with tempfile.TemporaryDirectory(prefix="bb-pypi-smoke-") as temporary:
        for artifact in artifacts:
            smoke_artifact(artifact, Path(temporary))
    # smoke中の変更も検出し、全検証成功後にのみ公開対象を生成する。
    verify_bundle(args.input.resolve(), args.tag)
    args.output.mkdir(parents=True)
    for artifact in artifacts:
        shutil.copyfile(artifact, args.output / artifact.name)
        print(f"verified: {artifact.name}")


if __name__ == "__main__":
    main()
