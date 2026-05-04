"""Generate regression impact graph from feature_spec.json and test_model.json.

Produces GraphViz DOT and D3.js HTML outputs for visualizing feature dependencies.

Usage:
    python scripts/regression-graph.py --input <dir_or_files> --format <dot|html> --output <file>

Example:
    python scripts/regression-graph.py \
        --input examples/artifacts/*.feature_spec.json \
        --format dot \
        --output examples/regression-graph.dot

    python scripts/regression-graph.py \
        --input examples/artifacts/ \
        --format html \
        --output examples/regression-graph.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

__version__ = "0.2.0"


# ============== Dependency Parsing ==============

def load_json_file(path: Path) -> dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def parse_feature_specs(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Parse multiple feature_spec.json files.

    Returns dict mapping feature_id -> feature_data.
    """
    features: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = load_json_file(path)
        feature_id = data.get("feature_id", "")
        if feature_id:
            features[feature_id] = data
    return features


def parse_test_models(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Parse multiple test_model.json files.

    Returns dict mapping feature_id -> test_model_data.
    """
    models: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = load_json_file(path)
        feature_id = data.get("feature_id", "")
        if feature_id:
            models[feature_id] = data
    return models


def build_area_feature_map(features: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Build mapping of changed_areas -> feature_ids.

    Returns dict mapping area_name -> list of feature_ids that affect it.
    """
    area_map: dict[str, list[str]] = {}
    for feature_id, data in features.items():
        changed_areas = data.get("changed_areas", [])
        for area in changed_areas:
            if area not in area_map:
                area_map[area] = []
            area_map[area].append(feature_id)
    return area_map


def build_regression_edges(
    features: dict[str, dict[str, Any]],
    test_models: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build regression dependency edges.

    Returns list of edge dicts with source, target, type, and area.
    """
    edges: list[dict[str, Any]] = []

    # Edges from shared changed_areas
    area_map = build_area_feature_map(features)
    for area, feature_ids in area_map.items():
        if len(feature_ids) > 1:
            # All features sharing this area are related
            for i, src in enumerate(feature_ids):
                for tgt in feature_ids[i + 1:]:
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "type": "shared_area",
                        "area": area,
                    })

    # Edges from test_model regression_edges
    for feature_id, model in test_models.items():
        regression_edges = model.get("regression_edges", [])
        for edge_str in regression_edges:
            # Parse edge format: "direct:service_name" or "external:service_name"
            parts = edge_str.split(":")
            if len(parts) == 2:
                edge_type = parts[0]
                service = parts[1]
                # Find features that affect this service
                for other_id, other_data in features.items():
                    other_areas = other_data.get("changed_areas", [])
                    if service in other_areas and other_id != feature_id:
                        edges.append({
                            "source": feature_id,
                            "target": other_id,
                            "type": edge_type,
                            "area": service,
                        })

    return edges


def deduplicate_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate edges, keeping unique source-target pairs."""
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for edge in edges:
        key = (edge["source"], edge["target"])
        reverse_key = (edge["target"], edge["source"])
        if key not in seen and reverse_key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique


# ============== GraphViz DOT Output ==============

def generate_dot(
    features: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]]
) -> str:
    """Generate GraphViz DOT format output."""
    lines: list[str] = [
        "digraph RegressionImpact {",
        "  rankdir=LR;",
        "  node [shape=box, style=filled, fillcolor=lightblue];",
    ]

    # Add nodes
    for feature_id, data in features.items():
        title = data.get("title", feature_id)
        # Escape quotes in title
        safe_title = title.replace('"', "'")
        lines.append(f'  "{feature_id}" [label="{feature_id}\\n{safe_title}"];')

    # Add edges
    lines.append("")
    lines.append("  // Regression dependencies")
    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        edge_type = edge.get("type", "dependency")
        # Different arrow styles for different edge types
        if edge_type == "direct":
            lines.append(f'  "{src}" -> "{tgt}" [style=solid, color=red];')
        elif edge_type == "external":
            lines.append(f'  "{src}" -> "{tgt}" [style=dashed, color=orange];')
        else:
            lines.append(f'  "{src}" -> "{tgt}" [style=solid];')

    lines.append("}")
    return "\n".join(lines)


# ============== D3.js HTML Output ==============

def generate_d3_json(
    features: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]]
) -> dict[str, Any]:
    """Generate D3.js force layout compatible JSON."""
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    for feature_id, data in features.items():
        nodes.append({
            "id": feature_id,
            "label": data.get("title", feature_id),
            "areas": data.get("changed_areas", []),
        })

    for i, edge in enumerate(edges):
        links.append({
            "source": edge["source"],
            "target": edge["target"],
            "type": edge.get("type", "dependency"),
            "area": edge.get("area", ""),
        })

    return {"nodes": nodes, "links": links}


def generate_html_wrapper(d3_data: dict[str, Any]) -> str:
    """Generate self-contained HTML with embedded D3.js visualization."""
    d3_json_str = json.dumps(d3_data, indent=2)

    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '  <meta charset="utf-8">',
        '  <title>Regression Impact Graph</title>',
        '  <script src="https://d3js.org/d3.v7.min.js"></script>',
        '  <style>',
        '    body { margin: 0; font-family: sans-serif; }',
        '    .node { cursor: pointer; }',
        '    .node rect { fill: lightblue; stroke: steelblue; stroke-width: 1px; }',
        '    .node text { font-size: 12px; }',
        '    .link { stroke: #999; stroke-opacity: 0.6; }',
        '    .link.direct { stroke: red; stroke-width: 2px; }',
        '    .link.external { stroke: orange; stroke-dasharray: 5,5; }',
        '    .link.shared_area { stroke: #666; }',
        '  </style>',
        '</head>',
        '<body>',
        '  <svg id="graph" width="800" height="600"></svg>',
        '  <script>',
        f'    const data = {d3_json_str};',
        '',
        '    const svg = d3.select("#graph");',
        '    const width = 800;',
        '    const height = 600;',
        '',
        '    const simulation = d3.forceSimulation(data.nodes)',
        '      .force("link", d3.forceLink(data.links).id(d => d.id).distance(150))',
        '      .force("charge", d3.forceManyBody().strength(-300))',
        '      .force("center", d3.forceCenter(width / 2, height / 2));',
        '',
        '    const link = svg.selectAll(".link")',
        '      .data(data.links)',
        '      .enter().append("line")',
        '      .attr("class", d => "link " + d.type)',
        '      .attr("stroke-width", d => d.type === "direct" ? 2 : 1);',
        '',
        '    const node = svg.selectAll(".node")',
        '      .data(data.nodes)',
        '      .enter().append("g")',
        '      .attr("class", "node")',
        '      .call(d3.drag()',
        '        .on("start", dragstarted)',
        '        .on("drag", dragged)',
        '        .on("end", dragended));',
        '',
        '    node.append("rect")',
        '      .attr("width", 100)',
        '      .attr("height", 40)',
        '      .attr("x", -50)',
        '      .attr("y", -20);',
        '',
        '    node.append("text")',
        '      .attr("dy", -5)',
        '      .attr("text-anchor", "middle")',
        '      .text(d => d.id);',
        '',
        '    node.append("text")',
        '      .attr("dy", 10)',
        '      .attr("text-anchor", "middle")',
        '      .attr("font-size", "10px")',
        '      .text(d => d.label.substring(0, 15) + (d.label.length > 15 ? "..." : ""));',
        '',
        '    simulation.on("tick", () => {',
        '      link',
        '        .attr("x1", d => d.source.x)',
        '        .attr("y1", d => d.source.y)',
        '        .attr("x2", d => d.target.x)',
        '        .attr("y2", d => d.target.y);',
        '      node.attr("transform", d => "translate(" + d.x + "," + d.y + ")");',
        '    });',
        '',
        '    function dragstarted(event, d) {',
        '      if (!event.active) simulation.alphaTarget(0.3).restart();',
        '      d.fx = d.x;',
        '      d.fy = d.y;',
        '    }',
        '',
        '    function dragged(event, d) {',
        '      d.fx = event.x;',
        '      d.fy = event.y;',
        '    }',
        '',
        '    function dragended(event, d) {',
        '      if (!event.active) simulation.alphaTarget(0);',
        '      d.fx = null;',
        '      d.fy = null;',
        '    }',
        '  </script>',
        '</body>',
        '</html>',
    ]
    return '\n'.join(html_parts)


# ============== Main ==============

def expand_input_paths(input_arg: Path) -> tuple[list[Path], list[Path]]:
    """Expand input argument to lists of feature_spec and test_model files."""
    if input_arg.is_file():
        # Single file
        files = [input_arg]
    else:
        # Directory: glob for JSON files
        files = list(input_arg.glob("*.json"))

    feature_specs: list[Path] = []
    test_models: list[Path] = []

    for f in files:
        name = f.name.lower()
        if "feature_spec" in name:
            feature_specs.append(f)
        elif "test_model" in name:
            test_models.append(f)

    return feature_specs, test_models


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate regression impact graph from feature specs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input file glob or directory containing feature_spec.json and test_model.json files",
    )
    parser.add_argument(
        "--format",
        choices=["dot", "html", "json"],
        required=True,
        help="Output format: dot (GraphViz), html (D3.js), or json (raw data)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file path",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"regression-graph {__version__}",
    )

    args = parser.parse_args()

    try:
        # Expand input paths
        feature_specs, test_models = expand_input_paths(args.input)

        if not feature_specs and not test_models:
            print("Error: No feature_spec.json or test_model.json files found", file=sys.stderr)
            return 1

        # Parse data
        features = parse_feature_specs(feature_specs)
        models = parse_test_models(test_models)

        # Build edges
        edges = build_regression_edges(features, models)
        edges = deduplicate_edges(edges)

        # Generate output
        if args.format == "dot":
            content = generate_dot(features, edges)
        elif args.format == "html":
            d3_data = generate_d3_json(features, edges)
            content = generate_html_wrapper(d3_data)
        elif args.format == "json":
            d3_data = generate_d3_json(features, edges)
            content = json.dumps(d3_data, indent=2, ensure_ascii=False)

        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")

        print(f"Generated: {args.output}")
        print(f"  Features: {len(features)}, Edges: {len(edges)}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())