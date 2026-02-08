#!/bin/bash
# ============================================================================
# Cortex Setup — Intègre l'équipe IA dans votre workspace
# ============================================================================
#
# Usage :
#   ./setup.sh                     # Setup dans le workspace courant
#   ./setup.sh /chemin/vers/projet # Setup dans un projet spécifique
#   ./setup.sh --theme h2g2        # Spécifier un thème (défaut: h2g2)
#   ./setup.sh --no-personality    # Sans couche personnalité
#
# ============================================================================

set -euo pipefail

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

CORTEX_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR=""
THEME="h2g2"
NO_PERSONALITY=false

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
        -h|--help)
            echo "Usage: ./setup.sh [TARGET_DIR] [--theme THEME] [--no-personality]"
            echo ""
            echo "Options:"
            echo "  TARGET_DIR          Répertoire du projet cible (défaut: répertoire parent de cortex)"
            echo "  --theme THEME       Thème de personnalité à activer (défaut: h2g2)"
            echo "  --no-personality    Désactiver la couche personnalité"
            echo "  -h, --help          Afficher cette aide"
            exit 0
            ;;
        *)
            TARGET_DIR="$1"
            shift
            ;;
    esac
done

# Déterminer le répertoire cible
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

# --- 1. Vérifier que le thème existe si personnalité activée ---
if [ "$NO_PERSONALITY" = false ]; then
    THEME_DIR="$CORTEX_DIR/agents/personalities/$THEME"
    if [ ! -d "$THEME_DIR" ]; then
        echo -e "${RED}❌ Thème '$THEME' introuvable dans $CORTEX_DIR/agents/personalities/${NC}"
        echo "   Thèmes disponibles :"
        ls -1 "$CORTEX_DIR/agents/personalities/" | grep -v README.md | sed 's/^/     - /'
        exit 1
    fi
    echo -e "${GREEN}✅${NC} Thème de personnalité : ${BLUE}$THEME${NC}"
else
    echo -e "${YELLOW}ℹ️${NC}  Personnalité désactivée (mode rôles uniquement)"
fi

# --- 2. Générer le copilot-instructions.md ---
GITHUB_DIR="$TARGET_DIR/.github"
INSTRUCTIONS_FILE="$GITHUB_DIR/copilot-instructions.md"

mkdir -p "$GITHUB_DIR"

# Construire le contenu
INSTRUCTIONS_CONTENT="# Cortex AI Team

## 1. Source de vérité
Avant de répondre, consulte toujours :
- **Contexte projet :** \`cortex/agents/project-context.md\`
- **Rôles agents :** \`cortex/agents/roles/\`"

if [ "$NO_PERSONALITY" = false ]; then
    INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT
- **Personnalité active :** \`cortex/agents/personalities/$THEME/\`"
fi

INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

## 2. Comportement
- Adopte le rôle correspondant au domaine de la tâche demandée (voir \`roles/\`)
- Consulte \`project-context.md\` pour la stack, les conventions et les règles métier"

if [ "$NO_PERSONALITY" = false ]; then
    INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT
- Applique la personnalité du thème actif (\`personalities/$THEME/theme.md\` et \`characters.md\`)"
fi

INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

## 3. Prompt Manager (auto-actif)
Le rôle Prompt Manager (\`roles/prompt-manager.md\`) est activé automatiquement :
- Analyser chaque demande en début de réponse
- Dispatcher vers l'expert approprié
- Proposer l'archivage en fin de tâche"

if [ -f "$INSTRUCTIONS_FILE" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  $INSTRUCTIONS_FILE existe déjà.${NC}"
    read -p "   Remplacer ? (o/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Oo]$ ]]; then
        echo "$INSTRUCTIONS_CONTENT" > "$INSTRUCTIONS_FILE"
        echo -e "${GREEN}✅${NC} $INSTRUCTIONS_FILE remplacé"
    else
        echo -e "${YELLOW}ℹ️${NC}  Fichier conservé tel quel"
    fi
else
    echo "$INSTRUCTIONS_CONTENT" > "$INSTRUCTIONS_FILE"
    echo -e "${GREEN}✅${NC} $INSTRUCTIONS_FILE créé"
fi

# --- 3. Vérifier project-context.md ---
CONTEXT_FILE="$CORTEX_DIR/agents/project-context.md"
if grep -q "<!-- ex:" "$CONTEXT_FILE" 2>/dev/null; then
    echo ""
    echo -e "${YELLOW}📝 IMPORTANT :${NC} Le fichier project-context.md est encore un template."
    echo "   → Remplissez-le avec les informations de votre projet :"
    echo "   → $CONTEXT_FILE"
fi

# --- 4. Résumé ---
echo ""
echo "═══════════════════════════════════════════"
echo -e "${GREEN}🚀 Cortex est prêt !${NC}"
echo ""
echo "   Structure :"
echo "   ├── cortex/agents/roles/          ← Compétences (15 rôles)"

if [ "$NO_PERSONALITY" = false ]; then
    echo "   ├── cortex/agents/personalities/$THEME/ ← Personnalité"
fi

echo "   ├── cortex/agents/project-context.md  ← À REMPLIR"
echo "   └── .github/copilot-instructions.md   ← Auto-généré"
echo ""
echo "   Invoquez un agent dans votre IDE :"

if [ "$NO_PERSONALITY" = false ] && [ "$THEME" = "h2g2" ]; then
    echo "   → @Hactar pour le backend"
    echo "   → @Eddie pour le frontend"
    echo "   → @Marvin pour la sécurité"
    echo "   → @Slartibartfast pour l'architecture"
else
    echo "   → Mentionnez le rôle souhaité dans votre prompt"
fi

echo ""
