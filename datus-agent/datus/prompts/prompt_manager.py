# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
Simple File-based Template Version Management

Manages prompt templates with simple file-based versioning.
Template files follow the pattern: {template_name}_{version}.j2
No configuration file needed - versions are determined by scanning files.
"""

import hashlib
import json
import re
import shutil
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, List, Optional

from jinja2 import Environment, FileSystemLoader, Template, meta

from datus.prompts.prompt_runtime_template_downstream import find_runtime_template
from datus.utils.loggings import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from datus.utils.path_manager import DatusPathManager


_captured_template_identities: ContextVar[list[dict[str, str]] | None] = ContextVar(
    "captured_prompt_template_identities",
    default=None,
)


@contextmanager
def capture_prompt_template_identities() -> Iterator[list[dict[str, str]]]:
    """Capture the exact templates rendered while building one system prompt."""

    identities: list[dict[str, str]] = []
    token = _captured_template_identities.set(identities)
    try:
        yield identities
    finally:
        _captured_template_identities.reset(token)


class PromptManager:
    """Manages file-based versioned prompt templates with Jinja2 rendering support."""

    # Class-level Jinja2 environment cache, shared across instances.
    # Keyed by template directory path so different tenants get separate environments.
    # Uses OrderedDict with LRU eviction to prevent unbounded growth in long-running
    # SaaS servers where tenants come and go.
    _MAX_ENV_CACHE_SIZE: int = 128
    _env_cache: OrderedDict[str, Environment] = OrderedDict()

    def __init__(
        self,
        *,
        path_manager: Optional["DatusPathManager"] = None,
        agent_config: Optional[Any] = None,
    ):
        """
        Initialize the prompt manager.

        User templates are stored in {agent.home}/template/ (fixed path).
        Falls back to built-in prompt_templates/ directory if user template not found.
        Configure agent.home in agent.yml to change the root directory.
        """
        self.default_templates_dir = Path(__file__).parent / "prompt_templates"
        self._path_manager = path_manager
        self._agent_config = agent_config

    @property
    def user_templates_dir(self) -> Path:
        """Get user templates directory from the current configured home."""
        from datus.utils.path_manager import get_path_manager

        return get_path_manager(path_manager=self._path_manager, agent_config=self._agent_config).template_dir

    def _get_env(self) -> Environment:
        """Get Jinja2 environment with multi-directory search path.

        Cached per ``user_templates_dir`` so different homes (SaaS tenants)
        get separate Jinja2 environments without re-creating on every call.
        Uses LRU eviction when the cache exceeds ``_MAX_ENV_CACHE_SIZE``.
        """
        cache_key = str(self.user_templates_dir)
        env = self._env_cache.get(cache_key)
        if env is not None:
            self._env_cache.move_to_end(cache_key)
            return env
        search_paths = [cache_key, str(self.default_templates_dir)]
        # Keep the environment but not Jinja's logical-filename template
        # cache. A cached builtin include remains "up to date" even when a
        # same-name user override later appears earlier in the loader search
        # path, which would make the rendered prompt disagree with its current
        # provenance. Session-level prompt snapshots provide the useful cache.
        env = Environment(
            loader=FileSystemLoader(search_paths),
            trim_blocks=True,
            lstrip_blocks=True,
            cache_size=0,
        )
        self._env_cache[cache_key] = env
        if len(self._env_cache) > self._MAX_ENV_CACHE_SIZE:
            self._env_cache.popitem(last=False)
        logger.debug(f"Template search paths: {search_paths}")
        return env

    @classmethod
    def clear_env_cache(cls) -> None:
        """Remove all cached Jinja2 environments."""
        cls._env_cache.clear()

    @classmethod
    def invalidate_env(cls, user_templates_dir: str) -> None:
        """Remove a single tenant's cached Jinja2 environment.

        Args:
            user_templates_dir: The template directory path used as cache key.
        """
        cls._env_cache.pop(user_templates_dir, None)

    def _get_template_path(self, template_name: str, version: Optional[str] = None) -> Path:
        """
        Get the actual file path for a template and version.

        Args:
            template_name: Name of the template (without version suffix)
            version: Version string or None for latest version

        Returns:
            Actual file_path
        """
        if not version:
            # Find the latest version
            version = self.get_latest_version(template_name)
            if not version:
                raise FileNotFoundError(f"No versions found for template '{template_name}'")

        filename = f"{template_name}_{version}.j2"

        # Check user templates directory first
        user_file_path = self.user_templates_dir / filename

        if user_file_path.exists():
            logger.debug(f"Loading template from user directory: {user_file_path}")
            return user_file_path

        # Fallback to default templates directory
        default_file_path = self.default_templates_dir / filename
        if default_file_path.exists():
            logger.debug(f"Loading template from default directory: {default_file_path}")
            return default_file_path

        raise FileNotFoundError(
            f"Prompt Template file '{filename}' not found in user directory ({self.user_templates_dir})"
            f" or default directory ({self.default_templates_dir})"
        )

    def _get_template_filename(self, template_name: str, version: Optional[str] = None) -> str:
        """
        Get the actual filename for a template and version.

        Args:
            template_name: Name of the template (without version suffix)
            version: Version string or None for latest version

        Returns:
            Actual filename with version
        """
        file_path = self._get_template_path(template_name, version)
        return file_path.name

    def load_template(self, template_name: str, version: Optional[str] = None) -> Template:
        """
        Load a template by name and version.

        Args:
            template_name: Name of the template (without version suffix)
            version: Version string (e.g., '1.0') or None for latest

        Returns:
            Jinja2 Template object
        """
        filename = self._get_template_filename(template_name, version)
        return self._get_env().get_template(filename)

    @staticmethod
    def _content_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _version_from_filename(filename: str) -> str:
        match = re.search(r"_(\d+\.\d+)\.j2$", filename)
        return match.group(1) if match else ""

    def _named_template_source(self, filename: str) -> tuple[str, str]:
        user_path = self.user_templates_dir / filename
        if user_path.is_file():
            return user_path.read_text(encoding="utf-8"), "user"
        default_path = self.default_templates_dir / filename
        if default_path.is_file():
            return default_path.read_text(encoding="utf-8"), "builtin"
        raise FileNotFoundError(f"Prompt Template dependency '{filename}' not found")

    def _template_revision(self, *, filename: str, content: str, source: str) -> str:
        """Hash one template plus all statically referenced Jinja templates."""

        resolved: dict[str, dict[str, str]] = {}

        def collect(current_name: str, current_content: str, current_source: str) -> None:
            if current_name in resolved:
                return
            resolved[current_name] = {
                "source": current_source,
                "content_sha256": self._content_sha256(current_content),
            }
            parsed = self._get_env().parse(current_content)
            for dependency_name in meta.find_referenced_templates(parsed) or ():
                if dependency_name is None:
                    continue
                dependency_content, dependency_source = self._named_template_source(dependency_name)
                collect(dependency_name, dependency_content, dependency_source)

        collect(filename, content, source)
        canonical = json.dumps(resolved, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return self._content_sha256(canonical)

    def _resolve_template_source(
        self,
        template_name: str,
        version: Optional[str],
    ) -> tuple[str, str, str, str]:
        runtime = find_runtime_template(self._agent_config, template_name, version)
        if runtime is not None:
            content, configured_version = runtime
            return content, f"{template_name}_runtime.j2", configured_version or str(version or ""), "runtime"

        path = self._get_template_path(template_name, version)
        source = "user" if path.parent == self.user_templates_dir else "builtin"
        return path.read_text(encoding="utf-8"), path.name, self._version_from_filename(path.name), source

    def get_template_identity(self, template_name: str, version: Optional[str] = None) -> dict[str, str]:
        """Return stable, non-secret provenance for the effective template."""

        content, filename, resolved_version, source = self._resolve_template_source(template_name, version)
        return self._template_identity_from_resolution(
            template_name=template_name,
            requested_version=version,
            content=content,
            filename=filename,
            resolved_version=resolved_version,
            source=source,
        )

    def _template_identity_from_resolution(
        self,
        *,
        template_name: str,
        requested_version: Optional[str],
        content: str,
        filename: str,
        resolved_version: str,
        source: str,
    ) -> dict[str, str]:
        return {
            "template_name": template_name,
            "requested_version": str(requested_version or ""),
            "resolved_version": resolved_version,
            "source": source,
            "content_sha256": self._content_sha256(content),
            "revision_sha256": self._template_revision(filename=filename, content=content, source=source),
        }

    def render_template(self, template_name: str, version: Optional[str] = None, **kwargs) -> str:
        """
        Render a template with the given variables.

        Args:
            template_name: Name of the template
            version: Version string (e.g., '1.0') or None for latest
            **kwargs: Variables to pass to the template

        Returns:
            Rendered template string
        """
        content, filename, resolved_version, source = self._resolve_template_source(template_name, version)
        captured = _captured_template_identities.get()
        if captured is not None:
            captured.append(
                self._template_identity_from_resolution(
                    template_name=template_name,
                    requested_version=version,
                    content=content,
                    filename=filename,
                    resolved_version=resolved_version,
                    source=source,
                )
            )
        # Render the exact source selected above. Loading again by logical
        # filename can replay a cached builtin after a same-name user override
        # appears, making provenance and rendered bytes disagree.
        template = self._get_env().from_string(content)
        return template.render(**kwargs)

    def get_raw_template(self, template_name: str, version: Optional[str] = None) -> str:
        """
        Get the raw template content without rendering.

        Args:
            template_name: Name of the template
            version: Version string (e.g., '1.0') or None for latest

        Returns:
            Raw template string
        """
        content, filename, resolved_version, source = self._resolve_template_source(template_name, version)
        captured = _captured_template_identities.get()
        if captured is not None:
            captured.append(
                self._template_identity_from_resolution(
                    template_name=template_name,
                    requested_version=version,
                    content=content,
                    filename=filename,
                    resolved_version=resolved_version,
                    source=source,
                )
            )
        return content

    def list_templates(self) -> List[str]:
        """
        List all available template names (without versions).

        Returns:
            List of template names
        """
        template_names = set()

        # Check user templates directory first
        if self.user_templates_dir.exists():
            for file_path in self.user_templates_dir.glob("*.j2"):
                match = re.match(r"(.+)_(\d+\.\d+)\.j2$", file_path.name)
                if match:
                    template_names.add(match.group(1))

        # Also check default templates directory
        for file_path in self.default_templates_dir.glob("*.j2"):
            match = re.match(r"(.+)_(\d+\.\d+)\.j2$", file_path.name)
            if match:
                template_names.add(match.group(1))

        return sorted(template_names)

    def list_template_versions(self, template_name: str) -> List[str]:
        """
        List all available versions for a specific template.

        Args:
            template_name: Name of the template

        Returns:
            List of version strings sorted by version number
        """
        versions = set()

        # Check user templates directory first
        pattern = f"{template_name}_*.j2"

        if self.user_templates_dir.exists():
            for file_path in self.user_templates_dir.glob(pattern):
                match = re.search(r"_(\d+\.\d+)\.j2$", file_path.name)
                if match:
                    versions.add(match.group(1))

        # Also check default templates directory for versions not in user directory
        for file_path in self.default_templates_dir.glob(pattern):
            match = re.search(r"_(\d+\.\d+)\.j2$", file_path.name)
            if match:
                version = match.group(1)
                # Only add if not already found in user directory
                user_file = self.user_templates_dir / f"{template_name}_{version}.j2"
                if not user_file.exists():
                    versions.add(version)

        # Sort versions naturally (1.0, 1.1, 2.0, etc.)
        def version_key(v):
            try:
                return tuple(map(int, v.split(".")))
            except BaseException:
                return (0, 0)

        return sorted(versions, key=version_key)

    def get_latest_version(self, template_name: str) -> str:
        """
        Get the latest version for a template.

        Args:
            template_name: Name of the template

        Returns:
            Latest version string
        """
        versions = self.list_template_versions(template_name)
        if not versions:
            raise FileNotFoundError(f"No versions found for template '{template_name}'")
        return versions[-1]

    def create_template_version(self, template_name: str, new_version: str, base_version: Optional[str] = None) -> None:
        """
        Create a new version of a template by copying from an existing version.

        Args:
            template_name: Name of the template
            new_version: New version string (e.g., '1.1')
            base_version: Version to copy from, or None for latest version
        """
        # Get source file
        if base_version is None:
            base_version = self.get_latest_version(template_name)

        source_path = self._get_template_path(template_name, base_version)

        # Create new file in user templates directory
        new_filename = f"{template_name}_{new_version}.j2"
        new_path = self.user_templates_dir / new_filename

        if new_path.exists():
            raise ValueError(f"Version '{new_version}' already exists for template '{template_name}'")

        # Ensure user templates directory exists
        self.user_templates_dir.mkdir(parents=True, exist_ok=True)

        # Copy content
        shutil.copy2(source_path, new_path)
        logger.info(f"Created {new_filename} based on {source_path.name}")

    def template_exists(self, template_name: str, version: Optional[str] = None) -> bool:
        """
        Check if a template exists.

        Args:
            template_name: Name of the template
            version: Version string or None for any version

        Returns:
            True if template exists
        """
        try:
            self._get_template_filename(template_name, version)
            return True
        except FileNotFoundError:
            return False

    def get_template_info(self, template_name: str) -> dict:
        """
        Get information about a template.

        Args:
            template_name: Name of the template

        Returns:
            Dictionary with template information
        """
        versions = self.list_template_versions(template_name)
        latest_version = versions[-1] if versions else None

        return {
            "name": template_name,
            "available_versions": versions,
            "latest_version": latest_version,
            "total_versions": len(versions),
        }

    def copy_to(
        self,
        src_name: str,
        target_name: str,
        target_version: str = "1.0",
        overwrite: bool = False,
    ) -> str:
        if not self.user_templates_dir.exists():
            self.user_templates_dir.mkdir(parents=True)

        target_path = self.user_templates_dir / f"{target_name}_{target_version}.j2"
        if overwrite or not target_path.exists():
            src_path = self._get_template_path(src_name)
            shutil.copy2(src_path, target_path)
        return str(target_path)


def get_prompt_manager(agent_config: Optional[Any] = None) -> "PromptManager":
    """
    Get a prompt manager instance for the given agent context.

    Resolution order:
    1. ``agent_config.prompt_manager`` if already attached
    2. A new ``PromptManager`` bound to ``agent_config`` (and its path_manager)
    3. Default ``PromptManager()`` (falls back to the path_manager ContextVar)

    Calling convention in prompt utility functions:

    * If a function renders exactly **one** template, call inline:
      ``get_prompt_manager(agent_config=agent_config).render_template(...)``
    * If a function renders **two or more** templates, bind a local first:
      ``pm = get_prompt_manager(agent_config=agent_config)``
      then reuse ``pm.render_template(...)`` at each call site.

    Both forms are functionally equivalent because the Jinja2 environment is
    cached on the class-level ``_env_cache``; this split is a readability
    convention only.

    Args:
        agent_config: Optional config object exposing ``prompt_manager`` or ``path_manager``.

    Returns:
        PromptManager instance
    """
    if agent_config is None:
        return PromptManager()

    config_pm = getattr(agent_config, "prompt_manager", None)
    if config_pm is not None:
        return config_pm

    return PromptManager(
        path_manager=getattr(agent_config, "path_manager", None),
        agent_config=agent_config,
    )


# Backward-compatible global instance.
# Prefer ``get_prompt_manager()`` for new code so that SaaS multi-tenant
# isolation is respected.
prompt_manager = PromptManager()
