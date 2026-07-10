"""User-owned model credential helpers."""

from __future__ import annotations

import base64
import hashlib
import re
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import urlparse

from datus.configuration.agent_config import ProviderConfig
from datus.utils.exceptions import DatusException, ErrorCode

PROVIDER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MODEL_RE = re.compile(r"^[A-Za-z0-9_.:/@-]+$")
CUSTOM_OPENAI_PROVIDER = "custom_openai_compatible"
OPENAI_PROVIDER = "openai"

MAX_PROVIDER_LENGTH = 80
MAX_MODEL_LENGTH = 160
MAX_DISPLAY_NAME_LENGTH = 120
MAX_API_KEY_LENGTH = 4096
MAX_BASE_URL_LENGTH = 512


def api_key_hint(api_key: str) -> str:
    """Return a redaction-safe suffix hint for a model API key."""

    if len(api_key) <= 4:
        return "***"
    return f"***{api_key[-4:]}"


class CredentialSecretCodec:
    """Encrypt/decrypt user model API keys with a server-side secret."""

    def __init__(self, encryption_secret: str | None = None) -> None:
        try:
            from cryptography.fernet import Fernet, InvalidToken
        except ImportError as exc:
            raise DatusException(
                ErrorCode.COMMON_CONFIG_ERROR,
                message="cryptography is required for persistent user model credential stores.",
            ) from exc

        raw_secret = (encryption_secret or "").strip()
        if len(raw_secret) < 32:
            raise DatusException(
                ErrorCode.COMMON_CONFIG_ERROR,
                message="User model credential encryption secret must be at least 32 characters.",
            )
        key = base64.urlsafe_b64encode(hashlib.sha256(raw_secret.encode("utf-8")).digest())
        self._fernet = Fernet(key)
        self._invalid_token = InvalidToken

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, blob: str) -> str:
        try:
            return self._fernet.decrypt(blob.encode("ascii")).decode("utf-8")
        except (self._invalid_token, UnicodeDecodeError) as exc:
            raise DatusException(
                ErrorCode.COMMON_CONFIG_ERROR,
                message="Model credential secret decrypt failed.",
            ) from exc


def normalize_provider(value: str) -> str:
    provider = value.strip().lower()
    if not provider or len(provider) > MAX_PROVIDER_LENGTH or not PROVIDER_RE.fullmatch(provider):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid model provider.")
    return provider


def normalize_model(value: str) -> str:
    model = value.strip()
    if not model or len(model) > MAX_MODEL_LENGTH or not MODEL_RE.fullmatch(model):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid model name.")
    return model


def normalize_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > MAX_DISPLAY_NAME_LENGTH:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Display name is too long.")
    return text


def normalize_api_key(value: str) -> str:
    api_key = value.strip()
    if not api_key:
        raise DatusException(ErrorCode.COMMON_FIELD_REQUIRED, message="API key is required.")
    if len(api_key) > MAX_API_KEY_LENGTH:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="API key is too long.")
    return api_key


def normalize_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    base_url = value.strip().rstrip("/")
    if not base_url:
        return None
    if len(base_url) > MAX_BASE_URL_LENGTH:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Model base URL is too long.")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Model base URL must be http or https.")
    if parsed.username or parsed.password:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Model base URL must not include credentials.")
    return base_url


def provider_options(agent_config: Any) -> list[dict[str, Any]]:
    """Return provider/model options from the server catalog, independent of shared keys."""

    catalog = agent_config.provider_catalog if isinstance(agent_config.provider_catalog, dict) else {}
    providers_meta = catalog.get("providers", {}) if isinstance(catalog, dict) else {}
    if not isinstance(providers_meta, dict):
        return []

    options: list[dict[str, Any]] = []
    for provider, meta in providers_meta.items():
        if not isinstance(provider, str) or not isinstance(meta, dict):
            continue
        auth_type = str(meta.get("auth_type") or "api_key")
        if auth_type != "api_key":
            continue
        models = [str(item) for item in meta.get("models", []) if isinstance(item, str) and item.strip()]
        if not models:
            continue
        options.append(
            {
                "provider": provider,
                "label": str(meta.get("label") or meta.get("name") or provider),
                "default_model": str(meta.get("default_model") or models[0]),
                "models": sorted(set(models)),
                "custom": False,
                "requires_base_url": False,
            }
        )
    custom = custom_openai_compatible_options(agent_config)
    if custom["enabled"]:
        options.append(
            {
                "provider": CUSTOM_OPENAI_PROVIDER,
                "label": "Custom OpenAI Compatible",
                "default_model": "",
                "models": [],
                "custom": True,
                "requires_base_url": True,
            }
        )
    return sorted(options, key=lambda option: (bool(option.get("custom")), str(option["provider"])))


def provider_model_allowed(agent_config: Any, provider: str, model: str) -> bool:
    for option in provider_options(agent_config):
        if option["provider"] == provider and model in option["models"]:
            return True
    return False


def custom_openai_compatible_options(agent_config: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    enterprise = getattr(agent_config, "enterprise_config", {}) or {}
    if isinstance(enterprise, dict):
        parent = enterprise.get("user_model_credentials") or enterprise.get("personal_models") or {}
        if isinstance(parent, dict):
            custom = parent.get("custom_openai_compatible")
            raw = custom if isinstance(custom, dict) else parent
    allowed_base_urls = _normalized_list(raw.get("allowed_base_urls"))
    return {
        "enabled": bool(raw.get("enabled")) and bool(allowed_base_urls),
        "allowed_base_urls": allowed_base_urls,
    }


def validate_custom_openai_compatible_policy(agent_config: Any, *, provider: str, base_url: str) -> None:
    if provider not in {OPENAI_PROVIDER, CUSTOM_OPENAI_PROVIDER}:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message="Custom model endpoints must use an OpenAI-compatible provider.",
        )
    options = custom_openai_compatible_options(agent_config)
    if not options["enabled"]:
        raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="Custom OpenAI-compatible models are not enabled.")
    normalized_url = base_url.lower()
    if not any(fnmatchcase(normalized_url, pattern) for pattern in options["allowed_base_urls"]):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Model base URL is not allowed.")


def credential_model_allowed(agent_config: Any, *, provider: str, model: str, base_url: str | None) -> bool:
    if base_url:
        validate_custom_openai_compatible_policy(agent_config, provider=provider, base_url=base_url)
        return True
    return provider_model_allowed(agent_config, provider, model)


async def apply_user_model_credential(
    *,
    store: Any,
    user_id: str | None,
    agent_config: Any,
    requested_model: str | None,
    requested_credential_id: str | None = None,
) -> dict[str, Any] | None:
    """Overlay a user's enabled credential onto a request-scoped AgentConfig clone.

    The function never mutates the shared service config. Chat routes call it
    after datasource projection, and ``ChatTaskManager`` deep-copies the result
    once more before execution.
    """

    if not user_id or store is None:
        return None

    credential = await _resolve_execution_credential(
        store=store,
        user_id=user_id,
        requested_model=requested_model,
        requested_credential_id=requested_credential_id,
    )
    if credential is None:
        return None

    provider = normalize_provider(str(credential["provider"]))
    model = normalize_model(str(credential["model"]))
    base_url = normalize_base_url(credential.get("base_url"))
    if not credential_model_allowed(agent_config, provider=provider, model=model, base_url=base_url):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="User model credential is not allowed.")
    agent_config.providers[provider] = ProviderConfig(api_key=str(credential["api_key"]), base_url=base_url)
    agent_config.set_active_provider_model(provider, model, persist=False)
    await store.touch_credential_used(user_id, str(credential["id"]))
    return {
        "credential_id": str(credential["id"]),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "ref_hint": str(credential.get("ref_hint") or ""),
    }


async def _resolve_execution_credential(
    *,
    store: Any,
    user_id: str,
    requested_model: str | None,
    requested_credential_id: str | None,
) -> dict[str, Any] | None:
    credentials = [item for item in await store.list_credentials(user_id) if item.get("enabled") is True]
    if not credentials:
        if requested_credential_id:
            raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="User model credential is unavailable.")
        return None

    if requested_credential_id:
        for item in credentials:
            if item.get("id") == requested_credential_id:
                return dict(item)
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="User model credential is unavailable.")

    requested_provider: str | None = None
    requested_model_id: str | None = None
    if requested_model and "/" in requested_model:
        requested_provider, _, requested_model_id = requested_model.partition("/")
        if requested_provider == "custom":
            return None
        requested_provider = normalize_provider(requested_provider)
        requested_model_id = normalize_model(requested_model_id)
        for item in credentials:
            if item.get("provider") == requested_provider:
                selected = dict(item)
                selected["model"] = requested_model_id
                return selected
        return None

    preference = await store.get_preference(user_id)
    default_id = preference.get("default_credential_id")
    if default_id:
        for item in credentials:
            if item.get("id") == default_id:
                selected = dict(item)
                if preference.get("default_model"):
                    selected["model"] = str(preference["default_model"])
                return selected

    return credentials[0]


def _normalized_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        return []
    return sorted({str(item).strip().rstrip("/").lower() for item in raw_values if str(item).strip()})
