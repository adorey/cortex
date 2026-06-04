"""Local built-in tools — a minimal MCP-free tool set for the executable slice (Phase 5).

Enough for an observable run against a real working tree, without any external service:
read code, list files, post an internal comment (captured locally). In production these
are replaced by MCP servers (issue tracker, DB, code host); the loop gates them all the
same way, by ``ActionKind``.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from .safety import ActionKind
from .tools import Tool, ToolRegistry


def _safe_path(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root``, refusing any path that escapes the working tree."""
    root_r = Path(root).resolve()
    target = (root_r / rel).resolve()
    if target != root_r and root_r not in target.parents:
        raise ValueError(f"path '{rel}' escapes the workspace root")
    return target


def local_tool_registry(root: Path, comment_sink: Optional[List[str]] = None) -> Tuple[ToolRegistry, List[str]]:
    """Build a registry of local tools bound to ``root``. Returns ``(registry, comment_sink)``
    — internal comments are appended to ``comment_sink`` (a list) so a local run is observable."""
    root = Path(root)
    sink: List[str] = comment_sink if comment_sink is not None else []

    def read_file(path: str, **_):
        return _safe_path(root, path).read_text(encoding="utf-8")

    def list_files(subdir: str = ".", **_):
        base = _safe_path(root, subdir)
        return sorted(str(p.relative_to(root)) for p in base.rglob("*") if p.is_file())

    def post_internal_comment(body: str, **_):
        sink.append(body)
        return f"internal comment posted ({len(body)} chars)"

    reg = ToolRegistry()
    reg.register(Tool("read_file", ActionKind.CODE_READ, read_file, "Read a file from the working tree"))
    reg.register(Tool("list_files", ActionKind.CODE_READ, list_files, "List files under the working tree"))
    reg.register(Tool("post_internal_comment", ActionKind.INTERNAL_COMMENT, post_internal_comment,
                      "Post an internal comment with the diagnosis"))
    return reg, sink
