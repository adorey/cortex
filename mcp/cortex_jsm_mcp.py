"""Minimal MCP server: post an INTERNAL (public:false) comment on a Jira Service Management
request — the one thing the official Atlassian Rovo MCP does NOT expose.

This is a standalone example, NOT part of the cortex_runtime package. The runtime consumes it
like any MCP server (declare it in the project's .mcp.json + bind `internal-comment` to its tool).

Why this exists: Rovo's `addCommentToJiraIssue` only offers group/role visibility, not the JSM
`public:false` internal note. This server calls the JSM Service Desk API directly:
    POST {JIRA_URL}/rest/servicedeskapi/request/{key}/comment   {"body": ..., "public": false}

Install as a named command (so .mcp.json needs no raw path):
    pipx install /path/to/cortex/mcp      # → the `cortex-jsm-mcp` command, on PATH
Or run directly:  pip install mcp  &&  python cortex_jsm_mcp.py
Env:  JIRA_URL (e.g. https://your-site.atlassian.net), JIRA_EMAIL, JIRA_API_TOKEN (an ATATT token).
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cortex_jsm")

JIRA_URL = os.environ.get("JIRA_URL", "").rstrip("/")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
# accept either name — JIRA_API_TOKEN (canonical) or JIRA_BEARER_TOKEN (common host var)
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN") or os.environ.get("JIRA_BEARER_TOKEN", "")
_BASIC = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()


def _get(path: str):
    if not (JIRA_URL and JIRA_EMAIL and JIRA_API_TOKEN):
        raise RuntimeError("Set JIRA_URL, JIRA_EMAIL and JIRA_API_TOKEN in the environment.")
    req = urllib.request.Request(
        f"{JIRA_URL}{path}", method="GET",
        headers={"Authorization": f"Basic {_BASIC}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Jira API {exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc


@mcp.tool()
def get_jira_issue(issue_key: str) -> str:
    """Read a Jira issue (key, summary, status, priority, reporter, description, recent comments).
    Basic-auth REST — works headless, no OAuth needed. Returns JSON the agent can parse."""
    data = _get(f"/rest/api/3/issue/{issue_key}"
                "?fields=summary,status,priority,reporter,description,comment")
    f = data.get("fields", {})
    comments = [{"author": (c.get("author") or {}).get("displayName"),
                 "public": c.get("jsdPublic"), "body": c.get("body")}
                for c in (f.get("comment", {}) or {}).get("comments", [])[-10:]]
    return json.dumps({
        "key": data.get("key"), "summary": f.get("summary"),
        "status": (f.get("status") or {}).get("name"),
        "priority": (f.get("priority") or {}).get("name"),
        "reporter": (f.get("reporter") or {}).get("displayName"),
        "description": f.get("description"), "comments": comments,
    }, ensure_ascii=False)


@mcp.tool()
def add_internal_comment(issue_key: str, body: str) -> str:
    """Add an INTERNAL comment (public:false) to a JSM request — visible to agents, hidden from
    the customer. ``issue_key`` is the ticket key (e.g. "BLUSUPP-3197"); ``body`` is plain text."""
    if not (JIRA_URL and JIRA_EMAIL and JIRA_API_TOKEN):
        raise RuntimeError("Set JIRA_URL, JIRA_EMAIL and JIRA_API_TOKEN in the environment.")
    url = f"{JIRA_URL}/rest/servicedeskapi/request/{issue_key}/comment"
    payload = json.dumps({"body": body, "public": False}).encode()
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Authorization": f"Basic {_BASIC}",
                 "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Jira API {exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc
    return f"Internal comment posted on {issue_key} (comment id {result.get('id')}, public=false)."


def main():
    """Console-script entry point (`cortex-jsm-mcp`)."""
    mcp.run()   # stdio transport


if __name__ == "__main__":
    main()
