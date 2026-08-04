"""Shared normalization for immutable enterprise Agent prompt versions."""

from __future__ import annotations

import copy
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any


class PromptVersionConflictError(ValueError):
    """Raised when a prompt version label or activation precondition conflicts."""


class PromptVersionNotFoundError(LookupError):
    """Raised when a prompt version does not belong to the requested Agent."""


class PromptVersionAgentNotFoundError(LookupError):
    """Raised when prompt version operations target an unknown Agent."""


def prompt_content_sha256(content: str) -> str:
    """Return the stable SHA-256 identity for one exact prompt body."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def prompt_template_value(value: Any) -> str | None:
    """Preserve one non-blank Prompt body exactly, including surrounding whitespace."""

    if value is None:
        return None
    content = str(value)
    return content if content.strip() else None


def new_prompt_version_id() -> str:
    return f"pv_{uuid.uuid4().hex}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalized_prompt_version_input(
    *,
    agent_id: str,
    version: str,
    prompt_template: str,
    prompt_language: str,
    change_note: str | None,
    based_on_version_id: str | None,
    created_by: str | None,
    version_id: str | None = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    normalized_version = str(version or "").strip()
    normalized_content = str(prompt_template or "")
    normalized_language = str(prompt_language or "en").strip() or "en"
    if not normalized_agent_id:
        raise ValueError("Agent id is required.")
    if not normalized_version:
        raise ValueError("Prompt version is required.")
    if len(normalized_version) > 40:
        raise ValueError("Prompt version must contain at most 40 characters.")
    if not normalized_content.strip():
        raise ValueError("Prompt template must not be empty.")
    if len(normalized_language) > 20:
        raise ValueError("Prompt language must contain at most 20 characters.")
    normalized_note = _optional_str(change_note)
    if normalized_note is not None and len(normalized_note) > 500:
        raise ValueError("Prompt version change note must contain at most 500 characters.")
    return {
        "version_id": _optional_str(version_id) or new_prompt_version_id(),
        "agent_id": normalized_agent_id,
        "version": normalized_version,
        "prompt_template": normalized_content,
        "prompt_language": normalized_language,
        "content_sha256": prompt_content_sha256(normalized_content),
        "change_note": normalized_note,
        "based_on_version_id": _optional_str(based_on_version_id),
        "created_by": _optional_str(created_by),
    }


def copy_prompt_version_record(record: dict[str, Any], *, active: bool | None = None) -> dict[str, Any]:
    copied = copy.deepcopy(record)
    copied["version_id"] = str(copied["version_id"])
    copied["agent_id"] = str(copied["agent_id"])
    copied["version"] = str(copied["version"])
    copied["prompt_template"] = str(copied["prompt_template"])
    copied["prompt_language"] = str(copied.get("prompt_language") or "en")
    copied["content_sha256"] = str(copied["content_sha256"])
    copied["change_note"] = _optional_str(copied.get("change_note"))
    copied["based_on_version_id"] = _optional_str(copied.get("based_on_version_id"))
    copied["created_by"] = _optional_str(copied.get("created_by"))
    copied["created_at"] = _optional_str(copied.get("created_at"))
    if active is not None:
        copied["active"] = bool(active)
    else:
        copied["active"] = bool(copied.get("active", False))
    return copied


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
