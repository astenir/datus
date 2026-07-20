#!/usr/bin/env python3
"""Fail-fast validation for the local Docker Compose model configuration."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

_ENV_VALUE_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*))?}$")
_PLACEHOLDERS = {"change-me", "changeme", "replace-me", "replace-with-a-real-secret"}
_SENSITIVE_KEYS = {"api_key", "password", "secret", "token"}


def _resolved_value(value: str, environ: Mapping[str, str] | None = None) -> str:
    match = _ENV_VALUE_RE.fullmatch(value.strip())
    if match is None:
        return value.strip()
    env_name, default = match.groups()
    env = os.environ if environ is None else environ
    return env.get(env_name, default or "").strip()


def _placeholder_paths(
    value: Any,
    *,
    path: str = "",
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    if isinstance(value, dict):
        invalid: list[str] = []
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in _SENSITIVE_KEYS and isinstance(child, str):
                resolved = _resolved_value(child, environ)
                if not resolved or resolved.lower() in _PLACEHOLDERS or resolved.startswith("<MISSING:"):
                    invalid.append(child_path)
            invalid.extend(_placeholder_paths(child, path=child_path, environ=environ))
        return invalid
    if isinstance(value, list):
        invalid = []
        for index, child in enumerate(value):
            invalid.extend(_placeholder_paths(child, path=f"{path}[{index}]", environ=environ))
        return invalid
    return []


def validate_models_file(path: Path, environ: Mapping[str, str] | None = None) -> list[str]:
    env = os.environ if environ is None else environ
    if not path.is_file():
        return [f"model configuration file not found: {path}"]

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [f"failed to parse {path}: {exc}"]
    if not isinstance(raw, dict):
        return [f"{path} must contain a YAML mapping"]

    errors = [f"placeholder or empty credential: {item}" for item in _placeholder_paths(raw, environ=env)]

    providers = raw.get("providers") or {}
    models = raw.get("models") or {}
    if not isinstance(providers, dict):
        errors.append("providers must be a mapping")
        providers = {}
    if not isinstance(models, dict):
        errors.append("models must be a mapping")
        models = {}

    embedding_key = env.get("DATUS_EMBEDDING_MODEL_KEY", "compose_embedding").strip()
    embedding = models.get(embedding_key)
    if not isinstance(embedding, dict):
        errors.append(f"models.{embedding_key} must define the selected embedding model")
    else:
        expected_name = env.get("DATUS_EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B").strip()
        configured_name = _resolved_value(str(embedding.get("model") or ""), env)
        if configured_name != expected_name:
            errors.append(f"models.{embedding_key}.model must match DATUS_EMBEDDING_MODEL_NAME ({expected_name})")

    dim_text = env.get("DATUS_EMBEDDING_DIM_SIZE", "1024").strip()
    try:
        if int(dim_text) <= 0:
            raise ValueError
    except ValueError:
        errors.append("DATUS_EMBEDDING_DIM_SIZE must be a positive integer")

    target = env.get("DATUS_TARGET", "").strip()
    target_provider = env.get("DATUS_TARGET_PROVIDER", "").strip()
    target_model = env.get("DATUS_TARGET_MODEL", "").strip()
    if target:
        if target not in models:
            errors.append(f"DATUS_TARGET references undefined models.{target}")
    elif target_provider or target_model:
        if not target_provider or not target_model:
            errors.append("DATUS_TARGET_PROVIDER and DATUS_TARGET_MODEL must be configured together")
        elif target_provider not in providers:
            errors.append(f"DATUS_TARGET_PROVIDER references undefined providers.{target_provider}")
    else:
        errors.append("configure DATUS_TARGET or DATUS_TARGET_PROVIDER plus DATUS_TARGET_MODEL")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-file", type=Path, required=True)
    args = parser.parse_args()

    errors = validate_models_file(args.models_file)
    if not errors:
        return 0
    print("Docker Compose model configuration is invalid:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
