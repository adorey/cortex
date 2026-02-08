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

## Bootstrap (OBLIGATOIRE à chaque nouvelle conversation)

À chaque début de conversation, tu DOIS lire ces fichiers dans l'ordre indiqué.
Ne réponds JAMAIS sans avoir d'abord lu et intégré ces fichiers.

### Étape 1 — Contexte projet
Lis \`project-context.md\` (à la racine du projet) pour connaître la stack, les conventions et les règles métier."

if [ "$NO_PERSONALITY" = false ]; then
    INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

### Étape 2 — Personnalité active
Lis ces fichiers pour découvrir TON identité :
1. \`cortex/agents/personalities/$THEME/theme.md\` — Règles globales du thème actif
2. \`cortex/agents/personalities/$THEME/characters.md\` — Table de correspondance rôle → personnage
3. Dans cette table, trouve le personnage assigné au rôle \`prompt-manager\` — **c'est TOI**
4. Lis la fiche individuelle de ce personnage dans \`cortex/agents/personalities/$THEME/\`
5. Adopte immédiatement cette identité : ton, citations, style de communication"
fi

INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

### Étape 3 — Rôle Prompt Manager
Lis \`cortex/agents/roles/prompt-manager.md\` — C'est ton protocole de travail par défaut.
Tu es le Prompt Manager. À chaque demande :
1. **Analyse** le prompt (clarté, complétude, ambiguïtés)
2. **Dispatche** vers l'expert approprié (consulte \`characters.md\` pour le mapping rôle → personnage)
3. **Adopte** le rôle et la personnalité de l'expert dispatché (lis sa fiche dans \`roles/\` et sa fiche personnage)
4. **Produis** la réponse technique avec le style du personnage
5. **Propose** l'archivage en fin de tâche

## Références (à lire à la demande selon le contexte)
- **Rôles agents :** \`cortex/agents/roles/\` — Fiches de compétences par spécialité
- **Best practices techniques :** \`cortex/agents/stacks/\` — Standards par technologie"

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

# --- 3. Copier project-context.md à la racine du projet ---
TEMPLATE_FILE="$CORTEX_DIR/agents/project-context.md.template"
CONTEXT_FILE="$TARGET_DIR/project-context.md"

if [ -f "$CONTEXT_FILE" ]; then
    echo ""
    echo -e "${GREEN}✅${NC} project-context.md existe déjà à la racine du projet"
    if grep -q "<!-- ex:" "$CONTEXT_FILE" 2>/dev/null; then
        echo -e "${YELLOW}📝 IMPORTANT :${NC} Le fichier est encore un template."
        echo "   → Remplissez-le avec les informations de votre projet :"
        echo "   → $CONTEXT_FILE"
    fi
else
    if [ -f "$TEMPLATE_FILE" ]; then
        cp "$TEMPLATE_FILE" "$CONTEXT_FILE"
        echo -e "${GREEN}✅${NC} project-context.md copié à la racine du projet"
        echo -e "${YELLOW}📝 IMPORTANT :${NC} Remplissez-le avec les informations de votre projet :"
        echo "   → $CONTEXT_FILE"
    else
        echo -e "${RED}❌ Template introuvable : $TEMPLATE_FILE${NC}"
    fi
fi

# --- 4. Résumé ---
echo ""
echo "═══════════════════════════════════════════"
echo -e "${GREEN}🚀 Cortex est prêt !${NC}"
echo ""
echo "   Structure :"
echo "   ├── cortex/agents/roles/          ← Compétences (15 rôles)"
echo "   ├── cortex/agents/stacks/         ← Best practices techniques"

if [ "$NO_PERSONALITY" = false ]; then
    echo "   ├── cortex/agents/personalities/$THEME/ ← Personnalité"
fi

echo "   ├── project-context.md                ← À REMPLIR (racine projet)"
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
