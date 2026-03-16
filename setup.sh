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
# Ce script :
# 1. Vérifie le thème de personnalité
# 2. Génère .github/copilot-instructions.md (bootstrap IA)
# 3. Copie project-context.md (template à remplir)
# 4. Configure .vscode/settings.json (injection personnalité Copilot)
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
            echo "  TARGET_DIR          Répertoire cible (défaut: répertoire parent de cortex)"
            echo "  --theme THEME       Thème de personnalité à activer (défaut: h2g2)"
            echo "  --no-personality    Désactiver la couche personnalité"
            echo "  --workspace         Mode workspace multi-projets (structure parent / services)"
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
PM_CHARACTER=""
PM_FILE=""
PM_CITATION=""

if [ "$NO_PERSONALITY" = false ]; then
    THEME_DIR="$CORTEX_DIR/agents/personalities/$THEME"
    if [ ! -d "$THEME_DIR" ]; then
        echo -e "${RED}❌ Thème '$THEME' introuvable dans $CORTEX_DIR/agents/personalities/${NC}"
        echo "   Thèmes disponibles :"
        ls -1 "$CORTEX_DIR/agents/personalities/" | grep -v README.md | sed 's/^/     - /'
        exit 1
    fi

    # Résoudre le personnage prompt-manager depuis characters.md
    CHARACTERS_FILE="$THEME_DIR/characters.md"
    if [ -f "$CHARACTERS_FILE" ]; then
        # Extraire : nom du personnage, fichier .md, citation
        PM_LINE=$(grep '| `prompt-manager`' "$CHARACTERS_FILE" || true)
        if [ -n "$PM_LINE" ]; then
            PM_CHARACTER=$(echo "$PM_LINE" | awk -F'|' '{print $3}' | xargs)
            PM_FILE_REF=$(echo "$PM_LINE" | grep -o '\[📄\]([^)]*' | sed 's/\[📄\](//' || true)
            PM_CITATION=$(echo "$PM_LINE" | awk -F'|' '{print $7}' | xargs || true)
            if [ -n "$PM_FILE_REF" ] && [ -f "$THEME_DIR/$PM_FILE_REF" ]; then
                PM_FILE="$PM_FILE_REF"
            fi
        fi
    fi

    if [ -n "$PM_CHARACTER" ]; then
        echo -e "${GREEN}✅${NC} Thème : ${BLUE}$THEME${NC} — Prompt Manager : ${BLUE}$PM_CHARACTER${NC}"
    else
        echo -e "${GREEN}✅${NC} Thème de personnalité : ${BLUE}$THEME${NC}"
        echo -e "${YELLOW}⚠️${NC}  Prompt Manager non résolu depuis characters.md (mode générique)"
    fi
else
    echo -e "${YELLOW}ℹ️${NC}  Personnalité désactivée (mode rôles uniquement)"
fi

# --- 2. Générer le copilot-instructions.md ---
GITHUB_DIR="$TARGET_DIR/.github"
INSTRUCTIONS_FILE="$GITHUB_DIR/copilot-instructions.md"

mkdir -p "$GITHUB_DIR"

# Construire le contenu
INSTRUCTIONS_CONTENT="# Cortex AI Team

## Bootstrap (OBLIGATOIRE — Exécution immédiate à chaque nouvelle conversation)

⚠️ **INSTRUCTION SYSTÈME CRITIQUE** ⚠️

Tu es un agent IA piloté par le framework Cortex.
AVANT de répondre à la moindre question, tu DOIS utiliser ton outil \`read_file\` pour lire les fichiers suivants **dans l'ordre**.
Ne produis AUCUNE réponse tant que tu n'as pas lu et intégré ces fichiers.
Si tu ne les lis pas, tu fonctionnes sans contexte et tes réponses seront incorrectes.

### Étape 1 — Contexte projet
Lis \`project-context.md\` (à la racine du projet) pour connaître la stack, les conventions et les règles métier."

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

### Étape 2 — Personnalité active
Lis ces fichiers pour découvrir TON identité :
1. \`cortex/agents/personalities/$THEME/theme.md\` — Règles globales du thème actif
2. \`cortex/agents/personalities/$THEME/characters.md\` — Table de correspondance rôle → personnage
3. Dans cette table, trouve le personnage assigné au rôle \`prompt-manager\` — **c'est TOI**
4. Lis la fiche individuelle de ce personnage dans \`cortex/agents/personalities/$THEME/\`
5. Adopte immédiatement cette identité : ton, citations, style de communication"
    fi
fi

INSTRUCTIONS_CONTENT="$INSTRUCTIONS_CONTENT

### Étape 3 — Rôle Prompt Manager
Lis \`cortex/agents/roles/prompt-manager.md\` — C'est ton protocole de travail par défaut.
Tu es le Prompt Manager. À chaque demande :
1. **Analyse** le prompt (clarté, complétude, ambiguïtés)
2. **Lookup workflow** — Recherche un workflow correspondant au contexte :
   - D'abord dans \`agents/workflows/\` à la racine du projet (spécifique, prioritaire)
   - Puis dans \`cortex/agents/workflows/\` (génériques)
   - Si trouvé → annonce le workflow activé et orchestre ses étapes
   - Si non trouvé → passe au dispatch classique
   - Si cas récurrent sans workflow → propose d'en créer un
3. **Dispatche** vers l'expert approprié (consulte \`characters.md\` pour le mapping rôle → personnage)
4. **Adopte** le rôle et la personnalité de l'expert dispatché (lis sa fiche dans \`roles/\` et sa fiche personnage)
5. **Charge les capacités** : lis la section \`🔌 Capacités\` de la fiche rôle, croise avec la stack dans \`project-context.md\`, charge les fichiers correspondants dans \`cortex/agents/capabilities/\`
6. **Produis** la réponse technique avec le style du personnage
7. **Propose** l'archivage en fin de tâche

## Références (à lire à la demande selon le contexte)
- **Rôles agents :** \`cortex/agents/roles/\` — Fiches de compétences par spécialité
- **Capacités techniques :** \`cortex/agents/capabilities/\` — Compétences chargeables par catégorie (languages, frameworks, databases, infrastructure, security)
- **Workflows génériques :** \`cortex/agents/workflows/\` — Trames d'orchestration multi-agents
- **Workflows projet :** \`agents/workflows/\` — Workflows spécifiques au projet (prioritaires)"

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

# --- 3. Copier les fichiers de contexte à la racine ---
CONTEXT_TEMPLATE="$CORTEX_DIR/templates/project-context.md.template"
OVERVIEW_TEMPLATE="$CORTEX_DIR/templates/project-overview.md.template"
CONTEXT_FILE="$TARGET_DIR/project-context.md"
OVERVIEW_FILE="$TARGET_DIR/project-overview.md"

# project-overview.md
if [ -f "$OVERVIEW_FILE" ]; then
    echo -e "${GREEN}✅${NC} project-overview.md existe déjà"
else
    if [ -f "$OVERVIEW_TEMPLATE" ]; then
        cp "$OVERVIEW_TEMPLATE" "$OVERVIEW_FILE"
        echo -e "${GREEN}✅${NC} project-overview.md créé"
        echo -e "${YELLOW}📝${NC}  → Remplissez la vision, les acteurs et les flux métier : $OVERVIEW_FILE"
    fi
fi

# project-context.md
if [ -f "$CONTEXT_FILE" ]; then
    echo ""
    echo -e "${GREEN}✅${NC} project-context.md existe déjà à la racine du projet"
    if grep -q "<!-- ex:" "$CONTEXT_FILE" 2>/dev/null; then
        echo -e "${YELLOW}📝 IMPORTANT :${NC} Le fichier est encore un template."
        echo "   → Remplissez-le avec la stack technique de votre projet :"
        echo "   → $CONTEXT_FILE"
    fi
else
    if [ -f "$CONTEXT_TEMPLATE" ]; then
        cp "$CONTEXT_TEMPLATE" "$CONTEXT_FILE"
        echo -e "${GREEN}✅${NC} project-context.md créé à la racine du projet"
        echo -e "${YELLOW}📝 IMPORTANT :${NC} Remplissez-le avec la stack technique de votre projet :"
        echo "   → $CONTEXT_FILE"
    else
        echo -e "${RED}❌ Template introuvable : $CONTEXT_TEMPLATE${NC}"
    fi
fi

# Mode workspace : initialiser les services
if [ "$WORKSPACE_MODE" = true ]; then
    echo ""
    echo -e "${BLUE}ℹ️  Mode workspace — initialisation des services${NC}"
    echo "   Entrez les noms des services à créer (entrée vide pour terminer) :"
    while true; do
        read -p "   Nom du service (ex: api-backend, front-web) : " SERVICE_NAME
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

# --- 4. Résumé ---
echo ""
echo "═══════════════════════════════════════════"
echo -e "${GREEN}🚀 Cortex est prêt !${NC}"
echo ""
echo "   Structure :"
echo "   ├── cortex/agents/roles/            ← Compétences (15 rôles, 5 catégories)"
echo "   ├── cortex/agents/capabilities/     ← Capacités techniques chargeables"

if [ "$NO_PERSONALITY" = false ]; then
    echo "   ├── cortex/agents/personalities/$THEME/ ← Personnalité"
fi

<<<<<<< HEAD
echo "   ├── project-context.md                ← À REMPLIR (racine projet)"
echo "   ├── .github/copilot-instructions.md   ← Auto-généré (bootstrap IA)"
echo "   └── .vscode/settings.json             ← Instructions Copilot"
echo ""

if [ "$NO_PERSONALITY" = false ] && [ -n "$PM_CHARACTER" ]; then
    echo "   🎭 Prompt Manager : $PM_CHARACTER"
    echo ""
fi

echo "   Invoquez un agent dans votre IDE :"
=======
if [ "$WORKSPACE_MODE" = true ]; then
    echo "   ├── project-overview.md            ← Vision globale du workspace (optionnel)"
    echo "   ├── project-context.md             ← Conventions partagées (optionnel)"
    echo "   ├── {service}/project-overview.md  ← Vision du service (À REMPLIR)"
    echo "   ├── {service}/project-context.md   ← Stack du service (À REMPLIR)"
else
    echo "   ├── project-overview.md            ← Vision & métier (À REMPLIR)"
    echo "   ├── project-context.md             ← Stack technique (À REMPLIR)"
fi

echo "   └── .github/copilot-instructions.md   ← Auto-généré"
echo ""
>>>>>>> 0875716 (feat: split project context into overview + context, add workspace mode)

if [ "$WORKSPACE_MODE" = true ]; then
    echo "   Mode workspace — ciblez un service avec son @alias dans votre prompt :"
    echo "   → ex: '@backend Ajoute un endpoint de pagination'"
    echo "   → Ou laissez Cortex déduire depuis les fichiers ouverts dans l'IDE"
elif [ "$NO_PERSONALITY" = false ] && [ "$THEME" = "h2g2" ]; then
    echo "   Invoquez un agent dans votre IDE :"
    echo "   → @Hactar pour le backend"
    echo "   → @Eddie pour le frontend"
    echo "   → @Marvin pour la sécurité"
    echo "   → @Slartibartfast pour l'architecture"
else
    echo "   Invoquez un agent dans votre IDE :"
    echo "   → Mentionnez le rôle souhaité dans votre prompt"
fi

echo ""
