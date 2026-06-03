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

A token is useless until a **tenant** exists and a token is **minted**. Seed them with the
admin CLI, which writes to the same StateStore the server reads:

```bash
cd deploy

# 1. register the tenant (idempotent — re-run to reconfigure budgets / rate limit)
docker compose exec cortex-runtime \
  python -m cortex_runtime.admin tenant bluspark --daily 20 --monthly 300 --rate 60

# 2. mint a token, scoped to the workspaces it may invoke. The RAW token is printed ONCE.
docker compose exec cortex-runtime \
  python -m cortex_runtime.admin token bluspark --scope bluspark --label wbtb-dashboard
#   → store the printed `rt_live_…` value now; only its SHA-256 hash is kept in the DB.

# 3. call the API with it
curl -H "Authorization: Bearer rt_live_…" \
  "https://cortex.local.dev/runs?workspace=bluspark"
```

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

**wbtb dashboards:** mint a token scoped to the workspaces it monitors and poll `GET /runs`,
`GET /auth-log`, `GET /budget` with it — all Bearer-protected, all read-only.

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
