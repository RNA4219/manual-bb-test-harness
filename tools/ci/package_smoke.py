"""Build wheel/sdist and smoke-test installed CLI outside the repository."""

from __future__ import annotations

import argparse
import os
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
