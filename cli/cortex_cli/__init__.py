"""cortex-cli — the ``cortex`` command (ADR-008).

Argument parsing, the store, ``cortex sync`` and ``cortex init`` live here; the cascade does not.
Everything the command computes from the spec, it asks ``cortex_core`` for.

- **Standard library only**, and the core: the binary embeds nothing else.
- **The core never imports it.** The CLI depends on the core, not the reverse — a test enforces it.
"""

from .version import VERSION

__all__ = ["VERSION"]
