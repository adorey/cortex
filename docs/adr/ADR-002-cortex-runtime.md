# ADR-002 — Cortex Runtime: deployable engine + runtime project binding

- **Status:** Accepted
- **Date:** 2026-06-02 (proposed) · 2026-06-02 (accepted)
- **Authors:** Cortex maintainers (initiated by @Slartibartfast, dispatched by @Oolon)
- **Affects:** Cortex packaging & deployment model, [ADR-001 cascade contract](ADR-001-layered-overrides.md), `setup.sh`, a new `cortex-runtime` service (out-of-repo or `cortex/runtime/`), secrets handling, host-project integration
- **Relates to:** [ADR-001](ADR-001-layered-overrides.md) — this ADR makes ADR-001's resolution algorithm **executable** at runtime

---

## 1. Context

Cortex today is a **design-time framework**: a layered cascade of Markdown (`roles/`, `capabilities/`, `personalities/`, `workflows/` + per-service `project-overview.md` / `project-context.md`) that an **LLM host reads and obeys** at conversation time. There is **no runtime**. The framework is "LLM-agnostic" in *philosophy*, but it relies entirely on a host (Claude Code, Copilot) reading the prose and behaving accordingly.

The cascade defined in [ADR-001](ADR-001-layered-overrides.md) is currently resolved in **three** non-executable ways:

1. A **prose contract** — the `resolveLayer()` pseudo-code in ADR-001 §3.1
2. **Prose instructions to an LLM** — the bootstrap protocol in each host's bootstrap file
3. A **bash validator** — `cortex/bin/validate-overlays.sh` (validation only, not resolution)

What is **missing** is the fourth form: an **executable resolver that a program (an API) can call at runtime**. Without it, Cortex cannot be *triggered* by anything other than a human typing into an LLM host.

### Triggering need (the driver)

The first concrete driver is **support automation** in a host workspace:

- An issue-tracker event (new ticket / human reply) must **trigger** an agent automatically.
- A dedicated `support-engineer` agent (Cortex base + a host overlay) must analyse the ticket, investigate (database read-only / anonymised, code, docs), and post an **internal comment** with its diagnosis and recommended next step.
- Iteration until resolution; later phases add dev-ticket creation, doc/ADR drafting, fix authoring, and statistics/alerts.

This is not a one-off. The same need recurs across contexts and projects (e.g. tech-watch → email, a steering dashboard, future projects). A reusable runtime is the natural next step.

### The core tension

> **The engine wants to be generic and deployable. But the *work* is project-bound** (its code, its database, its overlays, its secrets). **Where does the project live at runtime?**

Everything below resolves that tension.

## 2. Decision

We introduce **`cortex-runtime`**: a **deployable service** that turns Cortex from a design-time convention into an executable platform, by **compiling ADR-001** (an executable cascade resolver) and wrapping it in a thin, agnostic API plus an agentic loop and a model gateway.

The decision rests on **one non-negotiable architectural firewall**:

> **The runtime CONSUMES the spec. The spec NEVER depends on the runtime.**
> No `role.md` / `workflow.md` / overlay may contain an engine-specific field. The Markdown stays a pure, portable, host-agnostic knowledge layer (the "spec"); the runtime is a separate "engine" layer that reads it.

Cortex therefore conceptually splits into two layers (no fork, no rename of existing files):

```
cortex-spec     (existing: markdown cascade, ADR-001)   ← declarative, git-versioned, host-agnostic
      ▲   consumed by (one direction only)
cortex-runtime  (new: resolver + API + agentic loop + model gateway)   ← deployable engine
```

### Build vs Buy

The runtime is **assembled from mature components**; we build only the part that is uniquely ours.

| Layer | Decision | Rationale |
|---|---|---|
| **Cascade resolver** (ADR-001 → code) | **BUILD** | Cortex's singularity. ~50% already exists in `validate-overlays.sh`. |
| **Agnostic API** (`POST /run` + project endpoints) | **BUILD** (thin) | The entry contract of the engine. |
| **Agentic loop + MCP tool use** | **EMBED** | An agent SDK (e.g. Claude Agent SDK, Python/TS). Do not reimplement the `tool_use → result → loop` cycle. |
| **Model dispatch / model choice** | **EMBED** (optional) | An LLM gateway (e.g. LiteLLM). Aligns with Cortex's LLM-agnostic philosophy. |
| **Repo-aware execution / build / test** | **REUSE** existing CI | A pushed branch triggers the host project's existing pipeline. Do not rebuild CI. |

Language: **Python** for the first implementation (a web framework + an agent SDK), chosen for the AI ecosystem maturity. TypeScript remains a valid alternative.

## 3. Detailed contract

### 3.1 The executable resolver (ADR-001 compiled)

The runtime implements ADR-001 §3.1 as real code. The only parameter that varies between deployments is `root` (see §3.4):

```python
def resolve_layer(layer, file, service, root):           # ADR-001 §3.1, executable
    candidates = [root/"cortex"/"agents"/layer/file,      # base
                  root/"agents"/layer/file]               # workspace overlay
    if service:
        candidates.append(root/service/"agents"/layer/file)  # service overlay
    return [p for p in candidates if p.exists()]          # ordered base → workspace → service

def build_system_prompt(role, service, theme, root):      # additive merge per ADR-001 §3.2
    parts = []
    for layer, path in layers_for(role, theme):
        for p in resolve_layer(layer, path, service, root):
            parts.append(p.read_text())
    return "\n\n---\n\n".join(parts)
```

Merge semantics are inherited verbatim from ADR-001 §3.2 (workflows = replacement; roles/capabilities/personalities = additive; `characters.md` not overridable). The runtime **must reuse the same resolution logic** as `validate-overlays.sh` to avoid contract drift — ideally extracting a shared library that both consume.

### 3.2 The agnostic API

A single generic endpoint, plus project-declared aliases:

```
# Generic core — always present
POST /run
  { "workspace": "my-workspace", "role": "support-engineer",
    "service": "service-a", "workflow": "support-triage",
    "input": { ... }, "model": "<model-id>" }            # model is OPTIONAL

# Project-extensible domain endpoints — declared in a manifest, alias to /run
POST /support/analyze   → { role: support-engineer, workflow: support-triage }
POST /support/stats     → { role: data-analyst, ... }
POST /pr-review         → { role: lead-backend, workflow: code-review }
```

"Extensible in-project" means a project **declares** its endpoints (a manifest mapping a path to a `/run` payload); it does not write engine code. The engine stays agnostic — it hardcodes nothing project-specific.

### 3.3 The loop: the LLM decides, the workflow advises

The agentic loop's **mechanism** belongs to the agent SDK (call tool → feed result → repeat). The **decisions** — which tool, in what order, when done — belong to the **LLM**, conditioned by the resolved spec (project docs + codebase + workflow). A `workflow.md` is an **advisory recipe**, not executable control flow; the LLM reads it and applies judgement.

**Safety rails stay in code, not in the prompt.** The substance is improvised by the LLM; the guardrails are deterministic:

- Max iteration count per ticket → forced escalation beyond it.
- **Phase 1: no external action without human validation** — the agent only writes internal comments; dev-ticket creation, customer replies, and code writes are gated.
- Loop anti-recursion: the agent never reacts to its own output (state machine `awaiting-agent → awaiting-human → resolved`).

### 3.4 Project binding at runtime — the heart of the tension

The engine is generic; the project must reach it at execution time. Resolved with a **CI-runner model**: the engine is generic, the project is *bound* per run, the way a CI system binds a repo by checking it out.

**3.4.1 What a project needs:** (a) its overlays (markdown), (b) its code, (c) its data/issues, (d) its secrets.

**3.4.2 Two access modes, tiered by task — do not overpay:**

| Mode | Agent does | Needs | Binding |
|---|---|---|---|
| **Read / analyse** (≈ 90% of support) | reads code+docs, queries DB, reads issues | **read** access to code | a real local clone (mirror) |
| **Write / verify** (phase X) | edits code, build, tests | **buildable** environment | reuse host CI (push triggers it) |

Code access is via a **real git working tree**, deliberately **not** via a code-host API (a per-file peephole) nor a code-search index (a search, not a working copy). A real clone is the only base that serves **both** read-now and write-later (branch/commit/push in phase X).

**3.4.3 Topology — named warm mirrors (multi-tenant):**

One `cortex-runtime` instance holds **several named, persistent, read-mostly mirrors**, selected by name in the API. This is multi-tenant **without** per-request cloning.

```yaml
# cortex-runtime config (deployment-level)
workspaces:
  workspace-a: { mirror: /data/mirrors/workspace-a, secrets: workspace-a/* }
  workspace-b: { mirror: /data/mirrors/workspace-b, secrets: workspace-b/* }
```

- The mirror is cloned **once** (persistent volume), then kept current with **incremental `git fetch`** (deltas only) — periodic in background + on-demand `git pull` at job start for the repos a job touches. For a large multi-repo workspace the cost is amortised, **not paid per ticket**.
- `root` for the resolver (§3.1) = the selected workspace's mirror path.
- **Bind-at-deploy (per-project instance)** is the recommended starting topology; **bind-at-request (central multi-tenant)** is a later optimisation. The resolver code is identical in both — only the line that produces `root` differs.

**3.4.4 Concurrency & isolation — `git worktree`:**

Concurrent triggers must not collide on a shared working tree. The solution is **native git worktrees**, not hard-copies:

```bash
git -C <mirror>/<repo> fetch origin
git -C <mirror>/<repo> worktree add /tmp/run-<id> -b fix/<ISSUE> origin/master   # isolated tree, shared object store
#   ... agent works in /tmp/run-<id> ...
git -C <mirror>/<repo> push origin fix/<ISSUE>          # phase X → host CI runs automatically
git -C <mirror>/<repo> worktree remove /tmp/run-<id>
```

Worktrees share the (heavy) object store and isolate only the working files + branch — cheap and concurrency-safe. Read jobs use a worktree pinned at the current `master` SHA for a stable view. Worktree-per-job is the established pattern for parallel agents on one repo.

### 3.5 Model dispatch (optional gateway)

To make "choose the target model" a parameter and to stay LLM-agnostic, the runtime may call models **through an LLM gateway** (a self-hosted, OpenAI-compatible proxy: routing, fallbacks, per-tenant virtual keys, cost tracking). The agent SDK / CLI points at the gateway (a provider-format endpoint, or the OpenAI-compatible one). The gateway is **embedded, not built**, and is optional for an MVP.

### 3.6 Secrets — swappable backend, per-tenant, least privilege

Secrets are **never** baked into the image or git. They are loaded **per workspace (tenant)** from a swappable backend behind a stable interface:

```
Today:  K8s Secret (manually managed, encryption-at-rest ON, tight RBAC)  ─┐
                                                                           ├─▶ app reads a K8s Secret (unchanged)
Tomorrow: a secrets vault via External Secrets Operator / CSI driver  ─────┘
```

The application **always** consumes a K8s Secret (stable contract); migrating to a vault swaps only the *source* (e.g. External Secrets Operator pointing at the vault) without touching `cortex-runtime`. A code-level `SecretProvider.get(path)` interface is the equivalent at the application layer. A cloud-agnostic vault is preferred over a single-cloud manager for **multi-cloud + data-sovereignty** consistency, and unlocks dynamic short-lived credentials.

**Secret inventory (per tenant):**

| Secret | Purpose | Least privilege |
|---|---|---|
| LLM key (or gateway virtual key) | call the model | scoped per usage/budget |
| Issue-tracker token + service-account identity | read tickets, post internal comments, create dev tickets | **non-interactive** auth (headless cannot do interactive OAuth) |
| Code-host token (e.g. a scoped app token) | clone/fetch mirror; push branches (phase X) | **read-only** in phase 1; write added only in phase X |
| DB creds (read-only) — one set per cloud/region | investigation via DB tool | read-only, strictly |
| Webhook HMAC secret | verify inbound triggers are genuine | perimeter control |
| Runtime API token | protect `/run` if exposed | — |
| *(later)* email / chat / dashboard keys | alerts, stats, dashboard push | — |

**Rules:** never in image/git; scoped per tenant; least privilege with **phase separation** (read-only first, write only in phase X); dedicated **service accounts** (not personal tokens); short-lived/rotatable tokens; **audit log** of every action.

> Data-protection note: read-only protects **integrity** (no corruption), not **confidentiality**. The real GDPR control is **data anonymisation** (anonymised staging, nightly backups) — read-only is the belt, anonymisation is the braces.

### 3.7 Reference flow (support automation, end to end)

```
Issue tracker (human comment) ──webhook──▶ host endpoint ──enqueue──▶ queue ──▶ worker
   ▲                                                                     │ POST /run {workspace, role, workflow, issueKey}
   │ internal comment / branch push                                      ▼
   └──────────────────────────────────────────  cortex-runtime
                                                   ├─ load tenant profile (mirror + secrets)
                                                   ├─ resolve cascade (§3.1)
                                                   ├─ git worktree off named mirror (§3.4.4)
                                                   ├─ agentic loop (agent SDK) → [gateway] → model
                                                   │     tools via MCP: issue tracker, DB (RO/anon), code host
                                                   └─ act: internal comment  (phase 1)
                                                         | or push branch → host CI runs (phase X)
```

The inbound HTTP receiver, queue, and worker may live in the host project's existing stack (e.g. an existing web framework + a message broker) or in the runtime itself; that choice is host-specific and out of scope here.

## 4. Consequences

### Positive

- **ADR-001 becomes executable** — the cascade contract gains a fourth, programmatic form; any trigger (webhook, cron, CI, dashboard) can invoke a Cortex agent via an API.
- **One engine, many consumers** — support automation is the first client; other contexts (a steering dashboard, scheduled tech-watch, future projects) reuse the same runtime.
- **Agnosticism preserved** — the firewall (runtime consumes spec) keeps the Markdown portable; project specificity travels in the project's own git (overlays + manifest), never in the engine.
- **Cost discipline** — named warm mirrors + worktrees amortise cloning; CI reuse avoids rebuilding a second pipeline.
- **Future-proof toward phase X** — a real working tree supports branch/commit/push from day one.

### Negative

- **A platform to operate** — the runtime is a 24/7 service: SLA, security surface, observability, semver, and a named **owner**. This is a real product, not a script.
- **Crowded space** — LLMOps/agent platforms abound; discipline is required to stay thin (assemble, don't reinvent).
- **Multi-tenant secret convergence** — a central instance concentrates all tenants' secrets; per-tenant scoping and the HMAC perimeter are mandatory, not optional.
- **Spec/runtime coupling risk** — if convenience tempts engine-specific fields into the Markdown, the agnostic value is lost. The firewall must be enforced in review.

### Neutral

- **Topology is a deliberate choice** — per-project (start) vs central multi-tenant (scale); both use the identical resolver.
- **Secret backend is swappable** — K8s now, a vault later, behind a stable interface.
- **Host wiring stays host-specific** — trigger/queue/worker plumbing is not standardised by this ADR.

## 5. Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Keep a low-code orchestrator (local or hosted) as the brain** | Re-fragments intelligence outside Cortex; incoherent with the LLM-agnostic spec. Such a tool may remain for private automations, off the critical path. |
| **Custom per-service agent (no shared engine)** | No reuse across projects/contexts; duplicates the loop everywhere. |
| **Full agent-SDK headless, no service** | No stable entry contract, no project endpoints, weak operational glue (queue, rate-limit, audit). |
| **Low-code agent platforms (UI-defined apps)** | Brain lives in their UI/DB, not in the project's git — same fragmentation problem as a low-code orchestrator. |
| **A non-SDK language as the agent itself** | No official agent SDK in every language; it would have to reimplement the tool-use loop. The host language orchestrates, the engine (Python/TS) thinks. |
| **Code-host API / search index for code access** | A peephole and a search index, respectively — partial views. Neither supports phase-X branch/commit/push. A real clone does both. |
| **Clone-per-request multi-tenant** | Cloning a large multi-repo workspace per ticket = minutes of latency per job. Named warm mirrors amortise the cost. |
| **Hard-copy the workspace per concurrent job** | Duplicates the (large) object store per job. `git worktree` shares objects and isolates only working files. |
| **Build/test inside cortex-runtime** | Rebuilds a second CI to maintain. Pushing a branch triggers the host's existing pipeline for free. |
| **Single-cloud secrets manager** | Couples to a single cloud; conflicts with multi-cloud + data-sovereignty. A cloud-agnostic vault fits better. |
| **A graph framework as the loop engine** | Valid alternative, but an agent SDK already provides the loop + MCP for an MCP-native shop. Avoid redundancy. |

## 6. Follow-ups (out of scope for this ADR)

Dependent on this ADR, tracked separately:

1. **`support-engineer` role** (base) + **host overlay** + **character card** + **`support-triage` workflow** — the spec the runtime will consume.
2. **`cortex-runtime` MVP** — web framework + agent SDK + resolver extracted as a shared library with `validate-overlays.sh`.
3. **Trigger/queue/worker wiring** (host-specific: webhook → web framework → message broker → worker).
4. **Phase X** — branch authoring + push + CI feedback loop (requires a write-scoped code-host token).
5. **Statistics & alerts** — scheduled jobs (CronJob), volume baseline, semantic clustering of duplicate tickets.
6. **Steering dashboard** — metrics store + ingestion.
7. **Secret backend migration** — K8s Secrets → a vault via External Secrets Operator.
8. **Data anonymisation** for agent investigation (anonymised nightly-backed-up staging).

## 7. References

- [ADR-001 — Layered overrides](ADR-001-layered-overrides.md) — the cascade contract this ADR makes executable
- [cortex/agents/roles/prompt-manager.md](../../agents/roles/prompt-manager.md) — dispatch protocol
- [cortex/agents/workflows/README.md](../../agents/workflows/README.md) — workflow cascade
- [cortex/bin/validate-overlays.sh](../../bin/validate-overlays.sh) — existing partial resolver (validation)
- [cortex/docs/extending-layers.md](../extending-layers.md) — cascade user reference
