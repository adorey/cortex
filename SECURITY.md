# Security Policy

Cortex is two things with very different exposure, and this policy covers both:

- the **framework layer** (`agents/`, `templates/`, `setup.sh`) — Markdown and shell that a
  host project mounts and that an LLM reads;
- **`cortex-runtime`** — an HTTP service that drives an agentic loop, persists state and
  optionally enforces an API trust model
  ([ADR-004](docs/adr/ADR-004-api-security.md)).

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private reporting instead:
[**Report a vulnerability**](https://github.com/adorey/cortex/security/advisories/new).
It opens a confidential thread with the maintainers and lets a fix and an advisory be
published together.

Useful things to include, if you have them:

- which layer is affected (framework files, `setup.sh`, or the runtime);
- the version or commit (`git describe --tags`);
- how the runtime is exposed, if it is involved — behind an authenticating proxy, or
  reachable directly;
- a minimal reproduction, and the impact you believe it has.

## What to expect

Maintained by a single person, so honest expectations rather than a corporate SLA:

| Step | Target |
|---|---|
| Acknowledgement of your report | within 5 days |
| Initial assessment (valid / not / need more) | within 10 days |
| Fix for a confirmed high-impact issue | best effort, prioritised over features |
| Public advisory + release note | published together with the fix |

Credit is given in the advisory unless you prefer to stay anonymous.

## Supported versions

| Version | Supported |
|---|---|
| `0.4.x` | ✅ current |
| `< 0.4` | ❌ please upgrade |

Pre-1.0: fixes land on `main` and in the next release. There are no backports.

## Scope

**In scope** — anything shipped by this repository: the runtime's HTTP surface,
authentication and rate limiting, persistence, the job queue, HMAC webhooks, the
deployment definitions under `deploy/`, and `setup.sh` (it writes files into a host
project, so path handling matters).

**Out of scope** — how *you* deploy it: your reverse proxy, TLS termination, secret
storage, cluster policies, and any modification you made. Also out of scope: findings that
require an attacker to already hold valid administrative credentials, and scanner output
with no demonstrated impact.

## A note specific to an agent framework

Cortex composes instructions that an LLM then acts on. Two classes of issue are worth
reporting even though they are not memory-safety bugs:

- **Instruction injection through a layer** — content in a role, capability, personality or
  overlay file that can make an agent ignore its guardrails, escalate its own permissions,
  or exfiltrate context.
- **Cascade escape** — an overlay or template able to read or write outside the host
  project's expected paths.

Both are in scope. Prompt-level jailbreaks of the *underlying model* are not: report those
to the model provider.

## Secrets

No real credential belongs in this repository, including in an example. The runtime reads
its secrets from the environment or from a mounted secret store; `deploy/` ships
placeholders only. If you believe a real credential was ever committed here, report it
through the private channel above.
