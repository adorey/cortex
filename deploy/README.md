# Deploying cortex-runtime locally (Docker + Traefik + TLS)

Runs the runtime in a container, reachable at **`https://cortex.local.dev`** through a
**global, host-side Traefik** that terminates TLS.

## ⚠️ Prerequisite — a GLOBAL Traefik (not shipped here)

cortex-runtime does **not** ship its own reverse proxy. It expects a **host-side Traefik**, set
up **once** for your machine (shared by all your `*.local.dev` projects), that:

- terminates TLS for `*.local.dev` (use **mkcert** for a locally-trusted cert), and
- exposes a shared **external Docker network** named `traefik`.

cortex-runtime simply **joins that network** and declares routing labels (see `compose.yaml`).

If you don't have it yet, a minimal one-time setup:

```bash
# 1. a locally-trusted cert for *.local.dev
mkcert -install
mkcert "*.local.dev"

# 2. the shared network
docker network create traefik

# 3. run a host-side Traefik on that network, with the websecure (443) entrypoint and the mkcert
#    cert as the default TLS store. (Your existing Traefik for other *.local.dev projects already
#    does this — reuse it; don't run a second one.)

# 4. point the host at it
echo "127.0.0.1 cortex.local.dev" | sudo tee -a /etc/hosts
```

> This Traefik is **global / per-machine**, not part of this repo. Other projects (e.g. your app
> at `app.local.dev`) reuse the same instance and the same `traefik` network.

## Run cortex-runtime

```bash
cd deploy
cp .env.example .env                       # fill in CORTEX_PROJECT_PATH + secrets
cp cortex-mcp.json.example cortex-mcp.json  # declares + binds the cortex_jsm MCP (adjust if needed)
docker compose up --build
# → https://cortex.local.dev/health
```

The compose file mounts your project (`CORTEX_PROJECT_PATH`) read-only at `/workspace`, persists
the SQLite state store in a named volume, and passes secrets from `.env` (never baked into the
image).

## Security (ADR-004) — enabling Bearer auth

By default the API is **open** (local dev). Set `CORTEX_AUTH=on` in `.env` to protect the
direct routes (`/run`, `/resolve`, `/reply`) **and** the monitoring routes (`/runs`,
`/runs/{id}`, `/audit`, `/auth-log`, `/budget`) with Bearer tokens, and to run the
rate-limit / budget / idempotency chain on `/run`. `/health` stays open (liveness probe).

**Bootstrap: one manual "master" token, then everything over the API.** Only the master
token is created by hand; it then mints/revokes every other token via `POST /tokens`.

```bash
cd deploy

# 1. register the tenant (idempotent — re-run to reconfigure budgets / rate limit)
docker compose exec cortex-runtime \
  python -m cortex_runtime.admin tenant acme --daily 20 --monthly 300 --rate 60

# 2. mint the MASTER token (admin) — the only one made by hand. RAW printed ONCE.
docker compose exec cortex-runtime \
  python -m cortex_runtime.admin token acme --admin --label master
#   → store the printed `rt_live_…` now; only its SHA-256 hash is kept in the DB.
```

From then on the master token issues the rest over the API (no shell access needed):

```bash
MASTER="rt_live_…"

# mint a scoped, non-admin token (e.g. for a monitoring host)
curl -X POST -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
  -d '{"tenant":"acme","scopes":["acme"],"label":"monitoring-dashboard"}' \
  https://cortex.local.dev/tokens
#   → { "token_id": "...", "token": "rt_live_…" }   ← raw shown once

# list (metadata only — never the hash) / revoke / register another tenant
curl -H "Authorization: Bearer $MASTER" "https://cortex.local.dev/tokens?tenant=acme"
curl -X DELETE -H "Authorization: Bearer $MASTER" https://cortex.local.dev/tokens/<token_id>
curl -X POST -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
  -d '{"tenant":"newco","budget_daily_usd":5}' https://cortex.local.dev/tenants

# a minted token then calls the API
curl -H "Authorization: Bearer rt_live_…" "https://cortex.local.dev/runs?workspace=acme"
```

> The admin routes (`POST /tenants`, `POST|GET /tokens`, `DELETE /tokens/{id}`) require an
> **admin** token; a valid but non-admin token gets `403 forbidden` (logged in `auth_log`).
> A normal token minted via `POST /tokens` is non-admin unless created with `"admin": true`.

**What is stored, and how:**

| Secret | Where | Form |
|---|---|---|
| **Bearer tokens** | `api_tokens` table | **SHA-256 hash** only — never the raw value. Verified by hashing the incoming token + constant-time compare. Revocable / scoped / expirable. |
| **HMAC secrets** (webhook path) | `SecretProvider` (env / K8s Secret), key `<TENANT>_WEBHOOK_HMAC` | **raw** — HMAC must recompute the signature, so it can't be hashed; it therefore **never touches the DB**. |
| **Tenant config** (budgets, rate limit, enabled) | `tenants` table | plain operational config — no secrets. |
| **Every auth attempt** | `auth_log` table | who / route / verdict / reason — the perimeter log (read via `GET /auth-log`). |

> Tokens are **hashed, not encrypted**: they only ever need verifying, never recovering, so a
> one-way hash is strictly safer (no decryption key to leak). Plain SHA-256 is sufficient here
> because the token is a 256-bit random value (not a guessable password) — salting / bcrypt guard
> low-entropy inputs, which this isn't. Full at-rest encryption (TDE / encrypted volume) is a
> Postgres / disk concern, orthogonal to this.

**Monitoring hosts:** mint a token scoped to the workspaces it monitors and poll `GET /runs`,
`GET /auth-log`, `GET /budget` with it — all Bearer-protected, all read-only.

## Webhook triggers (ADR-004 §3.1)

Let a provider (Jira, GitHub…) trigger a run via `POST /webhook/{source}`, authenticated by
**HMAC over the raw body** (not a Bearer token — webhooks can't send one).

```bash
cp cortex-webhook.json.example cortex-webhook.json   # declare per-source bindings
# then in .env:  CORTEX_WEBHOOK_CONFIG=/config/cortex-webhook.json
```

A binding maps a `source` to a run, **agnostically** — no provider parsing in the engine:

```json
{ "jira": { "tenant": "acme", "role": "support-engineer",
            "workflow": "support-triage", "subject_path": "issue.key" } }
```

- `subject_path` is a **generic dotted lookup** into the payload (`issue.key` → the run's
  correlation `subject`); the whole payload is passed as the run `input`.
- The per-source **HMAC secret** lives in the `SecretProvider` as `<TENANT>_WEBHOOK_HMAC`
  (e.g. `ACME_WEBHOOK_HMAC`) — raw, **never in the DB**. Give the *same* secret to the provider.
- Headers: `X-Cortex-Timestamp` (unix seconds) + `X-Cortex-Signature: sha256=<hex of
  HMAC_SHA256(secret, "ts.rawbody")>`; optional `X-Delivery-Id` (the provider's delivery id) is
  used as the idempotency key. The runtime acks **202** (providers want a fast ack) and the run
  executes on the worker — poll `GET /runs/{id}`.
- **Replay vs retry**: an exact resend (same signature) is rejected `401 replay`; a re-signed
  retry (same delivery id, fresh signature) is deduped to the original run (`202 duplicate`).

## Notes

- **Backend**: the image bundles the Claude Code CLI (for `claude-cli`) **and** the `cortex_jsm`
  MCP (`cortex-jsm-mcp` on PATH). For `CORTEX_BACKEND=anthropic-api` or `demo` you can drop the
  Node layer from the Dockerfile for a smaller image.
- **Custom MCP (`cortex_jsm`)**: the Dockerfile installs it (`pip install /app/mcp` → the
  `cortex-jsm-mcp` command on PATH); `cortex-mcp.json` (mounted at `/config`, pointed to by
  `CORTEX_MCP_CONFIG`) both **declares** the server (`mcp_servers`) and **binds** its tools to
  `ActionKind`s (`mcp_bindings`). The server reads `JIRA_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN`;
  the example wires those from `.env` via `${JIRA_URL}` / `${JIRA_EMAIL}` / `${JIRA_BEARER_TOKEN}`,
  so set the `JIRA_*` secrets in `.env`. Posting `public:false` internal comments requires the
  account to be an **agent** on the service desk. (Installing it **outside Docker** — `pipx
  install ./mcp` — and the tool reference are documented in [`mcp/README.md`](../mcp/README.md).)
- **Secrets**: `.env` is gitignored; in a real cluster these come from a K8s Secret via the
  `SecretProvider` — the app code is unchanged (ADR-002 §3.6).
- **Postgres**: the compose ships a `postgres` service and the runtime uses the
  `PostgresStateStore` (`CORTEX_DATABASE_URL`) — so local is iso-prod (same backend as a cluster).
  State persists in the `cortex-pgdata` volume. (SQLite remains available via `CORTEX_DB` for a
  quick no-DB run.)
- **DB editor / port**: the runtime reaches Postgres internally on `postgres:5432` (the container
  port — never changes). To inspect the DB from your host, set `POSTGRES_PORT` to a free host port
  and connect your editor to `localhost:${POSTGRES_PORT}` (user `cortex`, db `cortex`).
