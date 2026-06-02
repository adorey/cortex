# Cortex Runtime — Conception & décisions

> 🧵 Thread d'archivage continu — append-only.
> Convention : une nouvelle session = une nouvelle entrée timeline, jamais un nouveau fichier.

## 📌 Synthèse vivante

**Quoi :** implémentation du `cortex-runtime` décidé par [ADR-002](../../adr/ADR-002-cortex-runtime.md) — le moteur déployable qui rend la cascade [ADR-001](../../adr/ADR-001-layered-overrides.md) **exécutable**.

**Topologie retenue :** monorepo. Le moteur vit dans [`runtime/`](../../../runtime/) (Python), à côté de la spec markdown. Le **firewall** (le runtime consomme la spec, jamais l'inverse) est garanti **par un test** ([`runtime/tests/test_firewall.py`](../../../runtime/tests/test_firewall.py)), pas par une frontière de repo.

**Décisions structurantes (gravées) :**
1. **Pré-résolution déterministe (Option A).** Le runtime exécute `resolve_layer` et **injecte** le prompt système assemblé dans le contexte initial du modèle. On ne laisse pas le LLM bootstrapper sa propre identité par lecture de prose. *« On résout et on intègre au contexte initial. »*
2. **Identité résolue vs travail investigué** — distinction clé : le résolveur fabrique l'**identité** (rôle + perso + capabilities) ; la boucle agentique lit le **code du projet** en live pour faire le travail. Deux lectures distinctes, jamais confondues.
3. **Le moteur ne transporte aucune spec.** `root` pointe sur le mirror du projet ; `root/cortex` = le cortex du projet (submodule). Une seule cascade en jeu (celle du projet) → **zéro collision** de spec.
4. **Validation des overlays → Python.** À terme, `validate-overlays.sh` se réduit à une coquille appelant le résolveur Python (source unique de vérité), remplaçant le test de parité bash↔Python.

**Avancement :** Phase 0 (scaffolding + firewall) ✅ · Phase 1 (résolveur §3.1/§3.2 + tests) ✅ — **33 tests verts**. Phase 2 (API `POST /run`) en cours.

## 🗓️ Timeline

### 2026-06-02 — Récapitulatif ADR-002 & démarrage du développement
**Contexte :** l'humanoïde demande un récap de l'ADR-002, puis lance la phase de développement.
**Initial prompt :**
> « peux tu regarder l'adr 2 et me faire une rapide récapitulatif » → « je suis ready pour qu'on passe à la phase de développement de l'ADR-2. Tu me fait une branche de feat et tu me propose un plan d'attaque ? »

**Optimised prompt :** récap ADR-002 + branche `feat/cortex-runtime` + plan d'attaque incrémental par phases.
**Participants :** @Oolon → @Slartibartfast (architecture) → @Hactar (build Python)
**Décisions / outputs :**
- Branche `feat/cortex-runtime` créée.
- Plan en 7 phases (0→6), MVP = follow-up #2 de l'ADR.
- Décisions verrouillées : **`runtime/` dans ce repo** + **résolveur d'abord**.
- Phase 0+1 livrées : [`resolver.py`](../../../runtime/cortex_runtime/resolver.py), fixtures 3-niveaux, 31 tests unitaires + test de parité vs `validate-overlays.sh` + test firewall.
**Tags :** `adr-002`, `runtime`, `resolver`, `phase-0`, `phase-1`

### 2026-06-02 — Clarification architecturale : pré-résolution déterministe
**Contexte :** l'humanoïde interroge la nature du résolveur (vérifie vs résout), l'injection de contexte, et le risque de collision avec les submodules.
**Initial prompt :**
> « le resolver vérifie ce que fait déjà le script shell ? » · « détaille les deux nuances » · « exemple de call à build_system_prompt » · « il ne risque pas d'avoir de collisions avec les submodules ? »

**Optimised prompt :** clarifier validate vs resolve ; détailler la dette (capabilities explicites, parité bash↔Python) ; trancher pré-résolution (A) vs auto-bootstrap (B).
**Participants :** @Oolon
**Décisions / outputs :**
- **validate ≠ resolve** : le `.sh` vérifie la *bonne formation* des overlays ; le résolveur lit et **fusionne** le contenu pour produire le prompt. Logique de cascade commune, métiers distincts.
- **Nuance A (capabilities)** : le résolveur les reçoit en paramètre explicite ; le mapping *stack → capability* (parsing `project-context.md`) appartient à la couche API (Phase 2).
- **Nuance B (parité)** : bash et Python ne partagent pas de lib → deux implémentations + test de parité ⇒ dérive **détectable**, pas **impossible**. Chemin retenu : validation en Python à terme.
- **Tranché → Option A (déterministe)** confirmée par l'humanoïde : on résout et on intègre au contexte initial.
- **Submodules** : pas de collision de spec (le moteur ne transporte aucun markdown). Vraie nuance = mécanique git (`git submodule update` après fetch, worktree + submodules) → à traiter en Phase 4.
- Confirmé : pour wbtb **et** Bluspark, cortex intégré au workspace via `root` (submodule), indépendamment du choix A/B.
**Tags :** `architecture`, `decision`, `pre-resolution`, `submodule`, `firewall`

## 📚 Documents liés
- [ADR-002 — Cortex Runtime](../../adr/ADR-002-cortex-runtime.md) (+ addendum « Identité résolue vs travail investigué »)
- [ADR-001 — Layered overrides](../../adr/ADR-001-layered-overrides.md)
- [`runtime/README.md`](../../../runtime/README.md) — statut des phases

## 🔮 Next steps connus
- **Phase 2** (@Hactar) : API `POST /run` + endpoints alias par manifeste + `derive_caps()` (parsing `project-context.md`) — solde la Nuance A.
- **Phase 4** (@Ford) : binding — warm mirrors + `git worktree` + synchro submodules.
- **Dette** : migrer la validation des overlays vers le résolveur Python (retirer le test de parité bash).
