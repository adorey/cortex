"""Agent SDK adapter — the boundary where a real model plugs into the loop (ADR-002 §3.3).

``AnthropicAgentClient`` implements the ``ModelClient`` protocol by calling the Anthropic
Messages API, pulling its key from a ``SecretProvider`` (§3.6). It is the integration point
the ADR calls "EMBED an agent SDK": we do not reimplement the loop, we plug the model in.

Runtime note: this needs the ``anthropic`` package + a live key, so it is NOT exercised by
the test suite (the import is lazy; tests cover the pure translation helpers instead). The
production-grade path may instead let the Agent SDK run its OWN loop with our ActionPolicy
attached as a tool-permission callback; this adapter is the minimal reference.

The two pure, testable pieces — ``tool_schemas`` and ``interpret_response`` — are the
SDK-agnostic translation surface and carry the real logic.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .loop import ModelTurn, ToolCall
from .secret_provider import SecretProvider
from .tools import ToolRegistry


def tool_schemas(registry: ToolRegistry) -> List[Dict[str, Any]]:
    """Render the registry as Anthropic tool definitions. Args are unconstrained (the
    runtime gates by ActionKind, not by JSON schema), so a permissive object is used."""
    return [
        {
            "name": tool.name,
            "description": tool.description or tool.kind.value,
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": True},
        }
        for tool in registry.tools()
    ]


def _battr(block: Any, attr: str, default: Any = None) -> Any:
    """Read an attribute from a content block whether it's a dict or an SDK object."""
    if isinstance(block, dict):
        return block.get(attr, default)
    return getattr(block, attr, default)


def interpret_response(content_blocks: List[Any]) -> ModelTurn:
    """Translate a model response's content blocks into a ``ModelTurn``.

    If any ``tool_use`` block is present, the turn is a tool-call turn (the loop executes
    and gates them); otherwise the concatenated ``text`` blocks are the final answer.
    """
    tool_calls: List[ToolCall] = []
    texts: List[str] = []
    for block in content_blocks:
        kind = _battr(block, "type")
        if kind == "tool_use":
            tool_calls.append(ToolCall(name=_battr(block, "name"), args=_battr(block, "input") or {}))
        elif kind == "text":
            texts.append(_battr(block, "text") or "")

    if tool_calls:
        return ModelTurn(tool_calls=tool_calls)
    return ModelTurn(final_text="".join(texts))


class AnthropicAgentClient:
    """A ``ModelClient`` backed by the Anthropic Messages API.

    Reference adapter: the (system_prompt, history) → messages mapping below is deliberately
    simple (text-only tool results, no tool_use/tool_result id pairing). A production loop
    should delegate that bookkeeping to the Agent SDK.
    """

    def __init__(self, registry: ToolRegistry, secrets: SecretProvider,
                 model: str = "claude-opus-4-8", max_tokens: int = 4096,
                 secret_name: str = "llm_key"):
        try:
            import anthropic  # lazy: keeps the package importable without the SDK
        except ImportError as exc:  # pragma: no cover - integration-only
            raise ImportError("AnthropicAgentClient requires the 'anthropic' package") from exc
        self._client = anthropic.Anthropic(api_key=secrets.get(secret_name))
        self._registry = registry
        self._model = model
        self._max_tokens = max_tokens

    def propose(self, system_prompt: str, history: List[Dict[str, Any]]) -> ModelTurn:  # pragma: no cover
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            tools=tool_schemas(self._registry),
            messages=_to_messages(history),
        )
        return interpret_response(response.content)


def _to_messages(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:  # pragma: no cover
    """Minimal reference mapping of the loop's generic history to Anthropic messages.

    Simplified on purpose (see class docstring): inputs and tool results become user turns,
    agent text becomes an assistant turn. Not id-paired tool_use/tool_result blocks.
    """
    messages: List[Dict[str, Any]] = []
    for entry in history:
        role = entry.get("role")
        if role == "input":
            messages.append({"role": "user", "content": str(entry.get("content"))})
        elif role in ("tool-result", "tool-error"):
            messages.append({"role": "user",
                             "content": f"[{entry.get('tool')}] {entry.get('content')}"})
        elif role == "agent":
            messages.append({"role": "assistant", "content": str(entry.get("content"))})
    return messages
