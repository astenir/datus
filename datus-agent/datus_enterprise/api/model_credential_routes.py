"""Current-user model credential routes."""

from __future__ import annotations

import asyncio
import copy
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.config_models import ProbeResultData
from datus.api.routes.config_routes import _probe_llm_sync
from datus.configuration.agent_config import ProviderConfig
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus_enterprise.model_credentials import (
    CUSTOM_OPENAI_PROVIDER,
    OPENAI_PROVIDER,
    credential_model_allowed,
    normalize_api_key,
    normalize_base_url,
    normalize_display_name,
    normalize_model,
    normalize_provider,
    provider_options,
    validate_custom_openai_compatible_policy,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/me", tags=["user-model-credentials"])
_require_chat_module = require_module("module.chat")
RequestContextDep = Annotated[AppContext, Depends(deps.get_request_app_context)]


class ModelProviderOption(BaseModel):
    provider: str
    label: str
    default_model: str
    models: list[str] = Field(default_factory=list)
    custom: bool = False
    requires_base_url: bool = False


class ModelCredentialSummary(BaseModel):
    id: str
    provider: str
    model: str
    base_url: str | None = None
    ref_hint: str
    display_name: str | None = None
    enabled: bool = True
    last_used_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpsertModelCredentialRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
    display_name: str | None = None
    enabled: bool = True


class ModelPreferenceSummary(BaseModel):
    default_credential_id: str | None = None
    default_model: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UpdateModelPreferenceRequest(BaseModel):
    default_credential_id: str | None = None
    default_model: str | None = None


@router.get(
    "/model-providers",
    response_model=Result[list[ModelProviderOption]],
    summary="List Model Provider Options",
    dependencies=[Depends(_require_chat_module)],
)
async def list_model_provider_options(svc: ServiceDep, _ctx: RequestContextDep) -> Result[list[ModelProviderOption]]:
    return Result(success=True, data=[ModelProviderOption(**option) for option in provider_options(svc.agent_config)])


@router.get(
    "/model-credentials",
    response_model=Result[list[ModelCredentialSummary]],
    summary="List Current User Model Credentials",
    dependencies=[Depends(_require_chat_module)],
)
async def list_my_model_credentials(ctx: RequestContextDep) -> Result[list[ModelCredentialSummary]]:
    user_id = _require_user_id(ctx)
    store = deps.get_enterprise_extensions().user_model_credential_store
    records = await store.list_credentials(user_id)
    return Result(success=True, data=[_credential_summary(record) for record in records])


@router.post(
    "/model-credentials",
    response_model=Result[ModelCredentialSummary],
    summary="Create Current User Model Credential",
    dependencies=[
        Depends(_require_chat_module),
        Depends(require_platform_active(operation="model_credentials.create", resource_type="model_credential")),
    ],
)
async def create_my_model_credential(
    body: UpsertModelCredentialRequest,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[ModelCredentialSummary]:
    user_id = _require_user_id(ctx)
    provider, model, api_key, base_url, display_name = _validated_credential_input(body, svc.agent_config)
    store = deps.get_enterprise_extensions().user_model_credential_store
    record = await store.put_credential(
        user_id=user_id,
        credential_id=uuid.uuid4().hex,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        display_name=display_name,
        enabled=body.enabled,
    )
    preference = await store.get_preference(user_id)
    if not preference.get("default_credential_id"):
        await store.put_preference(user_id=user_id, default_credential_id=str(record["id"]), default_model=model)
    return Result(success=True, data=_credential_summary(record))


@router.get(
    "/model-credentials/{credential_id}",
    response_model=Result[ModelCredentialSummary],
    summary="Get Current User Model Credential",
    dependencies=[Depends(_require_chat_module)],
)
async def get_my_model_credential(credential_id: str, ctx: RequestContextDep) -> Result[ModelCredentialSummary]:
    user_id = _require_user_id(ctx)
    store = deps.get_enterprise_extensions().user_model_credential_store
    record = await store.get_credential(user_id, credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MODEL_CREDENTIAL_NOT_FOUND")
    return Result(success=True, data=_credential_summary(record))


@router.put(
    "/model-credentials/{credential_id}",
    response_model=Result[ModelCredentialSummary],
    summary="Replace Current User Model Credential",
    dependencies=[
        Depends(_require_chat_module),
        Depends(require_platform_active(operation="model_credentials.update", resource_type="model_credential")),
    ],
)
async def update_my_model_credential(
    credential_id: str,
    body: UpsertModelCredentialRequest,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[ModelCredentialSummary]:
    user_id = _require_user_id(ctx)
    store = deps.get_enterprise_extensions().user_model_credential_store
    if await store.get_credential(user_id, credential_id) is None:
        raise HTTPException(status_code=404, detail="MODEL_CREDENTIAL_NOT_FOUND")
    provider, model, api_key, base_url, display_name = _validated_credential_input(body, svc.agent_config)
    record = await store.put_credential(
        user_id=user_id,
        credential_id=credential_id,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        display_name=display_name,
        enabled=body.enabled,
    )
    return Result(success=True, data=_credential_summary(record))


@router.delete(
    "/model-credentials/{credential_id}",
    response_model=Result[dict[str, bool]],
    summary="Delete Current User Model Credential",
    dependencies=[
        Depends(_require_chat_module),
        Depends(require_platform_active(operation="model_credentials.delete", resource_type="model_credential")),
    ],
)
async def delete_my_model_credential(credential_id: str, ctx: RequestContextDep) -> Result[dict[str, bool]]:
    user_id = _require_user_id(ctx)
    store = deps.get_enterprise_extensions().user_model_credential_store
    deleted = await store.delete_credential(user_id, credential_id)
    return Result(success=True, data={"deleted": deleted})


@router.post(
    "/model-credentials/{credential_id}/test",
    response_model=Result[ProbeResultData],
    response_model_exclude_none=True,
    summary="Test Current User Model Credential",
    dependencies=[
        Depends(_require_chat_module),
        Depends(require_platform_active(operation="model_credentials.probe", resource_type="model_credential")),
    ],
)
async def test_my_model_credential(
    credential_id: str,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[ProbeResultData]:
    user_id = _require_user_id(ctx)
    store = deps.get_enterprise_extensions().user_model_credential_store
    record = await store.get_credential(user_id, credential_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MODEL_CREDENTIAL_NOT_FOUND")
    payload = _model_probe_payload(svc.agent_config, record)
    try:
        await asyncio.to_thread(_probe_llm_sync, payload)
        return Result(success=True, data={"ok": True})
    except Exception as exc:
        logger.info("User model credential probe failed: %s", exc)
        return Result(success=True, data={"ok": False, "message": str(exc)})


@router.get(
    "/model-preferences",
    response_model=Result[ModelPreferenceSummary],
    summary="Get Current User Model Preference",
    dependencies=[Depends(_require_chat_module)],
)
async def get_my_model_preference(ctx: RequestContextDep) -> Result[ModelPreferenceSummary]:
    user_id = _require_user_id(ctx)
    store = deps.get_enterprise_extensions().user_model_credential_store
    return Result(success=True, data=_preference_summary(await store.get_preference(user_id)))


@router.put(
    "/model-preferences",
    response_model=Result[ModelPreferenceSummary],
    summary="Update Current User Model Preference",
    dependencies=[
        Depends(_require_chat_module),
        Depends(require_platform_active(operation="model_preferences.update", resource_type="model_preference")),
    ],
)
async def update_my_model_preference(
    body: UpdateModelPreferenceRequest,
    svc: ServiceDep,
    ctx: RequestContextDep,
) -> Result[ModelPreferenceSummary]:
    user_id = _require_user_id(ctx)
    store = deps.get_enterprise_extensions().user_model_credential_store
    credential_id = body.default_credential_id.strip() if body.default_credential_id else None
    default_model = normalize_model(body.default_model) if body.default_model else None
    if credential_id is not None:
        credential = await store.get_credential(user_id, credential_id)
        if credential is None:
            raise HTTPException(status_code=404, detail="MODEL_CREDENTIAL_NOT_FOUND")
        model = default_model or str(credential["model"])
        try:
            is_allowed = credential_model_allowed(
                svc.agent_config,
                provider=normalize_provider(str(credential["provider"])),
                model=model,
                base_url=normalize_base_url(credential.get("base_url")),
            )
        except DatusException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not is_allowed:
            raise HTTPException(status_code=400, detail="MODEL_NOT_ALLOWED_FOR_PROVIDER")
        default_model = model
    elif default_model is not None:
        raise HTTPException(status_code=400, detail="MODEL_PREFERENCE_REQUIRES_CREDENTIAL")
    record = await store.put_preference(
        user_id=user_id,
        default_credential_id=credential_id,
        default_model=default_model,
    )
    return Result(success=True, data=_preference_summary(record))


def _require_user_id(ctx: AppContext) -> str:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    return ctx.user_id


def _validated_credential_input(
    body: UpsertModelCredentialRequest, agent_config: Any
) -> tuple[str, str, str, str | None, str | None]:
    try:
        requested_provider = normalize_provider(body.provider)
        model = normalize_model(body.model)
        api_key = normalize_api_key(body.api_key)
        base_url = normalize_base_url(body.base_url)
        display_name = normalize_display_name(body.display_name)
        provider = OPENAI_PROVIDER if requested_provider == CUSTOM_OPENAI_PROVIDER else requested_provider
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if base_url is not None:
        try:
            validate_custom_openai_compatible_policy(agent_config, provider=provider, base_url=base_url)
        except DatusException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return provider, model, api_key, base_url, display_name

    if requested_provider == CUSTOM_OPENAI_PROVIDER:
        raise HTTPException(status_code=400, detail="MODEL_BASE_URL_REQUIRED")
    if not credential_model_allowed(agent_config, provider=provider, model=model, base_url=None):
        raise HTTPException(status_code=400, detail="MODEL_NOT_ALLOWED_FOR_PROVIDER")
    return provider, model, api_key, None, display_name


def _credential_summary(record: dict[str, Any]) -> ModelCredentialSummary:
    return ModelCredentialSummary(
        id=str(record["id"]),
        provider=str(record["provider"]),
        model=str(record["model"]),
        base_url=record.get("base_url"),
        ref_hint=str(record.get("ref_hint") or ""),
        display_name=record.get("display_name"),
        enabled=bool(record.get("enabled")),
        last_used_at=record.get("last_used_at"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


def _preference_summary(record: dict[str, Any]) -> ModelPreferenceSummary:
    return ModelPreferenceSummary(
        default_credential_id=record.get("default_credential_id"),
        default_model=record.get("default_model"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


def _model_probe_payload(agent_config: Any, record: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(agent_config)
    provider = normalize_provider(str(record["provider"]))
    model = normalize_model(str(record["model"]))
    base_url = normalize_base_url(record.get("base_url"))
    if not credential_model_allowed(agent_config, provider=provider, model=model, base_url=base_url):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="User model credential is not allowed.")
    config.providers[provider] = ProviderConfig(api_key=str(record["api_key"]), base_url=base_url)
    config.set_active_provider_model(provider, model, persist=False)
    return config.active_model().to_dict()
