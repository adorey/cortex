# Cortex

<p align="center">
  <img src="assets/logo.png" alt="Cortex — AI Agent Framework" width="200" height="300" />
</p>

Cortex est un framework d'agents IA spécialisés, prêts à être intégrés dans n'importe quel projet.

## 🚀 Concept

Chaque agent est composé de **4 couches indépendantes** :

```
┌─────────────────────────────────┐
│   project-context.md            │  ← Vos règles métier, conventions locales
├─────────────────────────────────┤
│   capabilities/{techno}.md      │  ← Compétences techniques chargeables (PHP, Docker…)
├─────────────────────────────────┤
│   personalities/{theme}/        │  ← Personnalité optionnelle (ex: H2G2)
├─────────────────────────────────┤
│   roles/{role}.md               │  ← Compétences métier génériques
├─────────────────────────────────┤
│   workflows/{contexte}.md       │  ← Trames d'orchestration multi-agents
└─────────────────────────────────┘
```

> *"Expliquons ça comme si la Terre venait d'être détruite et qu'on devait repartir de zéro."* — Arthur Dent

| Couche | Répond à | Exemple |
|---|---|---|
| `roles/` | **QUOI** faire | "Un lead backend structure, review, mentore" |
| `capabilities/` | **CE QUE JE SAIS FAIRE** | "En PHP : PSR-12, injection de dépendances..." |
| `personalities/` | **QUI** tu es | "Hactar, méthodique, élégant" |
| `project-context.md` | **OÙ** tu travailles | "Ce projet : Symfony 7.2, PHP 8.3, MySQL 8" |
| `workflows/` | **DANS QUEL ORDRE et AVEC QUI** | "Feature dev : architect → backend → QA → sécu → doc" |

Cette séparation permet de :
- Changer de **personnalité** (H2G2, Star Wars, corporate…) sans toucher aux compétences
- Réutiliser les **rôles** sur n'importe quelle stack technique
- Partager les **best practices** d'une techno entre tous les projets qui l'utilisent
- Personnaliser le **contexte projet** sans modifier les agents
- Définir des **workflows** réutilisables (génériques dans cortex) ou spécifiques (dans le projet hôte via `agents/workflows/`)

## 📁 Structure

```
cortex/
├── README.md                          # Ce fichier
├── setup.sh                           # Script d'installation
├── templates/
│   ├── copilot-instructions.md        # Template auto-généré à l'install
│   └── workflow.md.template           # Template pour créer un workflow projet
│
├── agents/
│   ├── project-context.md.template    # Template project-context
│   │
│   ├── roles/                         # Couche 1 : Rôles métier (agnostiques)
│   │   ├── prompt-manager.md         # Point d'entrée (racine, toujours actif)
│   │   ├── engineering/               # Conception & réalisation technique
│   │   │   ├── architect.md
│   │   │   ├── lead-backend.md
│   │   │   ├── lead-frontend.md
│   │   │   ├── dba.md
│   │   │   ├── platform-engineer.md
│   │   │   ├── performance-engineer.md
│   │   │   ├── consultant-platform.md
│   │   │   └── qa-automation.md
│   │   ├── product/                   # Vision produit & métier
│   │   │   ├── product-owner.md
│   │   │   └── business-analyst.md
│   │   ├── security-compliance/       # Sécurité & conformité
│   │   │   ├── security-engineer.md
│   │   │   └── compliance-officer.md
│   │   ├── data/                      # Données & analytique
│   │   │   └── data-analyst.md
│   │   └── communication/             # Contenu & transmission
│   │       └── tech-writer.md
│   │
│   ├── capabilities/                   # Couche 2 : Compétences techniques chargeables
│   │   ├── languages/
│   │   │   ├── php.md
│   │   │   └── typescript.md
│   │   ├── frameworks/
│   │   │   └── symfony.md
│   │   ├── infrastructure/
│   │   │   ├── docker.md
│   │   │   └── kubernetes.md
│   │   ├── databases/
│   │   │   └── mysql.md
│   │   └── security/
│   │       └── owasp.md
│   │
│   ├── personalities/                 # Couche 3 : Thèmes de personnalité
│   │   └── h2g2/                      # Thème H2G2 (Guide du voyageur galactique)
│   │       ├── theme.md
│   │       ├── characters.md
│   │       └── {personnage}.md        # Fiche personnalité individuelle
│   │
│   └── workflows/                     # Couche 5 : Trames d'orchestration multi-agents
│       ├── README.md
│       ├── feature-development.md
│       └── tech-watch.md
│
└── docs/
    └── creating-a-theme.md            # Guide pour créer un thème
```

## 🔧 Installation

### Prérequis

- Git
- Un IDE avec support Copilot (VS Code, Cursor, etc.)

### Étape 1 — Ajouter Cortex au projet

```bash
# En submodule Git (recommandé — partagé entre projets)
git submodule add <url-cortex> cortex
git submodule update --init --recursive
```

### Étape 2 — Lancer le setup

**Chaque développeur** doit lancer le setup sur sa machine :

```bash
./cortex/setup.sh
```

C'est tout. Le script fait le reste automatiquement.

> ⚠️ Les fichiers générés (`.github/copilot-instructions.md`, `.vscode/settings.json`) sont **personnels** au développeur — ils dépendent du thème choisi. Ils doivent être dans le `.gitignore` du projet.

### Ce que `setup.sh` fait

Le script effectue **4 actions** :

| # | Action | Fichier généré | Description |
|---|--------|----------------|-------------|
| 1 | **Vérifie le thème** | — | Vérifie que le thème existe, résout le personnage `prompt-manager` depuis `characters.md` |
| 2 | **Génère le bootstrap IA** | `.github/copilot-instructions.md` | Instructions système pour Copilot, avec nommage direct du personnage prompt-manager |
| 3 | **Copie le contexte projet** | `project-context.md` | Template à remplir avec les infos de votre projet (stack, conventions, domaine) |
| 4 | **Configure VS Code** | `.vscode/settings.json` | Injecte les fichiers personnalité via `codeGeneration.instructions` pour un chargement automatique |

### Options de `setup.sh`

```bash
# Thème par défaut (H2G2)
./cortex/setup.sh

# Thème spécifique
./cortex/setup.sh --theme star-wars

# Sans personnalité (rôles techniques uniquement)
./cortex/setup.sh --no-personality

# Projet cible différent
./cortex/setup.sh /chemin/vers/autre-projet

# Aide
./cortex/setup.sh --help
```

### Étape 3 — Remplir le contexte projet

Éditez `project-context.md` à la racine du projet avec :
- Le nom et la description du projet
- La stack technique (framework, langage, BDD, infra)
- Les conventions de code
- Le domaine métier et les règles importantes

> ⚠️ **Ce fichier est le "Guide du Voyageur Galactique" de votre projet.** C'est la source de vérité que tous les agents consultent. Plus il est complet, meilleures sont les réponses.

### Résultat après setup

```
mon-projet/
├── cortex/                            ← Submodule Git (committé)
├── project-context.md                 ← Committé — rempli une fois pour le projet
├── .github/
│   └── copilot-instructions.md        ← Gitignored — généré par setup.sh
├── .vscode/
│   └── settings.json                  ← Gitignored — généré par setup.sh
└── ... (votre code)
```

### Gitignore recommandé

Ajoutez ces lignes au `.gitignore` du projet :

```gitignore
# Cortex — Fichiers générés par setup.sh (personnalisés par développeur)
.github/copilot-instructions.md

# IDE (inclut les settings Cortex)
.vscode/
```

### Onboarding d'un nouveau développeur

```bash
# 1. Cloner le projet
git clone <url-projet>
cd mon-projet

# 2. Initialiser le submodule Cortex
git submodule update --init --recursive

# 3. Lancer le setup (choisir son thème)
./cortex/setup.sh                    # H2G2 par défaut
./cortex/setup.sh --theme star-wars  # ou un autre thème

# 4. Ouvrir le projet dans VS Code
code .

# → Cortex est prêt, la personnalité se charge dès la première conversation Copilot
```

## 🔄 Workflow au quotidien

### Comment Cortex fonctionne avec Copilot

La personnalité est chargée via **deux mécanismes complémentaires** :

```
┌─────────────────────────────────────────────────────────┐
│  Mécanisme 1 : .github/copilot-instructions.md         │
│  → Injecté dans le system prompt à chaque conversation  │
│  → Ordonne à l'IA de lire les fichiers personnalité    │
│  → Nomme directement le personnage prompt-manager       │
├─────────────────────────────────────────────────────────┤
│  Mécanisme 2 : .vscode/settings.json                   │
│  → codeGeneration.instructions avec refs fichiers       │
│  → VS Code injecte le CONTENU des fichiers directement  │
│  → Fonctionne même si l'IA "oublie" de lire les fichiers│
└─────────────────────────────────────────────────────────┘
```

### Invoquer un agent

Mentionnez le personnage par son alias dans votre prompt :

```
@Hactar : implémente ce service en PHP
@Slartibartfast : review cette architecture
@Marvin : audite la sécurité de ce code
@Trillian : écris les tests pour cette feature
@Vogon : optimise cette requête SQL
```

> Voir `cortex/agents/personalities/h2g2/characters.md` pour la table complète des 15 agents.

### Dispatch automatique

Le Prompt Manager (Oolon Colluphid en thème H2G2) analyse votre demande et dispatche automatiquement vers l'expert le plus pertinent :

```
Vous : "Cette requête SQL est lente en production"
→ @Oolon analyse → dispatche vers @Deep-Thought (performance) + @Vogon (DBA)
→ Réponse dans le style des personnages, avec la rigueur technique des rôles
```

## ⚠️ Points importants

### Ouvrir le projet directement

Cortex est conçu pour que vous ouvriez **le dossier du projet directement** dans VS Code (`code mon-projet/`). Les fichiers `.github/copilot-instructions.md` sont résolus relativement au dossier ouvert.

```
# ✅ Recommandé : ouvrir le projet directement
code mon-projet/
→ VS Code trouve .github/copilot-instructions.md ✅
→ Les chemins cortex/agents/... se résolvent ✅

# ⚠️ Workspace multi-root : chaque folder doit avoir son propre .github/
```

> **Pas besoin de fichier `.code-workspace`** — ouvrez simplement le dossier du projet.

### Mise à jour de Cortex

```bash
# Mettre à jour le submodule
cd cortex && git pull origin main && cd ..

# Re-run setup si le template a changé
./cortex/setup.sh
```

### La personnalité ne s'applique pas ?

Checklist de diagnostic :

1. ✅ `.github/copilot-instructions.md` existe **dans le projet** (pas dans un dossier parent)
2. ✅ Les chemins dans ce fichier sont relatifs au projet (`cortex/agents/...`)
3. ✅ `project-context.md` existe à la racine du projet et est rempli
4. ✅ `.vscode/settings.json` contient `github.copilot.chat.codeGeneration.instructions`
5. ✅ Le submodule `cortex/` est initialisé (`git submodule update --init`)
6. ✅ Relancez une **nouvelle conversation** Copilot (les instructions se chargent au début)

## 🎯 Philosophie

- **Zéro dépendance projet** : les rôles sont agnostiques, la stack est dans `project-context.md`
- **Plug & Play** : `setup.sh` et c'est prêt
- **Composable** : rôle + stack + personnalité + contexte + workflow = agent complet
- **Capacités chargeables** : les fiches `capabilities/` sont réutilisables d'un projet à l'autre, et chargées automatiquement par le PM selon le rôle actif et la stack du projet
- **Évolutif** : ajoutez vos propres rôles, capacités, thèmes ou workflows
- **Workflows projet** : créez vos workflows métier dans `{projet}/agents/workflows/` avec `cortex/templates/workflow.md.template`

> *"La documentation, c'est le thé du développeur : personne n'en veut jusqu'à ce qu'il en ait désespérément besoin."* — Arthur Dent
