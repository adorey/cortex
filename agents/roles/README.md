# Rôles — Agents Cortex

> Chaque fichier de ce dossier définit un **rôle métier générique**, indépendant de toute stack technique ou personnalité.

## Principe

Un rôle contient :
- Les **responsabilités** du poste
- Les **principes universels** à respecter
- Les **checklists** et **frameworks** réutilisables
- Les **interactions** avec les autres rôles
- La section **`🔌 Capacités`** déclarant les catégories à charger depuis `capabilities/`

Un rôle ne contient **PAS** :
- De stack technique spécifique (→ voir `capabilities/`)
- De personnalité ou de ton (→ voir `personalities/`)
- De données métier d'un projet (→ voir `project-context.md`)

## Rôles disponibles

### Point d'entrée

| Fichier | Rôle | Description |
|---------|------|-------------|
| `prompt-manager.md` | Prompt Manager | Analyse, dispatch, lookup workflow, chargement des capacités |

### `engineering/` — Conception & réalisation technique

| Fichier | Rôle | Domaine |
|---------|------|---------|
| `architect.md` | Lead Architect | Architecture système, design patterns |
| `lead-backend.md` | Lead Backend | Développement backend, API, services |
| `lead-frontend.md` | Lead UI/UX & Frontend | Interface utilisateur, composants, UX |
| `dba.md` | Database Administrator | BDD, optimisation SQL, migrations |
| `platform-engineer.md` | Platform & DevOps Lead | Infrastructure, CI/CD, IDP |
| `performance-engineer.md` | Performance Engineer | Optimisation, scalabilité, monitoring |
| `consultant-platform.md` | Consultant Platform | Audit, conseil stratégique, gouvernance |
| `qa-automation.md` | QA Automation Engineer | Tests unitaires, intégration, E2E |

### `product/` — Vision produit & métier

| Fichier | Rôle | Domaine |
|---------|------|---------|
| `product-owner.md` | Product Owner | Vision produit, backlog, priorisation |
| `business-analyst.md` | Business Analyst | Spécifications fonctionnelles, besoins métier |

### `security-compliance/` — Sécurité & conformité

| Fichier | Rôle | Domaine |
|---------|------|---------|
| `security-engineer.md` | Security Engineer (RSSI) | Sécurité applicative, infra, données |
| `compliance-officer.md` | Compliance Officer | RGPD, conformité, éthique |

### `data/` — Données & analytique

| Fichier | Rôle | Domaine |
|---------|------|---------|
| `data-analyst.md` | Data Analyst | Analyse de données, dashboards, KPIs |

### `communication/` — Contenu & transmission

| Fichier | Rôle | Domaine |
|---------|------|---------|
| `tech-writer.md` | Technical Writer | Documentation, onboarding |

## Comment ça fonctionne

Au runtime, un agent est composé de 5 couches :

```
┌─────────────────────────────────┐
│   project-context.md            │  ← Stack, règles métier, conventions
├─────────────────────────────────┤
│   capabilities/{catégorie}/     │  ← Compétences techniques chargées
├─────────────────────────────────┤
│   personalities/{theme}/        │  ← Ton, citations, traits (optionnel)
├─────────────────────────────────┤
│   roles/{catégorie}/{role}.md   │  ← Compétences, responsabilités
├─────────────────────────────────┤
│   workflows/{contexte}.md       │  ← Trame d'orchestration (optionnel)
└─────────────────────────────────┘
```

## Ajouter un rôle

1. Identifier la **catégorie** appropriée (ou en créer une nouvelle)
2. Créer `roles/{catégorie}/mon-nouveau-role.md`
3. Suivre la structure : Profil → Mission → Responsabilités → Principes → `🔌 Capacités` → Checklists → Interactions
4. Rester **agnostique** techniquement (pas de framework, pas de langage spécifique)
5. Si un thème de personnalité est actif, ajouter le mapping dans `personalities/{theme}/characters.md`

## Catégories futures envisagées

- `management/` — CTO, Team Lead, HR Manager, Engineering Manager...
- `sales-marketing/` — Sales Engineer, Content Strategist, Growth...
- `legal-finance/` — Legal Counsel, CFO, Financial Controller...
