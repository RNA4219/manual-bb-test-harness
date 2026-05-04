"""Ingest specification from external sources (Markdown, Confluence, Jira).

Generates feature_spec.json from various spec sources.

Usage:
    python scripts/spec-ingest.py --source markdown --input <file.md> --output <file.json>
    python scripts/spec-ingest.py --source confluence --url <url> --api-key <key> --output <dir>
    python scripts/spec-ingest.py --source jira --issue <key> --api-key <key> --output <file.json>

Example:
    python scripts/spec-ingest.py \
        --source markdown \
        --input docs/features/order-cancel.md \
        --output examples/artifacts/order-cancel.feature_spec.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

__version__ = "0.2.0"


# ============== Markdown Parser ==============

def parse_yaml_frontmatter(content: str) -> dict[str, str]:
    """Parse YAML frontmatter from Markdown content.

    Returns dict of key-value pairs.
    Returns empty dict if frontmatter is missing (not an error).
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return {}  # No frontmatter, return empty dict

    frontmatter_text = match.group(1)
    result: dict[str, str] = {}

    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            continue  # Skip invalid lines instead of raising error
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()

    return result


def extract_markdown_sections(content: str) -> dict[str, list[str]]:
    """Extract structured sections from Markdown.

    Returns dict with section headers as keys, list of items as values.
    """
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    current_items: list[str] = []

    lines = content.split("\n")
    # Skip frontmatter
    in_frontmatter = False
    frontmatter_end = 0

    for i, line in enumerate(lines):
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
            else:
                frontmatter_end = i + 1
                in_frontmatter = False
                break

    # Process content after frontmatter
    for line in lines[frontmatter_end:]:
        stripped = line.strip()

        # Section header (## or ###)
        section_match = re.match(r"^##+\s+(.+)$", stripped)
        if section_match:
            # Save previous section
            if current_section and current_items:
                sections[current_section] = current_items
            current_section = section_match.group(1).strip()
            current_items = []
            continue

        # List item
        if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.\s", stripped):
            item_text = stripped.lstrip("- *").strip()
            # Remove leading number if present
            item_text = re.sub(r"^\d+\.\s*", "", item_text)
            if item_text:
                current_items.append(item_text)
            continue

        # Paragraph text (non-empty, non-section)
        if stripped and current_section:
            current_items.append(stripped)

    # Save final section
    if current_section and current_items:
        sections[current_section] = current_items

    return sections


def normalize_section_name(name: str) -> str:
    """Normalize section name to standard keys."""
    name_lower = name.lower().strip()

    # Exact matches first (avoid substring issues like "ac" in "actors")
    exact_mappings = {
        "acceptance criteria": "acceptance_criteria",
        "ac": "acceptance_criteria",
        "business rules": "business_rules",
        "br": "business_rules",
        "requirements": "requirements",
        "actors": "actors",
        "summary": "summary",
        "devices": "devices",
        "changed areas": "changed_areas",
    }

    # Check exact match first
    if name_lower in exact_mappings:
        return exact_mappings[name_lower]

    # Then check substring matches for longer section names
    for key, value in exact_mappings.items():
        if key in name_lower and len(key) >= 3:
            return value

    return name_lower.replace(" ", "_")


def ingest_markdown_spec(path: Path) -> dict[str, Any]:
    """Ingest specification from Markdown file.

    Returns feature_spec dict.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e

    # Parse frontmatter
    frontmatter = parse_yaml_frontmatter(content)

    # Extract sections
    sections = extract_markdown_sections(content)

    # Normalize section names
    normalized_sections: dict[str, list[str]] = {}
    for name, items in sections.items():
        normalized_name = normalize_section_name(name)
        normalized_sections[normalized_name] = items

    # Build feature_spec
    feature_id = frontmatter.get("feature_id", frontmatter.get("id", ""))
    if not feature_id:
        # Generate from filename
        filename = path.stem.upper().replace("-", "-")
        feature_id = re.sub(r"[^A-Z0-9-]", "", filename)

    title = frontmatter.get("title", frontmatter.get("name", path.stem))

    result: dict[str, Any] = {
        "feature_id": feature_id,
        "title": title,
        "source_refs": [
            {
                "id": f"MD-{path.stem}",
                "kind": "spec",
                "excerpt": f"Ingested from {path.name}",
            }
        ],
    }

    # Add optional fields from frontmatter
    if "summary" in frontmatter:
        result["summary"] = frontmatter["summary"]
    if "actors" in frontmatter:
        actors_str = frontmatter["actors"]
        result["actors"] = [a.strip() for a in actors_str.split(",")]

    # Add sections
    if "acceptance_criteria" in normalized_sections:
        result["acceptance_criteria"] = normalized_sections["acceptance_criteria"]
    else:
        # Required field, add placeholder
        result["acceptance_criteria"] = ["[NO ACCEPTANCE CRITERIA FOUND]"]
        result.setdefault("assumptions", []).append({
            "id": "ASM-1",
            "text": "No acceptance criteria section found in source",
            "severity": "high",
        })

    if "business_rules" in normalized_sections:
        result["business_rules"] = normalized_sections["business_rules"]

    if "actors" in normalized_sections and "actors" not in result:
        result["actors"] = normalized_sections["actors"]

    if "devices" in normalized_sections:
        result["devices"] = normalized_sections["devices"]

    if "changed_areas" in normalized_sections:
        result["changed_areas"] = normalized_sections["changed_areas"]

    if "summary" in normalized_sections and "summary" not in result:
        result["summary"] = normalized_sections["summary"][0] if normalized_sections["summary"] else ""

    return result


# ============== Confluence Parser ==============

def ingest_confluence_spec(url: str, api_key: str | None = None) -> dict[str, Any]:
    """Ingest specification from Confluence page.

    Supports Atlassian Confluence Cloud and Server/Data Center.
    Authentication via API token (Cloud) or Personal Access Token (Server).

    Args:
        url: Confluence page URL or page ID
        api_key: API token or PAT (uses env vars if not provided)

    Environment variables:
        CONFLUENCE_URL: Base URL (e.g., https://company.atlassian.net/wiki)
        CONFLUENCE_API_TOKEN: API token for Cloud authentication
        CONFLUENCE_PAT: Personal Access Token for Server authentication
        CONFLUENCE_USERNAME: Username for basic auth (Cloud)
    """
    import os

    # Get credentials from environment
    base_url = os.environ.get("CONFLUENCE_URL", "")
    api_token = api_key or os.environ.get("CONFLUENCE_API_TOKEN", "")
    pat = os.environ.get("CONFLUENCE_PAT", "")
    username = os.environ.get("CONFLUENCE_USERNAME", "")

    # Try to use requests if available
    try:
        import requests
    except ImportError:
        return {
            "feature_id": "CONFLUENCE-NO-REQUESTS",
            "title": "Confluence Import (requests not installed)",
            "acceptance_criteria": ["[Install requests: pip install requests]"],
            "source_refs": [{"id": "CONFLUENCE-URL", "kind": "spec", "excerpt": url}],
            "assumptions": [{"id": "ASM-REQUESTS", "text": "requests library not installed", "severity": "critical"}],
        }

    # Extract page ID from URL or use directly
    page_id = extract_confluence_page_id(url, base_url)

    if not page_id:
        return {
            "feature_id": "CONFLUENCE-INVALID-URL",
            "title": "Confluence Import (Invalid URL)",
            "acceptance_criteria": ["[Could not extract page ID from URL]"],
            "source_refs": [{"id": "CONFLUENCE-URL", "kind": "spec", "excerpt": url}],
            "assumptions": [{"id": "ASM-URL", "text": "Could not parse Confluence URL", "severity": "critical"}],
        }

    # Build API URL
    api_endpoint = f"{base_url}/rest/api/content/{page_id}?expand=body.storage,version"

    # Setup authentication
    headers = {"Accept": "application/json"}
    auth = None

    if api_token and username:
        # Basic auth (Cloud)
        auth = (username, api_token)
    elif pat:
        # PAT auth (Server/Data Center)
        headers["Authorization"] = f"Bearer {pat}"
    elif api_token:
        # Try as Bearer token
        headers["Authorization"] = f"Bearer {api_token}"
    else:
        return {
            "feature_id": "CONFLUENCE-NO-AUTH",
            "title": "Confluence Import (No credentials)",
            "acceptance_criteria": ["[Set CONFLUENCE_API_TOKEN or CONFLUENCE_PAT environment variable]"],
            "source_refs": [{"id": "CONFLUENCE-URL", "kind": "spec", "excerpt": url}],
            "assumptions": [{"id": "ASM-AUTH", "text": "No Confluence credentials configured", "severity": "critical"}],
        }

    # Fetch page content
    try:
        response = requests.get(api_endpoint, headers=headers, auth=auth, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {
            "feature_id": "CONFLUENCE-ERROR",
            "title": f"Confluence Import Error: {e}",
            "acceptance_criteria": ["[API request failed]"],
            "source_refs": [{"id": "CONFLUENCE-URL", "kind": "spec", "excerpt": url}],
            "assumptions": [{"id": "ASM-ERROR", "text": f"API error: {e}", "severity": "critical"}],
        }

    # Parse page content
    title = data.get("title", "Untitled")
    content_html = data.get("body", {}).get("storage", {}).get("value", "")

    # Extract structured content from HTML
    acceptance_criteria, business_rules, actors, devices, changed_areas = parse_confluence_html(content_html)

    # Build feature_spec
    feature_id = generate_feature_id(title, page_id)

    result: dict[str, Any] = {
        "feature_id": feature_id,
        "title": title,
        "summary": f"Imported from Confluence page {page_id}",
        "source_refs": [
            {"id": f"CONFLUENCE-{page_id}", "kind": "spec", "excerpt": url},
        ],
    }

    if acceptance_criteria:
        result["acceptance_criteria"] = acceptance_criteria
    else:
        result["acceptance_criteria"] = ["[NO ACCEPTANCE CRITERIA FOUND IN PAGE]"]
        result.setdefault("assumptions", []).append({
            "id": "ASM-AC",
            "text": "No acceptance criteria section found in Confluence page",
            "severity": "high",
        })

    if business_rules:
        result["business_rules"] = business_rules

    if actors:
        result["actors"] = actors

    if devices:
        result["devices"] = devices

    if changed_areas:
        result["changed_areas"] = changed_areas

    return result


def extract_confluence_page_id(url: str, base_url: str) -> str:
    """Extract page ID from Confluence URL."""
    import re

    # If it's already a page ID (numeric)
    if url.isdigit():
        return url

    # Pattern: /pages/12345 or /wiki/spaces/ABC/pages/12345
    match = re.search(r"/pages/(\d+)", url)
    if match:
        return match.group(1)

    # Pattern: pageId=12345 in query string
    match = re.search(r"pageId=(\d+)", url)
    if match:
        return match.group(1)

    # Pattern: /display/SPACE/Page+Title -> need to look up by title
    # This requires search API, return empty for now
    return ""


def parse_confluence_html(html: str) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Parse Confluence HTML to extract structured sections."""
    import re

    # Simple HTML parsing (avoid heavy dependencies)
    # Remove HTML tags for text extraction
    def strip_html(text: str) -> str:
        # Remove tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode common entities
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return text.strip()

    # Extract list items from sections
    acceptance_criteria: list[str] = []
    business_rules: list[str] = []
    actors: list[str] = []
    devices: list[str] = []
    changed_areas: list[str] = []

    # Find sections by heading
    # Pattern: <h1/2/3>Heading</h1/2/3> followed by <ul> or <p>
    heading_pattern = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", re.IGNORECASE | re.DOTALL)
    list_pattern = re.compile(r"<ul[^>]*>(.*?)</ul>", re.IGNORECASE | re.DOTALL)
    li_pattern = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)

    # Split by headings
    sections = re.split(heading_pattern, html)

    current_section = ""
    for i, part in enumerate(sections):
        if i % 2 == 1:  # Heading text
            current_section = strip_html(part).lower()
        elif i % 2 == 0:  # Content after heading
            # Find lists in this section
            for ul_match in list_pattern.finditer(part):
                ul_content = ul_match.group(1)
                for li_match in li_pattern.finditer(ul_content):
                    item = strip_html(li_match.group(1))
                    if not item:
                        continue

                    # Categorize by section name
                    if "acceptance" in current_section or "ac" in current_section:
                        acceptance_criteria.append(item)
                    elif "business rule" in current_section or "br" in current_section:
                        business_rules.append(item)
                    elif "actor" in current_section or "user" in current_section:
                        actors.append(item)
                    elif "device" in current_section or "platform" in current_section:
                        devices.append(item)
                    elif "changed" in current_section or "affected" in current_section:
                        changed_areas.append(item)

    return acceptance_criteria, business_rules, actors, devices, changed_areas


def generate_feature_id(title: str, page_id: str) -> str:
    """Generate feature_id from title and page_id."""
    import re
    # Extract key words from title
    words = re.findall(r"[A-Z]+|[a-zA-Z]+", title)
    # Take first 2-3 meaningful words
    meaningful = [w.upper() for w in words if len(w) > 2][:3]
    if meaningful:
        return "-".join(meaningful) + "-" + page_id[:4]
    return "CONF-" + page_id


# ============== Jira Parser ==============

def ingest_jira_issue(issue_key: str, api_key: str | None = None) -> dict[str, Any]:
    """Ingest specification from Jira issue.

    Supports Atlassian Jira Cloud and Server/Data Center.

    Args:
        issue_key: Jira issue key (e.g., PROJ-123)
        api_key: API token (uses env vars if not provided)

    Environment variables:
        JIRA_URL: Base URL (e.g., https://company.atlassian.net)
        JIRA_API_TOKEN: API token for Cloud authentication
        JIRA_PAT: Personal Access Token for Server authentication
        JIRA_USERNAME: Username for basic auth (Cloud)
    """
    import os

    # Get credentials from environment
    base_url = os.environ.get("JIRA_URL", "")
    api_token = api_key or os.environ.get("JIRA_API_TOKEN", "")
    pat = os.environ.get("JIRA_PAT", "")
    username = os.environ.get("JIRA_USERNAME", "")

    # Try to use requests if available
    try:
        import requests
    except ImportError:
        return {
            "feature_id": issue_key.upper(),
            "title": "Jira Import (requests not installed)",
            "acceptance_criteria": ["[Install requests: pip install requests]"],
            "source_refs": [{"id": issue_key, "kind": "spec", "excerpt": f"Jira issue {issue_key}"}],
            "assumptions": [{"id": "ASM-REQUESTS", "text": "requests library not installed", "severity": "critical"}],
        }

    # Build API URL
    api_endpoint = f"{base_url}/rest/api/2/issue/{issue_key}?fields=summary,description,labels,customFields"

    # Setup authentication
    headers = {"Accept": "application/json"}
    auth = None

    if api_token and username:
        auth = (username, api_token)
    elif pat:
        headers["Authorization"] = f"Bearer {pat}"
    elif api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    else:
        return {
            "feature_id": issue_key.upper(),
            "title": "Jira Import (No credentials)",
            "acceptance_criteria": ["[Set JIRA_API_TOKEN or JIRA_PAT environment variable]"],
            "source_refs": [{"id": issue_key, "kind": "spec", "excerpt": f"Jira issue {issue_key}"}],
            "assumptions": [{"id": "ASM-AUTH", "text": "No Jira credentials configured", "severity": "critical"}],
        }

    # Fetch issue
    try:
        response = requests.get(api_endpoint, headers=headers, auth=auth, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {
            "feature_id": issue_key.upper(),
            "title": f"Jira Import Error: {e}",
            "acceptance_criteria": ["[API request failed]"],
            "source_refs": [{"id": issue_key, "kind": "spec", "excerpt": f"Jira issue {issue_key}"}],
            "assumptions": [{"id": "ASM-ERROR", "text": f"API error: {e}", "severity": "critical"}],
        }

    # Parse issue fields
    fields = data.get("fields", {})
    title = fields.get("summary", issue_key)
    description = fields.get("description", "")

    # Extract structured content from description
    acceptance_criteria, business_rules, actors = parse_jira_description(description)

    # Build feature_spec
    result: dict[str, Any] = {
        "feature_id": issue_key.upper(),
        "title": title,
        "summary": f"Imported from Jira issue {issue_key}",
        "source_refs": [
            {"id": issue_key, "kind": "spec", "excerpt": f"{base_url}/browse/{issue_key}"},
        ],
    }

    if acceptance_criteria:
        result["acceptance_criteria"] = acceptance_criteria
    else:
        result["acceptance_criteria"] = ["[NO ACCEPTANCE CRITERIA FOUND IN ISSUE]"]
        result.setdefault("assumptions", []).append({
            "id": "ASM-AC",
            "text": "No acceptance criteria found in Jira issue",
            "severity": "high",
        })

    if business_rules:
        result["business_rules"] = business_rules

    if actors:
        result["actors"] = actors

    # Add labels as changed areas if present
    labels = fields.get("labels", [])
    if labels:
        result["changed_areas"] = labels

    return result


def parse_jira_description(description: str) -> tuple[list[str], list[str], list[str]]:
    """Parse Jira description to extract structured sections."""
    import re

    acceptance_criteria: list[str] = []
    business_rules: list[str] = []
    actors: list[str] = []

    if not description:
        return acceptance_criteria, business_rules, actors

    # Jira descriptions can be plain text or wiki markup
    lines = description.split("\n")
    current_section = ""

    for line in lines:
        stripped = line.strip()

        # Detect section headers
        if stripped.startswith("h1.") or stripped.startswith("h2.") or stripped.startswith("h3."):
            current_section = stripped.split(".", 1)[1].strip().lower()
            continue

        # Markdown-style headers
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip().lower()
            continue

        # Bullet items
        if stripped.startswith("*") or stripped.startswith("-"):
            item = stripped.lstrip("*-").strip()
            if not item:
                continue

            if "acceptance" in current_section or "ac" in current_section:
                acceptance_criteria.append(item)
            elif "business rule" in current_section or "br" in current_section:
                business_rules.append(item)
            elif "actor" in current_section:
                actors.append(item)
            # Auto-detect patterns
            elif re.match(r"AC-\d+:", item) or item.lower().startswith("accept"):
                acceptance_criteria.append(item)
            elif re.match(r"BR-\d+:", item) or "must" in item.lower() or "shall" in item.lower():
                business_rules.append(item)

    return acceptance_criteria, business_rules, actors


# ============== Main ==============

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest specification from external sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["markdown", "confluence", "jira"],
        required=True,
        help="Source type: markdown, confluence, or jira",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input file path (for markdown)",
    )
    parser.add_argument(
        "--url",
        help="Confluence page URL (for confluence)",
    )
    parser.add_argument(
        "--issue",
        help="Jira issue key (for jira)",
    )
    parser.add_argument(
        "--api-key",
        help="API key for Confluence/Jira (optional, uses env var if not provided)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path (file or directory)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"spec-ingest {__version__}",
    )

    args = parser.parse_args()

    try:
        result: dict[str, Any]

        if args.source == "markdown":
            if not args.input:
                print("Error: --input required for markdown source", file=sys.stderr)
                return 1
            result = ingest_markdown_spec(args.input)

        elif args.source == "confluence":
            if not args.url:
                print("Error: --url required for confluence source", file=sys.stderr)
                return 1
            api_key = args.api_key or ""
            result = ingest_confluence_spec(args.url, api_key)

        elif args.source == "jira":
            if not args.issue:
                print("Error: --issue required for jira source", file=sys.stderr)
                return 1
            api_key = args.api_key or ""
            result = ingest_jira_issue(args.issue, api_key)

        else:
            print(f"Error: Unknown source type: {args.source}", file=sys.stderr)
            return 1

        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"Generated: {args.output}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())