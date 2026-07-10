"""
API routes for configuration status and metadata.

This module provides endpoints for initialization status checks
and supported provider/database type listings.
"""

import asyncio
import copy
from dataclasses import asdict, is_dataclass
from typing import Annotated, Any, Dict, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.config_models import AgentConfigSummaryData, MutationResultData, ProbeResultData
from datus.configuration.agent_config import _SAFE_NAME_RE, DbConfig, load_model_config, resolve_env
from datus.configuration.agent_config_loader import configuration_manager
from datus.configuration.project_config import (
    ProjectOverride,
    ProjectTarget,
    load_project_override,
    project_config_path,
    save_project_override,
)
from datus.models.base import LLMBaseModel
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus.utils.text_utils import redact_uri

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["configuration"])

_require_config_view = require_module("module.config.view")
_require_config_edit = require_module("module.config.edit")
ConfigViewCtx = Annotated[AppContext, Depends(_require_config_view)]
ConfigEditCtx = Annotated[AppContext, Depends(_require_config_edit)]

REDACTED_CONFIG_VALUE = "********"
_SENSITIVE_FIELD_NAMES = {
    "api_key",
    "apikey",
    "password",
    "secret",
    "client_secret",
    "access_token",
    "refresh_token",
    "private_key",
    "private_key_file",
    "bearer_token",
    "auth_token",
    "token",
    "authorization",
}
_URI_FIELD_NAMES = {"uri", "dsn", "url", "jdbc_url", "connection_string"}


class UpdateDatasourcesRequest(BaseModel):
    """Full desired state for `services.datasources`.

    Any existing datasource key absent from `datasources` will be deleted.
    """

    datasources: Dict[str, Dict[str, Any]]


class TargetModelRequest(BaseModel):
    """Structured project-level target for provider or custom models."""

    provider: Optional[str] = None
    model: Optional[str] = None
    custom: Optional[str] = None

    @model_validator(mode="after")
    def validate_target_shape(self) -> "TargetModelRequest":
        provider = (self.provider or "").strip()
        model = (self.model or "").strip()
        custom = (self.custom or "").strip()
        if custom and not provider and not model:
            self.custom = custom
            return self
        if provider and model and not custom:
            self.provider = provider
            self.model = model
            return self
        raise ValueError("target must provide either custom or both provider and model")


class UpdateModelsRequest(BaseModel):
    """Optional full-replace for providers/models and/or update to target.

    At least one field must be provided.
    """

    providers: Optional[Dict[str, Dict[str, Any]]] = None
    models: Optional[Dict[str, Dict[str, Any]]] = None
    target: Optional[str | TargetModelRequest] = None


class ProbeModelRequest(BaseModel):
    """Single LLM model config dict — flat shape matching IModelInfo."""

    model_config = {"extra": "allow"}

    type: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ProbeSavedModelRequest(TargetModelRequest):
    """Reference a saved provider model or custom model configuration."""


class ProbeDatasourceRequest(BaseModel):
    """Single datasource config dict — flat shape matching IDatasourceConfig."""

    model_config = {"extra": "allow"}

    type: str


class ProbeSavedDatasourceRequest(BaseModel):
    """Reference a saved datasource configuration by name."""

    name: str


def _probe_llm_sync(payload: Dict[str, Any]) -> None:
    """Build a one-shot LLM client from a raw dict and send a tiny probe."""
    model_cfg = load_model_config(payload)
    model_class_name = LLMBaseModel.MODEL_TYPE_MAP.get(model_cfg.type)
    if model_class_name is None:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Unsupported model type: {model_cfg.type}",
        )
    module = __import__(f"datus.models.{model_cfg.type}_model", fromlist=[model_class_name])
    model_class = getattr(module, model_class_name)
    client = model_class(model_config=model_cfg)
    client.generate("Hello")


def _embedding_config_for_custom(name: str) -> Optional[Dict[str, Any]]:
    """Return the first OpenAI embedding storage config referencing a custom model."""
    storage = configuration_manager().data.get("storage") or {}
    if not isinstance(storage, dict):
        return None
    for config in storage.values():
        if not isinstance(config, dict) or config.get("registry_name") != "openai":
            continue
        target_model = config.get("target_model")
        if isinstance(target_model, str) and resolve_env(target_model).strip() == name:
            return dict(config)
    return None


def _probe_embedding_sync(model_config: Any, embedding_config: Dict[str, Any]) -> None:
    """Build the configured embedding client and generate one probe vector."""
    from datus.storage.embedding_models import EmbeddingModel

    embedding_model = EmbeddingModel(
        model_name=str(embedding_config["model_name"]),
        dim_size=int(embedding_config["dim_size"]),
        registry_name=str(embedding_config.get("registry_name") or "openai"),
        openai_config=model_config,
        batch_size=int(embedding_config.get("batch_size", 32)),
        single_input_only=bool(embedding_config.get("single_input_only", False)),
    )
    embedding_model.init_model()


def _probe_datasource_sync(payload: Dict[str, Any]) -> None:
    """Build a one-shot connector from a raw dict and run a SELECT 1 probe."""
    from datus.tools.db_tools.db_manager import DBManager

    kwargs = dict(payload)
    kwargs.setdefault("name", "_probe_")
    db_config = DbConfig.filter_kwargs(DbConfig, kwargs)

    manager = DBManager({"_probe_": db_config})
    try:
        conn = manager.get_conn("_probe_")
        conn.test_connection()
    finally:
        manager.close()


def _validate_keys(entries: Dict[str, Any], kind: str) -> None:
    """Ensure every key matches the naming policy used by AgentConfig."""
    for name in entries.keys():
        if not _SAFE_NAME_RE.match(name):
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=(
                    f"Invalid {kind} name '{name}'. Only alphanumeric characters, underscores, and hyphens are allowed."
                ),
            )


def _raise_bad_request(exc: DatusException) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _field_name_parts(value: str) -> list[str]:
    import re

    acronym_spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    camel_spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", acronym_spaced)
    return [part for part in re.split(r"[^A-Za-z0-9]+", camel_spaced.lower()) if part]


def _normalized_field_name(value: str) -> str:
    return "_".join(_field_name_parts(value))


def _is_sensitive_config_field(key: str) -> bool:
    normalized = _normalized_field_name(key)
    if normalized in _SENSITIVE_FIELD_NAMES:
        return True
    return normalized.endswith(("_api_key", "_password", "_secret", "_token"))


def _is_uri_config_field(key: str) -> bool:
    normalized = _normalized_field_name(key)
    return normalized in _URI_FIELD_NAMES or normalized.endswith(("_uri", "_dsn", "_url", "_connection_string"))


def _plain_config_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_config_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_plain_config_value(item) for item in value]
    if isinstance(value, tuple):
        return [_plain_config_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return _plain_config_value(value.model_dump(exclude_none=True))
    if hasattr(value, "to_dict"):
        return _plain_config_value(value.to_dict())
    if is_dataclass(value) and not isinstance(value, type):
        return _plain_config_value(asdict(value))
    return value


def _redact_config_value(value: Any, *, key: str = "") -> Any:
    plain = _plain_config_value(value)
    if isinstance(plain, Mapping):
        return {
            str(child_key): _redact_config_value(child_value, key=str(child_key))
            for child_key, child_value in plain.items()
        }
    if isinstance(plain, list):
        return [_redact_config_value(item) for item in plain]
    if _is_sensitive_config_field(key) and plain not in (None, ""):
        return REDACTED_CONFIG_VALUE
    if _is_uri_config_field(key) and isinstance(plain, str):
        return redact_uri(plain)
    return plain


def _merge_redacted_placeholders(new_value: Any, previous_value: Any, *, key: str = "") -> Any:
    if _is_sensitive_config_field(key) and new_value == REDACTED_CONFIG_VALUE:
        return copy.deepcopy(previous_value)
    if _is_uri_config_field(key) and isinstance(new_value, str) and isinstance(previous_value, str):
        if new_value == redact_uri(previous_value):
            return previous_value
    if isinstance(new_value, Mapping):
        previous_mapping = previous_value if isinstance(previous_value, Mapping) else {}
        return {
            str(child_key): _merge_redacted_placeholders(
                child_value,
                previous_mapping.get(child_key),
                key=str(child_key),
            )
            for child_key, child_value in new_value.items()
        }
    if isinstance(new_value, list):
        previous_list = previous_value if isinstance(previous_value, list) else []
        return [
            _merge_redacted_placeholders(
                child_value,
                previous_list[index] if index < len(previous_list) else None,
            )
            for index, child_value in enumerate(new_value)
        ]
    return new_value


async def _evict_current_project(project_id: str) -> None:
    """Drop the cached DatusService so the next request reloads from YAML."""
    try:
        await deps.evict_datus_service(project_id)
    except Exception:
        logger.exception(f"Failed to evict service cache for project {project_id}")


@router.get(
    "/config/agent",
    response_model=Result[AgentConfigSummaryData],
    summary="Get Agent Configuration",
    description="Get the current project's agent configuration (models, datasource, agentic_nodes)",
)
async def get_agent_config_endpoint(
    _ctx: ConfigViewCtx,
    svc: ServiceDep,
) -> Result[AgentConfigSummaryData]:
    """Return the project's loaded AgentConfig summary."""
    config = svc.agent_config
    flat_datasources: dict = {}

    for db_name, db_config in config.datasource_configs.items():
        if db_config is None:
            continue
        flat_datasources[db_name] = _redact_config_value(db_config)

    if config._target_provider and config._target_model:
        target: Any = {"provider": config._target_provider, "model": config._target_model}
    elif config.target:
        target = {"custom": config.target}
    else:
        target = None

    catalog = config.provider_catalog if isinstance(config.provider_catalog, dict) else {}
    providers_meta = catalog.get("providers", {}) if isinstance(catalog, dict) else {}
    provider_options = []
    if isinstance(providers_meta, dict):
        for name, meta in providers_meta.items():
            if not isinstance(name, str) or not isinstance(meta, dict):
                continue
            provider_options.append(
                {
                    "value": name,
                    "label": str(meta.get("label") or meta.get("name") or name),
                    "auth_type": str(meta.get("auth_type") or "api_key"),
                    "base_url": str(meta.get("base_url") or ""),
                }
            )

    return Result(
        success=True,
        data={
            "target": target,
            "providers": _redact_config_value(config.providers or {}),
            "provider_options": provider_options,
            "models": _redact_config_value(config.models or {}),
            "current_datasource": config.current_datasource,
            "datasources": flat_datasources,
            "home": config.home,
        },
    )


@router.put(
    "/config/datasources",
    response_model=Result[MutationResultData],
    summary="Update Datasources",
    description="Replace the datasources (services.datasources) block in agent.yml.",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="config.datasources.update", resource_type="config")),
    ],
)
async def update_datasources_endpoint(
    body: UpdateDatasourcesRequest,
    ctx: ConfigEditCtx,
) -> Result[MutationResultData]:
    """Full-replace `services.datasources` with the provided datasources."""
    try:
        _validate_keys(body.datasources, kind="datasource")
    except DatusException as exc:
        _raise_bad_request(exc)

    cm = configuration_manager()
    previous_data = copy.deepcopy(cm.data)
    services = cm.data.setdefault("services", {})
    previous_datasources = previous_data.get("services", {}).get("datasources", {})
    services["datasources"] = _merge_redacted_placeholders(dict(body.datasources), previous_datasources)
    try:
        cm.save()
    except Exception:
        cm.data = previous_data
        raise

    await _evict_current_project(ctx.project_id or "default")

    return Result(success=True, data={"updated": True})


@router.put(
    "/config/models",
    response_model=Result[MutationResultData],
    summary="Update Models and Target",
    description="Replace provider/model configuration and/or update the project default model.",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="config.models.update", resource_type="config")),
    ],
)
async def update_models_endpoint(
    body: UpdateModelsRequest,
    ctx: ConfigEditCtx,
) -> Result[MutationResultData]:
    """Optionally replace providers/models and update the project target."""
    try:
        if body.providers is None and body.models is None and body.target is None:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message="At least one of 'providers', 'models', or 'target' must be provided.",
            )

        if body.providers is not None:
            _validate_keys(body.providers, kind="provider")
            allowed_provider_fields = {"api_key", "base_url", "auth_type"}
            for name, provider in body.providers.items():
                unsupported_fields = set(provider) - allowed_provider_fields
                if unsupported_fields:
                    raise DatusException(
                        ErrorCode.COMMON_FIELD_INVALID,
                        message=f"Provider '{name}' contains unsupported fields: {sorted(unsupported_fields)}.",
                    )

        if body.models is not None:
            _validate_keys(body.models, kind="model")

        cm = configuration_manager()

        if isinstance(body.target, str):
            effective_models = body.models if body.models is not None else cm.data.get("models") or {}
            if body.target not in effective_models:
                raise DatusException(
                    ErrorCode.COMMON_FIELD_INVALID,
                    message=f"target '{body.target}' does not exist in models.",
                )
        elif body.target is not None and body.target.custom:
            effective_models = body.models if body.models is not None else cm.data.get("models") or {}
            if body.target.custom not in effective_models:
                raise DatusException(
                    ErrorCode.COMMON_FIELD_INVALID,
                    message=f"target custom model '{body.target.custom}' does not exist in models.",
                )
    except DatusException as exc:
        _raise_bad_request(exc)

    previous_data = copy.deepcopy(cm.data)
    project_root = str(cm.data.get("project_root") or "") or None
    previous_override = None
    override_path = None
    override_existed = False
    override_content = None
    if isinstance(body.target, TargetModelRequest):
        previous_override = load_project_override(cwd=project_root)
        override_path = project_config_path(project_root)
        override_existed = override_path.exists()
        override_content = override_path.read_bytes() if override_existed else None
    if body.models is not None:
        cm.data["models"] = _merge_redacted_placeholders(dict(body.models), previous_data.get("models", {}))
    if body.providers is not None:
        cm.data["providers"] = _merge_redacted_placeholders(
            dict(body.providers),
            previous_data.get("providers", {}),
        )
    if isinstance(body.target, str):
        cm.data["target"] = body.target
    try:
        if isinstance(body.target, TargetModelRequest):
            override = copy.deepcopy(previous_override) if previous_override is not None else ProjectOverride()
            if body.target.custom:
                override.target = ProjectTarget(custom=body.target.custom)
            else:
                override.target = ProjectTarget(provider=body.target.provider, model=body.target.model)
            save_project_override(override, cwd=project_root)
        cm.save()
    except Exception:
        cm.data = previous_data
        if isinstance(body.target, TargetModelRequest) and override_path is not None:
            if override_existed and override_content is not None:
                override_path.parent.mkdir(parents=True, exist_ok=True)
                override_path.write_bytes(override_content)
            else:
                override_path.unlink(missing_ok=True)
        raise

    await _evict_current_project(ctx.project_id or "default")

    return Result(success=True, data={"updated": True})


@router.post(
    "/config/models/test",
    response_model=Result[ProbeResultData],
    response_model_exclude_none=True,
    summary="Test Model Connectivity",
    description="Send a tiny probe to verify an LLM model config is reachable.",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="config.models.probe", resource_type="config")),
    ],
)
async def probe_model_connectivity_endpoint(
    body: ProbeModelRequest,
    _ctx: ConfigEditCtx,
) -> Result[ProbeResultData]:
    """Return `{ok: True}` if the probe succeeds, else `{ok: False, message: ...}`."""
    payload = body.model_dump()
    try:
        await asyncio.to_thread(_probe_llm_sync, payload)
        return Result(success=True, data={"ok": True})
    except Exception as e:
        logger.info(f"Model connectivity probe failed: {e}")
        return Result(success=True, data={"ok": False, "message": str(e)})


@router.post(
    "/config/models/test-saved",
    response_model=Result[ProbeResultData],
    response_model_exclude_none=True,
    summary="Test Saved Model Connectivity",
    description="Resolve a saved provider or custom model config and send a tiny connectivity probe.",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="config.models.probe", resource_type="config")),
    ],
)
async def probe_saved_model_connectivity_endpoint(
    body: ProbeSavedModelRequest,
    _ctx: ConfigEditCtx,
    svc: ServiceDep,
) -> Result[ProbeResultData]:
    """Probe a saved config without exposing its resolved credentials to the client."""
    try:
        if body.custom:
            model_config = svc.agent_config.model_config(body.custom)
            embedding_config = _embedding_config_for_custom(body.custom)
            if embedding_config is not None:
                await asyncio.to_thread(_probe_embedding_sync, model_config, embedding_config)
                return Result(success=True, data={"ok": True})
        else:
            model_config = svc.agent_config._synthesize_model(body.provider, body.model)
        await asyncio.to_thread(_probe_llm_sync, _plain_config_value(model_config))
        return Result(success=True, data={"ok": True})
    except Exception as e:
        logger.info(f"Saved model connectivity probe failed: {e}")
        return Result(success=True, data={"ok": False, "message": str(e)})


@router.post(
    "/config/datasources/test",
    response_model=Result[ProbeResultData],
    response_model_exclude_none=True,
    summary="Test Datasource Connectivity",
    description="Run SELECT 1 against a datasource config to verify reachability and credentials.",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="config.datasources.probe", resource_type="config")),
    ],
)
async def probe_datasource_connectivity_endpoint(
    body: ProbeDatasourceRequest,
    _ctx: ConfigEditCtx,
) -> Result[ProbeResultData]:
    """Return `{ok: True}` if the probe succeeds, else `{ok: False, message: ...}`."""
    payload = body.model_dump()
    try:
        await asyncio.to_thread(_probe_datasource_sync, payload)
        return Result(success=True, data={"ok": True})
    except Exception as e:
        logger.info(f"Datasource connectivity probe failed: {e}")
        return Result(success=True, data={"ok": False, "message": str(e)})


@router.post(
    "/config/datasources/test-saved",
    response_model=Result[ProbeResultData],
    response_model_exclude_none=True,
    summary="Test Saved Datasource Connectivity",
    description="Resolve a saved datasource config and run a connectivity probe without exposing credentials.",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="config.datasources.probe", resource_type="config")),
    ],
)
async def probe_saved_datasource_connectivity_endpoint(
    body: ProbeSavedDatasourceRequest,
    _ctx: ConfigEditCtx,
    svc: ServiceDep,
) -> Result[ProbeResultData]:
    """Probe a saved datasource using its server-side resolved credentials."""
    try:
        datasource = svc.agent_config.datasource_configs.get(body.name)
        if datasource is None:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Datasource '{body.name}' does not exist.",
            )
        await asyncio.to_thread(_probe_datasource_sync, _plain_config_value(datasource))
        return Result(success=True, data={"ok": True})
    except Exception as e:
        logger.info(f"Saved datasource connectivity probe failed: {e}")
        return Result(success=True, data={"ok": False, "message": str(e)})
