# Rôles — Agents Cortex

> Chaque fichier de ce dossier définit un **rôle métier générique**, indépendant de toute stack technique ou personnalité.

## Principe

Un rôle contient :
- Les **responsabilités** du poste
- Les **principes universels** à respecter
- Les **checklists** et **frameworks** réutilisables
- Les **interactions** avec les autres rôles

Un rôle ne contient **PAS** :
- De stack technique spécifique (→ voir `project-context.md`)
- De personnalité ou de ton (→ voir `personalities/`)
- De données métier d'un projet (→ voir `project-context.md`)

## Rôles disponibles

| Fichier | Rôle | Domaine |
|---------|------|---------|
| `prompt-manager.md` | Prompt Manager | Communication IA, optimisation des prompts |
| `architect.md` | Lead Architect | Architecture système, design patterns |
| `lead-backend.md` | Lead Backend | Développement backend, API, services |
| `lead-frontend.md` | Lead UI/UX & Frontend | Interface utilisateur, composants, UX |
| `security-engineer.md` | Security Engineer (RSSI) | Sécurité applicative, infra, données |
| `qa-automation.md` | QA Automation Engineer | Tests unitaires, intégration, E2E |
| `platform-engineer.md` | Platform & DevOps Lead | Infrastructure, CI/CD, IDP |
| `product-owner.md` | Product Owner | Vision produit, backlog, priorisation |
| `tech-writer.md` | Technical Writer | Documentation, onboarding |
| `data-analyst.md` | Data Analyst | Analyse de données, dashboards, KPIs |
| `compliance-officer.md` | Compliance Officer | RGPD, conformité, éthique |
| `dba.md` | Database Administrator | BDD, optimisation SQL, migrations |
| `business-analyst.md` | Business Analyst | Spécifications fonctionnelles, besoins métier |
| `performance-engineer.md` | Performance Engineer | Optimisation, scalabilité, monitoring |
| `consultant-platform.md` | Consultant Platform | Audit, conseil stratégique, gouvernance |

## Comment ça fonctionne

Au runtime, un agent est composé de 3 couches :

```
┌─────────────────────────────────┐
│   project-context.md            │  ← Stack, règles métier, conventions
├─────────────────────────────────┤
│   personalities/{theme}/        │  ← Ton, citations, traits (optionnel)
├─────────────────────────────────┤
│   roles/{role}.md               │  ← Compétences, responsabilités
└─────────────────────────────────┘
```

## Ajouter un rôle

1. Créer `roles/mon-nouveau-role.md`
2. Suivre la structure : Profil → Mission → Responsabilités → Principes → Checklists → Interactions
3. Rester **agnostique** techniquement (pas de framework, pas de langage spécifique)
4. Si un thème de personnalité est actif, ajouter le mapping dans `personalities/{theme}/characters.md`
