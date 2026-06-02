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


# Map our agnostic ActionKind autonomy onto the Claude Code CLI's built-in tool names.
# This is how per-request autonomy is enforced in the CLI backend: the CLI owns the loop and
# its own tools, so we gate by whitelisting via --allowedTools (read-only by default).
_CLI_TOOLS_BY_ACTION = {
    "code-read": ["Read", "Grep", "Glob"],
    "code-write": ["Edit", "Write"],
}


def cli_allowed_tools(action_kinds: List[str]) -> str:
    """Render allowed ActionKinds as a comma-separated Claude Code --allowedTools value.
    Only actions with a built-in CLI equivalent map (reads/writes); db/git/issue actions have
    no built-in tool and would be MCP servers later."""
    tools: List[str] = []
    for kind in action_kinds:
        for tool in _CLI_TOOLS_BY_ACTION.get(kind, []):
            if tool not in tools:
                tools.append(tool)
    return ",".join(tools)


def build_cli_argv(prompt: str, *, system_prompt: str, model: str, allowed_tools: str,
                   cli: str = "claude", output_format: str = "json",
                   permission_mode: Optional[str] = None) -> List[str]:
    """Build the `claude -p` argv. Pure (no subprocess) so it can be unit-tested."""
    argv = [cli, "-p", prompt,
            "--append-system-prompt", system_prompt,
            "--model", model,
            "--output-format", output_format]
    if allowed_tools:
        argv += ["--allowedTools", allowed_tools]
    if permission_mode:
        argv += ["--permission-mode", permission_mode]
    return argv


def parse_cli_result(stdout: str):
    """Parse `claude -p --output-format json` stdout → (final_text, usage_dict)."""
    import json
    data = json.loads(stdout)
    usage = {"total_cost_usd": data.get("total_cost_usd"), **(data.get("usage") or {})}
    return data.get("result", ""), usage


class ClaudeCodeCliClient:
    """A ``ModelClient`` backed by the **Claude Code CLI subprocess**, authenticated via a
    **Pro/Max subscription** — the only supported way to use the subscription (instead of a
    per-token API key) for automated runs.

    Important (verified): the Claude *Agent SDK* (Python library) does NOT allow subscription
    auth — Anthropic restricts the SDK to API keys. Only the Claude *Code CLI* can use a
    subscription, via a headless OAuth token (`claude setup-token` → CLAUDE_CODE_OAUTH_TOKEN).

    Shape: `claude -p` runs its OWN full agentic loop and returns the final text, so this client
    is a **one-shot agent** — ``propose`` runs the CLI once and returns the result as
    ``final_text`` (our AgentLoop then resolves in one turn). Per-request autonomy maps to the
    CLI's ``--allowedTools`` (read-only by default); the resolved system prompt is appended via
    ``--append-system-prompt``; the run executes in the bound working tree (``cwd``).

    Caveats: draws on the (interactive-oriented) subscription quota — fine for local testing,
    not 24/7 multi-tenant prod (use api keys / the gateway §3.5). ANTHROPIC_API_KEY would
    override the subscription token, so it is removed from the subprocess env.

    Not exercised by the test suite (needs the CLI + a login); the pure helpers above are tested.
    Setup: see runtime/docs/claude-cli-setup.md.
    """

    def __init__(self, model: str = "claude-opus-4-8", root=None, allowed_tools: str = "Read,Grep,Glob",
                 cli: str = "claude", permission_mode: Optional[str] = None):
        import shutil
        if shutil.which(cli) is None:  # pragma: no cover - integration-only
            raise FileNotFoundError(
                f"'{cli}' CLI not found. Install it (npm i -g @anthropic-ai/claude-code) and run "
                "`claude setup-token` to authenticate with your Pro/Max subscription."
            )
        self._model = model
        self._root = root
        self._allowed_tools = allowed_tools
        self._cli = cli
        self._permission_mode = permission_mode
        self.last_usage: Optional[Dict[str, Any]] = None

    def propose(self, system_prompt: str, history: List[Dict[str, Any]]) -> ModelTurn:  # pragma: no cover
        import os
        import subprocess

        task = _task_from_history(history)
        argv = build_cli_argv(task, system_prompt=system_prompt, model=self._model,
                              allowed_tools=self._allowed_tools, cli=self._cli,
                              permission_mode=self._permission_mode)

        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)        # must not override the subscription token
        env.setdefault("DISABLE_TELEMETRY", "1")

        proc = subprocess.run(argv, cwd=self._root, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI failed (exit {proc.returncode}): {proc.stderr.strip()}")
        text, self.last_usage = parse_cli_result(proc.stdout)
        return ModelTurn(final_text=text)


def _task_from_history(history: List[Dict[str, Any]]) -> str:  # pragma: no cover
    import json
    for entry in history:
        if entry.get("role") == "input":
            content = entry.get("content")
            return content if isinstance(content, str) else json.dumps(content)
    return ""


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
