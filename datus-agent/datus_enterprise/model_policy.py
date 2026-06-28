"""Enterprise model/provider allowlist helpers."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Iterable, Sequence

from datus.api.auth.context import AppContext
from datus.api.models.config_models import ModelInfo


def filter_allowed_models(ctx: AppContext | None, models: Sequence[ModelInfo]) -> list[ModelInfo]:
    """Return models allowed by the server-built model policy in ``ctx``."""

    if not has_model_policy(ctx):
        return list(models)
    return [model for model in models if is_model_allowed(ctx, model.provider, model.id)]


def is_model_ref_allowed(ctx: AppContext | None, model_ref: str | None) -> bool:
    """Return whether ``provider/model_id`` is allowed for ``ctx``."""

    if not model_ref or not has_model_policy(ctx):
        return True
    provider, model_id = split_model_ref(model_ref)
    if not provider or not model_id:
        return False
    return is_model_allowed(ctx, provider, model_id)


def is_model_allowed(ctx: AppContext | None, provider: str, model_id: str) -> bool:
    """Evaluate one provider/model pair against optional enterprise policy.

    The policy is intentionally read-only and optional. Production auth/RBAC
    providers can populate ``principal.model_policy`` or the compatible top-level
    principal keys from trusted server-side metadata; request bodies are ignored.
    """

    policy = _model_policy(ctx)
    if not policy:
        return True

    provider = str(provider)
    model_id = str(model_id)
    model_ref = f"{provider}/{model_id}"

    if _matches_any(provider, _policy_values(policy, "denied_providers")):
        return False
    if _matches_any(model_ref, _policy_values(policy, "denied_models", "denied_model_patterns")):
        return False
    if _matches_any(model_id, _policy_values(policy, "denied_models", "denied_model_patterns")):
        return False

    allowed_providers = _policy_values(policy, "allowed_providers")
    if allowed_providers and not _matches_any(provider, allowed_providers):
        return False

    allowed_models = _policy_values(policy, "allowed_models", "allowed_model_patterns")
    if allowed_models:
        return _matches_any(model_ref, allowed_models) or _matches_any(model_id, allowed_models)

    return True


def has_model_policy(ctx: AppContext | None) -> bool:
    """Return True when ctx carries any model policy field."""

    return bool(_model_policy(ctx))


def split_model_ref(model_ref: str) -> tuple[str | None, str | None]:
    """Split ``provider/model_id`` while allowing slashes inside model ids."""

    if "/" not in model_ref:
        return None, None
    provider, model_id = model_ref.split("/", 1)
    provider = provider.strip()
    model_id = model_id.strip()
    if not provider or not model_id:
        return None, None
    return provider, model_id


def _model_policy(ctx: AppContext | None) -> dict[str, Any]:
    principal = getattr(ctx, "principal", None) or {}
    if not isinstance(principal, dict):
        return {}

    raw_policy = principal.get("model_policy")
    policy = dict(raw_policy) if isinstance(raw_policy, dict) else {}

    for key in (
        "allowed_models",
        "allowed_model_patterns",
        "allowed_providers",
        "denied_models",
        "denied_model_patterns",
        "denied_providers",
    ):
        if key in principal and key not in policy:
            policy[key] = principal[key]

    return {key: value for key, value in policy.items() if _string_values(value)}


def _policy_values(policy: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(_string_values(policy.get(key)))
    return values


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        result = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
        return result
    return []


def _matches_any(value: str, patterns: Sequence[str]) -> bool:
    return any(value == pattern or fnmatchcase(value, pattern) for pattern in patterns)
