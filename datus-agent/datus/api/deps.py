"""FastAPI dependency injection — plugin-based auth + DatusService cache."""

import copy
import hashlib
import re
from fnmatch import fnmatchcase
from inspect import isawaitable
from typing import Annotated, Any, Optional

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
_SCOPE_GLOB_META_CHARS = "*?["


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


async def _validate_enterprise_context(ctx: AppContext, enterprise_extensions: EnterpriseExtensions) -> None:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    try:
        user = await enterprise_extensions.user_store.get_user(ctx.user_id)
    except Exception as e:
        await _write_enterprise_audit_best_effort(
            enterprise_extensions,
            AuditEvent(
                user_id=ctx.user_id,
                action="auth.enterprise_user_status",
                resource_type="user",
                resource_id=ctx.user_id,
                decision="deny",
                reason="user status unavailable",
            ),
        )
        raise HTTPException(status_code=403, detail="USER_STATUS_UNAVAILABLE") from e
    if user is not None and not bool(user.get("enabled", True)):
        await _write_enterprise_audit_best_effort(
            enterprise_extensions,
            AuditEvent(
                user_id=ctx.user_id,
                action="auth.enterprise_user_status",
                resource_type="user",
                resource_id=ctx.user_id,
                decision="deny",
                reason="user disabled",
            ),
        )
        raise HTTPException(status_code=403, detail="USER_DISABLED")


async def _refresh_enterprise_context(ctx: AppContext, enterprise_extensions: EnterpriseExtensions) -> None:
    """Merge request RBAC and datasource grants from enterprise metadata stores."""

    try:
        stored_role_ids = await enterprise_extensions.role_store.list_user_roles(ctx.user_id or "")
        role_ids = _merge_string_lists(stored_role_ids)
        role_permissions: set[str] = set()
        for role_id in role_ids:
            role = await enterprise_extensions.role_store.get_role(role_id)
            if role is None:
                await _audit_enterprise_context_deny(
                    ctx,
                    enterprise_extensions,
                    reason="role metadata missing",
                    metadata={"role_id": role_id},
                )
                raise HTTPException(status_code=403, detail="ROLE_CONTEXT_UNAVAILABLE")
            if isinstance(role, dict):
                role_permissions.update(_string_set(role.get("permissions")))
    except HTTPException:
        raise
    except Exception as e:
        await _audit_enterprise_context_deny(ctx, enterprise_extensions, reason="role context unavailable")
        raise HTTPException(status_code=403, detail="ROLE_CONTEXT_UNAVAILABLE") from e

    try:
        datasource_grants = await _merged_datasource_grants(ctx, role_ids, enterprise_extensions)
    except Exception as e:
        await _audit_enterprise_context_deny(ctx, enterprise_extensions, reason="datasource grants unavailable")
        raise HTTPException(status_code=403, detail="DATASOURCE_GRANTS_UNAVAILABLE") from e

    ctx.roles = role_ids
    ctx.permissions = role_permissions
    ctx.datasource_grants = datasource_grants
    ctx.principal = dict(ctx.principal or {})
    ctx.principal["roles"] = list(ctx.roles)
    ctx.principal["permissions"] = sorted(ctx.permissions)
    ctx.principal["datasource_grants"] = copy.deepcopy(ctx.datasource_grants)


async def _merged_datasource_grants(
    ctx: AppContext,
    role_ids: list[str],
    enterprise_extensions: EnterpriseExtensions,
) -> dict[str, Any]:
    grants: dict[str, Any] = {}
    for role_id in role_ids:
        records = await enterprise_extensions.datasource_grant_store.list_grants(
            subject_type="role",
            subject_id=role_id,
        )
        for record in records:
            _merge_grant_record(grants, record, mode="union")

    records = await enterprise_extensions.datasource_grant_store.list_grants(
        subject_type="user",
        subject_id=ctx.user_id,
    )
    for record in records:
        _merge_grant_record(grants, record, mode="narrow")
    return grants


def _merge_grant_record(grants: dict[str, Any], record: dict[str, Any], *, mode: str = "union") -> None:
    datasource_key = str(record.get("datasource_key") or "").strip()
    if not datasource_key:
        return
    merged = dict(record.get("scope") or {})
    effect = str(record.get("effect") or "allow").strip().lower()
    merged["effect"] = effect
    existing = grants.get(datasource_key)
    if _grant_effect(existing) == "deny" or effect == "deny":
        grants[datasource_key] = {"effect": "deny"}
        return
    if not isinstance(existing, dict):
        grants[datasource_key] = merged
        return
    if mode == "narrow":
        grants[datasource_key] = _intersect_allow_grants(existing, merged)
        return
    grants[datasource_key] = _union_allow_grants(existing, merged)


def _union_allow_grants(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = {"effect": "allow"}
    for key in ("allow_catalog", "allow_sql"):
        merged[key] = _grant_bool_allows(left, key) or _grant_bool_allows(right, key)
    for key in ("catalogs", "databases", "schemas", "tables"):
        patterns = _union_scope_patterns(left.get(key), right.get(key))
        if patterns is not None:
            merged[key] = patterns
    return merged


def _intersect_allow_grants(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = {"effect": "allow"}
    for key in ("allow_catalog", "allow_sql"):
        merged[key] = _grant_bool_allows(left, key) and _grant_bool_allows(right, key)
    for key in ("catalogs", "databases", "schemas", "tables"):
        patterns = _intersect_scope_patterns(left.get(key), right.get(key))
        if patterns is not None:
            merged[key] = patterns
    return merged


def _grant_bool_allows(grant: dict[str, Any], key: str) -> bool:
    return grant.get(key) is not False


def _union_scope_patterns(left: Any, right: Any) -> list[str] | None:
    left_patterns = _scope_pattern_list(left)
    right_patterns = _scope_pattern_list(right)
    if left_patterns is None:
        return right_patterns
    if right_patterns is None:
        return left_patterns
    return sorted({*left_patterns, *right_patterns})


def _intersect_scope_patterns(left: Any, right: Any) -> list[str] | None:
    left_patterns = _scope_pattern_list(left)
    right_patterns = _scope_pattern_list(right)
    if left_patterns is None:
        return right_patterns
    if right_patterns is None:
        return left_patterns
    intersected: set[str] = set()
    for left_pattern in left_patterns:
        for right_pattern in right_patterns:
            narrower = _narrower_scope_pattern(left_pattern, right_pattern)
            if narrower is not None:
                intersected.add(narrower)
    return sorted(intersected)


def _narrower_scope_pattern(left_pattern: str, right_pattern: str) -> str | None:
    if _scope_pattern_includes(left_pattern, right_pattern):
        return right_pattern
    if _scope_pattern_includes(right_pattern, left_pattern):
        return left_pattern
    return None


def _scope_pattern_includes(container: str, candidate: str) -> bool:
    if container == candidate or container == "*":
        return True
    if not _has_scope_glob(candidate):
        return fnmatchcase(candidate, container)

    container_prefix = _simple_prefix_glob(container)
    if container_prefix is None:
        return False
    return _literal_glob_prefix(candidate).startswith(container_prefix)


def _has_scope_glob(pattern: str) -> bool:
    return any(char in pattern for char in _SCOPE_GLOB_META_CHARS)


def _simple_prefix_glob(pattern: str) -> str | None:
    if not pattern.endswith("*"):
        return None
    prefix = pattern[:-1]
    if _has_scope_glob(prefix):
        return None
    return prefix


def _literal_glob_prefix(pattern: str) -> str:
    for index, char in enumerate(pattern):
        if char in _SCOPE_GLOB_META_CHARS:
            return pattern[:index]
    return pattern


def _scope_pattern_list(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _grant_effect(grant: Any) -> str | None:
    if grant is True:
        return "allow"
    if grant is False:
        return "deny"
    if isinstance(grant, dict):
        return str(grant.get("effect") or "allow").strip().lower()
    return None


def _merge_string_lists(values: list[Any]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def _string_set(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item.strip() for item in raw if isinstance(item, str) and item.strip()}
    return set()


async def _audit_enterprise_context_deny(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
    *,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    await _write_enterprise_audit_best_effort(
        enterprise_extensions,
        AuditEvent(
            user_id=ctx.user_id,
            action="auth.enterprise_context",
            resource_type="user",
            resource_id=ctx.user_id,
            decision="deny",
            reason=reason,
            metadata=metadata or {},
        ),
    )


async def _write_enterprise_audit_best_effort(
    enterprise_extensions: EnterpriseExtensions,
    event: AuditEvent,
) -> None:
    try:
        await enterprise_extensions.audit_sink.write(event)
    except Exception as exc:
        logger.warning(
            "Enterprise audit write failed for action '%s' decision '%s': %s",
            event.action,
            event.decision,
            exc,
        )


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
