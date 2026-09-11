"""PyPI公開後に配布物と隔離インストールを検証する。公開・削除は行わない。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ATTEMPTS = 6
DELAY = 10


class PublicationPending(RuntimeError):
    """PyPIへの配布情報の反映待ち。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_url(url: str, host: str) -> None:
    parsed = urlsplit(url)
    require(
        parsed.scheme == "https" and parsed.netloc == host,
        "配布物の取得元URLが許可されたHTTPSホストと一致しません",
    )


def fetch(url: str, *, maximum: int, host: str) -> bytes:
    validate_url(url, host)
    with urllib.request.urlopen(url, timeout=30) as response:
        validate_url(response.geturl(), host)
        data = response.read(maximum + 1)
    require(len(data) <= maximum, "応答サイズが上限を超えています")
    return data


def expected_files(directory: Path, tag: str) -> tuple[str, dict]:
    require(
        bool(re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag)),
        "正式版タグvX.Y.Zが必要です",
    )
    version = tag[1:]
    names = {f"bb_harness-{version}-py3-none-any.whl", f"bb_harness-{version}.tar.gz"}
    require(
        {path.name for path in directory.iterdir()} == names,
        "検証済みwheel・sdistの2ファイルだけを指定してください",
    )
    expected = {}
    for name in sorted(names):
        path = directory / name
        require(path.is_file() and not path.is_symlink(), "配布物は通常ファイルが必要です")
        data = path.read_bytes()
        expected[name] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return version, expected


def check_metadata(metadata: dict, version: str, expected: dict) -> list[dict]:
    info, files = metadata["info"], metadata["urls"]
    require(
        info["name"] == "bb-harness" and info["version"] == version,
        "PyPIのパッケージ名または版が一致しません",
    )
    names = [item["filename"] for item in files]
    require(len(names) == len(set(names)), "PyPI配布物の名前が重複しています")
    require(set(names) <= set(expected), "PyPIに余分な配布物があります")
    # 不足と同時に改変があっても、改変を伝搬待ちへ読み替えない。
    for item in files:
        reference = expected[item["filename"]]
        require(item["yanked"] is False, "PyPI配布物がyankedです")
        require(
            type(item["size"]) is int and item["size"] == reference["size"],
            "PyPI配布物のサイズが一致しません",
        )
        require(
            item["digests"]["sha256"] == reference["sha256"], "PyPI配布物のSHA-256が一致しません"
        )
        validate_url(item["url"], "files.pythonhosted.org")
    if set(names) != set(expected):
        raise PublicationPending("PyPIの配布物がまだ揃っていません")
    return files


def download_publication(version: str, expected: dict, output: Path) -> list[dict]:
    for attempt in range(ATTEMPTS):
        try:
            metadata = json.loads(
                fetch(
                    f"https://pypi.org/pypi/bb-harness/{version}/json",
                    maximum=2_000_000,
                    host="pypi.org",
                )
            )
            files = check_metadata(metadata, version, expected)
            downloaded = []
            for item in files:
                reference = expected[item["filename"]]
                data = fetch(item["url"], maximum=reference["size"], host="files.pythonhosted.org")
                require(
                    len(data) == reference["size"]
                    and hashlib.sha256(data).hexdigest() == reference["sha256"],
                    "実ダウンロードのサイズまたはSHA-256が一致しません",
                )
                downloaded.append((item, data))
            for item, data in downloaded:
                with (output / item["filename"]).open("xb") as stream:
                    stream.write(data)
            return [
                {"filename": item["filename"], "url": item["url"], **expected[item["filename"]]}
                for item in files
            ]
        except urllib.error.HTTPError as exc:
            if exc.code not in {404, 429} and not 500 <= exc.code <= 599:
                raise
            error = exc
        except (PublicationPending, urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            error = exc
        if attempt == ATTEMPTS - 1:
            raise RuntimeError("公開後の反映確認が再試行上限に達しました") from error
        time.sleep(DELAY)
    raise AssertionError("unreachable")  # pragma: no cover


def check_install_report(report: dict, version: str, expected: dict) -> None:
    matches = [
        item
        for item in report["install"]
        if re.sub(r"[-_.]+", "-", item["metadata"]["name"]).lower() == "bb-harness"
    ]
    require(len(matches) == 1, "pip reportに対象パッケージが一意に存在しません")
    item = matches[0]
    require(item["metadata"]["version"] == version, "pip reportの版が一致しません")
    info = item["download_info"]
    validate_url(info["url"], "files.pythonhosted.org")
    digest = expected[f"bb_harness-{version}-py3-none-any.whl"]["sha256"]
    require(
        info["archive_info"]["hashes"]["sha256"] == digest,
        "インストールされたwheelのSHA-256が一致しません",
    )


def install_and_smoke(version: str, expected: dict, output: Path) -> None:
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(key, None)
    # --isolatedでもpipのマシン共通設定は読み込まれるため、明示的に無効化する。
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PYTHONUTF8"] = "1"
    venv = output / "venv"
    subprocess.run([sys.executable, "-I", "-m", "venv", str(venv)], check=True, env=environment)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    report = output / "pip-install-report.json"
    subprocess.run(
        [
            str(python),
            "-I",
            "-m",
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "install",
            "--no-cache-dir",
            "--only-binary=:all:",
            "--index-url",
            "https://pypi.org/simple",
            "--report",
            str(report),
            f"bb-harness=={version}",
        ],
        cwd=output,
        check=True,
        env=environment,
    )
    check_install_report(json.loads(report.read_text(encoding="utf-8")), version, expected)
    cli = venv / ("Scripts/bb-harness.exe" if os.name == "nt" else "bin/bb-harness")
    fixture = output / "requirements.md"
    fixture.write_text(
        "# 公開確認\n\n## Acceptance Criteria\n- AC-1: 保存できる。\n", encoding="utf-8"
    )
    for args in (
        ["--version"],
        ["--help"],
        [
            "evaluate",
            "requirements",
            "--input",
            str(fixture),
            "--output",
            str(output / "requirements"),
        ],
    ):
        result = subprocess.run(
            [str(cli), *args],
            cwd=output,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if args == ["--version"]:
            require(result.stdout.strip() == f"bb-harness {version}", "実CLI版が一致しません")
    subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import importlib.metadata,sys; "
            "assert importlib.metadata.version('bb-harness') == sys.argv[1]",
            version,
        ],
        cwd=output,
        env=environment,
        check=True,
    )
    result = json.loads(
        (output / "requirements/requirements_confidence.json").read_text(encoding="utf-8")
    )
    require(result["counts"]["requirements"] == 1, "公開CLIの要件評価結果が一致しません")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--expected", type=Path, required=True, help="prepareが検証したwheelとsdistのディレクトリ"
    )
    parser.add_argument("--output", type=Path, required=True, help="新規の検証結果ディレクトリ")
    args = parser.parse_args(argv)
    version, expected = expected_files(args.expected.resolve(), args.tag)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {"version": version, "status": "failed", "expected": expected}
    try:
        downloads = output / "downloads"
        downloads.mkdir()
        record["published_files"] = download_publication(version, expected, downloads)
        install_and_smoke(version, expected, output)
        record.update(status="passed", isolated_install="passed")
    except Exception as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)[:1000]
        raise
    finally:
        record["verified_at"] = datetime.now(timezone.utc).isoformat()
        (output / "verification.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"PyPI {version}: 配布物照合・隔離インストール・CLI検証に成功")


if __name__ == "__main__":
    main()
