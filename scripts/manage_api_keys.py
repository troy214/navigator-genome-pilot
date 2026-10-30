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


def cmd_issue(args: argparse.Namespace) -> int:
    full_key, record = api_keys.generate_key(args.label, notes=args.notes or "")
    print("=" * 70)
    print("  API KEY ISSUED — RESEARCH USE ONLY")
    print("=" * 70)
    print(f"  Facility label : {record['label']}")
    print(f"  Key ID         : {record['key_id']}")
    print(f"  Created at      : {record['created_at']}")
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
    print(f"{'KEY_ID':<16}  {'ACTIVE':<7}  {'CREATED':<27}  LABEL")
    print("-" * 90)
    for k in keys:
        print(f"{k.get('key_id', ''):<16}  "
              f"{str(k.get('active', False)):<7}  "
              f"{str(k.get('created_at', '')):<27}  "
              f"{k.get('label', '')}")
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
    p_issue.set_defaults(func=cmd_issue)

    p_list = sub.add_parser("list", help="List issued keys (no secrets).")
    p_list.set_defaults(func=cmd_list)

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
