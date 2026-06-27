#!/usr/bin/env python3
"""Generate SignedHeaderAuthProvider curl headers for local enterprise testing."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import time
from typing import Any

from datus.api.constants import HEADER_PRINCIPAL, HEADER_USER_ID
from datus_enterprise.auth_provider import SignedHeaderAuthProvider


def _csv_or_repeated(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item and item not in items:
                items.append(item)
    return items


def _json_object(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError("--principal must be a JSON object.")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate signed Datus enterprise identity headers.")
    parser.add_argument("--method", default="GET", help="HTTP method to sign.")
    parser.add_argument("--path", required=True, help="Request path to sign, for example /api/v1/me.")
    parser.add_argument("--user", default="alice", help="User id for X-Datus-User-Id.")
    parser.add_argument("--project", default="enterprise", help="Project id for X-Datus-Project-Id.")
    parser.add_argument("--role", action="append", default=None, help="Role value. Repeat or comma-separate.")
    parser.add_argument(
        "--permission",
        action="append",
        default=None,
        help="Permission value. Repeat or comma-separate.",
    )
    parser.add_argument("--principal", type=_json_object, default={}, help="Principal JSON object.")
    parser.add_argument("--email", default="", help="Email header value.")
    parser.add_argument("--display-name", default="", help="Display name header value.")
    parser.add_argument(
        "--secret",
        default="",
        help="Signing secret. Defaults to DATUS_ENTERPRISE_HEADER_SECRET.",
    )
    parser.add_argument(
        "--timestamp",
        default="",
        help="Unix timestamp to sign. Defaults to current time.",
    )
    parser.add_argument(
        "--curl-base-url",
        default="",
        help="When set, print a full curl command instead of only header arguments.",
    )
    return parser


def _header_args(headers: dict[str, str]) -> list[str]:
    parts: list[str] = []
    for key, value in headers.items():
        parts.extend(["-H", f"{key}: {value}"])
    return parts


def main() -> None:
    args = _build_parser().parse_args()
    secret = args.secret or os.getenv("DATUS_ENTERPRISE_HEADER_SECRET", "")
    if not secret:
        raise SystemExit("Signing secret is required. Set DATUS_ENTERPRISE_HEADER_SECRET or pass --secret.")

    provider = SignedHeaderAuthProvider(secret=secret)
    roles = _csv_or_repeated(args.role)
    permissions = _csv_or_repeated(args.permission)
    timestamp = args.timestamp or str(int(time.time()))
    principal = dict(args.principal)

    headers = {
        HEADER_USER_ID: args.user,
        "X-Datus-Project-Id": args.project,
        "X-Datus-Roles": json.dumps(roles, separators=(",", ":")) if roles else "",
        "X-Datus-Permissions": json.dumps(permissions, separators=(",", ":")) if permissions else "",
        HEADER_PRINCIPAL: json.dumps(principal, separators=(",", ":"), ensure_ascii=False) if principal else "",
        "X-Datus-Email": args.email,
        "X-Datus-Display-Name": args.display_name,
    }
    signature = provider.sign_request(
        method=args.method,
        path=args.path,
        timestamp=timestamp,
        headers=headers,
    )
    headers["X-Datus-Timestamp"] = timestamp
    headers["X-Datus-Signature"] = f"sha256={signature}"

    parts = _header_args(headers)
    if args.curl_base_url:
        url = args.curl_base_url.rstrip("/") + args.path
        parts = ["curl", "-i", "-X", args.method.upper(), *parts, url]

    print(" ".join(shlex.quote(part) for part in parts))


if __name__ == "__main__":
    main()
