# Getting Started — Cortex

> *"Don't Panic. Et lis ce guide avant de faire quoi que ce soit."* — Arthur Dent

Ce guide pas à pas couvre les deux modes d'installation : **projet unique** et **workspace multi-services**.

---

## Prérequis

- Un dépôt Git (ou un dossier workspace pour le mode multi-repo)
- Un IDE compatible avec les instructions Copilot : VS Code + GitHub Copilot, Cursor, etc.
- Git installé (pour le submodule)

---

## 🚀 Mode 1 — Projet unique

### Étape 1 — Ajouter Cortex comme submodule

```bash
cd mon-projet/
git submodule add <url-cortex> cortex
```

### Étape 2 — Lancer le script d'installation

```bash
# Avec le thème H2G2 (défaut)
./cortex/setup.sh

# Sans personnalité (agents professionnels neutres)
./cortex/setup.sh --no-personality

# Avec un thème custom
./cortex/setup.sh --theme star-wars
```

Le script crée automatiquement :
- `.github/copilot-instructions.md` — bootstrap lu par votre IDE à chaque session
- `project-overview.md` — à remplir : vision, acteurs, flux métier
- `project-context.md` — à remplir : stack, conventions, outils

### Étape 3 — Remplir les fichiers de contexte

**`project-overview.md`** (le QUOI et le POURQUOI) :
```markdown
@alias: mon-projet

## 🎯 Mission
Plateforme B2B de gestion de contrats — SaaS, marché PME France.

## 👥 Acteurs
- Admin entreprise, Manager, Employé

## 🔄 Flux principaux
- Création / validation / signature de contrat
- Gestion des droits par rôle

## ⚠️ Contraintes
- RGPD, données hébergées en France
- SLA 99,9%
```

**`project-context.md`** (le COMMENT et OÙ) :
```markdown
@alias: mon-projet

## 🛠️ Stack technique
- PHP 8.3 / Symfony 7.2
- MySQL 8.0
- Docker + Kubernetes

## 📐 Conventions
- PSR-12, DDD, API REST
- Tests PHPUnit, couverture min 80%
```

### Étape 4 — Première interaction

Dans votre IDE, mentionnez simplement l'agent souhaité.

**Avec le thème H2G2 :**
```
@Oolon je veux ajouter un système de pagination sur l'API /contracts
```

**Sans thème (rôle direct) :**
```
@prompt-manager je veux ajouter un système de pagination sur l'API /contracts
```

### Étape 5 — Comment fonctionne le dispatch

Quand vous appelez `@Oolon` (ou `@prompt-manager`) :

1. **Analyse** — Oolon reformule et clarifie votre demande
2. **Workflow** — Il cherche un workflow adapté dans `agents/workflows/` (générique) puis dans votre `agents/workflows/` (projet)
3. **Dispatch** — Il identifie l'expert : *"Je passe la main à @Hactar (Lead Backend)"*
4. **Capacités** — Il charge les fichiers `capabilities/` correspondant à votre stack (ex: `php.md`, `symfony.md`, `mysql.md`)
5. **Transmission** — L'expert répond avec le contexte complet de votre projet

---

## 🏢 Mode 2 — Workspace multi-services

Pour un workspace contenant plusieurs services (microservices, monorepo, multi-repo) :

```
workspace/
├── cortex/          ← submodule partagé
├── api-backend/
├── front-web/
└── service-notif/
```

### Étape 1 — Placer Cortex dans le dossier parent

```bash
cd workspace/
git submodule add <url-cortex> cortex
```

### Étape 2 — Lancer en mode workspace

```bash
./cortex/setup.sh --workspace
# Le script demande les noms de services à initialiser :
# → Nom du service (ex: api-backend, front-web) : api-backend
# → Nom du service (ex: api-backend, front-web) : front-web
# → Nom du service (ex: api-backend, front-web) :  ← entrée vide pour terminer
```

Le script crée pour chaque service :
- `{service}/project-overview.md` — avec `@alias: {service}` pré-rempli
- `{service}/project-context.md` — avec `@alias: {service}` pré-rempli

Et à la racine workspace (optionnel) :
- `project-overview.md` — vision globale (acteurs partagés, contraintes communes)
- `project-context.md` — conventions partagées (linting, CI/CD, versionning)

### Étape 3 — Copier le bootstrap workspace

```bash
cp cortex/templates/copilot-instructions-workspace.md .github/copilot-instructions.md
```

### Étape 4 — Remplir les contextes par service

Chaque service a ses propres fichiers de contexte. L'`@alias` permet de cibler un service :

**`api-backend/project-overview.md`** :
```markdown
<!-- @alias: api-backend -->

## 🎯 Mission
API REST — gestion des contrats, authentification JWT
```

**`front-web/project-context.md`** :
```markdown
<!-- @alias: front-web -->

## 🛠️ Stack
- TypeScript / React 18
- Vite, TailwindCSS
```

### Étape 5 — Cibler un service dans vos prompts

```
@api-backend Ajoute un endpoint de pagination sur /contracts
@front-web   Crée un composant de tableau avec tri et filtres
```

Si vous n'utilisez pas d'alias, Cortex déduit le service depuis les fichiers ouverts dans l'IDE.

---

## ➕ Aller plus loin

### Créer un workflow projet

Les workflows Cortex sont dans `cortex/agents/workflows/` (génériques, partagés entre projets).

Pour créer un workflow spécifique à votre projet :

```bash
mkdir -p agents/workflows/
cp cortex/templates/workflow.md.template agents/workflows/mon-workflow.md
# Remplissez le template
```

Le PM cherche d'abord dans votre `agents/workflows/` (prioritaire), puis dans `cortex/agents/workflows/`.

### Ajouter une capability

Les capabilities sont dans `cortex/agents/capabilities/`. Pour en ajouter une au framework :

```
cortex/agents/capabilities/
├── languages/    php.md, typescript.md
├── frameworks/   symfony.md
├── databases/    mysql.md
└── security/     owasp.md
```

Copiez le format d'une capability existante, puis déclarez-la dans la section `🔌 Capacités` du rôle concerné.

### Créer un thème de personnalité

Consultez [`docs/creating-a-theme.md`](creating-a-theme.md) pour le guide complet.

```bash
./cortex/setup.sh --theme mon-theme
```

### Ajouter un rôle

1. Créez `cortex/agents/roles/{categorie}/mon-role.md` en suivant le format existant
2. Ajoutez une section `🔌 Capacités` si c'est un rôle technique
3. Si thème actif : ajoutez le personnage dans `characters.md` et créez sa fiche `.md`

---

## 🗺️ Récapitulatif des 5 couches

| Couche | Fichiers | Répond à |
|---|---|---|
| **Roles** | `cortex/agents/roles/{cat}/` | *QUOI* faire (compétences métier) |
| **Capabilities** | `cortex/agents/capabilities/` | *CE QUE JE SAIS FAIRE* (stack tech) |
| **Personalities** | `cortex/agents/personalities/{theme}/` | *QUI* tu es (ton, style) |
| **Context** | `project-overview.md` + `project-context.md` | *OÙ / POURQUOI* tu travailles |
| **Workflows** | `agents/workflows/` ou `cortex/agents/workflows/` | *COMMENT et AVEC QUI* orchestrer |

---

## ❓ FAQ rapide

**Q : Dois-je utiliser un thème de personnalité ?**
Non. `--no-personality` donne des agents sans fioritures, professionnels et neutres.

**Q : Je n'ai pas de workflow qui correspond. Que se passe-t-il ?**
Le PM dispatch directement au bon expert sans trame. Si le cas est récurrent, il proposera de créer un workflow via le template.

**Q : Puis-je appeler un agent directement sans passer par le PM ?**
Oui. `@Hactar` invoque directement le Lead Backend. Mais passer par le PM garantit l'optimisation du prompt et le chargement des capacités.

**Q : Le submodule Cortex est-il mis à jour automatiquement ?**
Non. Pour mettre à jour : `git submodule update --remote cortex`. Vérifiez le changelog avant de mettre à jour en production.

**Q : Puis-je utiliser Cortex sans Git submodule ?**
Oui, avec l'option manuelle : copiez les templates à la main (voir [README.md](../README.md#option-2--manuel)).
