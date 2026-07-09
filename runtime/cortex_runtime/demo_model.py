"""No-dependency model clients — run the full slice locally without a key or SDK (Phase 5).

``DemoModelClient`` lets you smoke-test the entire wire (HTTP → resolve → loop → tools →
persisted state) for free, before any real model is connected. ``ScriptedModelClient`` is
the deterministic test double.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .loop import ModelTurn, ToolCall
from .tools import ToolRegistry


class ScriptedModelClient:
    """Returns pre-baked turns in order — deterministic, ignores prompt/history."""

    def __init__(self, turns: List[ModelTurn]):
        self._turns = list(turns)
        self.calls = 0

    def propose(self, system_prompt: str, history: List[Dict[str, Any]]) -> ModelTurn:
        turn = self._turns[min(self.calls, len(self._turns) - 1)]
        self.calls += 1
        return turn


class DemoModelClient:
    """A canned agent for smoke-testing the wiring with no model: it lists files, posts an
    internal comment, then finalizes — skipping any tool the registry doesn't expose."""

    def __init__(self, registry: ToolRegistry):
        names = set(registry.names())
        steps: List[ModelTurn] = []
        if "list_files" in names:
            steps.append(ModelTurn(tool_calls=[ToolCall("list_files", {})]))
        if "post_internal_comment" in names:
            steps.append(ModelTurn(tool_calls=[ToolCall(
                "post_internal_comment", {"body": "Demo diagnosis: wiring is live, no real model attached."})]))
        steps.append(ModelTurn(final_text="Demo run complete — replace the backend with a real model."))
        self._steps = steps
        self.calls = 0

    def propose(self, system_prompt: str, history: List[Dict[str, Any]]) -> ModelTurn:
        turn = self._steps[min(self.calls, len(self._steps) - 1)]
        self.calls += 1
        return turn
