#!/usr/bin/env python3
"""Local mock userinfo service for UserInfoBearerAuthProvider testing."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


class UserInfoProfile(BaseModel):
    username: str
    userId: str
    email: str
    realname: str
    userStatus: str
    department: str | None = None
    company: str | None = None
    title: str | None = None
    mobilePhone: str | None = None
    fixedPhone: str | None = None
    sortNumber: str | None = None


DEFAULT_TOKEN_PROFILES: dict[str, dict[str, Any]] = {
    "dev-alice-token": {
        "username": "alice",
        "userId": "10001",
        "email": "alice@example.com",
        "realname": "Alice",
        "userStatus": "正常",
        "department": "fund",
        "company": "local-dev",
        "title": "administrator",
        "mobilePhone": "",
        "fixedPhone": "",
        "sortNumber": "1",
    },
    "dev-bob-token": {
        "username": "bob",
        "userId": "10002",
        "email": "bob@example.com",
        "realname": "Bob",
        "userStatus": "正常",
        "department": "fund",
        "company": "local-dev",
        "title": "analyst",
        "mobilePhone": "",
        "fixedPhone": "",
        "sortNumber": "2",
    },
    "dev-charlie-token": {
        "username": "charlie",
        "userId": "10003",
        "email": "charlie@example.com",
        "realname": "Charlie",
        "userStatus": "正常",
        "department": "fund",
        "company": "local-dev",
        "title": "unseeded-user",
        "mobilePhone": "",
        "fixedPhone": "",
        "sortNumber": "3",
    },
    "disabled-token": {
        "username": "disabled_user",
        "userId": "10004",
        "email": "disabled@example.com",
        "realname": "Disabled User",
        "userStatus": "停用",
        "department": "fund",
        "company": "local-dev",
        "title": "disabled",
        "mobilePhone": "",
        "fixedPhone": "",
        "sortNumber": "4",
    },
}


def _load_token_profiles() -> dict[str, dict[str, Any]]:
    raw = os.getenv("DATUS_MOCK_USERINFO_PROFILES", "").strip()
    if not raw:
        return copy.deepcopy(DEFAULT_TOKEN_PROFILES)

    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("DATUS_MOCK_USERINFO_PROFILES must be a JSON object keyed by bearer token.")

    profiles: dict[str, dict[str, Any]] = {}
    for token, profile in value.items():
        if not isinstance(token, str) or not token.strip():
            raise ValueError("DATUS_MOCK_USERINFO_PROFILES token keys must be non-empty strings.")
        if not isinstance(profile, dict):
            raise ValueError("DATUS_MOCK_USERINFO_PROFILES values must be JSON objects.")
        profiles[token.strip()] = UserInfoProfile.model_validate(profile).model_dump(exclude_none=True)
    return profiles


TOKEN_PROFILES = _load_token_profiles()
app = FastAPI(title="Datus Local Mock UserInfo", version="1.0.0")


def _read_bearer_token(authorization: str) -> str:
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="missing bearer token")
    return token.strip()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/userinfo", response_model=UserInfoProfile)
async def userinfo(authorization: Annotated[str, Header()] = "") -> dict[str, Any]:
    token = _read_bearer_token(authorization)
    profile = TOKEN_PROFILES.get(token)
    if profile is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return copy.deepcopy(profile)


@app.get("/tokens")
async def tokens() -> list[dict[str, str]]:
    return [
        {
            "token": token,
            "username": str(profile.get("username", "")),
            "userStatus": str(profile.get("userStatus", "")),
        }
        for token, profile in sorted(TOKEN_PROFILES.items())
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local mock userinfo service for Datus enterprise testing.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8010, help="Port to bind.")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.reload:
        uvicorn.run(
            "enterprise_mock_userinfo:app",
            host=args.host,
            port=args.port,
            reload=True,
            app_dir=str(Path(__file__).resolve().parent),
        )
        return
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
