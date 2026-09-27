# cortex-cli

The `cortex` command — [ADR-008](../docs/adr/ADR-008-cortex-binary.md).

It ships as a native binary, built with PyInstaller from this package and
[cortex-core](../core/README.md): the host needs no Python. This package is never
published on its own.

- **Standard library only**, and the core. The binary embeds nothing else — a test fails if a
  module imports anything more.
- **The core never imports it.** The command depends on the core, not the reverse — a test in
  the core's suite fails if it does.
- **Python 3.11 or later** for a development install, for `tomllib`. The binary embeds its own
  interpreter: the floor binds nobody else.

```bash
cd cli && python3 -m unittest discover -s tests   # nothing to install
pip install -e core -e cli                         # a `cortex` on PATH, from this checkout
```

The tests run the command from source, with nothing but `core/` and `cli/` on `sys.path`. With
`CORTEX_TEST_BINARY` naming a built binary, they run through it instead — which is how CI
checks each binary it builds.

## Version

`cortex --version` prints the version of the release the binary was built from, stamped by the
build from the tag. A source checkout is no release, and prints `0.0.0-dev`.
