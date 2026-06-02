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
from .run import ResolvedRun, RunRequest, resolve_run

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
]

__version__ = "0.0.1"
