"""Comprehensive tests for scripts/risk-heatmap.py.

Tests all major branches and functions:
- load_risk_register (JSON loading and error handling)
- generate_svg_heatmap (SVG output generation)
- generate_html_heatmap (HTML output with table)
- main (CLI execution with various inputs)

# TRACE: scripts/risk-heatmap.py (role: operations)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def load_risk_heatmap_module() -> object:
    """Load risk-heatmap.py module dynamically."""
    spec = importlib.util.spec_from_file_location(
        "risk_heatmap", REPO_ROOT / "scripts" / "risk-heatmap.py"
    )
    if spec is None or spec.loader is None:
        pytest.skip("Cannot load risk-heatmap.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["risk_heatmap"] = module
    spec.loader.exec_module(module)
    return module


class TestLoadRiskRegister:
    """Tests for load_risk_register function.

    # TRACE: scripts/risk-heatmap.py:46-54 (role: file_loading)
    """

    def test_load_valid_risk_register(self, tmp_path: Path) -> None:
        """Load valid risk register JSON."""
        module = load_risk_heatmap_module()

        risk_file = tmp_path / "risk.json"
        risk_file.write_text(
            json.dumps(
                {
                    "feature_id": "TEST-001",
                    "risks": [
                        {"id": "R1", "scenario": "Risk 1", "impact": 3, "likelihood": 2, "priority": "P2"}
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = module.load_risk_register(risk_file)
        assert result["feature_id"] == "TEST-001"
        assert len(result["risks"]) == 1

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Invalid JSON raises ValueError."""
        module = load_risk_heatmap_module()

        risk_file = tmp_path / "invalid.json"
        risk_file.write_text("{invalid json}", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid JSON"):
            module.load_risk_register(risk_file)

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Missing file raises ValueError."""
        module = load_risk_heatmap_module()

        missing_file = tmp_path / "missing.json"

        with pytest.raises(ValueError, match="Cannot read"):
            module.load_risk_register(missing_file)


class TestGenerateSvgHeatmap:
    """Tests for generate_svg_heatmap function.

    # TRACE: scripts/risk-heatmap.py:57-160 (role: svg_generation)
    """

    def test_generate_svg_basic(self, tmp_path: Path) -> None:
        """Generate basic SVG heatmap."""
        module = load_risk_heatmap_module()

        risks = [
            {"id": "R1", "scenario": "Risk 1", "impact": 3, "likelihood": 2, "priority": "P2"},
            {"id": "R2", "scenario": "Risk 2", "impact": 5, "likelihood": 5, "priority": "P0"},
        ]

        svg = module.generate_svg_heatmap(risks)
        assert "<?xml" in svg
        assert "<svg" in svg
        assert "Risk Heatmap" in svg

    def test_generate_svg_with_p0_p3(self, tmp_path: Path) -> None:
        """Generate SVG with all priority levels."""
        module = load_risk_heatmap_module()

        risks = [
            {"id": "R0", "impact": 5, "likelihood": 5, "priority": "P0"},
            {"id": "R1", "impact": 4, "likelihood": 4, "priority": "P1"},
            {"id": "R2", "impact": 3, "likelihood": 3, "priority": "P2"},
            {"id": "R3", "impact": 1, "likelihood": 1, "priority": "P3"},
        ]

        svg = module.generate_svg_heatmap(risks)
        assert "#ff4444" in svg  # P0 color
        assert "#ff8844" in svg  # P1 color
        assert "#ffcc44" in svg  # P2 color
        assert "#44ff44" in svg  # P3 color

    def test_generate_svg_empty_risks(self, tmp_path: Path) -> None:
        """Generate SVG with no risks."""
        module = load_risk_heatmap_module()

        svg = module.generate_svg_heatmap([])
        assert "<?xml" in svg
        assert "<svg" in svg

    def test_generate_svg_clamped_values(self, tmp_path: Path) -> None:
        """SVG clamps impact/likelihood to valid range."""
        module = load_risk_heatmap_module()

        risks = [
            {"id": "R1", "impact": 10, "likelihood": 10, "priority": "P0"},  # Out of range
            {"id": "R2", "impact": 0, "likelihood": 0, "priority": "P3"},  # Below range
        ]

        svg = module.generate_svg_heatmap(risks)
        # Should still generate valid SVG
        assert "<svg" in svg

    def test_generate_svg_with_custom_size(self, tmp_path: Path) -> None:
        """Generate SVG with custom dimensions."""
        module = load_risk_heatmap_module()

        risks = [{"id": "R1", "impact": 3, "likelihood": 3, "priority": "P2"}]

        svg = module.generate_svg_heatmap(risks, width=800, height=600)
        assert "width=\"800\"" in svg
        assert "height=\"600\"" in svg


class TestGenerateHtmlHeatmap:
    """Tests for generate_html_heatmap function.

    # TRACE: scripts/risk-heatmap.py:163-252 (role: html_generation)
    """

    def test_generate_html_basic(self, tmp_path: Path) -> None:
        """Generate basic HTML heatmap."""
        module = load_risk_heatmap_module()

        risks = [
            {"id": "R1", "scenario": "Risk 1", "impact": 3, "likelihood": 2, "priority": "P2", "score": 6, "rationale": "Test"},
        ]

        html = module.generate_html_heatmap(risks)
        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "<table" in html

    def test_generate_html_with_title(self, tmp_path: Path) -> None:
        """Generate HTML with custom title."""
        module = load_risk_heatmap_module()

        risks = []
        html = module.generate_html_heatmap(risks, title="Custom Title")
        assert "<title>Custom Title</title>" in html
        assert "<h1>Custom Title</h1>" in html

    def test_generate_html_priority_distribution(self, tmp_path: Path) -> None:
        """HTML includes priority distribution."""
        module = load_risk_heatmap_module()

        risks = [
            {"id": "R1", "priority": "P0"},
            {"id": "R2", "priority": "P0"},
            {"id": "R3", "priority": "P2"},
        ]

        html = module.generate_html_heatmap(risks)
        assert "<strong>P0</strong>: 2 risks" in html
        assert "<strong>P2</strong>: 1 risks" in html

    def test_generate_html_table_rows(self, tmp_path: Path) -> None:
        """HTML table includes risk details."""
        module = load_risk_heatmap_module()

        risks = [
            {
                "id": "RISK-001",
                "scenario": "Data loss",
                "impact": 5,
                "likelihood": 4,
                "score": 20,
                "priority": "P0",
                "rationale": "Critical",
            },
        ]

        html = module.generate_html_heatmap(risks)
        assert "RISK-001" in html
        assert "Data loss" in html
        assert "class=\"p0\"" in html


class TestRiskHeatmapMain:
    """Tests for main function (CLI execution).

    # TRACE: scripts/risk-heatmap.py:255-321 (role: cli_entry)
    """

    def test_main_version(self, tmp_path: Path) -> None:
        """Version flag works."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "risk-heatmap.py"), "--version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "risk-heatmap" in result.stdout

    def test_main_generate_html(self, tmp_path: Path) -> None:
        """Generate HTML output."""
        import subprocess

        risk_file = tmp_path / "risk.json"
        risk_file.write_text(
            json.dumps(
                {
                    "feature_id": "TEST-001",
                    "risks": [
                        {"id": "R1", "scenario": "Risk", "impact": 3, "likelihood": 2, "priority": "P2"}
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        output_file = tmp_path / "heatmap.html"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "risk-heatmap.py"),
                "--input",
                str(risk_file),
                "--output",
                str(output_file),
                "--format",
                "html",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_main_generate_svg(self, tmp_path: Path) -> None:
        """Generate SVG output."""
        import subprocess

        risk_file = tmp_path / "risk.json"
        risk_file.write_text(
            json.dumps(
                {
                    "feature_id": "TEST-002",
                    "risks": [
                        {"id": "R1", "scenario": "Risk", "impact": 3, "likelihood": 2, "priority": "P2"}
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        output_file = tmp_path / "heatmap.svg"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "risk-heatmap.py"),
                "--input",
                str(risk_file),
                "--output",
                str(output_file),
                "--format",
                "svg",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "<?xml" in content

    def test_main_empty_risks_warning(self, tmp_path: Path) -> None:
        """Empty risk register prints warning."""
        import subprocess

        risk_file = tmp_path / "empty.json"
        risk_file.write_text(
            json.dumps({"feature_id": "EMPTY", "risks": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "heatmap.html"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "risk-heatmap.py"),
                "--input",
                str(risk_file),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "Warning" in result.stderr

    def test_main_missing_input(self, tmp_path: Path) -> None:
        """Missing input file returns error."""
        import subprocess

        output_file = tmp_path / "heatmap.html"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "risk-heatmap.py"),
                "--input",
                str(tmp_path / "missing.json"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_main_invalid_json(self, tmp_path: Path) -> None:
        """Invalid JSON returns error."""
        import subprocess

        risk_file = tmp_path / "invalid.json"
        risk_file.write_text("{invalid}", encoding="utf-8")

        output_file = tmp_path / "heatmap.html"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "risk-heatmap.py"),
                "--input",
                str(risk_file),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 1

    def test_main_custom_title(self, tmp_path: Path) -> None:
        """Custom title in output."""
        import subprocess

        risk_file = tmp_path / "risk.json"
        risk_file.write_text(
            json.dumps({"feature_id": "TEST", "risks": []}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "heatmap.html"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "risk-heatmap.py"),
                "--input",
                str(risk_file),
                "--output",
                str(output_file),
                "--title",
                "My Custom Title",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        content = output_file.read_text(encoding="utf-8")
        assert "My Custom Title" in content


class TestPriorityColors:
    """Tests for PRIORITY_COLORS constant.

    # TRACE: scripts/risk-heatmap.py:28-34 (role: constants)
    """

    def test_priority_colors_defined(self) -> None:
        """Priority colors are defined."""
        module = load_risk_heatmap_module()
        colors = module.PRIORITY_COLORS

        assert "P0" in colors
        assert "P1" in colors
        assert "P2" in colors
        assert "P3" in colors


class TestHeatColors:
    """Tests for HEAT_COLORS matrix.

    # TRACE: scripts/risk-heatmap.py:36-43 (role: constants)
    """

    def test_heat_colors_matrix(self) -> None:
        """Heat colors matrix is 5x5."""
        module = load_risk_heatmap_module()
        heat_colors = module.HEAT_COLORS

        assert len(heat_colors) == 5
        for row in heat_colors:
            assert len(row) == 5
