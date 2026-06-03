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
cp cortex-mcp.json.example cortex-mcp.json  # the mcp_bindings (adjust if needed)
docker compose up --build
# → https://cortex.local.dev/health
```

The compose file mounts your project (`CORTEX_PROJECT_PATH`) read-only at `/workspace`, persists
the SQLite state store in a named volume, and passes secrets from `.env` (never baked into the
image).

## Notes

- **Backend**: the image bundles the Claude Code CLI (for `claude-cli`) **and** the `cortex_jsm`
  MCP (`cortex-jsm-mcp` on PATH). For `CORTEX_BACKEND=anthropic-api` or `demo` you can drop the
  Node layer from the Dockerfile for a smaller image.
- **Secrets**: `.env` is gitignored; in a real cluster these come from a K8s Secret via the
  `SecretProvider` — the app code is unchanged (ADR-002 §3.6).
- **Postgres**: the SQLite store is fine for a single local node; multi-replica / production needs
  the Postgres `StateStore` backend (ADR-003 follow-up).
