"""FastAPI dependency injection — plugin-based auth + DatusService cache."""

import hashlib
import re
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request

from datus.api.auth.context import AppContext
from datus.api.auth.provider import AuthProvider
from datus.api.enterprise.loader import EnterpriseExtensions, load_enterprise_extensions
from datus.api.enterprise.models import AuditEvent
from datus.api.services.datus_service import DatusService
from datus.api.services.datus_service_cache import DatusServiceCache
from datus.configuration.agent_config_loader import load_agent_config
from datus.utils.exceptions import DatusException
from datus.utils.loggings import get_logger

logger = get_logger(__name__)

# Module-level singletons (set during lifespan via init_deps)
_auth_provider: Optional[AuthProvider] = None
_service_cache: Optional[DatusServiceCache] = None
_enterprise_extensions: Optional[EnterpriseExtensions] = None
_datasource: str = "default"
_default_source: Optional[str] = None
_default_interactive: bool = True
_stream_thinking: bool = False

_DEFAULT_PROJECT_KEY = "default"
_SAFE_CACHE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_.\-]")
_SAFE_CACHE_SEGMENT_FULL_RE = re.compile(r"[A-Za-z0-9_.\-]+")


def init_deps(
    auth_provider: AuthProvider,
    cache: DatusServiceCache,
    datasource: str = "default",
    default_source: Optional[str] = None,
    default_interactive: bool = True,
    stream_thinking: bool = False,
    enterprise_extensions: Optional[EnterpriseExtensions] = None,
) -> None:
    """Initialize global auth provider and service cache.

    Called from main.py lifespan to inject dependencies.
    """
    global _auth_provider, _service_cache, _enterprise_extensions
    global _datasource, _default_source, _default_interactive, _stream_thinking
    _auth_provider = auth_provider
    _service_cache = cache
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

    try:
        ctx: AppContext = await _auth_provider.authenticate(request)
    except DatusException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    request.state.app_context = ctx
    enterprise_extensions = get_enterprise_extensions()
    if enterprise_extensions.enabled:
        await _validate_enterprise_context(ctx, enterprise_extensions)

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
        )

    return await _service_cache.get_or_create(cache_key, _factory, expected_fingerprint=expected_fp)


async def _validate_enterprise_context(ctx: AppContext, enterprise_extensions: EnterpriseExtensions) -> None:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    try:
        user = await enterprise_extensions.user_store.get_user(ctx.user_id)
    except Exception as e:
        await enterprise_extensions.audit_sink.write(
            AuditEvent(
                user_id=ctx.user_id,
                action="auth.enterprise_user_status",
                resource_type="user",
                resource_id=ctx.user_id,
                decision="deny",
                reason="user status unavailable",
            )
        )
        raise HTTPException(status_code=403, detail="USER_STATUS_UNAVAILABLE") from e
    if user is not None and not bool(user.get("enabled", True)):
        await enterprise_extensions.audit_sink.write(
            AuditEvent(
                user_id=ctx.user_id,
                action="auth.enterprise_user_status",
                resource_type="user",
                resource_id=ctx.user_id,
                decision="deny",
                reason="user disabled",
            )
        )
        raise HTTPException(status_code=403, detail="USER_DISABLED")


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
