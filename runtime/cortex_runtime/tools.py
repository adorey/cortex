"""Tool registry — the MCP tool surface, each tool tagged with its action kind (§3.3).

In production these wrap MCP servers (issue tracker, DB read-only/anonymised, code host).
Here a tool is just a callable + its ActionKind, so the loop can gate it deterministically
via the ActionPolicy without knowing what it does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .safety import ActionKind


@dataclass
class Tool:
    name: str
    kind: ActionKind
    fn: Callable[..., Any]
    description: str = ""


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> list:
        return sorted(self._tools)
