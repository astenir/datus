"""Temporary upload storage for knowledge-base bootstrap sources.

This is a KB upload metadata surface only. It records browser-uploaded source
files that later feed existing KB bootstrap flows; it does not store RAG/vector
data, chat session bodies, or generated artifacts.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException, UploadFile

from datus.api.models.kb_models import KbUploadedFile, KbUploadPurpose, KbUploadRecord, KbUploadStatus
from datus.api.utils.path_utils import safe_resolve
from datus.utils.exceptions import DatusException

if TYPE_CHECKING:
    from datus.configuration.agent_config import AgentConfig

DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_REQUEST_BYTES = 100 * 1024 * 1024

_CSV_EXTENSIONS = {".csv"}
_SQL_EXTENSIONS = {".sql"}
_DOC_EXTENSIONS = {".md", ".markdown", ".txt", ".rst", ".html", ".htm", ".json", ".yaml", ".yml"}
_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_SAFE_SEGMENT_FULL_RE = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class KbUploadLimits:
    """Upload size limits."""

    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES


class KbUploadStore:
    """SQLite-backed metadata store plus controlled filesystem staging."""

    def __init__(self, *, files_root: Path, metadata_db_path: Path, limits: KbUploadLimits | None = None) -> None:
        self.files_root = files_root
        self.metadata_db_path = metadata_db_path
        self.limits = limits or KbUploadLimits()
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.metadata_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    async def create_upload(
        self,
        *,
        purpose: KbUploadPurpose,
        files: list[UploadFile],
        owner_user_id: str | None,
        project_id: str,
        metadata: dict[str, str],
    ) -> KbUploadRecord:
        if not files:
            raise _upload_error(422, "KB_UPLOAD_EMPTY")

        upload_id = str(uuid.uuid4())
        owner_segment = _safe_storage_segment(owner_user_id or "anonymous")
        project_segment = _safe_storage_segment(project_id or "default")
        relative_dir = Path("uploads") / project_segment / owner_segment / upload_id
        upload_dir = safe_resolve(self.files_root, relative_dir.as_posix())
        upload_dir.mkdir(parents=True, exist_ok=False)

        saved_files: list[KbUploadedFile] = []
        total_size = 0
        try:
            for upload_file in files:
                saved_file, total_size = await self._save_file(
                    purpose=purpose,
                    upload_file=upload_file,
                    upload_dir=upload_dir,
                    relative_dir=relative_dir,
                    seen_files=saved_files,
                    total_size=total_size,
                )
                saved_files.append(saved_file)

            if not saved_files:
                raise _upload_error(422, "KB_UPLOAD_EMPTY")

            record = KbUploadRecord(
                upload_id=upload_id,
                purpose=purpose,
                files=saved_files,
                created_at=_utc_now(),
                expires_at=None,
                status=KbUploadStatus.AVAILABLE,
                owner_user_id=owner_user_id,
                project_id=project_id or "default",
                metadata=metadata,
            )
            self._insert_record(record)
            return record
        except Exception:
            shutil.rmtree(upload_dir, ignore_errors=True)
            _prune_empty_upload_parents(upload_dir, self.files_root / "uploads")
            raise
        finally:
            for upload_file in files:
                await upload_file.close()

    def get_upload(self, upload_id: str) -> KbUploadRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT upload_id, owner_user_id, project_id, purpose, status, created_at, expires_at, metadata_json
                FROM kb_uploads
                WHERE upload_id = ?
                """,
                (upload_id,),
            ).fetchone()
            if row is None:
                return None
            files = conn.execute(
                """
                SELECT file_id, filename, size, content_type, relative_path
                FROM kb_upload_files
                WHERE upload_id = ?
                ORDER BY ordinal ASC
                """,
                (upload_id,),
            ).fetchall()
        return _record_from_row(row, files)

    def mark_deleted(self, upload_id: str) -> KbUploadRecord | None:
        record = self.get_upload(upload_id)
        if record is None:
            return None

        deleted_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE kb_uploads
                SET status = ?, deleted_at = ?
                WHERE upload_id = ?
                """,
                (KbUploadStatus.DELETED.value, deleted_at, upload_id),
            )
            conn.commit()

        upload_dir = self.upload_directory(record)
        if upload_dir is not None:
            shutil.rmtree(upload_dir, ignore_errors=True)
            _prune_empty_upload_parents(upload_dir, self.files_root / "uploads")
        return record.model_copy(update={"status": KbUploadStatus.DELETED})

    def upload_directory(self, record: KbUploadRecord) -> Path | None:
        if not record.files:
            return None
        try:
            first_path = safe_resolve(self.files_root, record.files[0].relative_path)
        except DatusException:
            return None
        return first_path.parent

    def relative_upload_directory(self, record: KbUploadRecord) -> str:
        if not record.files:
            raise _upload_error(422, "KB_UPLOAD_EMPTY")
        return str(Path(record.files[0].relative_path).parent).replace("\\", "/")

    async def _save_file(
        self,
        *,
        purpose: KbUploadPurpose,
        upload_file: UploadFile,
        upload_dir: Path,
        relative_dir: Path,
        seen_files: list[KbUploadedFile],
        total_size: int,
    ) -> tuple[KbUploadedFile, int]:
        filename = _sanitize_filename(upload_file.filename)
        _validate_purpose_file(purpose, filename)

        file_id = str(uuid.uuid4())
        storage_name = _dedupe_storage_name(file_id, filename, seen_files)
        relative_path = (relative_dir / storage_name).as_posix()
        target_path = safe_resolve(self.files_root, relative_path)
        if target_path.parent != upload_dir:
            raise _upload_error(422, "KB_UPLOAD_PATH_INVALID")

        size = 0
        with target_path.open("wb") as handle:
            while chunk := await upload_file.read(1024 * 1024):
                size += len(chunk)
                total_size += len(chunk)
                if size > self.limits.max_file_bytes or total_size > self.limits.max_request_bytes:
                    raise _upload_error(413, "KB_UPLOAD_TOO_LARGE")
                handle.write(chunk)

        if size <= 0:
            raise _upload_error(422, "KB_UPLOAD_EMPTY")

        return (
            KbUploadedFile(
                file_id=file_id,
                filename=filename,
                size=size,
                content_type=upload_file.content_type,
                relative_path=relative_path,
            ),
            total_size,
        )

    def _insert_record(self, record: KbUploadRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO kb_uploads (
                    upload_id,
                    owner_user_id,
                    project_id,
                    purpose,
                    status,
                    created_at,
                    expires_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.upload_id,
                    record.owner_user_id,
                    record.project_id,
                    record.purpose.value,
                    record.status.value,
                    record.created_at,
                    record.expires_at,
                    json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
                ),
            )
            for ordinal, file in enumerate(record.files):
                conn.execute(
                    """
                    INSERT INTO kb_upload_files (
                        upload_id,
                        file_id,
                        ordinal,
                        filename,
                        size,
                        content_type,
                        relative_path
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.upload_id,
                        file.file_id,
                        ordinal,
                        file.filename,
                        file.size,
                        file.content_type,
                        file.relative_path,
                    ),
                )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.metadata_db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_uploads (
                    upload_id TEXT PRIMARY KEY,
                    owner_user_id TEXT,
                    project_id TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    deleted_at TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_upload_files (
                    upload_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    content_type TEXT,
                    relative_path TEXT NOT NULL,
                    PRIMARY KEY (upload_id, file_id),
                    FOREIGN KEY (upload_id) REFERENCES kb_uploads(upload_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_kb_uploads_owner
                ON kb_uploads (project_id, owner_user_id, status, created_at)
                """
            )
            conn.commit()


def make_kb_upload_store(agent_config: "AgentConfig") -> KbUploadStore:
    """Create the default single-node KB upload store for an AgentConfig."""

    home = Path(str(agent_config.home))
    limits = _upload_limits_from_config(agent_config)
    return KbUploadStore(
        files_root=home / "files",
        metadata_db_path=home / ".datus" / "kb_uploads.db",
        limits=limits,
    )


def _upload_limits_from_config(agent_config: "AgentConfig") -> KbUploadLimits:
    raw_api = getattr(agent_config, "api_config", {}) or {}
    raw_enterprise = getattr(agent_config, "enterprise_config", {}) or {}
    raw = {}
    if isinstance(raw_api, dict):
        raw.update(raw_api.get("kb_uploads") or {})
    if isinstance(raw_enterprise, dict):
        raw.update(raw_enterprise.get("kb_uploads") or {})
    return KbUploadLimits(
        max_file_bytes=_positive_int(raw.get("max_file_bytes"), DEFAULT_MAX_FILE_BYTES),
        max_request_bytes=_positive_int(raw.get("max_request_bytes"), DEFAULT_MAX_REQUEST_BYTES),
    )


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _sanitize_filename(raw_filename: str | None) -> str:
    raw = (raw_filename or "").replace("\\", "/").strip()
    name = Path(raw).name.strip()
    if not name or name in {".", ".."} or ".." in name or "/" in name or "\\" in name:
        raise _upload_error(422, "KB_UPLOAD_PATH_INVALID")
    if name.startswith(".") and name.count(".") == 1:
        raise _upload_error(422, "KB_UPLOAD_PATH_INVALID")
    safe = _SAFE_SEGMENT_RE.sub("_", name).strip("._ ")
    if not safe:
        raise _upload_error(422, "KB_UPLOAD_PATH_INVALID")
    return safe


def _validate_purpose_file(purpose: KbUploadPurpose, filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    allowed = {
        KbUploadPurpose.SUCCESS_STORY_CSV: _CSV_EXTENSIONS,
        KbUploadPurpose.REFERENCE_SQL: _SQL_EXTENSIONS,
        KbUploadPurpose.PLATFORM_DOCS: _DOC_EXTENSIONS,
    }[purpose]
    if suffix not in allowed:
        raise _upload_error(415, "KB_UPLOAD_INVALID_FILE_TYPE")


def _dedupe_storage_name(file_id: str, filename: str, seen_files: list[KbUploadedFile]) -> str:
    stem = Path(filename).stem or "upload"
    suffix = Path(filename).suffix.lower()
    storage_name = f"{file_id}_{stem}{suffix}"
    existing = {Path(file.relative_path).name for file in seen_files}
    if storage_name not in existing:
        return storage_name
    return f"{file_id}_{len(existing)}_{stem}{suffix}"


def _safe_storage_segment(value: str) -> str:
    raw = str(value).strip() or "default"
    if _SAFE_SEGMENT_FULL_RE.fullmatch(raw):
        return raw
    candidate = _SAFE_SEGMENT_RE.sub("_", raw).strip("._")
    return candidate or "default"


def _prune_empty_upload_parents(start_dir: Path, stop_dir: Path) -> None:
    stop = stop_dir.resolve()
    current = start_dir.parent
    while True:
        try:
            resolved = current.resolve()
        except OSError:
            return
        if not resolved.is_relative_to(stop) or resolved == stop.parent:
            return
        try:
            current.rmdir()
        except OSError:
            return
        if resolved == stop:
            return
        current = current.parent


def _record_from_row(row: tuple[object, ...], files: list[tuple[object, ...]]) -> KbUploadRecord:
    metadata: dict[str, str]
    try:
        raw_metadata = json.loads(row[7] or "{}")
        metadata = {str(k): str(v) for k, v in raw_metadata.items()} if isinstance(raw_metadata, dict) else {}
    except json.JSONDecodeError:
        metadata = {}

    return KbUploadRecord(
        upload_id=str(row[0]),
        owner_user_id=row[1],
        project_id=str(row[2]),
        purpose=KbUploadPurpose(str(row[3])),
        status=KbUploadStatus(str(row[4])),
        created_at=str(row[5]),
        expires_at=row[6],
        metadata=metadata,
        files=[
            KbUploadedFile(
                file_id=str(file_row[0]),
                filename=str(file_row[1]),
                size=int(file_row[2]),
                content_type=file_row[3],
                relative_path=str(file_row[4]),
            )
            for file_row in files
        ],
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _upload_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)
