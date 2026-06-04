# cortex-runtime — API reference

Three ways to consume the API contract:

## 1. Swagger UI / ReDoc (live, auto-generated)

FastAPI generates OpenAPI from the code, so a running instance always serves the **current**
contract — no drift:

- **Swagger UI** → `https://cortex.local.dev/docs`
- **ReDoc** → `https://cortex.local.dev/redoc`
- **Raw spec** → `https://cortex.local.dev/openapi.json`

> These pages are open (no auth) for local dev. Behind an ingress in production, gate or
> disable them as you see fit — the routes themselves stay protected by the `SecurityGate`.

## 2. Static OpenAPI ([`openapi.json`](openapi.json))

A versioned snapshot of the full surface (security + async + webhook), regenerated from the
app. Import it into any OpenAPI tool, or diff it in review. To regenerate after an API change:

```bash
cd runtime && python - <<'PY'
import json
from cortex_runtime.api import create_app
from cortex_runtime.app import WorkspaceConfig
from cortex_runtime.runtime import build_runtime
rt = build_runtime({"acme": WorkspaceConfig(root=".", theme=None)}, model_backend="demo",
                   manifest={"/support/triage": {"role": "support-engineer", "workflow": "support-triage"}})
json.dump(create_app(rt).openapi(), open("../docs/api/openapi.json", "w"), indent=2, ensure_ascii=False)
PY
```

## 3. Postman collection ([`cortex.postman_collection.json`](cortex.postman_collection.json))

Curated, with the auth wired up. **Import**, then set the collection **variables**:

| variable | what |
|---|---|
| `base_url` | e.g. `https://cortex.local.dev` |
| `token` | a Bearer token (mint via `python -m cortex_runtime.admin token …`) |
| `master_token` | an **admin** token (used by the *Admin* folder) |
| `hmac_secret` | a tenant's webhook HMAC secret (used by the *Webhook* folder) |
| `tenant`, `webhook_source` | defaults `acme` / `jira` |

Folders:

- **Health** — `/health`, `/ready` (no auth).
- **Run** — async `POST /run` (saves `run_id` to a variable), sync `?wait=true`, `GET /runs/{id}`,
  history, `/resolve`, `/reply`. Bearer at the collection level.
- **Monitoring** — `/audit`, `/auth-log`, `/budget` (Bearer).
- **Admin** — `/tenants`, `/tokens` (mint/list/revoke) — overrides auth with `master_token`.
- **Webhook** — `POST /webhook/{source}` with a **pre-request script that HMAC-signs the raw
  body** (`X-Cortex-Timestamp` + `X-Cortex-Signature` + `X-Delivery-Id`) using `hmac_secret`.
  The body is kept static (no `{{vars}}`) so the signed bytes match the sent bytes.

> Auth only matters when the server runs with `CORTEX_AUTH=on`. Open mode (dev) ignores the
> tokens/signature, so the collection works either way.
