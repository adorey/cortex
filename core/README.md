# cortex-core

The one implementation of the Cortex cascade in code — [ADR-007](../docs/adr/ADR-007-cortex-core.md).

Everything Cortex computes from the spec lives here: resolving a layer file through the
cascade, applying its merge semantic, finding a role, a workflow or a character, listing the
capabilities the cascade offers, assembling an agent's system prompt, and validating overlays.
The [runtime](../runtime/README.md) and `bin/validate-overlays.sh` consume it.

- **Standard library only, Python 3.9 or later.** It runs from source with nothing installed —
  which is what lets a host project validate its overlays from the Cortex checkout.
- **It never imports the runtime.** A test fails if it does.

```bash
cd core && python3 -m unittest discover -s tests   # nothing to install
pip install -e core                                 # to use it from another package
```

## Two roots

The base of the cascade is located by a `base_root`, the overlays by the project root:

```text
{base_root}/agents/{layer}/{file}                ← base      (base_root defaults to {project_root}/cortex)
{project_root}/agents/{layer}/{file}             ← workspace overlay
{project_root}/{service}/agents/{layer}/{file}   ← service overlay
```

Leaving `base_root` out gives the layout every host project uses today. Setting it to the
project root resolves a repository that is its own base — Cortex itself.
