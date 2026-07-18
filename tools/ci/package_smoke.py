"""Build wheel/sdist and smoke-test installed CLI outside the repository."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]
LICENSE_DOCUMENTS = {
    "LICENSE",
    "LICENSE.ja.md",
    "NOTICE",
    "LICENSING.md",
    "COMMERCIAL-LICENSE.md",
    "THIRD_PARTY_NOTICES.md",
}


def verify_release_metadata(repo_root: Path) -> str:
    """Reject unresolved contact placeholders and version drift before building."""
    commercial = (repo_root / "COMMERCIAL-LICENSE.md").read_text(encoding="utf-8")
    if "[COMMERCIAL_CONTACT]" in commercial:
        raise RuntimeError("COMMERCIAL-LICENSE.md still contains [COMMERCIAL_CONTACT]")
    if "https://licensing.rna4219.com/" not in commercial:
        raise RuntimeError("COMMERCIAL-LICENSE.md is missing the official application portal")

    sources = {
        "pyproject.toml": (
            (repo_root / "pyproject.toml").read_text(encoding="utf-8"),
            r'^version\s*=\s*"([^"]+)"$',
        ),
        "README.md": (
            (repo_root / "README.md").read_text(encoding="utf-8"),
            r"現行リリース系列:\s*\*\*([^*]+)\*\*",
        ),
        "src/bb_harness/__init__.py": (
            (repo_root / "src" / "bb_harness" / "__init__.py").read_text(encoding="utf-8"),
            r'^__version__\s*=\s*"([^"]+)"$',
        ),
    }
    versions: dict[str, str] = {}
    for label, (content, pattern) in sources.items():
        match = re.search(pattern, content, re.MULTILINE)
        if match is None:
            raise RuntimeError(f"{label} is missing its release version")
        versions[label] = match.group(1)
    expected = versions["pyproject.toml"]
    mismatches = {label: value for label, value in versions.items() if value != expected}
    if mismatches:
        raise RuntimeError(f"release version mismatch: expected {expected}, got {mismatches}")
    return expected


def verify_license_documents(artifact: Path) -> None:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            names = archive.namelist()
    else:
        with tarfile.open(artifact, "r:gz") as archive:
            names = archive.getnames()
    basenames = {PurePosixPath(name).name for name in names}
    missing = sorted(LICENSE_DOCUMENTS - basenames)
    if missing:
        raise RuntimeError(f"{artifact.name} is missing license documents: {missing}")


def run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        joined = " ".join(command)
        raise RuntimeError(
            f"Command failed ({result.returncode}): {joined}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def cli_path(venv: Path) -> Path:
    return venv / ("Scripts/bb-harness.exe" if os.name == "nt" else "bin/bb-harness")


def python_path(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def smoke_artifact(artifact: Path, root: Path) -> None:
    suffix = "wheel" if artifact.suffix == ".whl" else "sdist"
    venv = root / f"venv-{suffix}"
    work = root / f"work-{suffix}"
    work.mkdir()
    run(["uv", "venv", str(venv), "--python", sys.executable], root)
    run(["uv", "pip", "install", "--python", str(python_path(venv)), str(artifact)], root)
    cli = str(cli_path(venv))
    examples = REPO_ROOT / "examples" / "artifacts"
    commands = [
        [cli, "--help"],
        [cli, "--version"],
        [cli, "validate", str(REPO_ROOT / "skills" / "manual-bb-test-harness")],
        [
            cli,
            "ingest",
            "--source",
            "markdown",
            "--input",
            str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
            "--output",
            str(work / "feature.json"),
        ],
        [cli, "gate", "--input", str(examples), "--output", str(work / "gate.json")],
        [
            cli,
            "export",
            "notion",
            "--score",
            "90",
            "--status",
            "pass",
            "--db",
            "dummy",
            "--dry-run",
        ],
        [
            cli,
            "import",
            "testrail",
            "--project",
            "12",
            "--run",
            "34",
            "--output",
            str(work / "import"),
            "--feature-id",
            "SMOKE",
            "--dry-run",
        ],
        [
            cli,
            "run",
            "forward-test",
            "--skill",
            str(REPO_ROOT / "skills" / "manual-bb-test-harness"),
            "--input",
            str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
        ],
        [
            cli,
            "state-diagram",
            "--input",
            str(examples / "order-cancel.test_model.json"),
            "--output",
            str(work / "state.mmd"),
        ],
        [
            cli,
            "heatmap",
            "--input",
            str(examples / "order-cancel.risk_register.json"),
            "--output",
            str(work / "heatmap.html"),
        ],
    ]
    commands.extend(
        [
            [
                cli,
                "export",
                "testrail",
                "--input",
                str(examples / "order-cancel.manual_case_set.json"),
                "--format",
                "json",
                "--output",
                str(work / "testrail.json"),
            ],
            [
                cli,
                "export",
                "xray",
                "--input",
                str(examples / "order-cancel.manual_case_set.json"),
                "--output",
                str(work / "xray.json"),
            ],
            [
                cli,
                "import",
                "xray",
                "--exec",
                "SMOKE-1",
                "--output",
                str(work / "xray-import"),
                "--feature-id",
                "SMOKE",
                "--dry-run",
            ],
            [
                cli,
                "regression-graph",
                "--input",
                str(examples),
                "--format",
                "json",
                "--output",
                str(work / "regression.json"),
            ],
        ]
    )
    for command in commands:
        run(command, work)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="Keep temporary output")
    args = parser.parse_args()
    verify_release_metadata(REPO_ROOT)
    if args.keep:
        root = Path(tempfile.mkdtemp(prefix="bb-harness-package-smoke-"))
        cleanup = None
    else:
        cleanup = tempfile.TemporaryDirectory(prefix="bb-harness-package-smoke-")
        root = Path(cleanup.name)
    try:
        dist = root / "dist"
        run(["uv", "build", "--wheel", "--sdist", "--out-dir", str(dist)], REPO_ROOT)
        artifacts = [next(dist.glob("*.whl")), next(dist.glob("*.tar.gz"))]
        for artifact in artifacts:
            verify_license_documents(artifact)
            smoke_artifact(artifact, root)
        names = ", ".join(item.name for item in artifacts)
        print(f"Package smoke passed: {names}")
        return 0
    finally:
        if cleanup is not None:
            cleanup.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
