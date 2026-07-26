"""Enterprise datasource status and connection prewarm extensions."""

import time
from typing import List, Optional

from datus.api.models.downstream import DatasourceConnectionStatus
from datus.api.services.database_service import DatasourceService
from datus.configuration.agent_config import AgentConfig
from datus.tools.db_tools.db_manager import DBManager
from datus.utils.loggings import get_logger
from datus.utils.time_utils import now_utc_iso

logger = get_logger(__name__)
_TABLE_LIKE_VIEW_METHODS = ("get_views", "get_materialized_views")


class EnterpriseDatasourceService(DatasourceService):
    """Add cached status and prewarm behavior to the upstream datasource service."""

    def __init__(
        self,
        agent_config: Optional[AgentConfig] = None,
        db_manager: Optional[DBManager] = None,
    ):
        super().__init__(agent_config=agent_config, db_manager=db_manager)
        self._connection_status: dict[str, DatasourceConnectionStatus] = {}
        self._prewarm_in_progress: set[str] = set()

    def _get_table_like_names(
        self,
        connector,
        *,
        catalog_name: str | None = "",
        database_name: str | None = "",
        schema_name: str | None = "",
    ) -> List[str]:
        """Return tables and view-like objects in the legacy tables field."""

        names = [
            str(table_name).strip()
            for table_name in connector.get_tables(
                catalog_name=catalog_name or "",
                database_name=database_name or "",
                schema_name=schema_name or "",
            )
            if str(table_name).strip()
        ]
        for method_name in _TABLE_LIKE_VIEW_METHODS:
            method = getattr(connector, method_name, None)
            if not callable(method):
                continue
            try:
                names.extend(
                    str(table_name).strip()
                    for table_name in method(
                        catalog_name=catalog_name or "",
                        database_name=database_name or "",
                        schema_name=schema_name or "",
                    )
                    if str(table_name).strip()
                )
            except Exception as exc:
                logger.debug(
                    "%s unavailable on %s: %s",
                    method_name,
                    getattr(connector, "dialect", "unknown"),
                    exc,
                )
        return sorted(set(names))

    def _should_enumerate_databases(self, datasource: str) -> bool:
        config = getattr(getattr(self.agent_config, "services", None), "datasources", {}).get(datasource)
        return bool(getattr(config, "enumerate_databases", False))

    def _record_connection_status(
        self,
        datasource_id: str,
        status: str,
        *,
        started_at: float | None = None,
        error_message: str | None = None,
    ) -> None:
        if not datasource_id:
            return
        latency_ms = None
        if started_at is not None:
            latency_ms = max(0, int((time.perf_counter() - started_at) * 1000))
        self._connection_status[datasource_id] = DatasourceConnectionStatus(
            datasource_id=datasource_id,
            status=status,
            last_checked=now_utc_iso(),
            latency_ms=latency_ms,
            error_message=error_message,
            cached=True,
        )

    def record_datasource_timeout(self, datasource_id: str) -> None:
        """Record a route-level timeout for datasource operations."""

        self._record_connection_status(datasource_id, "timeout", error_message="Datasource query timed out")

    def datasource_statuses(self, datasource_ids: List[str] | None = None) -> List[DatasourceConnectionStatus]:
        """Return cached datasource statuses without opening any database connection."""

        configured = self.agent_config.datasource_configs if self.agent_config else {}
        requested = datasource_ids if datasource_ids is not None else list(configured)
        statuses: List[DatasourceConnectionStatus] = []
        for datasource_id in requested:
            cached = self._connection_status.get(datasource_id)
            if cached is not None:
                statuses.append(cached)
                continue
            statuses.append(
                DatasourceConnectionStatus(
                    datasource_id=datasource_id,
                    status="unknown",
                    last_checked=None,
                    latency_ms=None,
                    error_message=None,
                    cached=False,
                )
            )
        return statuses

    def start_prewarm(self, datasource_id: str) -> bool:
        """Mark a datasource as prewarming and reject duplicate schedules."""

        if datasource_id in self._prewarm_in_progress:
            return False
        self._prewarm_in_progress.add(datasource_id)
        self._record_connection_status(datasource_id, "connecting")
        return True

    def prewarm_datasource(self, datasource_id: str) -> None:
        """Open and test the selected datasource in the background."""

        started_at = time.perf_counter()
        try:
            connections = self.db_manager.get_connections(datasource_id)
            for connector in connections.values():
                connect = getattr(connector, "connect", None)
                if callable(connect):
                    connect()
                connector.test_connection()
            self._record_connection_status(datasource_id, "connected", started_at=started_at)
        except Exception as exc:
            self._record_connection_status(datasource_id, "failed", started_at=started_at, error_message=str(exc))
            logger.warning("Datasource prewarm failed for %s: %s", datasource_id, exc)
        finally:
            self._prewarm_in_progress.discard(datasource_id)
