#!/usr/bin/env python3
"""Manage researcher API keys for the Navigator Genome Pilot.

RESEARCH USE ONLY. These keys authenticate research facilities to a research tool
whose outputs are hypotheses with explicit uncertainty — never a diagnosis and never
medical advice. Issuing a key grants programmatic access to the /api/v1 namespace only.

Run with the project interpreter, from the repo root:

    /opt/abacus-python/bin/python3 scripts/manage_api_keys.py issue --label "Facility Name"
    /opt/abacus-python/bin/python3 scripts/manage_api_keys.py list
    /opt/abacus-python/bin/python3 scripts/manage_api_keys.py revoke --key-id nvk_xxxxxxxx

Keys are stored only as salted SHA-256 hashes in data/api_keys.json (git-ignored).
The full plaintext key is shown exactly once, at issue time, and cannot be recovered.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `src` / `config` importable when run as a script from anywhere.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils import api_keys  # noqa: E402


def _limits_from_args(args: argparse.Namespace) -> dict:
    """Collect the optional per-key limit overrides provided on the command line."""
    limits = {}
    if args.max_variants_per_request is not None:
        limits["max_variants_per_request"] = args.max_variants_per_request
    if args.requests_per_minute is not None:
        limits["requests_per_minute"] = args.requests_per_minute
    if args.requests_per_day is not None:
        limits["requests_per_day"] = args.requests_per_day
    if args.max_concurrent is not None:
        limits["max_concurrent"] = args.max_concurrent
    return limits


def _format_limits(limits: dict) -> str:
    """One-line rendering of a key's limit overrides (or 'defaults' when none)."""
    if not limits:
        return "defaults"
    return ", ".join(f"{k}={v}" for k, v in limits.items())


def cmd_issue(args: argparse.Namespace) -> int:
    limits = _limits_from_args(args)
    try:
        full_key, record = api_keys.generate_key(
            args.label, notes=args.notes or "", limits=limits or None)
    except ValueError as e:
        print(f"error: {e}")
        return 2
    print("=" * 70)
    print("  API KEY ISSUED — RESEARCH USE ONLY")
    print("=" * 70)
    print(f"  Facility label : {record['label']}")
    print(f"  Key ID         : {record['key_id']}")
    print(f"  Created at      : {record['created_at']}")
    print(f"  Limit overrides: {_format_limits(record.get('limits') or {})}")
    print("  (any limit not overridden uses the global default in config/settings.py)")
    print()
    print("  Full API key (send as the X-API-Key header):")
    print()
    print(f"      {full_key}")
    print()
    print("  !! This is the ONLY time the full key is shown. Store it securely and")
    print("  !! share it with the facility over a secure channel. It cannot be")
    print("  !! recovered — only revoked and re-issued.")
    print("=" * 70)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    keys = api_keys.list_keys()
    if not keys:
        print("No API keys issued yet.")
        return 0
    print(f"{'KEY_ID':<16}  {'ACTIVE':<7}  {'CREATED':<27}  {'LABEL':<28}  LIMITS")
    print("-" * 110)
    for k in keys:
        print(f"{k.get('key_id', ''):<16}  "
              f"{str(k.get('active', False)):<7}  "
              f"{str(k.get('created_at', '')):<27}  "
              f"{str(k.get('label', '')):<28}  "
              f"{_format_limits(k.get('limits') or {})}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Show one key's details, including its effective limits (overrides + defaults)."""
    from src.utils.throttle import effective_limits

    keys = api_keys.list_keys()
    rec = next((k for k in keys if k.get("key_id") == args.key_id), None)
    if rec is None:
        print(f"No key found with key_id {args.key_id!r}.")
        return 1
    overrides = rec.get("limits") or {}
    eff = effective_limits(rec)
    print("=" * 70)
    print(f"  Key ID         : {rec.get('key_id')}")
    print(f"  Facility label : {rec.get('label')}")
    print(f"  Active         : {rec.get('active')}")
    print(f"  Created at      : {rec.get('created_at')}")
    if rec.get("revoked_at"):
        print(f"  Revoked at      : {rec.get('revoked_at')}")
    if rec.get("notes"):
        print(f"  Notes          : {rec.get('notes')}")
    print(f"  Limit overrides: {_format_limits(overrides)}")
    print("  Effective limits (what is actually enforced):")
    for name, val in eff.items():
        tag = "override" if name in overrides else "default"
        print(f"      {name:<28} = {val}  ({tag})")
    print("=" * 70)
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    ok = api_keys.revoke_key(args.key_id)
    if ok:
        print(f"Revoked API key {args.key_id}. It will no longer authenticate.")
        return 0
    print(f"No active key found with key_id {args.key_id!r} (already revoked or unknown).")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Navigator Genome Pilot researcher API keys (research use only).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_issue = sub.add_parser("issue", help="Issue a new API key for a research facility.")
    p_issue.add_argument("--label", required=True,
                         help="Research facility name this key is issued to.")
    p_issue.add_argument("--notes", default="", help="Optional free-text notes.")
    # Optional per-key throttling overrides. Omitted flags fall back to the global
    # defaults in config/settings.py. All must be positive integers.
    p_issue.add_argument("--max-variants-per-request", type=int, default=None,
                         dest="max_variants_per_request",
                         help="Override the per-request variant cap for this key.")
    p_issue.add_argument("--requests-per-minute", type=int, default=None,
                         dest="requests_per_minute",
                         help="Override the per-minute request rate limit for this key.")
    p_issue.add_argument("--requests-per-day", type=int, default=None,
                         dest="requests_per_day",
                         help="Override the per-day request rate limit for this key.")
    p_issue.add_argument("--max-concurrent", type=int, default=None,
                         dest="max_concurrent",
                         help="Override the max concurrent in-flight analyses for this key.")
    p_issue.set_defaults(func=cmd_issue)

    p_list = sub.add_parser("list", help="List issued keys (no secrets).")
    p_list.set_defaults(func=cmd_list)

    p_inspect = sub.add_parser(
        "inspect", help="Show one key's details and effective limits.")
    p_inspect.add_argument("--key-id", required=True, dest="key_id",
                           help="Public key_id to inspect, e.g. nvk_1a2b3c4d.")
    p_inspect.set_defaults(func=cmd_inspect)

    p_revoke = sub.add_parser("revoke", help="Revoke a key by its key_id.")
    p_revoke.add_argument("--key-id", required=True, dest="key_id",
                          help="Public key_id to revoke, e.g. nvk_1a2b3c4d.")
    p_revoke.set_defaults(func=cmd_revoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
