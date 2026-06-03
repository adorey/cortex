"""Operator CLI for the API security model (ADR-004 §3.7) — register tenants & mint tokens.

The Bearer path is unusable until a tenant exists and a token is issued; this is the tool
that seeds them. It writes to the same StateStore the server reads (selected from the
environment, like the server: ``CORTEX_DATABASE_URL`` → Postgres, ``CORTEX_DB`` → SQLite).

    # register / reconfigure a tenant (idempotent)
    python -m cortex_runtime.admin tenant acme --daily 20 --monthly 300 --rate 60

    # mint a token scoped to one or more workspaces — the RAW token is printed ONCE
    python -m cortex_runtime.admin token acme --scope acme --label monitoring-dashboard

    # the "master" token: an ADMIN token, minted by hand once, that can then create/revoke
    # every other token over the API (POST /tokens). This is the only token made manually.
    python -m cortex_runtime.admin token acme --admin --label master

Only a **hash** of the token is stored (§3.7); if the printed value is lost, revoke and
re-issue. HMAC webhook secrets are NOT managed here — they live in the SecretProvider
(``<TENANT>_WEBHOOK_HMAC``), never the DB.
"""

from __future__ import annotations

import argparse
import secrets as _secrets
import sys

from .auth import hash_token
from .state_store import store_from_env

TOKEN_PREFIX = "rt_live_"


def _mint_raw_token() -> str:
    return TOKEN_PREFIX + _secrets.token_urlsafe(32)


def cmd_tenant(args) -> int:
    store = store_from_env()
    store.upsert_tenant(args.name, enabled=not args.disabled,
                        budget_daily_usd=args.daily, budget_monthly_usd=args.monthly,
                        rate_limit_per_min=args.rate)
    t = store.get_tenant(args.name)
    print(f"tenant '{t.tenant}': enabled={t.enabled} daily={t.budget_daily_usd} "
          f"monthly={t.budget_monthly_usd} rate/min={t.rate_limit_per_min}")
    return 0


def cmd_token(args) -> int:
    store = store_from_env()
    if store.get_tenant(args.tenant) is None:
        print(f"error: unknown tenant '{args.tenant}' — register it first "
              f"(`admin tenant {args.tenant}`)", file=sys.stderr)
        return 2
    raw = _mint_raw_token()
    token_id = store.add_token(args.tenant, hash_token(raw),
                               scopes=args.scope or [args.tenant], label=args.label,
                               expires_at=args.expires, admin=args.admin)
    print(f"token_id: {token_id}")
    print(f"tenant:   {args.tenant}")
    print(f"scopes:   {args.scope or [args.tenant]}")
    print(f"admin:    {args.admin}")
    print("\nRAW TOKEN (shown once — store it now):\n")
    print(f"  {raw}\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cortex_runtime.admin",
                                     description="Register tenants and mint API tokens (ADR-004).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("tenant", help="register/reconfigure a tenant (idempotent)")
    pt.add_argument("name")
    pt.add_argument("--daily", type=float, default=None, help="rolling 24h cost_usd ceiling")
    pt.add_argument("--monthly", type=float, default=None, help="rolling 30d cost_usd ceiling")
    pt.add_argument("--rate", type=int, default=None, help="rate limit per minute")
    pt.add_argument("--disabled", action="store_true", help="register but turn off")
    pt.set_defaults(func=cmd_tenant)

    pk = sub.add_parser("token", help="mint a Bearer token for a tenant")
    pk.add_argument("tenant")
    pk.add_argument("--scope", action="append", help="workspace the token may invoke (repeatable)")
    pk.add_argument("--label", default=None, help="human label (e.g. monitoring-dashboard)")
    pk.add_argument("--expires", default=None, help="expiry as unix seconds (default: never)")
    pk.add_argument("--admin", action="store_true",
                    help="grant admin privilege (manage tenants/tokens via the API) — the master token")
    pk.set_defaults(func=cmd_token)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
