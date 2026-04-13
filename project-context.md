<!-- @alias: cortex -->

# Technical context: Cortex

## 🏗️ Tech stack

### Stack principale
- **Format source :** Markdown (`.md`) — lisible nativement par tout agent IA sans parsing spécial
- **Configuration :** YAML front-matter pour les métadonnées (si nécessaire)
- **Scripting :** Bash (`setup.sh`)
- **Aucune dépendance runtime** — 100% fichiers statiques

### Intégration avec les outils IA
Cortex est **agnostique de l'outil IA**. Le fichier d'instructions d'entrée dépend du contexte d'utilisation :

| Outil | Fichier d'entrée typique |
|---|---|
| GitHub Copilot (VS Code) | `.github/copilot-instructions.md` |
| Cursor | `.cursorrules` ou `.cursor/rules/` |
| Claude Projects | Instructions système du projet |
| ChatGPT Custom Instructions | Instructions personnalisées |
| Autre | Tout fichier d'instructions supporté par l'outil |

Le contenu de ce fichier d'entrée est fourni dans `cortex/templates/`.

## 📁 Project structure

```
cortex/
├── agents/
│   ├── personalities/
│   │   └── h2g2/         ← Thème par défaut (configurable — créer d'autres dossiers ici)
│   ├── roles/            ← Fiches de mission par spécialité (prompt-manager, architect…)
│   ├── capabilities/     ← Compétences techniques chargeables (php, symfony, docker…)
│   └── workflows/        ← Templates d'orchestration multi-agents (génériques)
├── assets/               ← Ressources statiques
├── docs/                 ← Documentation du framework
├── templates/            ← Templates projet (instructions d'entrée, project-context…)
└── setup.sh              ← Script d'initialisation
```

## 📝 Code conventions

- **Format :** Markdown strict, une idée par section, titres concis
- **Naming :** kebab-case pour les fichiers, PascalCase pour les noms de personnages
- **Séparation des responsabilités :**
  - Fiches personnalité → ton et style uniquement
  - Role cards → mission et protocole technique uniquement
  - Capabilities → compétences techniques chargées à la demande
- **Longueur :** fichiers < 200 lignes pour ne pas saturer la fenêtre de contexte

## ⚡ Technical constraints

### Performance
- Fichiers courts et ciblés — chaque fichier doit tenir dans un seul appel de lecture
- Ne charger que les capabilities effectivement nécessaires selon la stack du projet hôte

### Security
- **Aucun secret, credential ou donnée projet** dans le repo Cortex
- Cortex est un repo public générique — tout ce qu'il contient doit être réutilisable sans modification par n'importe quel projet
