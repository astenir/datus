import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple

import logging
import os

import yaml

from datus_semantic_core import BaseSemanticAdapter
from datus_semantic_core.authoring import MetricMutationResult, MetricSource
from datus_semantic_core.models import SemanticValidationError
from datus_semantic_metricflow.authoring import MetricFlowMetricAuthor
from datus_semantic_metricflow.config import MetricFlowConfig
from datus_semantic_metricflow.models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    ValidationIssue,
    ValidationResult,
)

# Import MetricFlow API
from metricflow.api.metricflow_client import MetricFlowClient
from metricflow.configuration.datus_config_handler import DatusConfigHandler
from metricflow.configuration.dict_config_handler import (
    DictConfigHandler,
    build_config_dict_from_db_params,
)
from metricflow.naming.linkable_spec_name import StructuredLinkableSpecName
from metricflow.references import MetricReference, TimeDimensionReference

try:
    from metricflow.configuration.dict_config_handler import build_config_dict_from_datus_datasource
except ImportError:
    build_config_dict_from_datus_datasource = None

logger = logging.getLogger(__name__)


class MetricFlowSemanticValidationException(Exception):
    """A deterministic MetricFlow query validation rejection with structured payload."""

    def __init__(self, payload: SemanticValidationError):
        self.payload = payload
        super().__init__(payload.message or "semantic validation error")


class MetricFlowAdapter(BaseSemanticAdapter):
    """
    MetricFlow semantic layer adapter.

    Integrates with MetricFlow CLI to provide metric querying capabilities.
    """

    def __init__(self, config: MetricFlowConfig):
        super().__init__(config, service_type="metricflow")
        self.datasource = config.datasource
        self.timeout = config.timeout
        self._client_init_error: Optional[Exception] = None
        self._client_initialized = False

        logger.info(f"Initializing MetricFlowAdapter for datasource: {self.datasource}")

        try:
            # Import MetricFlow utilities
            from metricflow.configuration.constants import CONFIG_DWH_SCHEMA
            from metricflow.sql_clients.sql_utils import make_sql_client_from_config

            # Initialize config handler: dict-based or file-based
            if config.db_config:
                model_path = self._resolve_model_path(config)
                config_dict = self._build_metricflow_config_dict(config.db_config, model_path)
                self._config_handler = DictConfigHandler(config_dict)
                logger.info("Using DictConfigHandler (in-memory config, no file read)")
            else:
                config_path = getattr(config, "config_path", None)
                self._config_handler = DatusConfigHandler(
                    namespace=self.datasource, config_path=config_path
                )
                logger.info("Using DatusConfigHandler (reading agent.yml from disk)")

            # Build client components using the config handler
            sql_client = make_sql_client_from_config(self._config_handler)
            schema = self._config_handler.get_value(CONFIG_DWH_SCHEMA)
            self.client = SimpleNamespace(sql_client=sql_client, system_schema=schema)
            logger.info(
                "MetricFlowAdapter initialized; MetricFlowClient will load semantic YAML on first use"
            )

        except Exception as e:
            logger.error(f"Failed to initialize MetricFlowAdapter: {e}", exc_info=True)
            raise

    def _ensure_client_ready(self) -> MetricFlowClient:
        """Build the MetricFlowClient lazily so bad YAML does not break adapter startup."""
        if getattr(self, "_client_initialized", True):
            return self.client

        try:
            user_configured_model = self._build_user_configured_model_from_config(
                self._config_handler
            )
            self.client = MetricFlowClient(
                sql_client=self.client.sql_client,
                user_configured_model=user_configured_model,
                system_schema=self.client.system_schema,
            )
            self._client_initialized = True
            self._client_init_error = None
            logger.info("MetricFlowClient initialized successfully")
            return self.client
        except Exception as e:
            self._client_init_error = e
            logger.warning(
                "MetricFlowClient initialization deferred until semantic configuration is valid: %s",
                e,
            )
            logger.debug("Deferred MetricFlowClient initialization details", exc_info=True)
            raise RuntimeError(
                "MetricFlow semantic configuration is invalid. "
                "Run validate_semantic to inspect YAML errors before listing or querying metrics."
            ) from e

    @staticmethod
    def _resolve_model_path(config: MetricFlowConfig) -> str:
        """Resolve semantic models path from config."""

        if config.semantic_models_path:
            path = Path(config.semantic_models_path)
            path.mkdir(parents=True, exist_ok=True)
            return str(path)

        agent_home = config.agent_home or "~/.datus"
        path = Path(agent_home).expanduser().resolve() / "semantic_models" / config.datasource
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @staticmethod
    def _build_metricflow_config_dict(db_config: dict, model_path: str) -> dict:
        if build_config_dict_from_datus_datasource is not None:
            return build_config_dict_from_datus_datasource(db_config, model_path=model_path)

        return MetricFlowAdapter._build_metricflow_config_dict_legacy(db_config, model_path)

    @staticmethod
    def _build_metricflow_config_dict_legacy(db_config: dict, model_path: str) -> dict:
        kwargs = {
            "db_type": db_config.get("type", ""),
            "host": db_config.get("host", ""),
            "port": str(db_config.get("port", "")),
            "username": db_config.get("username", ""),
            "password": db_config.get("password", ""),
            "database": db_config.get("database") or db_config.get("database_name", ""),
            "schema": db_config.get("schema")
            or db_config.get("db_schema")
            or db_config.get("schema_name", ""),
            "uri": db_config.get("uri", ""),
            "warehouse": db_config.get("warehouse", ""),
            "account": db_config.get("account", ""),
            "project_id": db_config.get("project_id", ""),
            "model_path": model_path,
        }
        sslmode = db_config.get("sslmode")
        if sslmode and MetricFlowAdapter._build_config_supports_kwarg("sslmode"):
            kwargs["sslmode"] = sslmode
        catalog = db_config.get("catalog") or db_config.get("catalog_name")
        if catalog and MetricFlowAdapter._build_config_supports_kwarg("catalog"):
            kwargs["catalog"] = str(catalog)
        unsupported_keys = []
        for optional_key in ("role", "private_key", "private_key_file", "private_key_file_pwd"):
            value = db_config.get(optional_key)
            if value is None or value == "":
                continue
            if MetricFlowAdapter._build_config_supports_kwarg(optional_key):
                kwargs[optional_key] = str(value)
            else:
                unsupported_keys.append(optional_key)
        if unsupported_keys:
            unsupported = ", ".join(unsupported_keys)
            raise RuntimeError(
                "Installed datus-metricflow does not support Snowflake config fields: "
                f"{unsupported}. Install the matching datus-metricflow build before using Snowflake metrics."
            )
        return build_config_dict_from_db_params(**kwargs)

    @staticmethod
    def _build_config_supports_kwarg(name: str) -> bool:
        signature = inspect.signature(build_config_dict_from_db_params)
        return name in signature.parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )

    @staticmethod
    def _collect_model_file_paths(model_path: str) -> List[str]:
        """Collect MetricFlow YAML files from the configured model path.

        MetricFlow's directory collector skips files ignored by the nearest
        .gitignore. Datus stores generated semantic models under project-local
        subject/ directories, which are intentionally gitignored, so the adapter
        must treat the configured semantic_models_path as authoritative.
        """
        config_file_paths: List[str] = []
        for root, dirs, files in os.walk(model_path):
            dirs[:] = [directory for directory in dirs if not directory.startswith(".")]
            for file_name in files:
                if file_name.startswith("."):
                    continue
                if Path(file_name).suffix.lower() not in {".yml", ".yaml"}:
                    continue
                config_file_paths.append(os.path.join(root, file_name))
        return sorted(config_file_paths)

    @classmethod
    def _model_build_result_from_config(cls, handler, raise_issues_as_exceptions: bool = True):
        from metricflow.engine.utils import path_to_models
        from metricflow.model.parsing.dir_to_model import parse_yaml_file_paths_to_model

        model_path = path_to_models(handler=handler)
        file_paths = cls._collect_model_file_paths(model_path)
        return parse_yaml_file_paths_to_model(
            file_paths,
            raise_issues_as_exceptions=raise_issues_as_exceptions,
        )

    @classmethod
    def _build_user_configured_model_from_config(cls, handler):
        return cls._model_build_result_from_config(handler).model

    # Semantic Model Interface

    def get_semantic_model(
        self,
        table_name: str,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ):
        """MetricFlow doesn't directly expose semantic models."""
        return None

    def list_semantic_models(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ):
        """MetricFlow uses semantic models internally."""
        return []

    @staticmethod
    def _metricflow_metadata_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        to_string = getattr(value, "to_string", None)
        if callable(to_string):
            return to_string()

        raw_value = getattr(value, "value", None)
        if raw_value is not None:
            return MetricFlowAdapter._metricflow_metadata_value(raw_value)

        name = getattr(value, "name", None)
        if isinstance(name, str):
            return name

        if isinstance(value, dict):
            return {
                str(key): MetricFlowAdapter._metricflow_metadata_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [MetricFlowAdapter._metricflow_metadata_value(item) for item in value]

        return str(value)

    @staticmethod
    def _metricflow_input_measure_name(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        name = getattr(value, "name", None)
        if name is not None:
            return str(name)
        return None

    @staticmethod
    def _subject_path_from_tags(tags: Any) -> Optional[List[str]]:
        if not isinstance(tags, list):
            return None

        for raw_tag in tags:
            if not isinstance(raw_tag, str):
                continue
            tag = raw_tag.strip()
            if not tag:
                continue
            if tag.startswith("subject_tree:"):
                tag = tag.split(":", 1)[1].strip()
                path = [part.strip() for part in tag.split("/") if part.strip()]
                if path:
                    return path
        return None

    @classmethod
    def _metric_path_metadata_from_yaml_file(cls, file_path: str) -> Dict[str, List[str]]:
        metric_paths: Dict[str, List[str]] = {}
        try:
            with open(file_path, encoding="utf-8") as handle:
                docs = yaml.safe_load_all(handle)
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    metric = doc.get("metric")
                    if not isinstance(metric, dict):
                        continue
                    name = metric.get("name")
                    if not isinstance(name, str) or not name.strip():
                        continue
                    locked_metadata = metric.get("locked_metadata")
                    if not isinstance(locked_metadata, dict):
                        continue
                    path = cls._subject_path_from_tags(locked_metadata.get("tags"))
                    if path:
                        metric_paths[name.strip()] = path
        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping metric path metadata file %s: %s", file_path, exc)
        return metric_paths

    def _metric_path_metadata_by_name(self) -> Dict[str, List[str]]:
        try:
            from metricflow.engine.utils import path_to_models

            model_path = path_to_models(handler=self._config_handler)
            file_paths = self._collect_model_file_paths(model_path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Unable to collect metric path metadata: %s", exc)
            return {}

        metric_paths: Dict[str, List[str]] = {}
        for file_path in file_paths:
            metric_paths.update(self._metric_path_metadata_from_yaml_file(file_path))
        return metric_paths

    @classmethod
    def _metricflow_input_metric_metadata(cls, value: Any) -> Dict[str, Any]:
        name = getattr(value, "name", None) or getattr(value, "element_name", None)
        if not name:
            return {}

        item: Dict[str, Any] = {"name": str(name)}
        for field in ("alias", "offset_window", "offset_to_grain"):
            field_value = getattr(value, field, None)
            if field_value is not None:
                item[field] = cls._metricflow_metadata_value(field_value)

        constraint = getattr(value, "constraint", None)
        if constraint is not None:
            where = getattr(constraint, "where", None)
            item["constraint"] = cls._metricflow_metadata_value(where or constraint)

        return item

    @classmethod
    def _metric_metadata(cls, metric) -> Dict[str, Any]:
        """Expose MetricFlow type_params that are needed by metric-first agents."""
        type_params = getattr(metric, "type_params", None)
        if type_params is None:
            return {}

        metadata: Dict[str, Any] = {}

        expr = getattr(type_params, "expr", None)
        if expr:
            metadata["expr"] = expr

        input_metrics = getattr(metric, "input_metrics", None)
        if input_metrics is None:
            input_metrics = getattr(type_params, "metrics", None)
        inputs = [
            item
            for item in (
                cls._metricflow_input_metric_metadata(input_metric)
                for input_metric in (input_metrics or [])
            )
            if item
        ]
        if inputs:
            metadata["inputs"] = inputs
            offset_window = next(
                (item.get("offset_window") for item in inputs if item.get("offset_window")), None
            )
            if offset_window:
                metadata["offset_window"] = offset_window

        window = getattr(type_params, "window", None)
        if window is not None:
            metadata["window"] = cls._metricflow_metadata_value(window)

        grain_to_date = getattr(type_params, "grain_to_date", None)
        if grain_to_date is not None:
            metadata["grain_to_date"] = cls._metricflow_metadata_value(grain_to_date)

        for field in ("measure", "numerator", "denominator"):
            field_name = cls._metricflow_input_measure_name(getattr(type_params, field, None))
            if field_name:
                metadata[field] = field_name

        if metadata:
            metric_kind = cls._metricflow_metadata_value(getattr(metric, "type", None))
            if metric_kind:
                metadata["metric_kind"] = metric_kind

        return metadata

    # Metrics Interface

    async def list_metrics(
        self,
        path: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MetricDefinition]:
        """
        List available metrics using MetricFlow client.

        Args:
            path: Optional subject area filter
            limit: Maximum metrics to return
            offset: Number to skip

        Returns:
            List of metric definitions
        """
        client = self._ensure_client_ready()

        # Get full metric objects directly from semantic_model
        metric_semantics = client.semantic_model.metric_semantics
        metric_refs = metric_semantics.metric_references
        full_metrics = metric_semantics.get_metrics(metric_refs)
        path_by_name = self._metric_path_metadata_by_name()

        # Convert to MetricDefinition list
        metrics = []
        for metric in full_metrics:
            # Get dimensions for this metric
            dimensions = client.engine.simple_dimensions_for_metrics([metric.name])
            metrics.append(
                MetricDefinition(
                    name=metric.name,
                    description=metric.description,
                    type=metric.type,
                    dimensions=[d.name for d in dimensions],
                    measures=[m.name for m in metric.input_measures],
                    path=path_by_name.get(metric.name),
                    metadata=self._metric_metadata(metric),
                )
            )

        if path:
            metrics = [m for m in metrics if m.path and m.path[: len(path)] == path]

        return metrics[offset : offset + limit]

    async def get_dimensions(
        self,
        metric_name: str,
        path: Optional[List[str]] = None,
    ) -> List[DimensionInfo]:
        """
        Get dimensions for a metric using MetricFlow client.

        Args:
            metric_name: Name of the metric
            path: Optional subject area filter

        Returns:
            List of DimensionInfo objects containing name and description
        """
        client = self._ensure_client_ready()

        # Get dimensions from client (returns List[Dimension])
        dimensions = client.list_dimensions(metric_names=[metric_name])

        # Convert to DimensionInfo objects
        return [DimensionInfo(name=d.name, description=d.description) for d in dimensions]

    @staticmethod
    def _normalize_time_granularity(granularity: Optional[str]) -> Optional[str]:
        if granularity is None:
            return None
        value = str(granularity).strip().lower()
        return value or None

    _TIME_GRAINS = ("day", "week", "month", "quarter", "year")

    @classmethod
    def _time_grain_from_text(cls, value: Any) -> Optional[str]:
        text = str(cls._metricflow_metadata_value(value) or "").lower()
        for grain in cls._TIME_GRAINS:
            if grain in text:
                return grain
        return None

    @staticmethod
    def _is_metric_time_dimension(name: str) -> bool:
        parsed = StructuredLinkableSpecName.from_name(str(name).lower())
        return parsed.element_name == "metric_time"

    @classmethod
    def _metric_type_name(cls, metric: Any) -> str:
        value = cls._metricflow_metadata_value(getattr(metric, "type", None))
        return str(value or "").lower()

    @staticmethod
    def _metric_name(metric: Any) -> str:
        name = getattr(metric, "name", None) or getattr(metric, "element_name", None)
        return str(name or "").strip()

    @classmethod
    def _metric_input_metrics(cls, metric: Any) -> List[Any]:
        input_metrics = getattr(metric, "input_metrics", None)
        if input_metrics is not None:
            return list(input_metrics or [])
        type_params = getattr(metric, "type_params", None)
        return list(getattr(type_params, "metrics", None) or [])

    @classmethod
    def _cumulative_query_grain(cls, client, metric_name: str) -> Optional[str]:
        try:
            solver = client.engine._query_parser._time_granularity_solver
            local_dimension_granularity_range = solver.local_dimension_granularity_range
            if not callable(local_dimension_granularity_range):
                raise AttributeError("local_dimension_granularity_range is not callable")
        except AttributeError as exc:
            raise MetricFlowSemanticValidationException(
                SemanticValidationError(
                    code="metricflow_time_grain_resolver_unavailable",
                    metrics=[metric_name],
                    message=(
                        "Installed datus-metricflow does not expose the time-grain "
                        "resolver required to query cumulative metrics safely. "
                        "Install a compatible datus-metricflow build before querying "
                        f"metric `{metric_name}`."
                    ),
                )
            ) from exc

        try:
            _, query_granularity = local_dimension_granularity_range(
                metric_references=[MetricReference(element_name=metric_name)],
                local_time_dimension_reference=TimeDimensionReference(element_name="metric_time"),
            )
        except Exception as exc:
            raise MetricFlowSemanticValidationException(
                SemanticValidationError(
                    code="metricflow_time_grain_resolution_failed",
                    metrics=[metric_name],
                    message=(
                        "Failed to resolve the metric_time grain required to query "
                        f"cumulative metric `{metric_name}`: {exc}"
                    ),
                )
            ) from exc
        grain = cls._time_grain_from_text(query_granularity)
        if not grain:
            raise MetricFlowSemanticValidationException(
                SemanticValidationError(
                    code="metricflow_time_grain_resolution_failed",
                    metrics=[metric_name],
                    message=(
                        "MetricFlow returned an unsupported metric_time grain for "
                        f"cumulative metric `{metric_name}`: {query_granularity}"
                    ),
                )
            )
        return grain

    @classmethod
    def _metric_catalog_for_query(cls, client, metrics: List[str]) -> Dict[str, Any]:
        try:
            metric_semantics = client.semantic_model.metric_semantics
            metric_refs = getattr(metric_semantics, "metric_references", None)
            if not isinstance(metric_refs, (list, tuple)):
                metric_refs = [MetricReference(element_name=metric) for metric in metrics]
            full_metrics = client.semantic_model.metric_semantics.get_metrics(metric_refs)
        except Exception:
            return {}
        if not isinstance(full_metrics, (list, tuple)):
            return {}
        return {name: metric for metric in full_metrics if (name := cls._metric_name(metric))}

    @classmethod
    def _metric_has_offset_dependency(
        cls,
        metric: Any,
        catalog: Dict[str, Any],
        seen_metrics: Optional[Set[str]] = None,
    ) -> bool:
        for input_metric in cls._metric_input_metrics(metric):
            if getattr(input_metric, "offset_window", None) or getattr(
                input_metric, "offset_to_grain", None
            ):
                return True

        seen_metrics = seen_metrics or set()
        metric_name = cls._metric_name(metric)
        if not metric_name or metric_name in seen_metrics:
            return False
        seen_metrics.add(metric_name)

        for input_metric in cls._metric_input_metrics(metric):
            referenced_name = str(getattr(input_metric, "name", "") or "").strip()
            referenced = catalog.get(referenced_name)
            if referenced is not None and cls._metric_has_offset_dependency(
                referenced, catalog, seen_metrics
            ):
                return True
        return False

    @classmethod
    def _metric_requires_time_dimension(cls, metric: Any, catalog: Dict[str, Any]) -> bool:
        type_params = getattr(metric, "type_params", None)
        if cls._metric_type_name(metric) == "cumulative":
            return bool(
                getattr(type_params, "window", None) or getattr(type_params, "grain_to_date", None)
            )
        return cls._metric_has_offset_dependency(metric, catalog)

    @classmethod
    def _static_required_grains(
        cls,
        metric: Any,
        catalog: Optional[Dict[str, Any]] = None,
        seen_metrics: Optional[Set[str]] = None,
    ) -> Set[str]:
        type_params = getattr(metric, "type_params", None)
        grains: Set[str] = set()
        if cls._metric_type_name(metric) != "cumulative":
            for source in (
                getattr(type_params, "grain_to_date", None),
                getattr(type_params, "window", None),
                getattr(metric, "grain_to_date", None),
                getattr(metric, "window", None),
            ):
                grain = cls._time_grain_from_text(source)
                if grain:
                    grains.add(grain)

        for input_metric in cls._metric_input_metrics(metric):
            for source in (
                getattr(input_metric, "offset_window", None),
                getattr(input_metric, "offset_to_grain", None),
            ):
                grain = cls._time_grain_from_text(source)
                if grain:
                    grains.add(grain)

        catalog = catalog or {}
        seen_metrics = seen_metrics or set()
        metric_name = cls._metric_name(metric)
        if not metric_name or metric_name in seen_metrics:
            return grains
        seen_metrics.add(metric_name)

        for input_metric in cls._metric_input_metrics(metric):
            referenced_name = str(getattr(input_metric, "name", "") or "").strip()
            referenced = catalog.get(referenced_name)
            if referenced is not None:
                grains.update(cls._static_required_grains(referenced, catalog, seen_metrics))
        return grains

    @classmethod
    def _ensure_time_grouping(
        cls,
        client,
        metrics: List[str],
        dimensions: Optional[List[str]],
        time_granularity: Optional[str],
    ) -> Tuple[List[str], Optional[str]]:
        dims = list(dimensions or [])
        if any(cls._is_metric_time_dimension(dimension) for dimension in dims):
            return dims, time_granularity

        catalog = cls._metric_catalog_for_query(client, metrics)
        if not catalog:
            return dims, time_granularity

        required_metrics: List[str] = []
        required_grains: Dict[str, List[str]] = {}
        for name in metrics:
            metric = catalog.get(name)
            if metric is None or not cls._metric_requires_time_dimension(metric, catalog):
                continue
            required_metrics.append(name)
            grains = cls._static_required_grains(metric, catalog)
            if cls._metric_type_name(metric) == "cumulative":
                cumulative_grain = cls._cumulative_query_grain(client, name)
                if cumulative_grain:
                    grains.add(cumulative_grain)
            for grain in grains:
                required_grains.setdefault(grain, []).append(name)

        if not required_metrics:
            return dims, time_granularity
        if len(required_grains) > 1:
            details = ", ".join(
                f"{grain}: {', '.join(names)}" for grain, names in sorted(required_grains.items())
            )
            raise MetricFlowSemanticValidationException(
                SemanticValidationError(
                    code="metric_time_grain_conflict",
                    metrics=required_metrics,
                    message=(
                        "Requested metrics require incompatible metric_time grains "
                        f"({details}). Query compatible metric groups separately."
                    ),
                )
            )

        grain = next(iter(required_grains), None) or time_granularity
        dims.append(f"metric_time__{grain}" if grain else "metric_time")
        return dims, time_granularity or grain

    @staticmethod
    def _is_query_validation_error(exc: BaseException) -> bool:
        return any(
            "InvalidQuery" in klass.__name__ or "UnableToSatisfyQuery" in klass.__name__
            for klass in type(exc).__mro__
        )

    @classmethod
    def _semantic_validation_error_from(
        cls, exc: BaseException, metrics: List[str]
    ) -> Optional[SemanticValidationError]:
        if not cls._is_query_validation_error(exc):
            return None
        text = str(exc)
        lowered = text.lower()
        code = "validation_error"
        required_dimensions: List[str] = []
        required_grain: Optional[str] = None
        if "granularity" in lowered and "must be" in lowered:
            code = "time_grain_required"
            required_grain = cls._time_grain_from_text(lowered.split("must be", 1)[1])
            if required_grain:
                required_dimensions = [f"metric_time__{required_grain}"]
        elif "metric_time" in lowered and ("offset" in lowered or "derived" in lowered):
            code = "offset_requires_metric_time"
            required_dimensions = ["metric_time"]
        elif "metric_time" in lowered and ("cumulative" in lowered or "accumulat" in lowered):
            code = "cumulative_requires_metric_time"
            required_dimensions = ["metric_time"]

        suggested = None
        if required_dimensions or required_grain:
            suggested = {
                "dimensions": required_dimensions,
                "time_granularity": required_grain,
            }
        return SemanticValidationError(
            code=code,
            metrics=list(metrics),
            required_dimensions=required_dimensions,
            required_time_granularity=required_grain,
            suggested_retry=suggested,
            message=text,
        )

    @staticmethod
    def _time_dimension_names_for_metrics(client, metrics: List[str]) -> Set[str]:
        """Return queryable time dimension names for the metric set.

        MetricFlow's public ``Dimension`` dataclass only exposes name and
        description. For canonicalization we inspect the internal linkable specs
        and use their type via the presence of ``time_granularity``.
        """
        try:
            metric_refs = [MetricReference(element_name=metric) for metric in metrics]
            specs = client.semantic_model.metric_semantics.element_specs_for_metrics(metric_refs)
        except Exception:
            return set()

        names: Set[str] = set()
        for spec in specs:
            if getattr(spec, "time_granularity", None) is None:
                continue

            element_name = getattr(spec, "element_name", None)
            if isinstance(element_name, str) and element_name:
                names.add(element_name.lower())

            qualified_name = getattr(spec, "qualified_name", None)
            if isinstance(qualified_name, str) and qualified_name:
                parsed = StructuredLinkableSpecName.from_name(qualified_name.lower())
                names.add(parsed.qualified_name_without_granularity)
                names.add(parsed.element_name)

            identifier_links = getattr(spec, "identifier_links", ()) or ()
            identifier_names = []
            for identifier in identifier_links:
                identifier_name = getattr(identifier, "element_name", None)
                if isinstance(identifier_name, str) and identifier_name:
                    identifier_names.append(identifier_name.lower())
            if identifier_names and isinstance(element_name, str) and element_name:
                names.add("__".join(identifier_names + [element_name.lower()]))

        return names

    @staticmethod
    def _is_known_time_dimension_name(name: str, time_dimension_names: Set[str]) -> bool:
        if not time_dimension_names:
            return False

        parsed = StructuredLinkableSpecName.from_name(name.lower())
        return (
            parsed.element_name in time_dimension_names
            or parsed.qualified_name_without_granularity in time_dimension_names
            or parsed.qualified_name in time_dimension_names
        )

    @classmethod
    def _canonicalize_time_query_params(
        cls,
        client,
        metrics: List[str],
        dimensions: Optional[List[str]],
        order_by: Optional[List[str]],
        granularity: Optional[str],
    ) -> Tuple[List[str], Optional[List[str]]]:
        query_dimensions = list(dimensions) if dimensions else []
        order_list = [o for o in (order_by or []) if o and o != "null"] or None

        normalized_granularity = cls._normalize_time_granularity(granularity)
        if not normalized_granularity:
            return query_dimensions, order_list

        metric_time_dimension = f"metric_time__{normalized_granularity}"
        time_dimension_names = cls._time_dimension_names_for_metrics(client, metrics)
        canonical_dimensions = []
        for dimension in query_dimensions:
            parsed = StructuredLinkableSpecName.from_name(dimension.lower())
            is_metric_time = parsed.element_name == "metric_time"
            is_time_dimension = cls._is_known_time_dimension_name(dimension, time_dimension_names)
            if is_metric_time or is_time_dimension:
                continue
            canonical_dimensions.append(dimension)

        if metric_time_dimension not in canonical_dimensions:
            canonical_dimensions.append(metric_time_dimension)

        if not order_list:
            return canonical_dimensions, None

        canonical_order = []
        for order_item in order_list:
            descending = order_item.startswith("-")
            order_name = order_item[1:] if descending else order_item
            parsed = StructuredLinkableSpecName.from_name(order_name.lower())
            is_metric_time = parsed.element_name == "metric_time"
            is_time_dimension = cls._is_known_time_dimension_name(order_name, time_dimension_names)
            if is_metric_time or is_time_dimension:
                order_name = metric_time_dimension

            canonical_item = f"-{order_name}" if descending else order_name
            if canonical_item not in canonical_order:
                canonical_order.append(canonical_item)

        return canonical_dimensions, canonical_order

    async def query_metrics(
        self,
        metrics: List[str],
        dimensions: List[str] = [],
        path: Optional[List[str]] = None,
        time_start: Optional[str] = None,
        time_end: Optional[str] = None,
        time_granularity: Optional[str] = None,
        where: Optional[str] = None,
        limit: Optional[int] = None,
        order_by: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> QueryResult:
        """
        Query metrics using MetricFlow client.

        Args:
            metrics: List of metric names
            dimensions: List of dimensions to group by
            path: Optional subject area filter
            time_start: Start time (ISO format like '2024-01-01' or relative like '-7d')
            time_end: End time (ISO format like '2024-01-31' or relative like 'now')
            time_granularity: Time granularity for aggregation ('day', 'week', 'month', 'quarter', 'year')
            where: Optional WHERE clause
            limit: Result limit
            order_by: Columns to order by
            dry_run: If True, explain query instead of executing

        Returns:
            Query result
        """
        client = self._ensure_client_ready()
        query_metric_names = metrics

        # Helper to convert "null" string to None
        def _normalize_null(value):
            if value is None or value == "null" or value == "":
                return None
            return value

        # Prepare query parameters (normalize "null" strings to None)
        start_time = _normalize_null(time_start)
        end_time = _normalize_null(time_end)
        granularity = self._normalize_time_granularity(_normalize_null(time_granularity))
        where_clause = _normalize_null(where)
        dimensions, granularity = self._ensure_time_grouping(
            client=client,
            metrics=metrics,
            dimensions=dimensions,
            time_granularity=granularity,
        )

        query_dimensions, order_list = self._canonicalize_time_query_params(
            client=client,
            metrics=query_metric_names,
            dimensions=dimensions,
            order_by=order_by,
            granularity=granularity,
        )

        if dry_run:
            # Use explain to get SQL without executing
            try:
                result = client.explain(
                    metrics=query_metric_names,
                    dimensions=query_dimensions,
                    start_time=start_time,
                    end_time=end_time,
                    where=where_clause,
                    limit=limit,
                    order=order_list,
                )
            except Exception as exc:
                payload = self._semantic_validation_error_from(exc, query_metric_names)
                if payload is None:
                    raise
                raise MetricFlowSemanticValidationException(payload) from exc
            # Return SQL as result
            sql = result.rendered_sql_without_descriptions.sql_query
            metadata = {"explain": True, "sql": sql}
            return QueryResult(
                columns=["sql"],
                data=[{"sql": sql}],
                metadata=metadata,
            )
        else:
            # Execute the query
            logger.debug(
                f"Executing query: metrics={query_metric_names}, dimensions={query_dimensions}, "
                f"start_time={start_time}, end_time={end_time}, where={where_clause}, limit={limit}"
            )
            try:
                result = client.query(
                    metrics=query_metric_names,
                    dimensions=query_dimensions,
                    start_time=start_time,
                    end_time=end_time,
                    where=where_clause,
                    limit=limit,
                    order=order_list,
                )
            except Exception as exc:
                payload = self._semantic_validation_error_from(exc, query_metric_names)
                if payload is None:
                    raise
                raise MetricFlowSemanticValidationException(payload) from exc
            logger.debug(
                f"Query result: result_df={result.result_df is not None}, empty={result.result_df.empty if result.result_df is not None else 'N/A'}"
            )

            # Convert DataFrame to QueryResult
            if result.result_df is not None and not result.result_df.empty:
                columns = result.result_df.columns.tolist()
                # Convert to list of dicts (QueryResult.data expects List[Dict[str, Any]])
                data = result.result_df.to_dict(orient="records")
                metadata = {"dataflow_plan": result.dataflow_plan}
                return QueryResult(
                    columns=columns,
                    data=data,
                    metadata=metadata,
                )
            else:
                return QueryResult(columns=[], data=[], metadata={})

    async def validate_semantic(
        self,
        scope: str = "all",
        validation_scope: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate MetricFlow configuration using full validation pipeline.

        This performs the same validations as 'mf validate-configs':
        1. Lint validation (YAML format)
        2. Parsing validation (model building)
        3. Semantic validation (model semantics)
        4. Data warehouse validation

        Args:
            scope: "all" validates semantic models and metrics. "semantic_model"
                validates semantic models before metric files exist: the expected
                no-metrics semantic issue is ignored, but data-source, dimension,
                identifier, and measure warehouse validations still run.
            validation_scope: Alias for scope.

        Returns:
            Validation result
        """
        from metricflow.engine.utils import path_to_models
        from metricflow.model.model_validator import ModelValidator
        from metricflow.model.parsing.config_linter import ConfigLinter
        from metricflow.model.data_warehouse_model_validator import DataWarehouseModelValidator

        scope = validation_scope if validation_scope is not None else scope
        if scope is None:
            scope = "all"
        if scope not in {"all", "semantic_model"}:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        severity="error",
                        message="scope must be one of: all, semantic_model",
                    )
                ],
            )

        all_issues: List[ValidationIssue] = []

        # Step 1: Lint Validation
        try:
            model_path = path_to_models(handler=self._config_handler)
            config_file_paths = self._collect_model_file_paths(model_path)
            lint_results = ConfigLinter().lint_files(config_file_paths)
            all_issues.extend(self._convert_validation_results(lint_results))
            if lint_results.has_blocking_issues:
                return ValidationResult(valid=False, issues=all_issues)
        except Exception as e:
            logger.error(f"Lint validation failed: {e}")
            all_issues.append(
                ValidationIssue(severity="error", message=f"Lint validation failed: {e}")
            )
            return ValidationResult(valid=False, issues=all_issues)

        # Step 2: Parsing Validation
        try:
            parsing_result = self._model_build_result_from_config(
                self._config_handler,
                raise_issues_as_exceptions=False,
            )
            all_issues.extend(self._convert_validation_results(parsing_result.issues))
            if parsing_result.issues.has_blocking_issues:
                return ValidationResult(valid=False, issues=all_issues)
            user_model = parsing_result.model
        except Exception as e:
            logger.error(f"Parsing validation failed: {e}")
            all_issues.append(
                ValidationIssue(severity="error", message=f"Parsing validation failed: {e}")
            )
            return ValidationResult(valid=False, issues=all_issues)

        # Step 3: Semantic Validation
        try:
            semantic_result = ModelValidator().validate_model(user_model)
            semantic_issues = self._convert_validation_results(semantic_result.issues)
            if scope == "semantic_model":
                effective_semantic_issues = [
                    issue
                    for issue in semantic_issues
                    if not self._is_no_metrics_present_issue(issue)
                ]
            else:
                effective_semantic_issues = semantic_issues
            all_issues.extend(effective_semantic_issues)
            if semantic_result.issues.has_blocking_issues:
                has_effective_errors = any(
                    issue.severity == "error" for issue in effective_semantic_issues
                )
                if has_effective_errors or scope != "semantic_model":
                    return ValidationResult(valid=False, issues=all_issues)
        except Exception as e:
            logger.error(f"Semantic validation failed: {e}")
            all_issues.append(
                ValidationIssue(severity="error", message=f"Semantic validation failed: {e}")
            )
            return ValidationResult(valid=False, issues=all_issues)

        # Step 4: Data Warehouse Validation
        try:
            dw_validator = DataWarehouseModelValidator(
                sql_client=self.client.sql_client,
                system_schema=self.client.system_schema,
            )
            dw_results = self._run_dw_validations(
                dw_validator,
                user_model,
                include_metrics=scope == "all",
            )
            all_issues.extend(self._convert_validation_results(dw_results))
        except Exception as e:
            logger.error(f"Data warehouse validation failed: {e}")
            all_issues.append(
                ValidationIssue(severity="error", message=f"Data warehouse validation failed: {e}")
            )

        has_errors = any(issue.severity == "error" for issue in all_issues)
        return ValidationResult(valid=not has_errors, issues=all_issues)

    def _run_dw_validations(self, dw_validator, model, *, include_metrics: bool = True):
        """Run all data warehouse validations and merge results."""
        from metricflow.model.validations.validator_helpers import ModelValidationResults

        timeout = self.timeout
        results = [
            dw_validator.validate_data_sources(model, timeout),
            dw_validator.validate_dimensions(model, timeout),
            dw_validator.validate_identifiers(model, timeout),
            dw_validator.validate_measures(model, timeout),
        ]
        if include_metrics:
            results.append(dw_validator.validate_metrics(model, timeout))

        return ModelValidationResults.merge(results)

    def _convert_validation_results(self, results) -> List[ValidationIssue]:
        """Convert ModelValidationResults to list of ValidationIssue."""
        issues = []
        for error in results.errors:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=str(error),
                )
            )
        for warning in results.warnings:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=str(warning),
                )
            )
        return issues

    @staticmethod
    def _is_no_metrics_present_issue(issue: ValidationIssue) -> bool:
        return issue.severity == "error" and "No metrics present in the model" in str(issue.message)

    # ==================== Authoring Interface ====================
    # Backend/editor surface; not exposed as an agent/LLM tool. Operates on the
    # MetricFlow YAML files (source of truth), not on the KB projection.

    def _author(self) -> MetricFlowMetricAuthor:
        return MetricFlowMetricAuthor(self._resolve_model_path(self.config))

    def _invalidate_client_cache(self) -> None:
        """Drop the cached MetricFlowClient so the next read reloads the YAML.

        The client caches the parsed semantic model, so after an authoring
        mutation subsequent list_metrics / query_metrics / get_dimensions must
        rebuild it via _ensure_client_ready() to see the change.
        """
        self._client_initialized = False

    def read_metric_source(
        self,
        metric_name: str,
        *,
        subject_path: Optional[List[str]] = None,
    ) -> MetricSource:
        return self._author().read(metric_name)

    def write_metric_source(
        self,
        metric_name: str,
        source: str,
        *,
        subject_path: Optional[List[str]] = None,
        create: bool = False,
    ) -> MetricMutationResult:
        result = self._author().write(metric_name, source, subject_path=subject_path, create=create)
        self._invalidate_client_cache()
        return result

    def delete_metric_source(
        self,
        metric_name: str,
        *,
        subject_path: Optional[List[str]] = None,
    ) -> MetricMutationResult:
        result = self._author().delete(metric_name)
        self._invalidate_client_cache()
        return result

    def validate_metric_source(
        self,
        source: str,
        *,
        metric_name: Optional[str] = None,
    ) -> ValidationResult:
        return self._author().validate(source, metric_name=metric_name)
