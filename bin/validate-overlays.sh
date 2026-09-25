#!/bin/bash
# ============================================================================
# Cortex — validate-overlays.sh
# ============================================================================
#
# Validates the integrity of overlay files in a host project: the Tier 1
# (blocking) and Tier 2 (warnings) checks of ADR-001.
#
# The checks live in cortex-core (core/cortex_core/validate.py, ADR-007). This
# script finds a Python and runs them from this Cortex checkout — there is
# nothing to install.
#
# Usage:
#   ./cortex/bin/validate-overlays.sh                        # check everything
#   ./cortex/bin/validate-overlays.sh --service path/to/svc  # check one service
#   ./cortex/bin/validate-overlays.sh --strict               # warnings → errors
#   ./cortex/bin/validate-overlays.sh --help
#
# Exit codes: 0 = clean, 1 = errors (or warnings in --strict),
#             2 = bad args, or no Python 3.9 or later found
#
# Requires Python 3.9 or later, as python3 or python on PATH — until ADR-008
# ships a native binary that embeds the core.
#
# See: docs/adr/ADR-001-layered-overrides.md, docs/adr/ADR-007-cortex-core.md
# ============================================================================

set -eo pipefail

# --- Paths -----------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORTEX_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$CORTEX_DIR")"

# --- Python ----------------------------------------------------------------
# The version is checked, not only the presence: an old python3 would fail
# later, on syntax, with a traceback instead of an explanation. The probe runs
# under -I too: without it, a sitecustomize.py on PYTHONPATH would run before it
# — code from the project under validation. Python 2 rejects -I and is skipped.
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "validate-overlays.sh needs Python 3.9 or later, as python3 or python on PATH." >&2
    echo "The overlay checks run from cortex-core, in $CORTEX_DIR/core (ADR-007)." >&2
    exit 2
fi

# --- Run -------------------------------------------------------------------
# Python runs under -I (isolated mode): neither the working directory nor PYTHONPATH lands on
# sys.path, and no sitecustomize from the project runs. Without it, validating a project that
# holds, say, an fnmatch.py would execute that file — code from the very project under
# validation, in CI included. The core is then imported from this checkout, first on sys.path:
# the validator runs the same cascade rules as the runtime.
exec "$PYTHON" -I -c 'import sys; sys.path.insert(0, sys.argv.pop(1)); from cortex_core.validate import main; sys.exit(main())' \
    "$CORTEX_DIR/core" --project-root "$PROJECT_DIR" --base-root "$CORTEX_DIR" "$@"
