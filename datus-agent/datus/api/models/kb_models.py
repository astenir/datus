"""Pydantic v2 models for the bootstrap-kb API."""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class KbComponent(str, Enum):
    """Knowledge base components that can be bootstrapped."""

    METADATA = "metadata"
    SEMANTIC_MODEL = "semantic_model"
    METRICS = "metrics"
    REFERENCE_SQL = "reference_sql"


class KbUploadPurpose(str, Enum):
    """Temporary upload purposes supported by the KB bootstrap API."""

    SUCCESS_STORY_CSV = "success_story_csv"
    REFERENCE_SQL = "reference_sql"
    PLATFORM_DOCS = "platform_docs"


class KbUploadStatus(str, Enum):
    """Lifecycle state for temporary KB uploads."""

    AVAILABLE = "available"
    DELETED = "deleted"
    EXPIRED = "expired"


class KbUploadedFile(BaseModel):
    """File saved in a KB upload batch."""

    file_id: str = Field(..., description="Opaque file identifier inside the upload batch.")
    filename: str = Field(..., description="Sanitized display filename.")
    size: int = Field(..., ge=0, description="Saved file size in bytes.")
    content_type: Optional[str] = Field(default=None, description="Client-provided content type, if available.")
    relative_path: str = Field(
        ...,
        description="Path relative to the controlled project files root. Never an absolute server path.",
    )


class KbUploadRecord(BaseModel):
    """Metadata returned for a temporary KB upload."""

    upload_id: str
    purpose: KbUploadPurpose
    files: list[KbUploadedFile]
    created_at: str
    expires_at: Optional[str] = None
    status: KbUploadStatus = KbUploadStatus.AVAILABLE
    owner_user_id: Optional[str] = Field(default=None, description="Upload owner user id.")
    project_id: str = Field(default="default", description="Project id the upload belongs to.")
    metadata: dict[str, str] = Field(default_factory=dict, description="Non-sensitive upload metadata.")


class KbUploadDeleteResponse(BaseModel):
    """Response returned after deleting a temporary KB upload."""

    upload_id: str
    deleted: bool


class BootstrapKbInput(BaseModel):
    """POST body for /api/v1/kb/bootstrap.

    Mirrors the subset of `datus-agent bootstrap-kb` options exposed by the backend API.
    """

    model_config = ConfigDict(use_enum_values=True)

    components: list[KbComponent] = Field(
        ...,
        min_length=1,
        description=(
            "Knowledge base components to initialize. "
            "`metadata` scans live database schema and sample rows; "
            "`semantic_model` derives semantic schema objects from success-story SQLs; "
            "`metrics` derives MetricFlow-style business metrics; "
            "`reference_sql` indexes reusable SQL files."
        ),
    )
    strategy: Literal["overwrite", "check", "incremental"] = Field(
        default="incremental",
        description=(
            "Update strategy. `check` inspects existing data without rebuilding where supported, "
            "`overwrite` clears and rebuilds, and `incremental` appends or updates changed entries."
        ),
    )

    # metadata-specific
    schema_linking_type: str = Field(
        default="full",
        description=(
            "Metadata-only option controlling which object types are indexed from the database. "
            "Expected values follow `datus-agent bootstrap-kb`: `table`, `view`, `mv`, or `full`."
        ),
    )
    catalog: str = Field(
        default="",
        description=(
            "Optional metadata catalog filter. Mainly relevant for engines with a catalog layer, "
            "such as Snowflake or StarRocks."
        ),
    )
    database_name: str = Field(
        default="",
        description=(
            "Optional metadata database filter. Passed through to adapter-specific initialization; "
            "for Snowflake it maps to schema name, while for MySQL/PostgreSQL/StarRocks it is the database name."
        ),
    )

    # semantic_model / metrics source
    success_story: Optional[str] = Field(
        default=None,
        description=(
            "Project-root-relative path to a success-story CSV containing historical question/SQL pairs. "
            "Used by `semantic_model` and `metrics` when bootstrapping from success stories. "
            "Advanced/server-side mode only; browser clients should prefer upload references."
        ),
    )
    upload_id: Optional[str] = Field(
        default=None,
        description=(
            "Generic upload reference for browser flows. For `semantic_model`/`metrics`, it must point to a "
            "`success_story_csv` upload; for `reference_sql`, it must point to a `reference_sql` upload."
        ),
    )
    success_story_upload_id: Optional[str] = Field(
        default=None,
        description="Upload id for a `success_story_csv` batch used by `semantic_model` or `metrics`.",
    )
    success_story_file_id: Optional[str] = Field(
        default=None,
        description="Optional file id inside the success-story upload. If omitted, the first CSV is used.",
    )
    subject_tree: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional predefined hierarchical categories in `domain/layer1/layer2` form, such as "
            "`Sales/Reporting/Daily`. Used by `metrics` and `reference_sql`; "
            "if omitted, bootstrap reuses or learns categories from existing KB content."
        ),
    )

    # reference_sql source
    sql_dir: Optional[str] = Field(
        default=None,
        description=(
            "Project-root-relative directory containing `.sql` files for the `reference_sql` component. "
            "Files are scanned recursively and only `SELECT` statements are indexed. "
            "Advanced/server-side mode only; browser clients should prefer upload references."
        ),
    )
    reference_sql_upload_id: Optional[str] = Field(
        default=None,
        description="Upload id for a `reference_sql` batch. The uploaded directory is used as the SQL source.",
    )


class BootstrapDocInput(BaseModel):
    """POST body for /api/v1/kb/bootstrap-docs.

    Only ``platform`` is required.  Every other field falls back to the
    matching ``DocumentConfig`` in ``agent.yml`` (``agent.document.<platform>``).
    """

    model_config = ConfigDict(use_enum_values=True)

    platform: str = Field(..., description="Platform name, e.g. 'snowflake', 'duckdb', 'postgresql'.")
    build_mode: Literal["overwrite", "check"] = Field(
        default="overwrite",
        description="'check' returns existing store stats; 'overwrite' clears and rebuilds.",
    )
    pool_size: int = Field(default=4, ge=1, le=16, description="Thread pool size for parallel processing.")

    # Optional overrides — if omitted, resolved from AgentConfig.document_configs[platform]
    source_type: Optional[str] = Field(default=None, description="Source type: 'github', 'website', or 'local'.")
    source: Optional[str] = Field(default=None, description="GitHub repo 'owner/repo', URL, or local path.")
    upload_id: Optional[str] = Field(
        default=None,
        description=(
            "Upload id for a `platform_docs` batch. When `source_type` is `local`, the uploaded directory is used "
            "as the local documentation source and `source` is not required."
        ),
    )
    version: Optional[str] = Field(default=None, description="Document version (auto-detected if omitted).")
    github_ref: Optional[str] = Field(default=None, description="Git branch / tag / commit for GitHub sources.")
    github_token: Optional[str] = Field(default=None, description="GitHub API token for authenticated access.")
    paths: Optional[list[str]] = Field(default=None, description="File/directory paths to include.")
    chunk_size: Optional[int] = Field(default=None, description="Target chunk size in characters.")
    max_depth: Optional[int] = Field(default=None, description="Max crawl depth for website sources.")
    include_patterns: Optional[list[str]] = Field(default=None, description="File/URL patterns to include (regex).")
    exclude_patterns: Optional[list[str]] = Field(default=None, description="File/URL patterns to exclude (regex).")


class BootstrapKbEvent(BaseModel):
    """SSE event envelope sent to the client."""

    model_config = ConfigDict(use_enum_values=True)

    stream_id: str
    component: str
    stage: str
    message: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[dict] = None
    payload: Optional[dict] = None
    timestamp: str


class BootstrapKbResult(BaseModel):
    """Final summary after all components complete."""

    stream_id: str
    components: dict[str, dict]
