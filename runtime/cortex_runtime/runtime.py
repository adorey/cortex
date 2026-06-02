"""The executable vertical slice — assembles the bricks into a runnable engine (Phase 5).

``Runtime`` ties resolution (the spec) to execution (the loop + tools + state). It is the
piece that turns `POST /run` from "resolve a bundle" into "actually run the agent":

    resolve_run → build tools (for the bound root) → pick a ModelClient (by config)
    → AgentLoop with the request's autonomy → run_session (durable state + audit)

The model backend is swappable by config — ``demo`` (no deps, free, smoke-tests the wire),
``claude-cli`` (Pro/Max subscription via the Claude Code CLI, for local testing — the Agent
SDK itself cannot use a subscription), ``anthropic-api`` (an API key, for the deployed service).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from .app import WorkspaceConfig, build_run_request
from .demo_model import DemoModelClient
from .local_tools import local_tool_registry
from .loop import AgentLoop, ModelClient
from .run import ResolvedRun, resolve_run
from .safety import ActionPolicy
from .secret_provider import SecretProvider, local_secret_provider
from .session import run_session
from .state_store import InMemoryStateStore, StateStore
from .tools import ToolRegistry

DEFAULT_MODEL = "claude-opus-4-8"


def make_model_client(backend: str, registry: ToolRegistry,
                      secrets: Optional[SecretProvider] = None,
                      model_id: Optional[str] = None,
                      root=None, allowed_actions: Optional[list] = None) -> ModelClient:
    """Build the model client for a backend. ``demo`` needs nothing; the real backends are
    imported lazily so the engine stays install-free until one is actually used."""
    if backend == "demo":
        return DemoModelClient(registry)
    if backend == "claude-cli":
        # Pro/Max subscription via the Claude Code CLI (CLAUDE_CODE_OAUTH_TOKEN). The CLI owns
        # the loop + its own tools; our per-request autonomy maps to --allowedTools.
        from .agent_client import ClaudeCodeCliClient, cli_allowed_tools
        return ClaudeCodeCliClient(model=model_id or DEFAULT_MODEL, root=root,
                                   allowed_tools=cli_allowed_tools(allowed_actions or []))
    if backend == "anthropic-api":
        from .agent_client import AnthropicAgentClient
        if secrets is None:
            raise ValueError("anthropic-api backend requires a SecretProvider (llm_key)")
        return AnthropicAgentClient(registry, secrets, model=model_id or DEFAULT_MODEL)
    raise ValueError(f"unknown model backend: {backend}")


@dataclass
class RuntimeConfig:
    workspaces: Mapping[str, WorkspaceConfig]
    store: StateStore
    manifest: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    model_backend: str = "demo"
    secrets: Optional[SecretProvider] = None
    max_iterations: int = 12


class Runtime:
    def __init__(self, config: RuntimeConfig):
        self.cfg = config

    def _workspace(self, name: str) -> WorkspaceConfig:
        if name not in self.cfg.workspaces:
            raise KeyError(name)
        return self.cfg.workspaces[name]

    def resolve(self, payload: Mapping[str, Any], alias: Optional[Mapping[str, Any]] = None) -> ResolvedRun:
        """Resolution only — the identity bundle, no execution (used by `POST /resolve`)."""
        req = build_run_request(payload, alias)
        wcfg = self._workspace(req.workspace)
        return resolve_run(req, wcfg.root, wcfg.theme)

    def run(self, payload: Mapping[str, Any], alias: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Resolve then EXECUTE the agentic loop with durable state + audit."""
        req = build_run_request(payload, alias)
        wcfg = self._workspace(req.workspace)
        resolved = resolve_run(req, wcfg.root, wcfg.theme)

        registry, comments = local_tool_registry(wcfg.root)
        model = make_model_client(self.cfg.model_backend, registry, self.cfg.secrets, req.model,
                                  root=wcfg.root, allowed_actions=resolved.allowed_actions)
        loop = AgentLoop(registry, ActionPolicy.from_names(req.autonomy), self.cfg.max_iterations)
        subject = req.subject or req.input.get("issue") or "default"

        result = run_session(
            loop, model, self.cfg.store,
            workspace=req.workspace, role=req.role, subject=subject,
            system_prompt=resolved.system_prompt, initial_input=req.input, model_id=req.model,
        )

        if result.skipped:
            return {"skipped": True, "reason": result.reason, "subject": subject}
        o = result.outcome
        return {
            "skipped": False,
            "run_id": result.run_id,
            "subject": subject,
            "state": o.state.value,
            "iterations": o.iterations,
            "actions_taken": o.actions_taken,
            "gated_action": o.gated_action,
            "final_text": o.final_text,
            "comments": list(comments),
            "allowed_actions": resolved.allowed_actions,
        }


def build_runtime(workspaces: Mapping[str, WorkspaceConfig], *,
                  store: Optional[StateStore] = None,
                  manifest: Optional[Mapping[str, Mapping[str, Any]]] = None,
                  model_backend: str = "demo",
                  secrets: Optional[SecretProvider] = None,
                  max_iterations: int = 12) -> Runtime:
    """Convenience builder. Defaults: in-memory store, demo backend, local secrets."""
    return Runtime(RuntimeConfig(
        workspaces=workspaces,
        store=store or InMemoryStateStore(),
        manifest=dict(manifest or {}),
        model_backend=model_backend,
        secrets=secrets if secrets is not None else local_secret_provider(),
        max_iterations=max_iterations,
    ))
