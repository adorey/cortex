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
# later, on syntax, with a traceback instead of an explanation.
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
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
PYTHONPATH="$CORTEX_DIR/core${PYTHONPATH:+:$PYTHONPATH}" exec "$PYTHON" -m cortex_core.validate \
    --project-root "$PROJECT_DIR" --base-root "$CORTEX_DIR" "$@"
