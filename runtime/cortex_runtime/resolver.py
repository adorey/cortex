"""The runtime's view of the cascade (ADR-002 §3.1).

The cascade lives in cortex-core (ADR-007): resolution, merge semantics, lookups and prompt
assembly are re-exported here, so every name this module offered keeps working.
"""

from cortex_core.prompt import LAYER_SEPARATOR, build_system_prompt, layers_for  # noqa: F401
from cortex_core.resolver import (  # noqa: F401 — re-exported, part of this module's API
    ADDITIVE_SEPARATOR,
    MergeSemantic,
    character_for_role,
    find_role_relpath,
    find_workflow_relpath,
    read_resolved,
    resolve_layer,
    semantic_for,
)
