"""Generate risk heatmap visualization from risk_register.json.

Creates interactive HTML/SVG heatmap showing impact x likelihood matrix
with color-coded priority zones.

Usage:
    python scripts/risk-heatmap.py --input <risk_register.json> --output <heatmap.html>
    python scripts/risk-heatmap.py --input <risk_register.json> --format svg --output <heatmap.svg>
    python scripts/risk-heatmap.py --version

Example:
    python scripts/risk-heatmap.py \
        --input examples/artifacts/order-cancel.risk_register.json \
        --output examples/artifacts/risk-heatmap.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

__version__ = "0.1.0"


# Priority color scheme
PRIORITY_COLORS = {
    "P0": "#ff4444",  # Red - Critical
    "P1": "#ff8844",  # Orange - High
    "P2": "#ffcc44",  # Yellow - Medium
    "P3": "#44ff44",  # Green - Low
}

# Heatmap cell colors (impact x likelihood)
HEAT_COLORS = [
    ["#44ff44", "#88ff88", "#ccff88", "#ffff88", "#ffff44"],
    ["#88ff88", "#ccff88", "#ffff88", "#ffff44", "#ffcc44"],
    ["#ccff88", "#ffff88", "#ffff44", "#ffcc44", "#ff8844"],
    ["#ffff88", "#ffff44", "#ffcc44", "#ff8844", "#ff4444"],
    ["#ffff44", "#ffcc44", "#ff8844", "#ff4444", "#ff4444"],
]


def load_risk_register(path: Path) -> dict[str, Any]:
    """Load and parse risk_register.json."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def generate_svg_heatmap(
    risks: list[dict[str, Any]],
    width: int = 600,
    height: int = 500,
) -> str:
    """Generate SVG heatmap visualization."""
    svg_parts: list[str] = []

    # SVG header
    svg_parts.append('<?xml version="1.0" encoding="UTF-8?>')
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg_parts.append('  <style>')
    svg_parts.append('    .title { font: bold 16px sans-serif; }')
    svg_parts.append('    .axis-label { font: 12px sans-serif; }')
    svg_parts.append('    .risk-label { font: 10px sans-serif; fill: #333; }')
    svg_parts.append('    .cell { stroke: #333; stroke-width: 1; }')
    svg_parts.append('  </style>')

    # Layout calculations
    margin_top = 40
    margin_left = 60
    margin_right = 20
    margin_bottom = 40

    grid_width = width - margin_left - margin_right
    grid_height = height - margin_top - margin_bottom
    cell_size = min(grid_width, grid_height) // 5

    # Title
    svg_parts.append(f'  <text class="title" x="{width // 2}" y="20" text-anchor="middle">Risk Heatmap: Impact x Likelihood</text>')

    # Draw grid cells (5x5 matrix)
    for likelihood in range(1, 6):
        for impact in range(1, 6):
            x = margin_left + (impact - 1) * cell_size
            y = margin_top + (5 - likelihood) * cell_size
            color = HEAT_COLORS[likelihood - 1][impact - 1]
            svg_parts.append(f'  <rect class="cell" x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" fill="{color}"/>')

    # X-axis labels (Impact)
    svg_parts.append(f'  <text class="axis-label" x="{width // 2}" y="{height - 10}" text-anchor="middle">Impact</text>')
    for i in range(5):
        x = margin_left + i * cell_size + cell_size // 2
        svg_parts.append(f'  <text class="axis-label" x="{x}" y="{height - 25}" text-anchor="middle">{i + 1}</text>')

    # Y-axis labels (Likelihood)
    for i in range(5):
        y = margin_top + i * cell_size + cell_size // 2
        svg_parts.append(f'  <text class="axis-label" x="40" y="{y}" text-anchor="end">{5 - i}</text>')

    # Plot risks as circles
    for risk in risks:
        impact = risk.get("impact", 3)
        likelihood = risk.get("likelihood", 3)
        priority = risk.get("priority", "P2")
        risk_id = risk.get("id", "?")

        # Clamp values to valid range
        impact = max(1, min(5, impact))
        likelihood = max(1, min(5, likelihood))

        # Calculate position
        x = margin_left + (impact - 0.5) * cell_size
        y = margin_top + (5 - likelihood + 0.5) * cell_size

        color = PRIORITY_COLORS.get(priority, "#888888")

        # Draw circle and label
        svg_parts.append(f'  <circle cx="{x}" cy="{y}" r="12" fill="{color}" stroke="#333" stroke-width="1"/>')
        svg_parts.append(f'  <text class="risk-label" x="{x}" y="{y + 3}" text-anchor="middle">{risk_id}</text>')

    # Legend
    legend_x = width - 100
    legend_y = margin_top

    svg_parts.append(f'  <text class="axis-label" x="{legend_x}" y="{legend_y}">Priority</text>')
    for i, (priority, color) in enumerate(PRIORITY_COLORS.items()):
        y = legend_y + 20 + i * 20
        svg_parts.append(f'  <rect x="{legend_x}" y="{y}" width="15" height="15" fill="{color}" stroke="#333"/>')
        svg_parts.append(f'  <text class="risk-label" x="{legend_x + 20}" y="{y + 12}">{priority}</text>')

    svg_parts.append('</svg>')

    return "\n".join(svg_parts)


def generate_html_heatmap(
    risks: list[dict[str, Any]],
    title: str = "Risk Heatmap",
) -> str:
    """Generate interactive HTML heatmap with embedded SVG and tooltips."""
    svg_content = generate_svg_heatmap(risks, width=700, height=550)

    html_parts: list[str] = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html>')
    html_parts.append('<head>')
    html_parts.append('  <meta charset="utf-8">')
    html_parts.append(f'  <title>{title}</title>')
    html_parts.append('  <style>')
    html_parts.append('    body { font-family: sans-serif; margin: 20px; background: #f5f5f5; }')
    html_parts.append('    .container { max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; }')
    html_parts.append('    .heatmap-container { margin: 20px 0; }')
    html_parts.append('    .risk-table { margin-top: 30px; border-collapse: collapse; width: 100%; }')
    html_parts.append('    .risk-table th, .risk-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }')
    html_parts.append('    .risk-table th { background: #f0f0f0; }')
    html_parts.append('    .risk-table tr:hover { background: #f9f9f9; }')
    html_parts.append('    .p0 { background: #ff4444; color: white; }')
    html_parts.append('    .p1 { background: #ff8844; }')
    html_parts.append('    .p2 { background: #ffcc44; }')
    html_parts.append('    .p3 { background: #44ff44; }')
    html_parts.append('  </style>')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('  <div class="container">')
    html_parts.append(f'    <h1>{title}</h1>')
    html_parts.append(f'    <p>Total risks: {len(risks)}</p>')
    html_parts.append('    <div class="heatmap-container">')
    html_parts.append(svg_content)
    html_parts.append('    </div>')
    html_parts.append('    <h2>Risk Details</h2>')
    html_parts.append('    <table class="risk-table">')
    html_parts.append('      <thead>')
    html_parts.append('        <tr><th>ID</th><th>Scenario</th><th>Impact</th><th>Likelihood</th><th>Score</th><th>Priority</th><th>Rationale</th></tr>')
    html_parts.append('      </thead>')
    html_parts.append('      <tbody>')

    for risk in risks:
        risk_id = risk.get("id", "?")
        scenario = risk.get("scenario", "")
        impact = risk.get("impact", "?")
        likelihood = risk.get("likelihood", "?")
        score = risk.get("score", "?")
        priority = risk.get("priority", "?")
        rationale = risk.get("rationale", "")
        priority_class = priority.lower() if priority else ""

        html_parts.append(f'        <tr>')
        html_parts.append(f'          <td>{risk_id}</td>')
        html_parts.append(f'          <td>{scenario}</td>')
        html_parts.append(f'          <td>{impact}</td>')
        html_parts.append(f'          <td>{likelihood}</td>')
        html_parts.append(f'          <td>{score}</td>')
        html_parts.append(f'          <td class="{priority_class}">{priority}</td>')
        html_parts.append(f'          <td>{rationale}</td>')
        html_parts.append(f'        </tr>')

    html_parts.append('      </tbody>')
    html_parts.append('    </table>')
    html_parts.append('    <h2>Priority Distribution</h2>')
    html_parts.append('    <ul>')

    # Count by priority
    priority_counts: dict[str, int] = {}
    for risk in risks:
        p = risk.get("priority", "?")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    for priority in ["P0", "P1", "P2", "P3"]:
        count = priority_counts.get(priority, 0)
        html_parts.append(f'      <li><strong>{priority}</strong>: {count} risks</li>')

    html_parts.append('    </ul>')
    html_parts.append('  </div>')
    html_parts.append('</body>')
    html_parts.append('</html>')

    return "\n".join(html_parts)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate risk heatmap visualization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to risk_register.json file",
    )
    parser.add_argument(
        "--format",
        choices=["html", "svg"],
        default="html",
        help="Output format: html (interactive) or svg (static)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file path",
    )
    parser.add_argument(
        "--title",
        default="Risk Heatmap",
        help="Title for the visualization",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"risk-heatmap {__version__}",
    )

    args = parser.parse_args()

    try:
        # Load risk register
        risk_register = load_risk_register(args.input)
        risks = risk_register.get("risks", [])
        feature_id = risk_register.get("feature_id", "UNKNOWN")

        if not risks:
            print(f"Warning: No risks found in {args.input}", file=sys.stderr)
            risks = []

        # Generate output
        title = f"{args.title} - {feature_id}"

        if args.format == "svg":
            content = generate_svg_heatmap(risks)
        else:
            content = generate_html_heatmap(risks, title)

        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")

        print(f"Generated: {args.output}")
        print(f"  Risks plotted: {len(risks)}")
        print(f"  Format: {args.format}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())