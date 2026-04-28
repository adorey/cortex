#!/bin/bash
# ============================================================================
# Cortex — validate-overlays.sh
# ============================================================================
#
# Validates the integrity of overlay files in a host project.
# Implements Tier 1 (blocking) and Tier 2 (warnings) checks from ADR-001.
#
# Usage:
#   ./cortex/bin/validate-overlays.sh                        # check everything
#   ./cortex/bin/validate-overlays.sh --service path/to/svc  # check one service
#   ./cortex/bin/validate-overlays.sh --strict               # warnings → errors
#   ./cortex/bin/validate-overlays.sh --help
#
# Exit codes: 0 = clean, 1 = errors (or warnings in --strict), 2 = bad args
#
# See: docs/adr/ADR-001-layered-overrides.md, docs/extending-layers.md
# ============================================================================

set -eo pipefail

# --- Paths -----------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORTEX_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$CORTEX_DIR")"

# --- Args ------------------------------------------------------------------
SERVICE_FILTER=""
STRICT=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --service PATH     Validate overlays under a specific service folder only
                     (path relative to project root or absolute)
  --strict           Treat warnings as errors (CI-friendly)
  -h, --help         Show this help

Exit codes:
  0   No errors (and no warnings in --strict mode)
  1   Errors detected (or warnings in --strict mode)
  2   Bad arguments

Reference: ADR-001-layered-overrides.md
EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --service) SERVICE_FILTER="$2"; shift 2 ;;
        --strict) STRICT=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# --- Colors ----------------------------------------------------------------
if [ -t 1 ]; then
    GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
    BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
else
    GREEN=''; RED=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi

# --- State -----------------------------------------------------------------
ERRORS=0
WARNINGS=0
CHECKED=0
LAYERS=("roles" "capabilities" "personalities" "workflows")

# --- Helpers ---------------------------------------------------------------
extract_field() {
    # $1 = file, $2 = field name (Base, Scope, Semantic)
    sed -n '/<!-- OVERLAY/,/-->/p' "$1" \
      | grep -E "^[[:space:]]*$2:" \
      | head -1 \
      | sed -E "s/^[[:space:]]*$2:[[:space:]]*//; s/[[:space:]]*$//"
}

report_error() {
    # $1 = relpath, $2 = code, $3 = message
    echo -e "${RED}✗${NC} $1"
    echo -e "  ${RED}$2${NC} — $3"
    ERRORS=$((ERRORS + 1))
}

report_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    echo -e "  ${YELLOW}$2${NC} — $3"
    WARNINGS=$((WARNINGS + 1))
}

report_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

# --- Validation per file ---------------------------------------------------
validate_overlay_file() {
    local file="$1"
    local rel_path="${file#"$PROJECT_DIR"/}"
    CHECKED=$((CHECKED + 1))

    # Tier 1.1 — header presence (or skip if it's a custom addition, not an overlay)
    if ! head -10 "$file" | grep -q '<!-- OVERLAY'; then
        # No OVERLAY header → file is a "custom addition" (e.g. a fully custom theme,
        # a new role/capability that doesn't extend any cortex base).
        # Custom additions are valid; they just aren't overlays. Skip overlay validation.
        echo -e "${BLUE}ℹ${NC} $rel_path (custom addition — no cortex base, skipping overlay checks)"
        return
    fi

    # Tier 1.2 — required fields
    local base scope semantic
    base=$(extract_field "$file" "Base")
    scope=$(extract_field "$file" "Scope")
    semantic=$(extract_field "$file" "Semantic")

    if [ -z "$base" ]; then
        report_error "$rel_path" "MISSING_FIELD" "Base: is required in OVERLAY header"
        return
    fi
    if [ -z "$scope" ]; then
        report_error "$rel_path" "MISSING_FIELD" "Scope: is required in OVERLAY header"
        return
    fi
    if [ -z "$semantic" ]; then
        report_error "$rel_path" "MISSING_FIELD" "Semantic: is required in OVERLAY header"
        return
    fi

    # Tier 1.3 — base exists
    if [ ! -f "$PROJECT_DIR/$base" ]; then
        report_error "$rel_path" "BASE_NOT_FOUND" \
            "Base: '$base' does not exist (typo, or upstream removed it?)"
        return
    fi

    # Tier 1.4 — semantic valid
    case "$semantic" in
        additive|replacement) ;;
        *) report_error "$rel_path" "INVALID_SEMANTIC" \
               "Semantic: must be 'additive' or 'replacement' (got '$semantic')"
           return ;;
    esac

    # Tier 1.5 — replacement only for workflows
    if [ "$semantic" = "replacement" ] && [[ "$file" != *"/agents/workflows/"* ]]; then
        report_error "$rel_path" "REPLACEMENT_OUTSIDE_WORKFLOWS" \
            "Semantic: replacement is only allowed for files under agents/workflows/"
        return
    fi

    # Tier 1.6 — path mirroring (overlay path under agents/ matches base path under cortex/agents/)
    local file_rel_to_agents="${file#*/agents/}"
    local base_rel_to_agents="${base#cortex/agents/}"
    if [ "$file_rel_to_agents" != "$base_rel_to_agents" ]; then
        report_error "$rel_path" "PATH_MIRROR" \
            "overlay path 'agents/$file_rel_to_agents' must mirror base 'cortex/agents/$base_rel_to_agents'"
        return
    fi

    # Tier 2.1 — non-overridable: characters.md
    if [[ "$base" == *"/personalities/"*"/characters.md" ]]; then
        report_error "$rel_path" "NON_OVERRIDABLE" \
            "characters.md is not overridable; fork the theme instead (see docs/creating-a-theme.md)"
        return
    fi

    # Tier 2.2 — layer is known
    local file_layer
    file_layer=$(echo "$file_rel_to_agents" | cut -d/ -f1)
    local layer_known=false
    for known in "${LAYERS[@]}"; do
        [ "$file_layer" = "$known" ] && layer_known=true && break
    done
    if [ "$layer_known" = false ]; then
        report_warning "$rel_path" "UNKNOWN_LAYER" \
            "'$file_layer' is not a known layer (expected: ${LAYERS[*]})"
        # don't return — continue checking
    fi

    # Tier 2.3 — scope vs location coherence
    # Workspace overlays live at PROJECT_DIR/agents/...; service overlays live deeper
    local depth_from_project
    depth_from_project=$(echo "${file#"$PROJECT_DIR/"}" | tr -dc '/' | wc -c)
    # workspace overlay = 3 slashes (agents/{layer}/{...}/file.md → 3 minimum)
    # service overlay = 4+ slashes ({service}/agents/{layer}/{...}/file.md)
    if [[ "$scope" == "workspace"* ]] && [ "$depth_from_project" -gt 3 ]; then
        # likely service-level file with workspace scope → warn
        if [[ "$rel_path" != "agents/"* ]]; then
            report_warning "$rel_path" "SCOPE_MISMATCH" \
                "Scope: '$scope' but file is not at workspace root (agents/...)"
        fi
    fi
    if [[ "$scope" == "service"* ]] && [[ "$rel_path" == "agents/"* ]]; then
        report_warning "$rel_path" "SCOPE_MISMATCH" \
            "Scope: '$scope' but file is at workspace root — should be under {service}/agents/"
    fi

    # Tier 2.4 — additive sections tagging (sample check: at least one section is tagged)
    if [ "$semantic" = "additive" ]; then
        if ! grep -qE '^##.*\(additive\)|^## 🚫 Disabled rules from base' "$file"; then
            report_warning "$rel_path" "SECTIONS_UNTAGGED" \
                "additive overlay should tag at least one section as '(additive)' or use '## 🚫 Disabled rules from base'"
        fi
    fi

    # All good
    report_ok "$rel_path"
}

# --- Discovery -------------------------------------------------------------
declare -a OVERLAY_ROOTS

if [ -n "$SERVICE_FILTER" ]; then
    # Resolve to absolute
    if [[ "$SERVICE_FILTER" = /* ]]; then
        OVERLAY_ROOTS+=("$SERVICE_FILTER")
    else
        OVERLAY_ROOTS+=("$PROJECT_DIR/$SERVICE_FILTER")
    fi
else
    # Workspace-level
    [ -d "$PROJECT_DIR/agents" ] && OVERLAY_ROOTS+=("$PROJECT_DIR")
    # Service-level: any folder containing project-overview.md (excluding cortex itself and the project root)
    while IFS= read -r overview_file; do
        service_dir=$(dirname "$overview_file")
        [ "$service_dir" = "$PROJECT_DIR" ] && continue
        [ "$service_dir" = "$CORTEX_DIR" ] && continue
        [ -d "$service_dir/agents" ] || continue
        OVERLAY_ROOTS+=("$service_dir")
    done < <(find "$PROJECT_DIR" -maxdepth 5 -name "project-overview.md" \
                  -not -path "*/cortex/*" -not -path "*/.git/*" 2>/dev/null)
fi

# --- Run -------------------------------------------------------------------
echo -e "${BOLD}${BLUE}Cortex overlay validator${NC}"
echo "  Project root:  $PROJECT_DIR"
echo "  Cortex dir:    $CORTEX_DIR"
echo "  Strict mode:   $STRICT"
if [ -n "$SERVICE_FILTER" ]; then
    echo "  Service only:  $SERVICE_FILTER"
fi
echo ""

if [ "${#OVERLAY_ROOTS[@]}" -eq 0 ]; then
    echo -e "${YELLOW}ℹ${NC}  No overlay roots found (no agents/ directory at workspace or service level)."
    echo "   Nothing to validate. This is expected if you haven't created overlays yet."
    exit 0
fi

for root in "${OVERLAY_ROOTS[@]}"; do
    rel_root="${root#"$PROJECT_DIR/"}"
    [ -z "$rel_root" ] && rel_root="."
    echo -e "${BOLD}── Scope: $rel_root ──${NC}"
    found_in_root=0
    for layer in "${LAYERS[@]}"; do
        layer_dir="$root/agents/$layer"
        [ -d "$layer_dir" ] || continue
        while IFS= read -r overlay_file; do
            validate_overlay_file "$overlay_file"
            found_in_root=$((found_in_root + 1))
        done < <(find "$layer_dir" -name "*.md" -type f 2>/dev/null)
    done
    [ "$found_in_root" -eq 0 ] && echo "  (no overlay files)"
    echo ""
done

# --- Summary ---------------------------------------------------------------
echo "──────────────────────────────────────────"
echo -e "Checked:  ${BOLD}$CHECKED${NC} files"
if [ "$ERRORS" -gt 0 ]; then
    echo -e "Errors:   ${RED}${BOLD}$ERRORS${NC}"
else
    echo -e "Errors:   ${GREEN}0${NC}"
fi
if [ "$WARNINGS" -gt 0 ]; then
    echo -e "Warnings: ${YELLOW}${BOLD}$WARNINGS${NC}"
else
    echo -e "Warnings: ${GREEN}0${NC}"
fi

if [ "$ERRORS" -gt 0 ]; then
    exit 1
fi
if [ "$STRICT" = true ] && [ "$WARNINGS" -gt 0 ]; then
    echo -e "${RED}Strict mode: warnings count as errors.${NC}"
    exit 1
fi
exit 0
