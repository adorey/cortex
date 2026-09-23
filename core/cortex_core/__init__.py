"""cortex-core — the one implementation of the Cortex cascade in code (ADR-007).

Everything Cortex computes from the spec lives here: cascade resolution, merge
semantics, role/workflow/character lookup, the capability catalog, prompt assembly
and overlay validation. The runtime and the validator's entry point consume it.

Two rules hold for every module of this package:

- **Standard library only**, Python 3.9 or later — it runs from source, uninstalled.
- **It never imports the runtime.** The runtime depends on the core, not the reverse.
"""

from .catalog import capability_catalog, capability_dirs
from .prompt import LAYER_SEPARATOR, build_system_prompt, layers_for
from .resolver import (
    ADDITIVE_SEPARATOR,
    MergeSemantic,
    character_for_role,
    default_base_root,
    find_role_relpath,
    find_workflow_relpath,
    read_resolved,
    resolve_layer,
    semantic_for,
)

__all__ = [
    "ADDITIVE_SEPARATOR",
    "LAYER_SEPARATOR",
    "MergeSemantic",
    "build_system_prompt",
    "capability_catalog",
    "capability_dirs",
    "character_for_role",
    "default_base_root",
    "find_role_relpath",
    "find_workflow_relpath",
    "layers_for",
    "read_resolved",
    "resolve_layer",
    "semantic_for",
]
