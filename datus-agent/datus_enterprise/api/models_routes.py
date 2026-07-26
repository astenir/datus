"""Enterprise policy wrapper for the upstream model catalog route."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Request

from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_any_module
from datus.api.models.base_models import Result
from datus.api.models.downstream import ModelInfo, ModelsData
from datus.api.routes import models_routes as upstream_models_routes
from datus_enterprise.model_policy import filter_allowed_models, is_model_ref_allowed

router = APIRouter(prefix="/api/v1", tags=["models"])
_require_model_catalog_access = require_any_module("module.config.view", "module.chat")


def _resolve_current_model(agent_config: Any, models: List[ModelInfo]) -> Optional[str]:
    target_provider = getattr(agent_config, "_target_provider", None)
    target_model = getattr(agent_config, "_target_model", None)
    if target_provider and target_model:
        return f"{target_provider}/{target_model}"

    target = getattr(agent_config, "target", None)
    custom_models = getattr(agent_config, "models", None)
    if target and isinstance(custom_models, dict) and target in custom_models:
        if any(model.provider == "custom" and model.id == target and "chat" in model.capabilities for model in models):
            return f"custom/{target}"

    for model in models:
        if model.provider == "custom" and "chat" in model.capabilities:
            return f"custom/{model.id}"

    for model in models:
        if "chat" in model.capabilities:
            return f"{model.provider}/{model.id}"

    return None


@router.get(
    "/models",
    response_model=Result[ModelsData],
    summary="List Available Models",
    description="Return models for providers with credentials configured in agent.yml.",
    dependencies=[Depends(_require_model_catalog_access)],
)
async def list_models(svc: ServiceDep, request: Request) -> Result[ModelsData]:
    upstream_result = await upstream_models_routes.list_models(svc)
    if not upstream_result.success or upstream_result.data is None:
        return Result(
            success=False,
            errorCode=upstream_result.errorCode,
            errorMessage=upstream_result.errorMessage,
        )

    embedding_targets = set(getattr(svc.agent_config, "embedding_model_targets", set()) or set())
    models = [
        ModelInfo(
            **model.model_dump(),
            capabilities=(
                ["embedding"] if model.provider == "custom" and model.id in embedding_targets else ["chat"]
            ),
        )
        for model in upstream_result.data.models
    ]
    ctx = getattr(request.state, "app_context", None)
    current_model = _resolve_current_model(svc.agent_config, models)
    models = filter_allowed_models(ctx, models)
    if current_model and not is_model_ref_allowed(ctx, current_model):
        current_model = None
    filtered_providers = {model.provider for model in models}

    return Result(
        success=True,
        data=ModelsData(
            models=models,
            providers=[provider for provider in upstream_result.data.providers if provider in filtered_providers],
            current_model=current_model,
            fetched_at=upstream_result.data.fetched_at,
            source=upstream_result.data.source,
        ),
    )
