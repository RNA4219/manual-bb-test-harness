"""Confluence specification ingestion helpers."""

from __future__ import annotations

import os
import re
from typing import Any


def ingest_confluence_spec(url: str, api_key: str | None = None) -> dict[str, Any]:
    """Ingest a feature specification from a Confluence page."""
    base_url = os.environ.get("CONFLUENCE_URL", "")
    api_token = api_key or os.environ.get("CONFLUENCE_API_TOKEN", "")
    pat = os.environ.get("CONFLUENCE_PAT", "")
    username = os.environ.get("CONFLUENCE_USERNAME", "")

    try:
        import requests
    except ImportError:
        return _confluence_error(
            "CONFLUENCE-NO-REQUESTS",
            "Confluence Import (requests not installed)",
            "[Install requests: pip install requests]",
            url,
            "ASM-REQUESTS",
            "requests library not installed",
        )

    page_id = extract_confluence_page_id(url, base_url)
    if not page_id:
        return _confluence_error(
            "CONFLUENCE-INVALID-URL",
            "Confluence Import (Invalid URL)",
            "[Could not extract page ID from URL]",
            url,
            "ASM-URL",
            "Could not parse Confluence URL",
        )

    headers: dict[str, str] = {"Accept": "application/json"}
    auth: tuple[str, str] | None = None
    if api_token and username:
        auth = (username, api_token)
    elif pat:
        headers["Authorization"] = f"Bearer {pat}"
    elif api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    else:
        return _confluence_error(
            "CONFLUENCE-NO-AUTH",
            "Confluence Import (No credentials)",
            "[Set CONFLUENCE_API_TOKEN or CONFLUENCE_PAT environment variable]",
            url,
            "ASM-AUTH",
            "No Confluence credentials configured",
        )

    api_endpoint = f"{base_url}/rest/api/content/{page_id}?expand=body.storage,version"
    try:
        response = requests.get(api_endpoint, headers=headers, auth=auth, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        return _confluence_error(
            "CONFLUENCE-ERROR",
            f"Confluence Import Error: {exc}",
            "[API request failed]",
            url,
            "ASM-ERROR",
            f"API error: {exc}",
        )

    title = data.get("title", "Untitled")
    content_html = data.get("body", {}).get("storage", {}).get("value", "")
    parsed = parse_confluence_html(content_html)
    return _build_confluence_result(title, page_id, url, parsed)


def _confluence_error(
    feature_id: str,
    title: str,
    acceptance_text: str,
    url: str,
    assumption_id: str,
    assumption_text: str,
) -> dict[str, Any]:
    return {
        "feature_id": feature_id,
        "title": title,
        "acceptance_criteria": [acceptance_text],
        "source_refs": [{"id": "CONFLUENCE-URL", "kind": "spec", "excerpt": url}],
        "assumptions": [{"id": assumption_id, "text": assumption_text, "severity": "critical"}],
    }


def extract_confluence_page_id(url: str, base_url: str) -> str:
    """Extract a page ID from a Confluence URL or raw ID."""
    _ = base_url
    if url.isdigit():
        return url

    match = re.search(r"/pages/(\d+)", url)
    if match:
        return match.group(1)

    match = re.search(r"pageId=(\d+)", url)
    if match:
        return match.group(1)
    return ""


def parse_confluence_html(
    html: str,
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str]]:
    """Parse Confluence HTML and extract recognized sections."""
    buckets: dict[str, list[str]] = {
        "acceptance_criteria": [],
        "business_rules": [],
        "actors": [],
        "devices": [],
        "mobile_contexts": [],
        "changed_areas": [],
    }
    heading_pattern = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", re.IGNORECASE | re.DOTALL)
    list_pattern = re.compile(r"<ul[^>]*>(.*?)</ul>", re.IGNORECASE | re.DOTALL)
    li_pattern = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)

    current_section = ""
    for index, part in enumerate(re.split(heading_pattern, html)):
        if index % 2 == 1:
            current_section = _strip_html(part).lower()
            continue
        for ul_match in list_pattern.finditer(part):
            for li_match in li_pattern.finditer(ul_match.group(1)):
                item = _strip_html(li_match.group(1))
                bucket = _section_bucket(current_section)
                if item and bucket:
                    buckets[bucket].append(item)

    return (
        buckets["acceptance_criteria"],
        buckets["business_rules"],
        buckets["actors"],
        buckets["devices"],
        buckets["mobile_contexts"],
        buckets["changed_areas"],
    )


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )


def _section_bucket(section: str) -> str | None:
    if "acceptance" in section or "ac" in section:
        return "acceptance_criteria"
    if "business rule" in section or "br" in section:
        return "business_rules"
    if "actor" in section or "user" in section:
        return "actors"
    if "device" in section or "platform" in section:
        return "devices"
    if "mobile context" in section:
        return "mobile_contexts"
    if "changed" in section or "affected" in section:
        return "changed_areas"
    return None


def generate_feature_id(title: str, page_id: str) -> str:
    """Generate a feature_id from a Confluence title and page ID."""
    words = re.findall(r"[A-Z]+|[a-zA-Z]+", title)
    meaningful = [word.upper() for word in words if len(word) > 2][:3]
    if meaningful:
        return "-".join(meaningful) + "-" + page_id[:4]
    return "CONF-" + page_id


def _build_confluence_result(
    title: str,
    page_id: str,
    url: str,
    parsed: tuple[list[str], list[str], list[str], list[str], list[str], list[str]],
) -> dict[str, Any]:
    acceptance_criteria, business_rules, actors, devices, mobile_contexts, changed_areas = parsed
    result: dict[str, Any] = {
        "feature_id": generate_feature_id(title, page_id),
        "title": title,
        "summary": f"Imported from Confluence page {page_id}",
        "source_refs": [{"id": f"CONFLUENCE-{page_id}", "kind": "spec", "excerpt": url}],
    }

    if acceptance_criteria:
        result["acceptance_criteria"] = acceptance_criteria
    else:
        result["acceptance_criteria"] = ["[NO ACCEPTANCE CRITERIA FOUND IN PAGE]"]
        result.setdefault("assumptions", []).append(
            {
                "id": "ASM-AC",
                "text": "No acceptance criteria section found in Confluence page",
                "severity": "high",
            }
        )

    for key, value in {
        "business_rules": business_rules,
        "actors": actors,
        "devices": devices,
        "mobile_contexts": mobile_contexts,
        "changed_areas": changed_areas,
    }.items():
        if value:
            result[key] = value
    return result
