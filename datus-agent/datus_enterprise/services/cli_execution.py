"""Request-scoped connector helpers for downstream CLI execution."""

import asyncio
from dataclasses import dataclass
from typing import Callable, Optional, Type

from datus.tools.db_tools import db_manager as db_manager_module
from datus.tools.db_tools.db_manager import DBManager


@dataclass
class _SQLTaskRecord:
    task: asyncio.Task
    owner_user_id: Optional[str]


def request_scoped_db_manager(
    datasource_configs: dict,
    *,
    db_manager_type: Type[DBManager] = DBManager,
) -> tuple[DBManager, Optional[Callable[[], None]]]:
    if db_manager_module._factory is not None:
        return db_manager_module.db_manager_instance(datasource_configs), None
    db_manager = db_manager_type(datasource_configs)
    return db_manager, db_manager.close


def switch_connector_database(connector, database_name: str) -> None:
    catalog = getattr(connector, "catalog_name", "") or ""
    connector.switch_context(
        catalog_name=catalog,
        database_name=database_name,
    )
    try:
        connector.database_name = database_name
    except Exception:
        pass
