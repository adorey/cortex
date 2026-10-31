"""The GitHub REST API, as much as the release actions use — standard library only.

The token is the workflow's (``GITHUB_TOKEN``), given by the calling job with the permissions its
action documents. A draft release is listed only to a token with push access: a job that must see
drafts asks for ``contents: write``.
"""

from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, List, Optional


class GitHubError(Exception):
    """An answer other than a success, or no answer at all — a network error, whose ``status`` is
    None. Either way the API said nothing an action may act on."""

    def __init__(self, status: Optional[int], message: str):
        super().__init__(f"HTTP {status}: {message}" if status is not None else f"no answer: {message}")
        self.status = status


class GitHub:
    def __init__(self, repository: str, token: Optional[str] = None, api: Optional[str] = None):
        self.repository = repository
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.api = (api or os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")

    def request(self, method: str, path: str, body: Any = None, data: Optional[bytes] = None,
                content_type: Optional[str] = None, url: Optional[str] = None) -> Any:
        target = url or f"{self.api}{path}"
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "release-actions"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(target, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            try:
                detail = error.read().decode("utf-8", "replace")
            except (OSError, http.client.HTTPException):   # its body cut short: the status still says it
                detail = str(error.reason)
            try:
                detail = json.loads(detail).get("message", detail)
            except ValueError:
                pass
            raise GitHubError(error.code, f"{method} {target}: {detail}") from None
        except (OSError, http.client.HTTPException) as error:   # refused, reset, timed out, cut short
            raise GitHubError(None, f"{method} {target}: {error}") from None
        return json.loads(raw) if raw else None

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def download(self, url: str) -> bytes:
        """A release asset, by its API url. GitHub answers with a redirect to its storage, which
        refuses a request that still carries the token: the redirect is followed without it."""
        headers = {"Accept": "application/octet-stream", "User-Agent": "release-actions"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308) or not error.headers.get("Location"):
                raise GitHubError(error.code, f"GET {url}: {error.reason}") from None
            location = error.headers["Location"]
        except (OSError, http.client.HTTPException) as error:
            raise GitHubError(None, f"GET {url}: {error}") from None
        storage = location.split("?", 1)[0]   # its query is a signature: kept out of the logs
        try:
            with urllib.request.urlopen(urllib.request.Request(location, headers={"User-Agent": "release-actions"}),
                                        timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            raise GitHubError(error.code, f"GET {storage}: {error.reason}") from None
        except (OSError, http.client.HTTPException) as error:
            raise GitHubError(None, f"GET {storage}: {error}") from None

    def paginate(self, path: str) -> Iterator[Dict[str, Any]]:
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            items = self.get(f"{path}{separator}per_page=100&page={page}")
            if not items:
                return
            yield from items
            if len(items) < 100:
                return
            page += 1

    def repo(self, suffix: str = "") -> str:
        return f"/repos/{self.repository}{suffix}"

    # What the actions read.
    def releases(self) -> List[Dict[str, Any]]:
        """Every release, drafts included when the token may see them."""
        return list(self.paginate(self.repo("/releases")))

    def tags(self) -> List[str]:
        return [tag["name"] for tag in self.paginate(self.repo("/tags"))]

    def branches(self) -> List[str]:
        return [branch["name"] for branch in self.paginate(self.repo("/branches"))]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102 - hand the redirect back
        return None


def quote(text: str) -> str:
    return urllib.parse.quote(text, safe="")
