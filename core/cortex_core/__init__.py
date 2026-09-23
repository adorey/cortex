"""cortex-core — the one implementation of the Cortex cascade in code (ADR-007).

Everything Cortex computes from the spec lives here: cascade resolution, merge
semantics, role/workflow/character lookup, the capability catalog, prompt assembly
and overlay validation. The runtime and the validator's entry point consume it.

Two rules hold for every module of this package:

- **Standard library only**, Python 3.9 or later — it runs from source, uninstalled.
- **It never imports the runtime.** The runtime depends on the core, not the reverse.
"""
