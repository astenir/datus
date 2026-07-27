# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Engine binding lifecycle: lazy import, connections wiring, mtime reload."""

from __future__ import annotations

import glob
import os
import tempfile
import threading
import weakref
from typing import Any, Optional

import yaml

from datus_semantic_core.exceptions import SemanticCoreException

from datus_semantic_osi_engine.config import OSIEngineConfig
from datus_semantic_osi_engine.dialects import normalize_dialect

_INSTALL_HINT = (
    "datus-osi-engine is not installed; "
    "pip install 'datus-semantic-osi-engine[engine]'"
)


def _unlink_quietly(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def resolve_model_file(config: OSIEngineConfig) -> str:
    """The OSI model file to load: explicit semantic_model_path, else the sole
    model file in semantic_models_path (the Datus directory convention).

    Raises SemanticCoreException when nothing resolves, or when a directory
    holds several models (the engine loads exactly one).
    """
    if config.semantic_model_path:
        return config.semantic_model_path
    models_dir = config.semantic_models_path
    if models_dir:
        candidates = sorted(
            path
            for ext in ("*.yaml", "*.yml", "*.json")
            for path in glob.glob(os.path.join(models_dir, ext))
        )
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise SemanticCoreException(
                f"no OSI model file (*.yaml/*.yml/*.json) in {models_dir!r}"
            )
        raise SemanticCoreException(
            f"{len(candidates)} model files in {models_dir!r}; "
            "set semantic_model_path to select one"
        )
    raise SemanticCoreException(
        "osi_engine adapter requires semantic_model_path (an OSI model file) "
        "or semantic_models_path (a directory containing one)"
    )


def load_binding() -> Any:
    """Import the datus-osi-engine bindings, failing with an install hint."""
    try:
        import datus_osi_engine
    except ImportError as exc:  # pragma: no cover - exercised via fake absence
        raise SemanticCoreException(_INSTALL_HINT) from exc
    return datus_osi_engine


class EngineHandle:
    """One engine per adapter instance, rebuilt when the model file changes.

    Every access re-stats ``semantic_model_path`` (one os.stat, negligible
    next to the call it guards) so edits to the OSI YAML are picked up
    without restarting the process.
    """

    def __init__(self, config: OSIEngineConfig):
        self._config = config
        self._lock = threading.Lock()
        self._engine: Optional[Any] = None
        self._model_mtime: Optional[float] = None
        self._connections_file: Optional[str] = None

    @property
    def profile_name(self) -> Optional[str]:
        """The connection profile to execute on, when one is configured.

        Precedence mirrors _resolve_connections: an explicit connections_path
        is authoritative over db_config, so it is checked first — otherwise
        the name here (from db_config) would not exist in the file actually
        used.
        """
        config = self._config
        if config.connection:
            return config.connection
        if config.connections_path:
            # A bare `datasource` name is looked up in the connections file;
            # None lets the engine pick the file's default profile.
            return config.datasource
        if config.db_config:
            return config.datasource or "default"
        return None

    def model_file(self) -> str:
        """The resolved OSI model file path (raises if unresolvable)."""
        return resolve_model_file(self._config)

    def get(self) -> Any:
        config = self._config
        model_file = resolve_model_file(config)
        try:
            mtime = os.path.getmtime(model_file)
        except OSError as exc:
            raise SemanticCoreException(
                f"cannot read semantic model {model_file!r}: {exc}"
            ) from exc
        with self._lock:
            if self._engine is None or mtime != self._model_mtime:
                self._engine = self._build(config, model_file)
                self._model_mtime = mtime
            return self._engine

    def _build(self, config: OSIEngineConfig, model_file: str) -> Any:
        binding = load_binding()
        try:
            return binding.Engine(
                model_path=model_file,
                connections_path=self._resolve_connections(config),
                pool_size=config.pool_size,
            )
        except binding.OsiError as exc:
            raise SemanticCoreException(
                f"osi-engine failed to load model {model_file!r}: {exc}"
            ) from exc

    def _resolve_connections(self, config: OSIEngineConfig) -> Optional[str]:
        if config.connections_path:
            return config.connections_path
        if not config.db_config:
            return None
        if self._connections_file is None:
            self._connections_file = self._write_connections_file(config)
        return self._connections_file

    def _write_connections_file(self, config: OSIEngineConfig) -> str:
        """Materialize `db_config` as a `datasources:` YAML the engine reads.

        The engine's connections vocabulary IS the agent.yml datasource
        vocabulary, so fields pass through verbatim — only the `type` alias
        is normalized (the engine derives the dialect from it) and the entry
        is marked default so connection-less execution lands on it.
        """
        entry = dict(config.db_config or {})
        dialect = normalize_dialect(entry.get("type"))
        if dialect:
            entry["type"] = dialect
        entry.setdefault("default", True)
        payload = {"datasources": {self.profile_name or "default": entry}}
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="osi-connections-",
            delete=False,
        )
        with handle:
            yaml.safe_dump(payload, handle, default_flow_style=False)
        # Tie the temp file's lifetime to this handle so it doesn't leak for
        # the process lifetime (relevant when adapters are created per-request).
        weakref.finalize(self, _unlink_quietly, handle.name)
        return handle.name
