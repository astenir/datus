#!/usr/bin/env python3
"""Local enterprise API helper for signed-header testing without a gateway."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from datus.api.constants import HEADER_PRINCIPAL, HEADER_USER_ID
from datus_enterprise.auth_provider import SignedHeaderAuthProvider

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PERMISSIONS = [
    "module.chat",
    "module.datasource_catalog",
    "module.sql_executor",
    "module.config.view",
    "module.system.status",
]


@dataclass(frozen=True)
class SignedRequest:
    method: str
    path: str
    url: str
    headers: dict[str, str]
    body: bytes | None


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
        raise argparse.ArgumentTypeError("value must be a JSON object")
    return value


def _json_value(raw: str) -> Any:
    if not raw.strip():
        return None
    return json.loads(raw)


def _secret_from_args(args: argparse.Namespace) -> str:
    secret = getattr(args, "secret", "") or os.getenv("DATUS_ENTERPRISE_HEADER_SECRET", "")
    if not secret:
        raise SystemExit("Signing secret is required. Set DATUS_ENTERPRISE_HEADER_SECRET or pass --secret.")
    return secret


def _identity_headers(
    *,
    user: str,
    project: str,
    roles: list[str],
    permissions: list[str],
    principal: dict[str, Any],
    email: str,
    display_name: str,
) -> dict[str, str]:
    headers = {
        HEADER_USER_ID: user,
        "X-Datus-Project-Id": project,
        "X-Datus-Roles": json.dumps(roles, separators=(",", ":")) if roles else "",
        "X-Datus-Permissions": json.dumps(permissions, separators=(",", ":")) if permissions else "",
        HEADER_PRINCIPAL: json.dumps(principal, separators=(",", ":"), ensure_ascii=False) if principal else "",
        "X-Datus-Email": email,
        "X-Datus-Display-Name": display_name,
    }
    return headers


def _split_path(path_or_url: str) -> tuple[str, str]:
    parsed = parse.urlsplit(path_or_url)
    path = parsed.path or "/"
    signed_path = path
    request_path = path
    if parsed.query:
        request_path = f"{path}?{parsed.query}"
    return signed_path, request_path


def _request_url(base_url: str, path_or_url: str) -> str:
    parsed = parse.urlsplit(path_or_url)
    if parsed.scheme and parsed.netloc:
        return path_or_url
    return base_url.rstrip("/") + _split_path(path_or_url)[1]


def _sign_headers(
    *,
    secret: str,
    method: str,
    signed_path: str,
    timestamp: str,
    headers: dict[str, str],
) -> dict[str, str]:
    provider = SignedHeaderAuthProvider(secret=secret)
    signature = provider.sign_request(
        method=method,
        path=signed_path,
        timestamp=timestamp,
        headers=headers,
    )
    signed = dict(headers)
    signed["X-Datus-Timestamp"] = timestamp
    signed["X-Datus-Signature"] = f"sha256={signature}"
    return signed


def build_signed_request(
    *,
    base_url: str,
    method: str,
    path: str,
    secret: str,
    user: str,
    project: str,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    principal: dict[str, Any] | None = None,
    email: str = "",
    display_name: str = "",
    body: Any = None,
    timestamp: str | None = None,
) -> SignedRequest:
    normalized_method = method.upper()
    signed_path, _ = _split_path(path)
    headers = _identity_headers(
        user=user,
        project=project,
        roles=roles or [],
        permissions=permissions or [],
        principal=principal or {},
        email=email,
        display_name=display_name,
    )
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    signed_headers = _sign_headers(
        secret=secret,
        method=normalized_method,
        signed_path=signed_path,
        timestamp=timestamp or str(int(time.time())),
        headers=headers,
    )
    return SignedRequest(
        method=normalized_method,
        path=path,
        url=_request_url(base_url, path),
        headers=signed_headers,
        body=payload,
    )


def _curl_command(signed_request: SignedRequest) -> str:
    parts = ["curl", "-i", "-X", signed_request.method]
    for key, value in signed_request.headers.items():
        parts.extend(["-H", f"{key}: {value}"])
    if signed_request.body is not None:
        parts.extend(["--data", signed_request.body.decode("utf-8")])
    parts.append(signed_request.url)
    return " ".join(shlex.quote(part) for part in parts)


def _send(signed_request: SignedRequest, *, timeout: float) -> tuple[int, dict[str, str], str]:
    req = request.Request(
        signed_request.url,
        data=signed_request.body,
        headers=signed_request.headers,
        method=signed_request.method,
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, dict(response.headers.items()), body
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), body


def _print_response(status: int, body: str) -> None:
    print(f"HTTP {status}")
    try:
        parsed = json.loads(body)
    except ValueError:
        print(body)
        return
    print(json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True))


def _add_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Datus API base URL.")
    parser.add_argument("--secret", default="", help="Signing secret. Defaults to DATUS_ENTERPRISE_HEADER_SECRET.")
    parser.add_argument("--user", default="alice", help="Signed user id.")
    parser.add_argument("--project", default="enterprise", help="Signed project id.")
    parser.add_argument("--role", action="append", default=None, help="Role value. Repeat or comma-separate.")
    parser.add_argument(
        "--permission", action="append", default=None, help="Permission value. Repeat or comma-separate."
    )
    parser.add_argument("--principal", type=_json_object, default={}, help="Principal JSON object.")
    parser.add_argument("--email", default="", help="Signed email value.")
    parser.add_argument("--display-name", default="", help="Signed display name value.")
    parser.add_argument("--timestamp", default="", help="Unix timestamp. Defaults to current time.")


def _identity_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "base_url": args.base_url,
        "secret": _secret_from_args(args),
        "user": args.user,
        "project": args.project,
        "roles": _csv_or_repeated(args.role),
        "permissions": _csv_or_repeated(args.permission) or list(DEFAULT_PERMISSIONS),
        "principal": dict(args.principal),
        "email": args.email,
        "display_name": args.display_name,
        "timestamp": args.timestamp or None,
    }


def _cmd_secret(_: argparse.Namespace) -> int:
    print(secrets.token_urlsafe(32))
    return 0


def _cmd_curl(args: argparse.Namespace) -> int:
    body = _json_value(args.json) if args.json else None
    signed = build_signed_request(
        method=args.method,
        path=args.path,
        body=body,
        **_identity_from_args(args),
    )
    print(_curl_command(signed))
    return 0


def _cmd_request(args: argparse.Namespace) -> int:
    body = _json_value(args.json) if args.json else None
    signed = build_signed_request(
        method=args.method,
        path=args.path,
        body=body,
        **_identity_from_args(args),
    )
    if args.print_curl:
        print(_curl_command(signed))
    status, _, response_body = _send(signed, timeout=args.timeout)
    _print_response(status, response_body)
    return 0 if status < 400 else 1


def _smoke_steps(args: argparse.Namespace) -> list[tuple[str, str, Any]]:
    datasource = parse.quote(args.datasource, safe="")
    steps: list[tuple[str, str, Any]] = [
        ("GET", "/api/v1/me", None),
        ("GET", "/api/v1/me/features", None),
        ("GET", "/api/v1/me/datasource-grants", None),
        ("GET", f"/api/v1/catalog/list?datasource_id={datasource}", None),
    ]
    if args.sql:
        steps.append(
            (
                "POST",
                "/api/v1/sql/execute",
                {
                    "database_name": args.database,
                    "sql_query": args.sql,
                    "result_format": args.result_format,
                },
            )
        )
    return steps


def _cmd_smoke(args: argparse.Namespace) -> int:
    identity = _identity_from_args(args)
    failed = False
    for method, path, body in _smoke_steps(args):
        signed = build_signed_request(method=method, path=path, body=body, **identity)
        print(f"\n== {method} {path} ==")
        if args.print_curl:
            print(_curl_command(signed))
        status, _, response_body = _send(signed, timeout=args.timeout)
        _print_response(status, response_body)
        failed = failed or status >= 400
    return 1 if failed else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and send SignedHeaderAuthProvider requests for local enterprise API testing "
            "without an enterprise gateway."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    secret_parser = subparsers.add_parser("secret", help="Generate a local signing secret.")
    secret_parser.set_defaults(func=_cmd_secret)

    curl_parser = subparsers.add_parser("curl", help="Print a signed curl command.")
    _add_identity_args(curl_parser)
    curl_parser.add_argument("--method", default="GET", help="HTTP method.")
    curl_parser.add_argument("--path", required=True, help="Request path, with optional query string.")
    curl_parser.add_argument("--json", default="", help="JSON request body.")
    curl_parser.set_defaults(func=_cmd_curl)

    request_parser = subparsers.add_parser("request", help="Send one signed request.")
    _add_identity_args(request_parser)
    request_parser.add_argument("--method", default="GET", help="HTTP method.")
    request_parser.add_argument("--path", required=True, help="Request path, with optional query string.")
    request_parser.add_argument("--json", default="", help="JSON request body.")
    request_parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    request_parser.add_argument("--print-curl", action="store_true", help="Print the equivalent curl command first.")
    request_parser.set_defaults(func=_cmd_request)

    smoke_parser = subparsers.add_parser("smoke", help="Run a small local enterprise API smoke test.")
    _add_identity_args(smoke_parser)
    smoke_parser.add_argument("--datasource", default="ccks_fund", help="Datasource key for catalog smoke.")
    smoke_parser.add_argument("--database", default=None, help="Database name for optional SQL smoke.")
    smoke_parser.add_argument("--sql", default="", help="Optional SQL to execute after identity/catalog checks.")
    smoke_parser.add_argument("--result-format", default="json", help="SQL result format.")
    smoke_parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    smoke_parser.add_argument("--print-curl", action="store_true", help="Print equivalent curl commands.")
    smoke_parser.set_defaults(func=_cmd_smoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
