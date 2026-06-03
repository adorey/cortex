"""cortex-runtime — the deployable engine that consumes the Cortex spec (ADR-002).

The firewall: this package depends on the spec; the spec never depends on it.
"""

from .context import (
    capability_catalog,
    derive_capabilities,
    read_project_context,
)
from .resolver import (
    MergeSemantic,
    build_system_prompt,
    character_for_role,
    find_role_relpath,
    find_workflow_relpath,
    layers_for,
    read_resolved,
    resolve_layer,
    semantic_for,
)
from .agent_client import (
    AnthropicAgentClient,
    ClaudeCodeCliClient,
    interpret_response,
    tool_schemas,
)
from .demo_model import DemoModelClient, ScriptedModelClient
from .local_tools import local_tool_registry
from .loop import AgentLoop, ModelClient, ModelTurn, RunOutcome, ToolCall
from .runtime import Runtime, RuntimeConfig, build_runtime, make_model_client
from .secret_provider import (
    ChainSecretProvider,
    DotenvSecretProvider,
    EnvSecretProvider,
    SecretNotFound,
    SecretProvider,
    local_secret_provider,
    parse_dotenv,
)
from .run import ResolvedRun, RunRequest, resolve_run
from .session import SessionResult, mark_human_reply, run_session
from .state_store import (
    AuditEntry,
    InMemoryStateStore,
    PostgresStateStore,
    RunRecord,
    SqliteStateStore,
    StateStore,
    local_state_store,
)
from .safety import (
    SAFE_DEFAULT_ACTIONS,
    ActionKind,
    ActionPolicy,
    ConversationState,
    StateMachine,
)
from .tools import Tool, ToolRegistry

__all__ = [
    # resolver
    "MergeSemantic",
    "resolve_layer",
    "semantic_for",
    "read_resolved",
    "character_for_role",
    "find_role_relpath",
    "find_workflow_relpath",
    "layers_for",
    "build_system_prompt",
    # context
    "capability_catalog",
    "read_project_context",
    "derive_capabilities",
    # run
    "RunRequest",
    "ResolvedRun",
    "resolve_run",
    # safety rails
    "ActionKind",
    "ActionPolicy",
    "SAFE_DEFAULT_ACTIONS",
    "ConversationState",
    "StateMachine",
    # tools + loop
    "Tool",
    "ToolRegistry",
    "AgentLoop",
    "ModelClient",
    "ModelTurn",
    "ToolCall",
    "RunOutcome",
    # secrets (§3.6)
    "SecretProvider",
    "SecretNotFound",
    "EnvSecretProvider",
    "DotenvSecretProvider",
    "ChainSecretProvider",
    "local_secret_provider",
    "parse_dotenv",
    # agent SDK adapter (§3.3 boundary)
    "AnthropicAgentClient",
    "ClaudeCodeCliClient",
    "interpret_response",
    "tool_schemas",
    # no-dep model clients (Phase 5)
    "DemoModelClient",
    "ScriptedModelClient",
    # executable slice (Phase 5)
    "Runtime",
    "RuntimeConfig",
    "build_runtime",
    "make_model_client",
    "local_tool_registry",
    # persistence / operational state (ADR-003)
    "StateStore",
    "InMemoryStateStore",
    "SqliteStateStore",
    "PostgresStateStore",
    "local_state_store",
    "RunRecord",
    "AuditEntry",
    # session orchestration (§3.3 wiring)
    "run_session",
    "mark_human_reply",
    "SessionResult",
]

__version__ = "0.0.1"
