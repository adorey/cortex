# Workflow : Veille technologique

<!-- WORKFLOW GÉNÉRIQUE — cortex
     Peut être surchargé par {projet}/agents/workflows/tech-watch.md
-->

## 🎯 Déclencheurs

Ce workflow s'active lorsque le prompt contient des formulations du type :
- "veille", "benchmark", "comparer", "évaluer"
- "on devrait passer à", "quelle techno pour", "alternatives à"
- "est-ce que [outil/lib/framework] est adapté à notre projet"
- "qu'est-ce qui existe pour faire X"

## 👥 Agents impliqués

| Étape | Rôle | Responsabilité |
|---|---|---|
| 1 | `roles/architect.md` | Cadrage du besoin et critères d'évaluation |
| 2 | `roles/data-analyst.md` | Collecte et structuration des données |
| 3 | `roles/architect.md` | Analyse comparative et recommandation |
| 4 | `roles/security-engineer.md` | Évaluation sécurité des options retenues |
| 5 | `roles/tech-writer.md` | Formalisation du rapport de veille |

## 📋 Étapes

### Étape 1 — Cadrage
**Agent :** `architect`
**Objectif :** Définir précisément ce qu'on cherche et pourquoi.

**Checklist :**
- [ ] Identifier le problème ou le besoin à l'origine de la veille
- [ ] Définir les critères de sélection (performance, maturité, licence, coût, courbe d'apprentissage…)
- [ ] Identifier les contraintes non-négociables (compatibilité stack actuelle, RGPD, support…)
- [ ] Définir le scope : évaluation rapide ou étude approfondie ?
- [ ] Lister les options déjà connues ou pressenties

---

### Étape 2 — Collecte
**Agent :** `data-analyst`
**Objectif :** Rassembler des données fiables et comparables sur chaque option.

**Checklist :**
- [ ] Collecter les données clés pour chaque option (version, activité du projet, adoption, benchmarks)
- [ ] Vérifier la date des sources (les infos tech périsent vite)
- [ ] Identifier les cas d'usage similaires au projet (retours d'expérience, case studies)
- [ ] Repérer les limitations connues et les problèmes fréquemment remontés
- [ ] Structurer les données dans un tableau comparatif

---

### Étape 3 — Analyse & Recommandation
**Agent :** `architect`
**Objectif :** Produire une recommandation argumentée et contextuelle.

**Checklist :**
- [ ] Croiser les données avec les critères définis à l'étape 1
- [ ] Identifier les 2-3 finalistes
- [ ] Évaluer le coût de migration / d'adoption pour chaque option
- [ ] Formuler une recommandation principale + une alternative
- [ ] Justifier les choix avec les données, pas uniquement des opinions

---

### Étape 4 — Sécurité
**Agent :** `security-engineer`
**Objectif :** S'assurer que les options retenues n'introduisent pas de risques.

**Checklist :**
- [ ] Vérifier l'historique CVE de chaque option finaliste
- [ ] Évaluer la politique de maintenance et de patch sécurité
- [ ] Identifier les modèles de données ou d'accès introduits
- [ ] Vérifier la conformité avec les exigences RGPD / compliance du projet

---

### Étape 5 — Rapport
**Agent :** `tech-writer`
**Objectif :** Produire un document de référence exploitable et archivable.

**Checklist :**
- [ ] Rédiger un résumé exécutif (1 paragraphe)
- [ ] Inclure le tableau comparatif des options
- [ ] Documenter la recommandation et ses justifications
- [ ] Lister les prochaines étapes si la recommandation est acceptée
- [ ] Archiver le document dans la doc projet

---

## ✅ Définition de "terminé"

- [ ] Rapport de veille rédigé et archivé
- [ ] Recommandation validée par le décideur concerné
- [ ] Prochaines étapes identifiées (POC, adoption, abandon)

## 🔗 Workflows liés

- `feature-development.md` — si la veille débouche sur l'adoption d'un outil à intégrer
