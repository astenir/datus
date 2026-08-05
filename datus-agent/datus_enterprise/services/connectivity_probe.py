"""Shared one-shot connectivity probes for enterprise API surfaces."""

from __future__ import annotations

from typing import Any, Mapping

from datus.configuration.agent_config import DbConfig, load_model_config
from datus.models.base import LLMBaseModel
from datus.utils.exceptions import DatusException, ErrorCode


def probe_llm_connection(payload: Mapping[str, Any]) -> None:
    """Build a one-shot LLM client from raw config and send a tiny probe."""

    model_config = load_model_config(dict(payload))
    model_class_name = LLMBaseModel.MODEL_TYPE_MAP.get(model_config.type)
    if model_class_name is None:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Unsupported model type: {model_config.type}",
        )
    module = __import__(f"datus.models.{model_config.type}_model", fromlist=[model_class_name])
    model_class = getattr(module, model_class_name)
    client = model_class(model_config=model_config)
    client.generate("Hello")


def probe_datasource_connection(payload: Mapping[str, Any]) -> None:
    """Build a one-shot connector from raw config and run its connection probe."""

    from datus.tools.db_tools.db_manager import DBManager

    kwargs = dict(payload)
    kwargs.setdefault("name", "_probe_")
    db_config = DbConfig.filter_kwargs(DbConfig, kwargs)

    manager = DBManager({"_probe_": db_config})
    try:
        connection = manager.get_conn("_probe_")
        connection.test_connection()
    finally:
        manager.close()
