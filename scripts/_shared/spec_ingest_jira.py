"""Jira specification ingestion helpers."""

from __future__ import annotations

import os
import re
from typing import Any


def ingest_jira_issue(issue_key: str, api_key: str | None = None) -> dict[str, Any]:
    """Ingest a feature specification from a Jira issue."""
    base_url = os.environ.get("JIRA_URL", "")
    api_token = api_key or os.environ.get("JIRA_API_TOKEN", "")
    pat = os.environ.get("JIRA_PAT", "")
    username = os.environ.get("JIRA_USERNAME", "")

    try:
        import requests
    except ImportError:
        return _jira_error(
            issue_key,
            "Jira Import (requests not installed)",
            "[Install requests: pip install requests]",
            "ASM-REQUESTS",
            "requests library not installed",
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
        return _jira_error(
            issue_key,
            "Jira Import (No credentials)",
            "[Set JIRA_API_TOKEN or JIRA_PAT environment variable]",
            "ASM-AUTH",
            "No Jira credentials configured",
        )

    api_endpoint = (
        f"{base_url}/rest/api/2/issue/{issue_key}?fields=summary,description,labels,customFields"
    )
    try:
        response = requests.get(api_endpoint, headers=headers, auth=auth, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        return _jira_error(
            issue_key,
            f"Jira Import Error: {exc}",
            "[API request failed]",
            "ASM-ERROR",
            f"API error: {exc}",
        )

    fields = data.get("fields", {})
    return _build_jira_result(issue_key, base_url, fields)


def _jira_error(
    issue_key: str,
    title: str,
    acceptance_text: str,
    assumption_id: str,
    assumption_text: str,
) -> dict[str, Any]:
    return {
        "feature_id": issue_key.upper(),
        "title": title,
        "acceptance_criteria": [acceptance_text],
        "source_refs": [{"id": issue_key, "kind": "spec", "excerpt": f"Jira issue {issue_key}"}],
        "assumptions": [
            {"id": assumption_id, "text": assumption_text, "severity": "critical"}
        ],
    }


def _build_jira_result(issue_key: str, base_url: str, fields: dict[str, Any]) -> dict[str, Any]:
    acceptance_criteria, business_rules, actors = parse_jira_description(
        fields.get("description", "")
    )
    result: dict[str, Any] = {
        "feature_id": issue_key.upper(),
        "title": fields.get("summary", issue_key),
        "summary": f"Imported from Jira issue {issue_key}",
        "source_refs": [
            {"id": issue_key, "kind": "spec", "excerpt": f"{base_url}/browse/{issue_key}"}
        ],
    }

    if acceptance_criteria:
        result["acceptance_criteria"] = acceptance_criteria
    else:
        result["acceptance_criteria"] = ["[NO ACCEPTANCE CRITERIA FOUND IN ISSUE]"]
        result.setdefault("assumptions", []).append(
            {
                "id": "ASM-AC",
                "text": "No acceptance criteria found in Jira issue",
                "severity": "high",
            }
        )

    if business_rules:
        result["business_rules"] = business_rules
    if actors:
        result["actors"] = actors
    if fields.get("labels"):
        result["changed_areas"] = fields["labels"]
    return result


def parse_jira_description(description: str) -> tuple[list[str], list[str], list[str]]:
    """Parse Jira description text and extract recognized sections."""
    acceptance_criteria: list[str] = []
    business_rules: list[str] = []
    actors: list[str] = []
    if not description:
        return acceptance_criteria, business_rules, actors

    current_section = ""
    for line in description.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("h1.", "h2.", "h3.")):
            current_section = stripped.split(".", 1)[1].strip().lower()
            continue
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip().lower()
            continue
        if not stripped.startswith(("*", "-")):
            continue

        item = stripped.lstrip("*-").strip()
        if not item:
            continue
        if "acceptance" in current_section or "ac" in current_section:
            acceptance_criteria.append(item)
        elif "business rule" in current_section or "br" in current_section:
            business_rules.append(item)
        elif "actor" in current_section:
            actors.append(item)
        elif re.match(r"AC-\d+:", item) or item.lower().startswith("accept"):
            acceptance_criteria.append(item)
        elif re.match(r"BR-\d+:", item) or "must" in item.lower() or "shall" in item.lower():
            business_rules.append(item)

    return acceptance_criteria, business_rules, actors
