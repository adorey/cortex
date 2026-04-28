#!/bin/bash
# ============================================================================
# Cortex Setup — Integrates the AI team into your workspace
# ============================================================================
#
# Usage:
#   ./setup.sh                     # Setup in the current workspace
#   ./setup.sh /path/to/project    # Setup in a specific project
#   ./setup.sh --theme h2g2        # Specify a theme (default: h2g2)
#   ./setup.sh --no-personality    # Without the personality layer
#   ./setup.sh --workspace         # Multi-service workspace mode
#   ./setup.sh --tool copilot      # GitHub Copilot: .github/copilot-instructions.md (default)
#   ./setup.sh --tool cursor       # Cursor: .cursor/rules/cortex.mdc
#   ./setup.sh --tool claude       # Claude Code: CLAUDE.md
#   ./setup.sh --tool agents       # Generic (Codex, etc.): AGENTS.md
#   ./setup.sh --tool custom --instructions-file path/to/file  # Custom path
#
# This script:
# 1. Resolves the personality theme (validates folder exists)
# 2. Loads the bootstrap content from cortex/templates/bootstrap-instructions[-workspace].md
# 3. Applies theme substitution and personality strip if requested
# 4. Writes the content to the AI tool's expected file (--tool option)
# 5. Copies project-overview.md and project-context.md templates to fill in
# 6. In --workspace mode: scaffolds project-overview/context.md per service
#
# ============================================================================

set -eo pipefail

# Colours
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

CORTEX_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR=""
THEME="h2g2"
NO_PERSONALITY=false
WORKSPACE_MODE=false
TOOL="copilot"
CUSTOM_INSTRUCTIONS_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --theme)
            THEME="$2"
            shift 2
            ;;
        --no-personality)
            NO_PERSONALITY=true
            shift
            ;;
        --workspace)
            WORKSPACE_MODE=true
            shift
            ;;
        --tool)
            TOOL="$2"
            shift 2
            ;;
        --instructions-file)
            CUSTOM_INSTRUCTIONS_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: ./setup.sh [TARGET_DIR] [--theme THEME] [--no-personality] [--workspace] [--tool TOOL]"
            echo ""
            echo "Options:"
            echo "  TARGET_DIR                    Target directory (default: cortex parent directory)"
            echo "  --theme THEME                 Personality theme to activate (default: h2g2)"
            echo "  --no-personality              Disable the personality layer"
            echo "  --workspace                   Multi-project workspace mode (parent / services structure)"
            echo "  --tool TOOL                   AI tool target (default: copilot)"
            echo "                                  copilot → .github/copilot-instructions.md"
            echo "                                  cursor  → .cursor/rules/cortex.mdc"
            echo "                                  claude  → CLAUDE.md"
            echo "                                  agents  → AGENTS.md"
            echo "                                  custom  → use --instructions-file"
            echo "  --instructions-file PATH      Custom output path (requires --tool custom)"
            echo "  -h, --help                    Display this help"
            exit 0
            ;;
        *)
            TARGET_DIR="$1"
            shift
            ;;
    esac
done

# Determine the target directory
if [ -z "$TARGET_DIR" ]; then
    TARGET_DIR="$(dirname "$CORTEX_DIR")"
fi

echo -e "${BLUE}"
echo "  ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗  ██╗"
echo " ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝"
echo " ██║     ██║   ██║██████╔╝   ██║   █████╗   ╚███╔╝ "
echo " ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝   ██╔██╗ "
echo " ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗██╔╝ ██╗"
echo "  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "${GREEN}🧠 Cortex Setup${NC}"
echo "═══════════════════════════════════════════"
echo ""

# --- 1. Check that the theme exists if personality is enabled ---
if [ "$NO_PERSONALITY" = false ]; then
    THEME_DIR="$CORTEX_DIR/agents/personalities/$THEME"
    if [ ! -d "$THEME_DIR" ]; then
        echo -e "${RED}❌ Theme '$THEME' not found in $CORTEX_DIR/agents/personalities/${NC}"
        echo "   Available themes:"
        ls -1 "$CORTEX_DIR/agents/personalities/" | grep -v README.md | sed 's/^/     - /'
        exit 1
    fi
    echo -e "${GREEN}✅${NC} Personality theme: ${BLUE}$THEME${NC}"
else
    echo -e "${YELLOW}ℹ️${NC}  Personality disabled (roles-only mode)"
fi

# --- 2. Resolve instructions file path based on --tool ---
case "$TOOL" in
    copilot)
        INSTRUCTIONS_FILE="$TARGET_DIR/.github/copilot-instructions.md"
        mkdir -p "$TARGET_DIR/.github"
        ;;
    cursor)
        INSTRUCTIONS_FILE="$TARGET_DIR/.cursor/rules/cortex.mdc"
        mkdir -p "$TARGET_DIR/.cursor/rules"
        ;;
    claude)
        INSTRUCTIONS_FILE="$TARGET_DIR/CLAUDE.md"
        ;;
    agents)
        INSTRUCTIONS_FILE="$TARGET_DIR/AGENTS.md"
        ;;
    custom)
        if [ -z "$CUSTOM_INSTRUCTIONS_FILE" ]; then
            echo -e "${RED}❌ --tool custom requires --instructions-file PATH${NC}"
            exit 1
        fi
        INSTRUCTIONS_FILE="$CUSTOM_INSTRUCTIONS_FILE"
        mkdir -p "$(dirname "$INSTRUCTIONS_FILE")"
        ;;
    *)
        echo -e "${RED}❌ Unknown tool '$TOOL'. Valid values: copilot, cursor, claude, agents, custom${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}✅${NC} AI tool target: ${BLUE}$TOOL${NC} → $INSTRUCTIONS_FILE"

# --- 2bis. Load the bootstrap content from the appropriate template ---
if [ "$WORKSPACE_MODE" = true ]; then
    BOOTSTRAP_TEMPLATE="$CORTEX_DIR/templates/bootstrap-instructions-workspace.md"
else
    BOOTSTRAP_TEMPLATE="$CORTEX_DIR/templates/bootstrap-instructions.md"
fi

if [ ! -f "$BOOTSTRAP_TEMPLATE" ]; then
    echo -e "${RED}❌ Bootstrap template not found: $BOOTSTRAP_TEMPLATE${NC}"
    exit 1
fi

echo -e "${GREEN}✅${NC} Bootstrap template: ${BLUE}$(basename "$BOOTSTRAP_TEMPLATE")${NC}"

INSTRUCTIONS_CONTENT="$(cat "$BOOTSTRAP_TEMPLATE")"

# Strip the personality block if --no-personality
# Templates wrap the personality section in <!-- PERSONALITY:BEGIN --> ... <!-- PERSONALITY:END -->
if [ "$NO_PERSONALITY" = true ]; then
    INSTRUCTIONS_CONTENT="$(echo "$INSTRUCTIONS_CONTENT" | sed '/<!-- PERSONALITY:BEGIN -->/,/<!-- PERSONALITY:END -->/d')"
fi

# --- 2ter. Write the active theme marker (single source of truth, INSIDE cortex) ---
# The marker is a cortex concern (cortex decides which theme to load), so it lives in cortex.
# Cortex's own .gitignore excludes it → each user has their local choice without polluting git.
# Editable at any time post-setup to switch theme without re-running setup.sh.
ACTIVE_THEME_MARKER="$CORTEX_DIR/agents/personalities/.active-theme"
if [ "$NO_PERSONALITY" = true ]; then
    echo "none" > "$ACTIVE_THEME_MARKER"
    echo -e "${GREEN}✅${NC} Active theme marker → ${BLUE}none${NC} (no-personality mode)"
else
    echo "$THEME" > "$ACTIVE_THEME_MARKER"
    echo -e "${GREEN}✅${NC} Active theme marker → ${BLUE}$THEME${NC} (edit cortex/agents/personalities/.active-theme to switch theme later)"
fi

if [ -f "$INSTRUCTIONS_FILE" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  $INSTRUCTIONS_FILE already exists.${NC}"
    read -p "   Replace? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$INSTRUCTIONS_CONTENT" > "$INSTRUCTIONS_FILE"
        echo -e "${GREEN}✅${NC} $INSTRUCTIONS_FILE replaced"
    else
        echo -e "${YELLOW}ℹ️${NC}  File kept as-is"
    fi
else
    echo "$INSTRUCTIONS_CONTENT" > "$INSTRUCTIONS_FILE"
    echo -e "${GREEN}✅${NC} $INSTRUCTIONS_FILE created"
fi

# --- 3. Copy context files to the project root ---
CONTEXT_TEMPLATE="$CORTEX_DIR/templates/project-context.md.template"
OVERVIEW_TEMPLATE="$CORTEX_DIR/templates/project-overview.md.template"
CONTEXT_FILE="$TARGET_DIR/project-context.md"
OVERVIEW_FILE="$TARGET_DIR/project-overview.md"

# project-overview.md
if [ -f "$OVERVIEW_FILE" ]; then
    echo -e "${GREEN}✅${NC} project-overview.md already exists"
else
    if [ -f "$OVERVIEW_TEMPLATE" ]; then
        cp "$OVERVIEW_TEMPLATE" "$OVERVIEW_FILE"
        echo -e "${GREEN}✅${NC} project-overview.md created"
        echo -e "${YELLOW}📝${NC}  → Fill in the vision, actors and business flows: $OVERVIEW_FILE"
    fi
fi

# project-context.md
if [ -f "$CONTEXT_FILE" ]; then
    echo ""
    echo -e "${GREEN}✅${NC} project-context.md already exists at the project root"
    if grep -q "<!-- ex:" "$CONTEXT_FILE" 2>/dev/null; then
        echo -e "${YELLOW}📝 IMPORTANT:${NC} The file is still a template."
        echo "   → Fill it in with your project's tech stack:"
        echo "   → $CONTEXT_FILE"
    fi
else
    if [ -f "$CONTEXT_TEMPLATE" ]; then
        cp "$CONTEXT_TEMPLATE" "$CONTEXT_FILE"
        echo -e "${GREEN}✅${NC} project-context.md created at the project root"
        echo -e "${YELLOW}📝 IMPORTANT:${NC} Fill it in with your project's tech stack:"
        echo "   → $CONTEXT_FILE"
    else
        echo -e "${RED}❌ Template not found: $CONTEXT_TEMPLATE${NC}"
    fi
fi

# Workspace mode: initialise services
if [ "$WORKSPACE_MODE" = true ]; then
    echo ""
    echo -e "${BLUE}ℹ️  Workspace mode — initialising services${NC}"
    echo "   Enter the names of the services to create (empty entry to stop):"
    while true; do
        read -p "   Service name (e.g. api-backend, front-web): " SERVICE_NAME
        if [ -z "$SERVICE_NAME" ]; then
            break
        fi
        SERVICE_DIR="$TARGET_DIR/$SERVICE_NAME"
        mkdir -p "$SERVICE_DIR"
        if [ ! -f "$SERVICE_DIR/project-overview.md" ]; then
            sed "s/<!-- @alias: mon-projet -->/<!-- @alias: $SERVICE_NAME -->/" "$OVERVIEW_TEMPLATE" > "$SERVICE_DIR/project-overview.md"
            echo -e "${GREEN}  ✅${NC} $SERVICE_NAME/project-overview.md"
        fi
        if [ ! -f "$SERVICE_DIR/project-context.md" ]; then
            sed "s/<!-- @alias: mon-projet -->/<!-- @alias: $SERVICE_NAME -->/" "$CONTEXT_TEMPLATE" > "$SERVICE_DIR/project-context.md"
            echo -e "${GREEN}  ✅${NC} $SERVICE_NAME/project-context.md"
        fi
    done
fi

# --- 4. Summary ---
echo ""
echo "═══════════════════════════════════════════"
echo -e "${GREEN}🚀 Cortex is ready!${NC}"
echo ""
echo "   Structure:"
echo "   ├── cortex/agents/roles/            ← Skills (15 roles, 5 categories)"
echo "   ├── cortex/agents/capabilities/     ← Loadable technical capabilities"

if [ "$NO_PERSONALITY" = false ]; then
    echo "   ├── cortex/agents/personalities/$THEME/ ← Personality"
fi

if [ "$WORKSPACE_MODE" = true ]; then
    echo "   ├── project-overview.md            ← Global workspace vision (optional)"
    echo "   ├── project-context.md             ← Shared conventions (optional)"
    echo "   ├── {service}/project-overview.md  ← Service vision (TO FILL IN)"
    echo "   ├── {service}/project-context.md   ← Service stack (TO FILL IN)"
else
    echo "   ├── project-overview.md            ← Vision & business (TO FILL IN)"
    echo "   ├── project-context.md             ← Technical stack (TO FILL IN)"
fi

echo "   └── $INSTRUCTIONS_FILE"
echo ""

if [ "$WORKSPACE_MODE" = true ]; then
    echo "   Workspace mode — target a service with its @alias in your prompt:"
    echo "   → e.g. '@backend Add a pagination endpoint'"
    echo "   → Or let Cortex infer from the active file context"
elif [ "$NO_PERSONALITY" = false ] && [ "$THEME" = "h2g2" ]; then
    echo "   Invoke an agent in your prompt:"
    echo "   → @Hactar for backend"
    echo "   → @Eddie for frontend"
    echo "   → @Marvin for security"
    echo "   → @Slartibartfast for architecture"
else
    echo "   Invoke an agent in your prompt:"
    echo "   → Mention the desired role in your prompt"
fi

echo ""
