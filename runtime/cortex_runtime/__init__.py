"""cortex-runtime — the deployable engine that consumes the Cortex spec (ADR-002).

The firewall: this package depends on the spec; the spec never depends on it.
"""

from .resolver import (
    MergeSemantic,
    build_system_prompt,
    character_for_role,
    layers_for,
    read_resolved,
    resolve_layer,
    semantic_for,
)

__all__ = [
    "MergeSemantic",
    "resolve_layer",
    "semantic_for",
    "read_resolved",
    "character_for_role",
    "layers_for",
    "build_system_prompt",
]

__version__ = "0.0.1"
