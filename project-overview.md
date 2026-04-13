<!-- @alias: cortex -->

# Overview: Cortex

## 📋 General information

**Name:** Cortex
**Description:** Framework d'orchestration d'agents IA agnostique — fournit les rôles, personnalités, workflows et capabilities pour qu'un agent IA opère comme une équipe experte pluridisciplinaire sur n'importe quel projet.
**Business domain:** Developer Tooling / AI-assisted development
**Status:** Actif — framework public réutilisable

## 🎯 Main actors

| Actor | Description |
|-------|-------------|
| Utilisateur | Toute personne interagissant avec un agent IA via des prompts |
| Agent IA | Lit les fichiers de contexte Cortex et adopte le rôle/personnalité approprié |

## 🔄 Key business processes

### Bootstrap de conversation
- L'agent lit le fichier d'instructions du workspace (ex: copilot-instructions.md, .cursorrules, AGENTS.md, ou tout autre fichier supporté par l'outil IA utilisé)
- Il charge project-overview.md et project-context.md du projet hôte
- Il identifie le thème de personnalité actif (H2G2 par défaut, mais configurable) et adopte le rôle prompt-manager

### Reformulation & dispatch — le coeur du Prompt Manager
C'est l'étape **la plus critique** du framework :
1. **Analyser** le prompt reçu : clarté, complétude, ambiguïtés potentielles
2. **Reformuler** la demande pour la rendre précise, complète et sans ambiguïté
3. **Identifier** le rôle expert le mieux placé pour répondre (via characters.md)
4. **Charger** la role card + la fiche personnalité + les capabilities pertinentes
5. **Dispatcher** vers l'expert et produire la réponse

Sans cette étape de reformulation, tous les échanges suivants sont construits sur des fondations instables.

### Activation d'un workflow
- Recherche d'abord dans agents/workflows/ du projet hôte (priorité haute)
- Puis dans cortex/agents/workflows/ (workflows génériques)
- Orchestre les étapes et les agents concernés

## 📏 Important business rules

- **Agnosticisme outil IA :** Cortex est indépendant de tout outil ou IDE. Le fichier d'instructions d'entrée est propre à chaque intégration (GitHub Copilot, Cursor, Claude, ChatGPT custom instructions...)
- **Thème configurable :** H2G2 est le thème de personnalité livré par défaut. Tout autre thème peut être créé dans personalities/ et activé
- **Capabilities à la demande :** chargées uniquement selon la stack du projet hôte définie dans project-context.md
- **Workflows projet > workflows génériques :** toujours priorité au contexte projet
- **Repo public générique :** aucun nom de projet, aucune donnée métier ne doit figurer dans Cortex lui-même

## 📚 Resources & documentation

- **Documentation :** cortex/docs/ (getting-started.md, creating-a-theme.md)
- **Templates :** cortex/templates/ (instructions d'entrée, project-context, project-overview...)
