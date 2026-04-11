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
#
# Ce script :
# 1. Vérifie le thème de personnalité
# 2. Génère .github/copilot-instructions.md (bootstrap IA)
# 3. Copie project-context.md (template à remplir)
# 4. Configure .vscode/settings.json (injection personnalité Copilot)
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
        -h|--help)
            echo "Usage: ./setup.sh [TARGET_DIR] [--theme THEME] [--no-personality] [--workspace]"
            echo ""
            echo "Options:"
            echo "  TARGET_DIR          Target directory (default: cortex parent directory)"
            echo "  --theme THEME       Personality theme to activate (default: h2g2)"
            echo "  --no-personality    Disable the personality layer"
            echo "  --workspace         Multi-project workspace mode (parent / services structure)"
            echo "  -h, --help          Display this help"
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

# --- 2. Generate copilot-instructions.md ---
GITHUB_DIR="$TARGET_DIR/.github"
INSTRUCTIONS_FILE="$GITHUB_DIR/copilot-instructions.md"

mkdir -p "$GITHUB_DIR"

# Build the content
INSTRUCTIONS_CONTENT="# Cortex AI Team

## Bootstrap (MANDATORY at the start of every new conversation)

At the start of every conversation, you MUST read these files in the order listed.
NEVER respond without having first read and integrated these files.

### Step 1 — Project context
Read \`project-context.md\` (at the project root) to learn the stack, conventions and business rules."

if [ "$NO_PERSONALITY" = false ]; then
    if [ -n "$PM_CHARACTER" ] && [ -n "$PM_FILE" ]; then
        # Mode résolu : on nomme directement le personnage
        INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

### Étape 2 — Personnalité active
Lis ces fichiers pour découvrir et adopter TON identité :
1. \`cortex/agents/personalities/$THEME/theme.md\` — Règles globales du thème $(echo "$THEME" | tr '[:lower:]' '[:upper:]')
2. \`cortex/agents/personalities/$THEME/characters.md\` — Table de correspondance rôle → personnage
3. \`cortex/agents/personalities/$THEME/$PM_FILE\` — **C'est TOI.** Tu es $PM_CHARACTER, le Prompt Manager.

**Applique IMMÉDIATEMENT** : citation signature en début de réponse, ton analytique, références $(echo "$THEME" | tr '[:lower:]' '[:upper:]'), style de communication du personnage."
    else
        # Mode générique : le personnage n'a pas pu être résolu
        INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

### Step 2 — Active personality
Read these files to discover YOUR identity:
1. \`cortex/agents/personalities/$THEME/theme.md\` — Global rules for the active theme
2. \`cortex/agents/personalities/$THEME/characters.md\` — Role to character mapping table
3. In this table, find the character assigned to the \`prompt-manager\` role — **that is YOU**
4. Read that character's individual card in \`cortex/agents/personalities/$THEME/\`
5. Immediately adopt this identity: tone, quotes, communication style"
    fi
fi

INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

### Step 3 — Prompt Manager role
Read \`cortex/agents/roles/prompt-manager.md\` — This is your default working protocol.
You are the Prompt Manager. On every request:
1. **Analyse** the prompt (clarity, completeness, ambiguities)
2. **Lookup workflow** — Search for a workflow matching the context:
   - First in \`agents/workflows/\` at the project root (specific, higher priority)
   - Then in \`cortex/agents/workflows/\` (generic)
   - If found: announce the activated workflow and orchestrate its steps
   - If not found: fall back to classic dispatch
   - If a recurring case has no workflow: suggest creating one
3. **Dispatch** to the appropriate expert (consult \`characters.md\` for the role to character mapping)
4. **Adopt** the dispatched expert's role and personality (read their card in \`roles/\` and their character card)
5. **Load capabilities**: read the \`🔌 Capabilities\` section of the role card, cross-reference with the stack in \`project-context.md\`, load the corresponding files from \`cortex/agents/capabilities/\`
6. **Produce** the technical response in the character's style
7. **Propose** archiving at the end of the task

## References (read on demand depending on context)
- **Agent roles:** \`cortex/agents/roles/\` — Skill cards by specialty
- **Technical capabilities:** \`cortex/agents/capabilities/\` — Loadable skills by category (languages, frameworks, databases, infrastructure, security)
- **Generic workflows:** \`cortex/agents/workflows/\` — Multi-agent orchestration templates
- **Project workflows:** \`agents/workflows/\` — Project-specific workflows (higher priority)"

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

echo "   └── .github/copilot-instructions.md   ← Auto-generated"
echo ""

if [ "$WORKSPACE_MODE" = true ]; then
    echo "   Workspace mode — target a service with its @alias in your prompt:"
    echo "   → e.g. '@backend Add a pagination endpoint'"
    echo "   → Or let Cortex infer from the files open in the IDE"
elif [ "$NO_PERSONALITY" = false ] && [ "$THEME" = "h2g2" ]; then
    echo "   Invoke an agent in your IDE:"
    echo "   → @Hactar for backend"
    echo "   → @Eddie for frontend"
    echo "   → @Marvin for security"
    echo "   → @Slartibartfast for architecture"
else
    echo "   Invoke an agent in your IDE:"
    echo "   → Mention the desired role in your prompt"
fi

echo ""
