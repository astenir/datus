"""Service for idempotently persisting success stories to benchmark CSV files."""

import csv
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from datus.api.models.success_story_models import SuccessStoryData, SuccessStorySource
from datus.configuration.agent_config import AgentConfig
from datus.utils.csv_utils import sanitize_csv_field
from datus.utils.loggings import get_logger
from datus.utils.time_utils import now_utc_iso

logger = get_logger(__name__)

_CSV_FIELDS = (
    "question",
    "sql",
    "datasource_id",
    "source_id",
    "session_id",
    "session_link",
    "subagent_name",
    "timestamp",
)
_PRE_DATASOURCE_FIELDS = ("question", "sql", "source_id", "session_id", "session_link", "subagent_name", "timestamp")
_LEGACY_API_FIELDS = ("session_link", "session_id", "subagent_name", "user_message", "sql", "timestamp")
_MINIMAL_FIELDS = ("question", "sql")
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,127}$")
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.\-]+")


class SuccessStoryCsvSchemaError(OSError):
    """Raised when an existing success-story CSV has an unsupported schema."""


@dataclass(frozen=True)
class SuccessStoryMigrationData:
    """Summary returned by an explicit legacy-file migration."""

    datasource_id: str
    subagent_name: str
    storage_key: str
    total_rows: int
    migrated_rows: int
    skipped_rows: int


class SuccessStoryService:
    """Canonical CSV writer with schema migration and source idempotency."""

    def __init__(self, agent_config: AgentConfig, project_id: str = "default"):
        self.agent_config = agent_config
        self.project_id = project_id

    def save(self, source: SuccessStorySource) -> SuccessStoryData:
        """Persist a server-resolved execution, returning the stable story metadata."""
        subagent_name = source.subagent_name
        target_dir = self._resolve_target_dir(source.datasource_id, subagent_name)
        target_dir.mkdir(parents=True, exist_ok=True)
        csv_path = target_dir / "success_story.csv"

        timestamp = now_utc_iso()
        story_id = self._story_id(source)
        row = {
            "question": sanitize_csv_field(source.question),
            "sql": sanitize_csv_field(source.sql),
            "datasource_id": sanitize_csv_field(source.datasource_id),
            "source_id": story_id,
            "session_id": sanitize_csv_field(source.session_id),
            "session_link": sanitize_csv_field(source.session_link),
            "subagent_name": sanitize_csv_field(subagent_name),
            "timestamp": timestamp,
        }

        created, persisted_timestamp = self._write_row(csv_path, row, source.datasource_id)
        storage_key = csv_path.relative_to(self.agent_config.path_manager.benchmark_dir.resolve()).as_posix()
        logger.info(
            "%s success story %s for session %s under %s",
            "Saved" if created else "Reused",
            story_id,
            source.session_id,
            csv_path,
        )

        return SuccessStoryData(
            story_id=story_id,
            created=created,
            datasource_id=source.datasource_id,
            subagent_name=subagent_name,
            storage_key=storage_key,
            session_id=source.session_id,
            timestamp=persisted_timestamp,
        )

    def migrate_legacy_file(
        self,
        source_path: str | Path,
        *,
        datasource_id: str,
        subagent_name: str,
    ) -> SuccessStoryMigrationData:
        """Copy a known single-datasource legacy CSV into the isolated layout."""
        normalized_datasource = datasource_id.strip()
        normalized_subagent = subagent_name.strip()
        if not normalized_datasource or not normalized_subagent:
            raise SuccessStoryCsvSchemaError("Datasource and subagent must not be blank")

        source_csv = Path(source_path).expanduser().resolve()
        if not source_csv.is_file() or source_csv.stat().st_size == 0:
            raise SuccessStoryCsvSchemaError("Legacy success-story CSV does not exist or is empty")

        source_rows = self._read_canonical_rows(source_csv, normalized_datasource)
        if not source_rows:
            raise SuccessStoryCsvSchemaError("Legacy success-story CSV contains no data rows")
        unique_source_rows = []
        seen_source_ids = set()
        for row in source_rows:
            row["datasource_id"] = sanitize_csv_field(normalized_datasource)
            row["subagent_name"] = sanitize_csv_field(normalized_subagent)
            source_id = row.get("source_id")
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            unique_source_rows.append(row)

        target_dir = self._resolve_target_dir(normalized_datasource, normalized_subagent)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_csv = target_dir / "success_story.csv"
        lock_path = target_csv.with_suffix(f"{target_csv.suffix}.lock")
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            try:
                _lock_file(lock_file)
                target_rows = self._read_canonical_rows(target_csv, normalized_datasource)
                existing_ids = {row.get("source_id") for row in target_rows}
                migrated_rows = [row for row in unique_source_rows if row.get("source_id") not in existing_ids]
                if migrated_rows:
                    self._atomic_write(target_csv, [*target_rows, *migrated_rows])
            finally:
                _unlock_file(lock_file)

        storage_key = target_csv.relative_to(self.agent_config.path_manager.benchmark_dir.resolve()).as_posix()
        return SuccessStoryMigrationData(
            datasource_id=normalized_datasource,
            subagent_name=normalized_subagent,
            storage_key=storage_key,
            total_rows=len(source_rows),
            migrated_rows=len(migrated_rows),
            skipped_rows=len(source_rows) - len(migrated_rows),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_target_dir(self, datasource_id: str, subagent_name: str) -> Path:
        """Compute the per-datasource/per-subagent directory inside benchmark_dir.

        Both names came from server-owned session history, but still encode
        unsafe path segments and verify that the final path cannot escape.
        """
        base_dir = self.agent_config.path_manager.benchmark_dir.resolve()
        datasource_key = _safe_storage_key(datasource_id)
        subagent_key = _safe_storage_key(subagent_name)
        target_dir = (base_dir / datasource_key / subagent_key).resolve()
        try:
            target_dir.relative_to(base_dir)
        except ValueError as e:
            raise SuccessStoryCsvSchemaError("Unsafe success-story target directory") from e
        return target_dir

    def _story_id(self, source: SuccessStorySource) -> str:
        digest = hashlib.sha256(
            f"{self.project_id}\0{source.session_id}\0{source.call_tool_id}".encode("utf-8")
        ).hexdigest()
        return f"ss_{digest[:24]}"

    @classmethod
    def _write_row(
        cls,
        csv_path: Path,
        row: dict[str, str | None],
        datasource_id: str,
    ) -> tuple[bool, str]:
        """Write under a sidecar lock and atomically normalize the whole CSV."""
        lock_path = csv_path.with_suffix(f"{csv_path.suffix}.lock")
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            try:
                _lock_file(lock_file)
                rows = cls._read_canonical_rows(csv_path, datasource_id)
                for existing in rows:
                    if existing.get("source_id") == row["source_id"]:
                        return False, existing.get("timestamp") or str(row["timestamp"])

                rows.append(row)
                cls._atomic_write(csv_path, rows)
                return True, str(row["timestamp"])
            finally:
                _unlock_file(lock_file)

    @staticmethod
    def _read_canonical_rows(csv_path: Path, datasource_id: str) -> list[dict[str, str | None]]:
        if not csv_path.exists() or csv_path.stat().st_size == 0:
            return []

        with open(csv_path, newline="", encoding="utf-8-sig") as source_file:
            reader = csv.DictReader(source_file)
            header = tuple(reader.fieldnames or ())
            supported = header in {_CSV_FIELDS, _PRE_DATASOURCE_FIELDS, _LEGACY_API_FIELDS, _MINIMAL_FIELDS}
            if not supported:
                raise SuccessStoryCsvSchemaError("Existing success-story CSV has an unsupported schema")

            rows = []
            for index, raw in enumerate(reader):
                question = raw.get("question") or raw.get("user_message") or ""
                sql = raw.get("sql") or ""
                row_datasource_id = (raw.get("datasource_id") or datasource_id).strip()
                if row_datasource_id != datasource_id:
                    raise SuccessStoryCsvSchemaError("Existing success-story CSV belongs to another datasource")
                source_id = raw.get("source_id") or SuccessStoryService._legacy_source_id(raw, index)
                rows.append(
                    {
                        "question": sanitize_csv_field(question),
                        "sql": sanitize_csv_field(sql),
                        "datasource_id": sanitize_csv_field(row_datasource_id),
                        "source_id": source_id,
                        "session_id": sanitize_csv_field(raw.get("session_id") or ""),
                        "session_link": sanitize_csv_field(raw.get("session_link") or ""),
                        "subagent_name": sanitize_csv_field(raw.get("subagent_name") or ""),
                        "timestamp": raw.get("timestamp") or "",
                    }
                )
            return rows

    @staticmethod
    def _legacy_source_id(row: dict[str, str | None], index: int) -> str:
        material = "\0".join(
            str(row.get(key) or "") for key in ("session_id", "user_message", "question", "sql", "timestamp")
        )
        digest = hashlib.sha256(f"{index}\0{material}".encode("utf-8")).hexdigest()
        return f"legacy_{digest[:24]}"

    @staticmethod
    def _atomic_write(csv_path: Path, rows: list[dict[str, str | None]]) -> None:
        fd, temp_name = tempfile.mkstemp(prefix=f".{csv_path.name}.", suffix=".tmp", dir=csv_path.parent)
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=list(_CSV_FIELDS))
                writer.writeheader()
                writer.writerows(rows)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_name, csv_path)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise


def _safe_storage_key(value: str) -> str:
    normalized = value.strip()
    if normalized not in {"", ".", ".."} and _SAFE_SEGMENT_RE.fullmatch(normalized):
        return normalized

    slug = _UNSAFE_CHARS.sub("_", normalized).strip("._-")[:80] or "value"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{slug}--{digest}"


def _lock_file(f) -> None:
    """Best-effort advisory lock; no-op on platforms without fcntl."""
    try:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except (ImportError, OSError):
        pass


def _unlock_file(f) -> None:
    try:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (ImportError, OSError):
        pass
