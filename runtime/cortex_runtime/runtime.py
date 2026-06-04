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


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def make_model_client(backend: str, registry: ToolRegistry,
                      secrets: Optional[SecretProvider] = None,
                      model_id: Optional[str] = None,
                      root=None, allowed_actions: Optional[list] = None,
                      mcp_servers: Optional[dict] = None,
                      mcp_bindings: Optional[dict] = None,
                      timeout: int = 600) -> ModelClient:
    """Build the model client for a backend. ``demo`` needs nothing; the real backends are
    imported lazily so the engine stays install-free until one is actually used. ``timeout``
    caps a single model/agent call so a hung run fails cleanly instead of blocking forever."""
    if backend == "demo":
        return DemoModelClient(registry)
    if backend == "claude-cli":
        # Pro/Max subscription via the Claude Code CLI (CLAUDE_CODE_OAUTH_TOKEN). The CLI owns
        # the loop + its own tools; our per-request autonomy maps to --allowedTools, and the
        # workspace's MCP servers (e.g. Jira) are passed via --mcp-config.
        from .agent_client import ClaudeCodeCliClient, cli_allowed_tools
        return ClaudeCodeCliClient(model=model_id or DEFAULT_MODEL, root=root,
                                   allowed_tools=cli_allowed_tools(allowed_actions or [], mcp_bindings),
                                   mcp_servers=mcp_servers, timeout=timeout)
    if backend == "anthropic-api":
        from .agent_client import AnthropicAgentClient
        if secrets is None:
            raise ValueError("anthropic-api backend requires a SecretProvider (llm_key)")
        return AnthropicAgentClient(registry, secrets, model=model_id or DEFAULT_MODEL, timeout=timeout)
    raise ValueError(f"unknown model backend: {backend}")


@dataclass
class RuntimeConfig:
    workspaces: Mapping[str, WorkspaceConfig]
    store: StateStore
    manifest: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    # Webhook bindings (ADR-002 §3.7, ADR-004 §3.1): {source → {tenant, role, workflow?,
    # subject_path}}. Host-declared, agnostic — `subject_path` is a generic dotted lookup into
    # the provider payload; the engine never interprets a specific provider.
    webhooks: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    model_backend: str = "demo"
    secrets: Optional[SecretProvider] = None
    max_iterations: int = 12
    run_timeout: int = 600          # per-call timeout (s) — kills a hung agent run
    max_concurrent_runs: int = 4    # async worker-pool size / concurrency cap (ADR-005 §3.3)
    max_pending_runs: int = 100     # bounded queue → backpressure (429) when full


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

    def _subject(self, req) -> str:
        return req.subject or req.input.get("issue") or "default"

    @staticmethod
    def new_run_id() -> str:
        """A fresh run id, mintable BEFORE :meth:`prepare` — so the boundary can reserve it as
        an idempotency claim before any DB record or model call exists (ADR-004 §3.3)."""
        import uuid
        return uuid.uuid4().hex

    def run(self, payload: Mapping[str, Any], alias: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Resolve then EXECUTE the agentic loop synchronously (durable state + audit)."""
        return self._execute(build_run_request(payload, alias))

    def prepare(self, payload: Mapping[str, Any], alias: Optional[Mapping[str, Any]] = None,
                run_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate + create a **queued** run record and return its id, WITHOUT executing
        (ADR-005). The async API returns this immediately (202); a worker then calls
        :meth:`execute`. ``run_id`` lets the caller supply a pre-minted id (an idempotency
        claim). Validation (unknown workspace/role) still fails fast, synchronously."""
        req = build_run_request(payload, alias)
        self._workspace(req.workspace)        # validate now → 404 before enqueueing
        subject = self._subject(req)
        run_id = self.cfg.store.start_run(req.workspace, req.role, subject, req.model, run_id=run_id)
        return {"run_id": run_id, "subject": subject}

    def execute(self, job: Mapping[str, Any]) -> Dict[str, Any]:
        """The job-queue handler: run a previously :meth:`prepare`d job by its ``run_id``."""
        req = build_run_request(job["payload"], job.get("alias"))
        return self._execute(req, run_id=job["run_id"])

    def build_queue(self):
        """An in-process job queue wired to :meth:`execute`, sized from the config (ADR-005).
        A multi-node deployment swaps in a broker-backed queue with the same handler."""
        from .job_queue import InProcessJobQueue
        return InProcessJobQueue(self.execute, max_workers=self.cfg.max_concurrent_runs,
                                 max_pending=self.cfg.max_pending_runs)

    def _execute(self, req, run_id: Optional[str] = None) -> Dict[str, Any]:
        wcfg = self._workspace(req.workspace)
        resolved = resolve_run(req, wcfg.root, wcfg.theme)

        registry, comments = local_tool_registry(wcfg.root)
        model = make_model_client(self.cfg.model_backend, registry, self.cfg.secrets, req.model,
                                  root=wcfg.root, allowed_actions=resolved.allowed_actions,
                                  mcp_servers=wcfg.mcp_servers, mcp_bindings=wcfg.mcp_bindings,
                                  timeout=self.cfg.run_timeout)
        loop = AgentLoop(registry, ActionPolicy.from_names(req.autonomy), self.cfg.max_iterations)
        subject = self._subject(req)

        result = run_session(
            loop, model, self.cfg.store,
            workspace=req.workspace, role=req.role, subject=subject,
            system_prompt=resolved.system_prompt, initial_input=req.input, model_id=req.model,
            handoff=req.handoff, force=req.force, at=_now(), run_id=run_id,
        )

        if result.skipped:
            return {"skipped": True, "reason": result.reason, "subject": subject}
        if result.error:  # the run was recorded as failed; surface it without a raw 500
            return {"failed": True, "error": result.error, "run_id": result.run_id, "subject": subject}
        o = result.outcome
        return {
            "skipped": False,
            "failed": False,
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
                  webhooks: Optional[Mapping[str, Mapping[str, Any]]] = None,
                  model_backend: str = "demo",
                  secrets: Optional[SecretProvider] = None,
                  max_iterations: int = 12,
                  run_timeout: int = 600,
                  max_concurrent_runs: int = 4,
                  max_pending_runs: int = 100) -> Runtime:
    """Convenience builder. Defaults: in-memory store, demo backend, local secrets."""
    return Runtime(RuntimeConfig(
        workspaces=workspaces,
        store=store or InMemoryStateStore(),
        manifest=dict(manifest or {}),
        webhooks=dict(webhooks or {}),
        model_backend=model_backend,
        secrets=secrets if secrets is not None else local_secret_provider(),
        max_iterations=max_iterations,
        run_timeout=run_timeout,
        max_concurrent_runs=max_concurrent_runs,
        max_pending_runs=max_pending_runs,
    ))
