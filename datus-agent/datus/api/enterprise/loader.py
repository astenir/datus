"""Load enterprise extension providers from ``agent.yml``."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from datus.api.enterprise.defaults import (
    InMemoryEnterpriseAgentStore,
    InMemoryEnterpriseDatasourceGrantStore,
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseUserStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.protocols import (
    ArtifactAclStore,
    AuditSink,
    AuthorizationProvider,
    ConfigProjector,
    EnterpriseAgentStore,
    EnterpriseDatasourceGrantStore,
    EnterpriseQuotaStore,
    EnterpriseRoleStore,
    EnterpriseSecretStore,
    EnterpriseUserStore,
    SessionBodyStore,
    SessionOwnerStore,
)
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class UserAutoProvisioningConfig:
    """Enterprise first-login user provisioning settings."""

    enabled: bool = False
    default_role_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnterpriseExtensions:
    """Loaded enterprise extension set."""

    enabled: bool
    authorization_provider: AuthorizationProvider
    config_projector: ConfigProjector
    session_owner_store: SessionOwnerStore
    audit_sink: AuditSink
    session_body_store: SessionBodyStore | None = None
    artifact_acl_store: ArtifactAclStore | None = None
    quota_store: EnterpriseQuotaStore | None = None
    secret_store: EnterpriseSecretStore | None = None
    user_auto_provisioning: UserAutoProvisioningConfig = field(default_factory=UserAutoProvisioningConfig)
    user_store: EnterpriseUserStore = field(default_factory=InMemoryEnterpriseUserStore)
    role_store: EnterpriseRoleStore = field(default_factory=InMemoryEnterpriseRoleStore)
    datasource_grant_store: EnterpriseDatasourceGrantStore = field(
        default_factory=InMemoryEnterpriseDatasourceGrantStore
    )
    agent_store: EnterpriseAgentStore = field(default_factory=InMemoryEnterpriseAgentStore)

    async def close(self) -> None:
        """Close extension providers that expose a best-effort ``close`` hook."""
        seen: set[int] = set()
        for component in (
            self.authorization_provider,
            self.config_projector,
            self.session_owner_store,
            self.session_body_store,
            self.audit_sink,
            self.artifact_acl_store,
            self.quota_store,
            self.secret_store,
            self.user_store,
            self.role_store,
            self.datasource_grant_store,
            self.agent_store,
        ):
            if component is None:
                continue
            component_id = id(component)
            if component_id in seen:
                continue
            seen.add(component_id)
            close = getattr(component, "close", None)
            if close is None:
                continue
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception(f"Failed to close enterprise extension provider {component.__class__.__name__}")


def load_enterprise_extensions(enterprise_config: dict[str, Any] | None) -> EnterpriseExtensions:
    """Load enterprise extension providers.

    ``enterprise.enabled=false`` returns local-compatible no-op providers.
    ``enterprise.enabled=true`` requires production authorization and audit
    providers to be configured explicitly. Config projection is loaded when
    configured, but remains a passthrough skeleton until execution paths adopt
    request-level projection in the datasource-grant phase.
    """

    raw = enterprise_config or {}
    if not isinstance(raw, dict):
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message="enterprise config must be a mapping.",
        )

    enabled = _coerce_bool(raw.get("enabled"), default=False)
    if not enabled:
        return EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            session_body_store=None,
            audit_sink=NoopAuditSink(),
            artifact_acl_store=None,
            quota_store=None,
            secret_store=None,
            user_auto_provisioning=UserAutoProvisioningConfig(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=InMemoryEnterpriseRoleStore(),
            datasource_grant_store=InMemoryEnterpriseDatasourceGrantStore(),
            agent_store=InMemoryEnterpriseAgentStore(),
        )

    authorization_provider = _load_required_component(
        raw,
        "authorization_provider",
        AuthorizationProvider,
    )
    config_projector = _load_optional_component(
        raw,
        "config_projector",
        ConfigProjector,
        PassthroughConfigProjector(),
    )
    audit_sink = _load_required_component(raw, "audit_sink", AuditSink)
    user_store = _load_optional_component(
        raw,
        "user_store",
        EnterpriseUserStore,
        InMemoryEnterpriseUserStore(),
    )
    role_store = _load_optional_component(
        raw,
        "role_store",
        EnterpriseRoleStore,
        InMemoryEnterpriseRoleStore(),
    )
    datasource_grant_store = _load_required_component(
        raw,
        "datasource_grant_store",
        EnterpriseDatasourceGrantStore,
    )
    session_owner_store = _load_optional_component(
        raw,
        "session_owner_store",
        SessionOwnerStore,
        InMemorySessionOwnerStore(),
    )
    session_body_store = _load_optional_component(
        raw,
        "session_body_store",
        SessionBodyStore,
        None,
    )
    artifact_acl_store = _load_optional_component(
        raw,
        "artifact_acl_store",
        ArtifactAclStore,
        None,
    )
    quota_store = _load_optional_component(
        raw,
        "quota_store",
        EnterpriseQuotaStore,
        None,
    )
    secret_store = _load_optional_component(
        raw,
        "secret_store",
        EnterpriseSecretStore,
        None,
    )
    agent_store = _load_optional_component(
        raw,
        "agent_store",
        EnterpriseAgentStore,
        InMemoryEnterpriseAgentStore(),
    )
    user_auto_provisioning = _load_user_auto_provisioning(raw.get("user_auto_provisioning"))

    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=authorization_provider,
        config_projector=config_projector,
        session_owner_store=session_owner_store,
        session_body_store=session_body_store,
        audit_sink=audit_sink,
        artifact_acl_store=artifact_acl_store,
        quota_store=quota_store,
        secret_store=secret_store,
        user_auto_provisioning=user_auto_provisioning,
        user_store=user_store,
        role_store=role_store,
        datasource_grant_store=datasource_grant_store,
        agent_store=agent_store,
    )


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _load_user_auto_provisioning(raw: Any) -> UserAutoProvisioningConfig:
    if raw is None:
        return UserAutoProvisioningConfig()
    if not isinstance(raw, dict):
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message="enterprise.user_auto_provisioning must be a mapping.",
        )
    return UserAutoProvisioningConfig(
        enabled=_coerce_bool(raw.get("enabled"), default=False),
        default_role_ids=tuple(_string_list(raw.get("default_role_ids"))),
    )


def _string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        values = raw.split(",")
    elif isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        return []
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _load_required_component(raw: dict[str, Any], key: str, protocol: type[Protocol]) -> Any:
    spec = raw.get(key)
    if not spec:
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message=f"enterprise.enabled=true requires enterprise.{key}.class.",
        )
    return _load_component(spec, key, protocol)


def _load_optional_component(raw: dict[str, Any], key: str, protocol: type[Protocol], default: T) -> T:
    spec = raw.get(key)
    if not spec:
        return default
    return _load_component(spec, key, protocol)


def _load_component(spec: Any, key: str, protocol: type[Protocol]) -> Any:
    if not isinstance(spec, dict):
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message=f"enterprise.{key} must be a mapping with class and optional kwargs.",
        )
    class_path = spec.get("class")
    if not class_path:
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message=f"enterprise.{key}.class is required.",
        )

    normalized = str(class_path).replace(":", ".")
    module_name, _, class_name = normalized.rpartition(".")
    if not module_name or not class_name:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Invalid enterprise.{key} class path: {class_path!r}. Expected 'module.Class' or 'module:Class'.",
        )

    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Failed to import enterprise.{key} module {module_name!r}: {e}",
        ) from e

    try:
        cls = getattr(module, class_name)
    except AttributeError as e:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Enterprise provider class {class_name!r} not found in module {module_name!r}",
        ) from e

    kwargs = spec.get("kwargs") or {}
    try:
        instance = cls(**kwargs)
    except Exception as e:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Failed to instantiate enterprise.{key} {class_path!r}: {e}",
        ) from e

    if not isinstance(instance, protocol):
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"{class_path} does not implement the enterprise.{key} protocol",
        )

    logger.info(f"Loaded enterprise.{key}: {class_path}")
    return instance
