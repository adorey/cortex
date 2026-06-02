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

**Avancement :** Phase 0 ✅ · 1 (résolveur) ✅ · 2 (API + `derive_capabilities` + alias) ✅ · 3 (boucle + garde-fous, autonomie par requête) ✅ · 3b (adaptateur SDK + secrets §3.6) ✅ · ADR-003 + StateStore (persistance, anti-récursion durable) ✅ · **5 (vertical slice exécutable — le MVP tourne, backend demo sans clé)** ✅ — **109 tests (102 verts, 7 API skipped)**. Reste : binding mirrors/worktree (Phase 4, prod), vrais outils MCP, sémantique handoff, et le test réel avec un vrai modèle (côté humanoïde).

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
- Confirmé : pour les projets hôtes, cortex intégré au workspace via `root` (submodule), indépendamment du choix A/B.
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
- **`SecretProvider`** ([secret_provider.py](../../../runtime/cortex_runtime/secret_provider.py)) : interface stable `get(name)` (§3.6). Backends : `DotenvSecretProvider` (`.env.local`, dev), `EnvSecretProvider` (env / K8s Secret, prod), `ChainSecretProvider` (file→env), factory `local_secret_provider`. **Per-tenant** via préfixe de namespace (`ACME_LLM_KEY`). Jamais commité : `.env.local` gitignoré + template `.env.local.example`.
- **`AnthropicAgentClient`** ([agent_client.py](../../../runtime/cortex_runtime/agent_client.py)) : implémente `ModelClient`, clé tirée du `SecretProvider`, **import `anthropic` paresseux** → package + tests restent install-free. Mapping `_to_messages` volontairement simple (référence ; le bookkeeping tool_use/tool_result revient à l'Agent SDK en prod).
- **Surface pure testée** : `interpret_response` (blocs réponse → `ModelTurn`) et `tool_schemas` (registry → défs d'outils Anthropic).
- 87 tests (80 verts, 7 API skipped). `import cortex_runtime` ne tire ni `anthropic` ni `fastapi`.
**Tags :** `phase-3b`, `secrets`, `secret-provider`, `dotenv`, `agent-sdk`, `model-client`, `least-privilege`

### 2026-06-02 — Décision : couche de persistance (ADR-003) + multi-provider différé
**Contexte :** revue du code Phase 3b. L'humanoïde soulève le nommage des clés multi-provider et propose d'introduire une base de données interne dès maintenant.
**Initial prompt :**
> « demain je veux pouvoir switcher entre modèle anthropic et openai, le modèle de nommage des clés va être un frein » · « est-ce qu'on ne ferait pas mieux dès maintenant de partir sur une base de données interne à cortex (config à chaud, GUI future, log pour le monitoring) ? »

**Participants :** @Oolon → @Slartibartfast (frontière archi) → @Marvin (secrets)
**Décisions / outputs :**
- **Multi-provider : laissé tel quel** pour l'instant (`llm_key` conservé, Anthropic-only). La vraie réponse = **model gateway LiteLLM** (§3.5) : une clé virtuelle par tenant, routing provider dans le gateway → le nommage cesse d'être un frein. Différé.
- **Persistance : OUI, mais opérationnel uniquement**, derrière une interface `StateStore` swappable (SQLite dev / Postgres prod), même discipline que `SecretProvider`. **Frontière git↔DB validée** par l'humanoïde : git = ce qui *définit* l'agent (spec) ; DB = ce que l'agent *produit/vit* (état de conversation pour l'anti-récursion, audit §3.6, run history). La spec n'est **jamais** déplacée en base (firewall ADR-002 §5).
- **Trou identifié** : la `StateMachine` anti-récursion est aujourd'hui en mémoire → non-fonctionnelle entre deux webhooks. La persistance la rend durable.
- **[ADR-003](../../adr/ADR-003-persistence-state-layer.md) rédigé et accepté** — après revue humanoïde : `ticket` → `subject` (agnostique), et scrub des noms de projets privés (WBTB/Bluspark → `acme`) dans les fichiers de session + le guide `extending-layers.md` (ADR-001 laissé tel quel comme trace ratifiée).
**Tags :** `adr-003`, `persistence`, `state-store`, `audit`, `git-vs-db`, `litellm`, `multi-provider`

### 2026-06-02 — ADR-003 follow-up #1 : StateStore + session orchestration
**Contexte :** implémentation de la couche de persistance actée par l'ADR-003.
**Participants :** @Oolon → @Vogon (schéma/persistance) → @Hactar (wiring)
**Décisions / outputs :**
- **`state_store.py`** ([lien](../../../runtime/cortex_runtime/state_store.py)) : interface `StateStore` (keyed by `subject`, agnostique) + dataclasses `RunRecord`/`AuditEntry`. Backends swappables : `InMemoryStateStore` (tests), `SqliteStateStore` (fichier ou `:memory:`). Postgres = backend ultérieur, même interface.
- **`session.py`** : `run_session()` = orchestration de référence §3.3 (load state → guard anti-récursion → run loop → record actions → persist). `mark_human_reply()` ré-arme l'agent.
- **Anti-récursion durable démontrée** : invocation 1 → action gated → `AWAITING_HUMAN` persisté ; invocation 2 sur le même `subject` → **skipped** (l'agent ne réagit pas à sa propre sortie) ; après `mark_human_reply` → l'agent re-tourne et résout.
- Audit log append-only branché ; `.db`/`.sqlite3` gitignorés.
- 101 tests (94 verts, 7 API skipped).
- **Sémantique à raffiner (noté)** : « agent poste un commentaire interne puis attend l'humain » ≠ `RESOLVED`. Aujourd'hui seul un *gated action* mène à `AWAITING_HUMAN`. Un futur signal `handoff`/`await_human` (ou un mapping phase-1) reste à définir côté boucle.
**Tags :** `adr-003`, `state-store`, `sqlite`, `session`, `anti-recursion`, `audit`

### 2026-06-02 — Phase 5 : vertical slice exécutable (MVP qui tourne)
**Contexte :** relier les briques en un fil exécutable + prévoir l'auth abonnement Max pour les tests locaux (coût marginal nul), clé API pour le déploiement.
**Participants :** @Oolon → @Ford (assemblage) → @Hactar
**Décisions / outputs :**
- **`runtime.py`** : `Runtime` + `build_runtime` assemblent resolve → outils → ModelClient → `AgentLoop` → `run_session`. `make_model_client(backend)` swappable : `demo` (no-dep), `claude-cli` (Max via CLI), `anthropic-api` (clé).
- **`local_tools.py`** : `read_file` / `list_files` / `post_internal_comment` (sandboxés sous `root`) → run observable sans MCP.
- **`demo_model.py`** : `DemoModelClient` (canned, zéro dépendance) → **smoke-test du fil complet sans clé ni SDK** ; `ScriptedModelClient` (double de test).
- **`agent_client.py`** : adaptateur Pro/Max ajouté à côté de `AnthropicAgentClient`. **Correction (vérifiée via claude-code-guide)** : le Claude *Agent SDK* (lib) **n'autorise pas** l'auth abonnement — clé API obligatoire. Seule la **CLI Claude Code** peut utiliser l'abonnement (`claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN`). → l'adaptateur Max est donc `ClaudeCodeCliClient` (sous-process CLI), pas un client SDK. Backend renommé `claude-agent-sdk` → `claude-cli`.
- **API** : `POST /resolve` (résout) + `POST /run` (exécute) + alias manifeste (exécutent) ; `create_app(runtime)`. Entrypoint `python -m cortex_runtime` (config par env).
- **`subject`** ajouté à `RunRequest`/payload (fallback `input.issue` → `default`).
- **Smoke test live (backend demo)** : resolve → `list_files` → `post_internal_comment` → `resolved`, état persisté, re-trigger même `subject` → **skipped** (anti-récursion). 109 tests (102 verts, 7 API skipped).
- **Auth** : Max/Agent-SDK pour tests locaux (décidé), clé API Console pour le service déployé. Frontière = `ModelClient`, zéro revert.
**Tags :** `phase-5`, `vertical-slice`, `runtime`, `demo-backend`, `local-tools`, `claude-cli`, `mvp`

### 2026-06-02 — Phase 5b : ClaudeCodeCliClient finalisé (chemin Max) + guide setup
**Contexte :** finir le client abonnement Max ; l'humanoïde testera via clé API en fin de semaine, mais veut le chemin Max + un pas-à-pas.
**Participants :** @Oolon → @Ford (CLI/infra) → @Hactar
**Décisions / outputs :**
- **Détails CLI vérifiés** (claude-code-guide) : `claude -p` lance sa **propre boucle agentique** et rend le texte final (one-shot). Flags exacts : `--append-system-prompt`, `--model`, `--output-format json` (`.result` + `usage`/`total_cost_usd`), `--allowedTools` (CSV), cwd via subprocess, auth `CLAUDE_CODE_OAUTH_TOKEN` (⚠️ `ANTHROPIC_API_KEY` prend le dessus → retiré de l'env du subprocess).
- **`ClaudeCodeCliClient`** implémenté : one-shot via subprocess → `ModelTurn(final_text)`. Notre **autonomie (`ActionKind`) → `--allowedTools`** (read-only par défaut : `Read,Grep,Glob`). `last_usage` capturé (tokens/coût) pour monitoring futur.
- Helpers purs **testés** : `cli_allowed_tools`, `build_cli_argv`, `parse_cli_result`. La méthode `propose` (subprocess) non testée ici (besoin CLI + login).
- **`root` + autonomie** câblés du `Runtime` jusqu'au client.
- **Guide pas-à-pas** : [runtime/docs/claude-cli-setup.md](../../../runtime/docs/claude-cli-setup.md) (install CLI → `setup-token` → env → run → curl).
- 115 tests (108 verts, 7 API skipped).
**Tags :** `phase-5b`, `claude-cli`, `subscription`, `subprocess`, `allowed-tools`, `setup-guide`

## 📚 Documents liés
- [ADR-002 — Cortex Runtime](../../adr/ADR-002-cortex-runtime.md) (+ addendum « Identité résolue vs travail investigué »)
- [ADR-003 — Persistence & operational state layer](../../adr/ADR-003-persistence-state-layer.md) (Accepted)
- [ADR-001 — Layered overrides](../../adr/ADR-001-layered-overrides.md)
- [`runtime/README.md`](../../../runtime/README.md) — statut des phases

## 🔮 Next steps connus
- **Phase 2** (@Hactar) : API `POST /run` + endpoints alias par manifeste + `derive_caps()` (parsing `project-context.md`) — solde la Nuance A.
- **Phase 4** (@Ford) : binding — warm mirrors + `git worktree` + synchro submodules.
- **Dette** : migrer la validation des overlays vers le résolveur Python (retirer le test de parité bash).
