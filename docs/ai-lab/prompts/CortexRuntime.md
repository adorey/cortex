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

**Avancement :** Phase 0 ✅ · Phase 1 (résolveur) ✅ · Phase 2 (API + `derive_capabilities` + alias) ✅ · Phase 3 (boucle + garde-fous, **autonomie par requête**) ✅ · Phase 3b (adaptateur Agent SDK + **secrets `SecretProvider`** §3.6) ✅ — **87 tests (80 verts, 7 API skipped)**. Reste : binding mirrors/worktree (Phase 4).

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

### 2026-06-02 — Phase 2 : API agnostique + dérivation des capabilities
**Contexte :** implémentation de la couche API (ADR-002 §3.2) après validation de la fondation.
**Participants :** @Oolon → @Hactar
**Décisions / outputs :**
- **`derive_capabilities()`** ([context.py](../../../runtime/cortex_runtime/context.py)) solde la Nuance A : intersection du catalogue de capabilities de la cascade avec les technos citées dans `project-context.md`. Dette assumée : match par *stem* (« postgresql » oui, « Postgres » non) → table d'alias = raffinement ultérieur.
- **`resolve_run()`** ([run.py](../../../runtime/cortex_runtime/run.py)) : cœur déterministe framework-agnostique → bundle {system_prompt, capabilities, workflow advisory, layers, model}.
- **Shell FastAPI mince** ([api.py](../../../runtime/cortex_runtime/api.py)) : `POST /run`, `/health`, endpoints alias déclarés par **manifeste** (le projet déclare, il n'écrit pas de code moteur).
- **Firewall préservé** : `import cortex_runtime` ne tire pas FastAPI (import paresseux dans api.py) → suite de tests sans dépendance.
- Pré-résolution respectée : `/run` retourne le bundle résolu ; le branchement de la boucle agentique est **Phase 3**.
**Tags :** `phase-2`, `api`, `derive-capabilities`, `manifest`, `fastapi`

### 2026-06-02 — Phase 3 : boucle agentique + garde-fous en code
**Contexte :** implémentation du §3.3 — la boucle décide via le LLM, les garde-fous sont déterministes.
**Participants :** @Oolon → @Ford (infra boucle) → @Hactar (rails)
**Décisions / outputs :**
- **Honnêteté d'archi** : le mécanisme `tool_use→result→loop` appartient à l'Agent SDK (EMBED). Non installable/appelable ici → on livre la **part uniquement nôtre** : les garde-fous + un driver minimal avec frontière modèle injectable (`ModelClient`).
- **`safety.py`** : `ActionPolicy` (phase-1 : read + internal-comment seulement, le reste gated), `StateMachine` (awaiting-agent → awaiting-human → resolved, **anti-récursion** : l'agent ne réagit jamais à sa propre sortie), cap d'itérations → `ESCALATED`.
- **`tools.py`** : `Tool` (callable + `ActionKind`) + `ToolRegistry` → le gating est déterministe sans connaître ce que fait l'outil.
- **`loop.py`** : `AgentLoop` enrobe le `ModelClient` des rails ; action gated → halt + `AWAITING_HUMAN` ; testé avec un faux modèle scripté.
- **Point d'intégration documenté** : l'adaptateur Agent SDK réel implémente `ModelClient.propose` (Phase 3b, requiert SDK + clé, non exécutable ici).
**Tags :** `phase-3`, `agentic-loop`, `safety-rails`, `gating`, `anti-recursion`, `state-machine`

### 2026-06-02 — Revue humanoïde Phase 3 : autonomie par requête + taxonomie d'actions enrichie
**Contexte :** revue pré-commit de la Phase 3. L'humanoïde demande deux changements.
**Initial prompt :**
> « il ne faut pas synchroniser l'autonomie laissée aux agents en parlant de "phase" ou même en dur dans le code. Il faudrait que ça puisse être en paramètre d'entrée, directement dans la request. »
> « quitte à mettre des garde-fous, j'irais beaucoup plus loin dans les rôles disponibles : Access DB, git, push/pull, Jira edit, add comment, create code, read code, deletion action… »

**Décisions / outputs :**
- **Autonomie = allowlist par requête** : suppression de l'enum `Phase` hardcodé. `ActionPolicy(allowed=…)` ; nouveau champ `RunRequest.autonomy` / payload API (liste d'action-kinds). Omis → `SAFE_DEFAULT_ACTIONS` (least-privilege : reads + internal-comment). `ResolvedRun.allowed_actions` reflète l'autonomie effective ; nom d'action inconnu → `ValueError` → 422.
- **Taxonomie `ActionKind` granularisée** : `code-read/code-write`, `db-read/db-write`, `git-read/git-push`, `issue-read/issue-edit/issue-create`, `internal-comment`, `customer-reply`, `delete`. Permet de trancher finement (ex. autoriser `git-read` mais pas `git-push`).
- La notion ADR « phase 1 / phase X » devient une **convention de déploiement** exprimée par l'autonomie accordée, plus un enum en dur.
- 75 tests (68 verts, 7 API skipped).
**Tags :** `phase-3`, `review`, `autonomy`, `per-request`, `action-kind`, `least-privilege`

### 2026-06-02 — Phase 3b : adaptateur Agent SDK + secrets locaux
**Contexte :** l'humanoïde valide la review Phase 3 et suggère de prévoir les secrets en local via un fichier `.env.local`.
**Initial prompt :**
> « ok pour la review et le passage à la phase 3b, pour un fonctionnement en local on peut peut-être prévoir le coup pour les secrets dans un fichier type .env.local ou un truc dans le genre »

**Participants :** @Oolon → @Marvin (secrets/sécurité) → @Hactar (adaptateur)
**Décisions / outputs :**
- **`SecretProvider`** ([secret_provider.py](../../../runtime/cortex_runtime/secret_provider.py)) : interface stable `get(name)` (§3.6). Backends : `DotenvSecretProvider` (`.env.local`, dev), `EnvSecretProvider` (env / K8s Secret, prod), `ChainSecretProvider` (file→env), factory `local_secret_provider`. **Per-tenant** via préfixe de namespace (`WBTB_LLM_KEY`). Jamais commité : `.env.local` gitignoré + template `.env.local.example`.
- **`AnthropicAgentClient`** ([agent_client.py](../../../runtime/cortex_runtime/agent_client.py)) : implémente `ModelClient`, clé tirée du `SecretProvider`, **import `anthropic` paresseux** → package + tests restent install-free. Mapping `_to_messages` volontairement simple (référence ; le bookkeeping tool_use/tool_result revient à l'Agent SDK en prod).
- **Surface pure testée** : `interpret_response` (blocs réponse → `ModelTurn`) et `tool_schemas` (registry → défs d'outils Anthropic).
- 87 tests (80 verts, 7 API skipped). `import cortex_runtime` ne tire ni `anthropic` ni `fastapi`.
**Tags :** `phase-3b`, `secrets`, `secret-provider`, `dotenv`, `agent-sdk`, `model-client`, `least-privilege`

## 📚 Documents liés
- [ADR-002 — Cortex Runtime](../../adr/ADR-002-cortex-runtime.md) (+ addendum « Identité résolue vs travail investigué »)
- [ADR-001 — Layered overrides](../../adr/ADR-001-layered-overrides.md)
- [`runtime/README.md`](../../../runtime/README.md) — statut des phases

## 🔮 Next steps connus
- **Phase 2** (@Hactar) : API `POST /run` + endpoints alias par manifeste + `derive_caps()` (parsing `project-context.md`) — solde la Nuance A.
- **Phase 4** (@Ford) : binding — warm mirrors + `git worktree` + synchro submodules.
- **Dette** : migrer la validation des overlays vers le résolveur Python (retirer le test de parité bash).
