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
from .agent_client import AnthropicAgentClient, interpret_response, tool_schemas
from .loop import AgentLoop, ModelClient, ModelTurn, RunOutcome, ToolCall
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
    "interpret_response",
    "tool_schemas",
]

__version__ = "0.0.1"
