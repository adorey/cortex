"""Secrets — swappable backend behind a stable interface, per-tenant (ADR-002 §3.6).

The application always consumes ``SecretProvider.get(name)``; only the *source* changes:

  • local dev   → a ``.env.local`` file  (DotenvSecretProvider)
  • production  → environment variables, themselves fed by a K8s Secret / a vault via the
                  External Secrets Operator (EnvSecretProvider) — the stable contract

Secrets are **never** baked into the image or git. Per-tenant scoping is a ``namespace``
prefix, so one backend can hold several tenants' secrets without them colliding
(``WBTB_LLM_KEY`` vs ``BLUSPARK_LLM_KEY``).

Canonical secret names mirror the ADR §3.6 inventory (see ``KNOWN_SECRETS``).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Protocol, runtime_checkable

# Canonical secret names (ADR-002 §3.6 inventory) — for reference / validation, not a gate.
KNOWN_SECRETS = (
    "llm_key",                 # call the model (or a gateway virtual key)
    "issue_tracker_token",     # read tickets, post internal comments, create dev tickets
    "code_host_token",         # clone/fetch mirror; push branches (phase X)
    "db_creds",                # read-only DB investigation
    "webhook_hmac",            # verify inbound triggers are genuine
    "runtime_api_token",       # protect /run if exposed
)


class SecretNotFound(KeyError):
    """Raised when a required secret is absent from every backend."""


@runtime_checkable
class SecretProvider(Protocol):
    def get(self, name: str) -> str: ...
    def get_optional(self, name: str, default: Optional[str] = None) -> Optional[str]: ...


def _key(name: str, namespace: str) -> str:
    """``("llm_key", "wbtb")`` → ``WBTB_LLM_KEY``; ``("llm_key", "")`` → ``LLM_KEY``."""
    raw = f"{namespace}_{name}" if namespace else name
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper()


class _MappingSecretProvider:
    """Shared logic: normalise the name, look it up in a string→string mapping."""

    def __init__(self, mapping: Mapping[str, str], namespace: str = ""):
        self._mapping = mapping
        self.namespace = namespace

    def get_optional(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self._mapping.get(_key(name, self.namespace), default)

    def get(self, name: str) -> str:
        value = self.get_optional(name)
        if value is None:
            raise SecretNotFound(f"missing secret '{name}' (key '{_key(name, self.namespace)}')")
        return value


class EnvSecretProvider(_MappingSecretProvider):
    """Reads from the live process environment — the production contract (K8s Secret → env)."""

    def __init__(self, namespace: str = ""):
        import os
        super().__init__(os.environ, namespace)


class DotenvSecretProvider(_MappingSecretProvider):
    """Reads from a local ``.env.local`` file — dev only, never committed."""

    def __init__(self, path: Path, namespace: str = ""):
        super().__init__(parse_dotenv(Path(path).read_text(encoding="utf-8")), namespace)


class ChainSecretProvider:
    """Tries each provider in order; first hit wins (e.g. .env.local, then env)."""

    def __init__(self, providers: Iterable[SecretProvider]):
        self._providers = list(providers)

    def get_optional(self, name: str, default: Optional[str] = None) -> Optional[str]:
        for provider in self._providers:
            value = provider.get_optional(name)
            if value is not None:
                return value
        return default

    def get(self, name: str) -> str:
        value = self.get_optional(name)
        if value is None:
            raise SecretNotFound(f"missing secret '{name}' in all backends")
        return value


def parse_dotenv(text: str) -> Dict[str, str]:
    """Minimal ``.env`` parser: ``KEY=VALUE`` lines; ``#`` comments and blanks ignored;
    optional ``export`` prefix; surrounding single/double quotes stripped."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def local_secret_provider(namespace: str = "", env_file: str = ".env.local") -> SecretProvider:
    """Dev convenience: ``.env.local`` first (if present), then the process environment."""
    providers = []
    path = Path(env_file)
    if path.is_file():
        providers.append(DotenvSecretProvider(path, namespace))
    providers.append(EnvSecretProvider(namespace))
    return ChainSecretProvider(providers)
