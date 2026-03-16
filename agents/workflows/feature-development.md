# Workflow : Développement d'une nouvelle feature

<!-- WORKFLOW GÉNÉRIQUE — cortex
     Peut être surchargé par {projet}/agents/workflows/feature-development.md
-->

## 🎯 Déclencheurs

Ce workflow s'active lorsque le prompt contient des formulations du type :
- "nouvelle feature", "nouvelle fonctionnalité", "nouvelle page", "nouveau module"
- "développer", "implémenter", "créer" + composant applicatif
- "besoin fonctionnel", "user story", "ticket de dev"

## 👥 Agents impliqués

| Étape | Rôle | Responsabilité |
|---|---|---|
| 1 | `roles/architect.md` | Design & découpage technique |
| 2 | `roles/lead-backend.md` et/ou `roles/lead-frontend.md` | Implémentation |
| 3 | `roles/qa-automation.md` | Stratégie de test |
| 4 | `roles/security-engineer.md` | Revue sécurité |
| 5 | `roles/tech-writer.md` | Documentation |

## 📋 Étapes

### Étape 1 — Cadrage & Design
**Agent :** `architect`
**Objectif :** Comprendre le besoin, proposer une solution technique cohérente avec l'existant.

**Checklist :**
- [ ] Comprendre le besoin fonctionnel (quoi, pour qui, pourquoi)
- [ ] Identifier les impacts sur l'architecture existante
- [ ] Proposer le découpage en composants/modules
- [ ] Identifier les dépendances externes (API, services tiers, BDD)
- [ ] Définir les contrats d'interface (API, events, DTOs)
- [ ] Estimer grossièrement la complexité
- [ ] Valider l'approche avec le Product Owner si nécessaire

**Livrable :** Proposition technique validée avant toute implémentation.

---

### Étape 2 — Implémentation
**Agent :** `lead-backend` et/ou `lead-frontend` selon le périmètre
**Objectif :** Produire le code selon les standards de la stack projet.

**Checklist :**
- [ ] Respecter les conventions définies dans `capabilities/` et `project-context.md`
- [ ] Implémenter la logique métier
- [ ] Gérer les cas d'erreur et les edge cases
- [ ] Écrire les tests unitaires en parallèle
- [ ] Respecter les principes SOLID / clean code
- [ ] Commiter avec des messages clairs et atomiques
- [ ] Ouvrir une PR avec une description complète

---

### Étape 3 — Tests & QA
**Agent :** `qa-automation`
**Objectif :** Définir et valider la stratégie de test.

**Checklist :**
- [ ] Définir les cas de test (nominal, limites, erreurs)
- [ ] Vérifier la couverture des tests unitaires
- [ ] Prévoir les tests d'intégration nécessaires
- [ ] Tester les régressions sur les modules impactés
- [ ] Valider le comportement en conditions dégradées

---

### Étape 4 — Revue sécurité
**Agent :** `security-engineer`
**Objectif :** S'assurer qu'aucune surface d'attaque n'est introduite.

**Checklist :**
- [ ] Vérifier la validation et la sanitisation des entrées
- [ ] Contrôler les autorisations (authentication / authorization)
- [ ] Vérifier l'absence de secrets en clair (code, logs, réponses API)
- [ ] Identifier les risques OWASP pertinents pour la feature
- [ ] Vérifier les dépendances ajoutées (vulnérabilités connues)

---

### Étape 5 — Documentation
**Agent :** `tech-writer`
**Objectif :** Garantir que la feature est documentée et maintenable.

**Checklist :**
- [ ] Documenter les endpoints ou interfaces exposés
- [ ] Mettre à jour le README ou la doc existante si nécessaire
- [ ] Documenter les décisions techniques (ADR si applicable)
- [ ] Vérifier que les commentaires de code sont suffisants
- [ ] Mettre à jour le changelog si le projet en a un

---

## ✅ Définition de "terminé"

- [ ] Code mergé sur la branche principale
- [ ] Tests passants en CI
- [ ] Revue sécurité signée
- [ ] Documentation à jour
- [ ] Product Owner a validé fonctionnellement

## 🔗 Workflows liés

- `code-review.md` — peut être déclenché à l'étape 2 (PR)
- `tech-watch.md` — si une technologie inconnue est introduite
