"""FastAPI dependency injection — plugin-based auth + DatusService cache."""

import asyncio
import hashlib
import re
from inspect import isawaitable
from typing import Annotated, Any, Optional

from fastapi import Depends, HTTPException, Request

from datus.api.auth.context import AppContext
from datus.api.auth.provider import AuthProvider
from datus.api.enterprise.loader import EnterpriseExtensions, load_enterprise_extensions
from datus.api.enterprise.models import AuditEvent
from datus.api.services.chat_admission import ChatAdmissionController
from datus.api.services.datus_service import DatusService
from datus.api.services.datus_service_cache import DatusServiceCache
from datus.configuration.agent_config_loader import load_agent_config
from datus.utils.exceptions import DatusException
from datus.utils.loggings import get_logger
from datus_enterprise.services import request_context_policy as _request_context_policy

logger = get_logger(__name__)

# Module-level singletons (set during lifespan via init_deps)
_auth_provider: Optional[AuthProvider] = None
_service_cache: Optional[DatusServiceCache] = None
_chat_admission: Optional[ChatAdmissionController] = None
_enterprise_extensions: Optional[EnterpriseExtensions] = None
_datasource: str = "default"
_default_source: Optional[str] = None
_default_interactive: bool = True
_stream_thinking: bool = False

_DEFAULT_PROJECT_KEY = "default"
_SAFE_CACHE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_.\-]")
_SAFE_CACHE_SEGMENT_FULL_RE = re.compile(r"[A-Za-z0-9_.\-]+")
_ENTERPRISE_METADATA_TIMEOUT_SECONDS = 5.0
_ENTERPRISE_AUDIT_TIMEOUT_SECONDS = 2.0

# Compatibility aliases for downstream callers and focused policy tests.
_intersect_allow_grants = _request_context_policy._intersect_allow_grants
_intersect_scope_patterns = _request_context_policy._intersect_scope_patterns


def init_deps(
    auth_provider: AuthProvider,
    cache: DatusServiceCache,
    datasource: str = "default",
    default_source: Optional[str] = None,
    default_interactive: bool = True,
    stream_thinking: bool = False,
    enterprise_extensions: Optional[EnterpriseExtensions] = None,
    chat_admission: Optional[ChatAdmissionController] = None,
) -> None:
    """Initialize global auth provider and service cache.

    Called from main.py lifespan to inject dependencies.
    """
    global _auth_provider, _service_cache, _enterprise_extensions, _chat_admission
    global _datasource, _default_source, _default_interactive, _stream_thinking
    _auth_provider = auth_provider
    _service_cache = cache
    _chat_admission = chat_admission or ChatAdmissionController()
    _enterprise_extensions = enterprise_extensions or load_enterprise_extensions(None)
    _datasource = datasource
    _default_source = default_source
    _default_interactive = default_interactive
    _stream_thinking = stream_thinking
    # Wire eviction callback: auth config changes trigger cache eviction
    auth_provider.on_evict(evict_datus_service)


def get_enterprise_extensions() -> EnterpriseExtensions:
    """Return loaded enterprise extension providers."""

    return _enterprise_extensions or load_enterprise_extensions(None)


def service_cache_key(project_id: str | None, *, enterprise_enabled: bool) -> str:
    """Return the DatusService cache key for local or enterprise mode."""

    project = _safe_cache_segment(project_id or _DEFAULT_PROJECT_KEY)
    if enterprise_enabled:
        return f"enterprise:{project}"
    return project


def _canonical_project_id(project_id: str | None) -> str:
    if project_id is None:
        return _DEFAULT_PROJECT_KEY
    candidate = str(project_id).strip()
    return candidate or _DEFAULT_PROJECT_KEY


def _safe_cache_segment(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        return _DEFAULT_PROJECT_KEY
    if _SAFE_CACHE_SEGMENT_FULL_RE.fullmatch(raw):
        return raw
    candidate = _SAFE_CACHE_SEGMENT_RE.sub("_", raw).strip("_")
    if not candidate:
        candidate = _DEFAULT_PROJECT_KEY
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"encoded:{digest}:{candidate[:80]}"


async def evict_datus_service(project_id: str | None) -> None:
    """Evict the current-mode DatusService cache entry for ``project_id``."""

    if _service_cache is None:
        return
    enterprise_enabled = get_enterprise_extensions().enabled
    await _service_cache.evict(service_cache_key(project_id, enterprise_enabled=enterprise_enabled))


async def get_datus_service(request: Request) -> DatusService:
    """Primary dependency for all agent routes.

    Authenticates the request, caches the resulting ``AppContext`` on
    ``request.state`` for downstream dependencies (e.g. ``AppContextDep``),
    then returns a cached-per-project DatusService. If AppContext has no
    config, loads it on-demand from YAML.
    """
    if _auth_provider is None:
        raise RuntimeError("Auth provider not initialized. Call init_deps() in lifespan.")
    if _service_cache is None:
        raise RuntimeError("Service cache not initialized. Call init_deps() in lifespan.")

    ctx = await get_request_app_context(request)
    enterprise_extensions = get_enterprise_extensions()

    expected_fp = DatusService.compute_fingerprint(ctx.config) if ctx.config is not None else None
    project_id = _canonical_project_id(ctx.project_id)
    cache_key = service_cache_key(project_id, enterprise_enabled=enterprise_extensions.enabled)

    async def _factory() -> DatusService:
        # Load config on-demand if not provided by auth provider
        agent_config = ctx.config
        if agent_config is None:
            try:
                agent_config = load_agent_config(datasource=_datasource)
            except Exception as e:
                logger.error(f"Failed to load agent config for datasource '{_datasource}': {e}")
                raise RuntimeError(f"Failed to load agent config: {e}") from e

        return DatusService(
            agent_config=agent_config,
            project_id=project_id,
            default_source=_default_source,
            default_interactive=_default_interactive,
            stream_thinking=_stream_thinking,
            session_owner_store=enterprise_extensions.session_owner_store,
            session_body_store=enterprise_extensions.session_body_store,
            artifact_acl_store=enterprise_extensions.artifact_acl_store,
            enterprise_enabled=enterprise_extensions.enabled,
            chat_admission=_chat_admission,
        )

    return await _service_cache.get_or_create(cache_key, _factory, expected_fingerprint=expected_fp)


async def resolve_datus_service_for_request(request: Request) -> DatusService:
    """Resolve ``get_datus_service`` after route-level validation has passed."""

    service_provider = request.app.dependency_overrides.get(get_datus_service, get_datus_service)
    result = service_provider(request)
    if isawaitable(result):
        return await result
    return result


async def get_request_app_context(request: Request) -> AppContext:
    """Authenticate and cache the request context without creating ``DatusService``."""

    enterprise_extensions = get_enterprise_extensions()
    cached = getattr(request.state, "app_context", None)
    if isinstance(cached, AppContext):
        if enterprise_extensions.enabled and not getattr(request.state, "app_context_enterprise_ready", False):
            await _validate_enterprise_context(cached, enterprise_extensions)
            await _refresh_enterprise_context(cached, enterprise_extensions)
            request.state.app_context_enterprise_ready = True
        return cached

    if _auth_provider is None:
        raise RuntimeError("Auth provider not initialized. Call init_deps() in lifespan.")

    try:
        ctx: AppContext = await _auth_provider.authenticate(request)
    except DatusException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    request.state.app_context = ctx
    if enterprise_extensions.enabled:
        await _validate_enterprise_context(ctx, enterprise_extensions)
        await _refresh_enterprise_context(ctx, enterprise_extensions)
        request.state.app_context_enterprise_ready = True

    return ctx


async def _validate_enterprise_context(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
) -> None:
    await _request_context_policy.validate_enterprise_context(
        ctx,
        enterprise_extensions,
        metadata_call=_enterprise_metadata_call,
        write_audit=_write_enterprise_audit_best_effort,
    )


async def _refresh_enterprise_context(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
) -> None:
    await _request_context_policy.refresh_enterprise_context(
        ctx,
        enterprise_extensions,
        metadata_call=_enterprise_metadata_call,
        write_audit=_write_enterprise_audit_best_effort,
    )


async def _write_enterprise_audit_best_effort(
    enterprise_extensions: EnterpriseExtensions,
    event: AuditEvent,
) -> None:
    try:
        await asyncio.wait_for(
            enterprise_extensions.audit_sink.write(event),
            timeout=_ENTERPRISE_AUDIT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning(
            "Enterprise audit write failed for action '%s' decision '%s': %s",
            event.action,
            event.decision,
            exc,
        )


async def _enterprise_metadata_call(awaitable: Any, *, operation: str) -> Any:
    try:
        return await asyncio.wait_for(awaitable, timeout=_ENTERPRISE_METADATA_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"Enterprise metadata operation timed out: {operation}") from exc


def get_app_context(request: Request) -> AppContext:
    """Return the ``AppContext`` cached on the request by ``get_datus_service``.

    Must be used together with (and after) ``ServiceDep`` on the same route.
    """
    ctx = getattr(request.state, "app_context", None)
    if ctx is None:
        raise RuntimeError(
            "AppContext not found on request.state — ensure ServiceDep is declared before AppContextDep."
        )
    return ctx


ServiceDep = Annotated[DatusService, Depends(get_datus_service)]
AppContextDep = Annotated[AppContext, Depends(get_app_context)]
