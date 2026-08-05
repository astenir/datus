"""Request-scoped credentials used by remote MCP connections."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MCPRequestCredentials:
    """Ephemeral caller credentials that must never enter persisted MCP config."""

    bearer_token: str | None = field(default=None, repr=False)
    user_id: str | None = None

    @classmethod
    def from_authorization_header(
        cls,
        authorization: str | None,
        *,
        user_id: str | None = None,
    ) -> "MCPRequestCredentials":
        raw = (authorization or "").strip()
        scheme, separator, token = raw.partition(" ")
        if not separator or scheme.casefold() != "bearer" or not token.strip():
            return cls(user_id=user_id)
        return cls(bearer_token=token.strip(), user_id=user_id)
