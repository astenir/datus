# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream regression tests for schema metadata storage."""

from unittest.mock import MagicMock

from datus.storage.schema_metadata import SchemaStorage
from datus.storage.schema_metadata.sample_rows_downstream import sanitize_sample_rows
from datus.storage.schema_metadata.store import SchemaWithValueRAG


class _EmbeddingModelStub:
    batch_size = 64
    dim_size = 4


def _make_value_row(idx: int, sample_rows: str) -> dict:
    return {
        "identifier": f"val_{idx}",
        "catalog_name": "cat",
        "database_name": "db",
        "schema_name": "sch",
        "table_name": f"table_{idx}",
        "table_type": "table",
        "sample_rows": sample_rows,
    }


def test_schema_metadata_uses_identifier_storage_key() -> None:
    store = SchemaStorage(_EmbeddingModelStub(), db=MagicMock())

    assert store._unique_columns == ["storage_key"]
    assert store._schema.field("storage_key").nullable is False
    assert store._storage_key_source_column == "identifier"

    rows = store._apply_default_values([{"identifier": "catalog.database.orders", "datasource_id": "sales"}])
    assert rows[0]["storage_key"] == "sales:catalog.database.orders"
    assert store._scope_column_migration_exprs()["storage_key"] == (
        "coalesce(nullif(datasource_id, ''), 'legacy') || ':' || identifier"
    )


def test_sanitize_sample_rows_keeps_small_csv_unchanged() -> None:
    sample_rows = "id,name\n1,Alice\n2,Bob\n"

    assert sanitize_sample_rows(sample_rows, max_cell_chars=100, max_chars=1_000) == sample_rows


def test_sanitize_sample_rows_replaces_oversized_cells_without_leaking_content() -> None:
    secret = "private-system-prompt-" * 200
    sample_rows = f'id,prompt\n1,"{secret}"\n'

    sanitized = sanitize_sample_rows(sample_rows, max_cell_chars=128, max_chars=1_000)

    assert secret not in sanitized
    assert "<DATUS_SAMPLE_CELL_TRUNCATED chars=" in sanitized
    assert "id,prompt" in sanitized
    assert len(sanitized) <= 1_000


def test_sanitize_sample_rows_caps_total_serialized_size() -> None:
    sample_rows = "id,value\n" + "\n".join(f"{idx},value-{idx:04d}" for idx in range(1_000))

    sanitized = sanitize_sample_rows(sample_rows, max_cell_chars=100, max_chars=512)

    assert len(sanitized) <= 512
    assert "<DATUS_SAMPLE_ROWS_TRUNCATED original_chars=" in sanitized


def test_sanitize_sample_rows_does_not_leak_oversized_unparseable_csv_fields() -> None:
    secret = "s" * 200_000
    sample_rows = f"id,prompt\n1,{secret}\n"

    sanitized = sanitize_sample_rows(sample_rows, max_cell_chars=1_000, max_chars=8_000)

    assert secret not in sanitized
    assert sanitized == f"<DATUS_SAMPLE_ROWS_UNPARSEABLE original_chars={len(sample_rows)}>"


def test_store_batch_sanitizes_values_before_vector_storage(real_agent_config) -> None:
    rag = SchemaWithValueRAG(real_agent_config)
    rag._sample_cell_max_chars = 32
    rag._sample_max_chars = 256
    rag.value_store.store_batch = MagicMock()
    secret = "private-system-prompt-" * 20

    rag.store_batch([], [_make_value_row(1, sample_rows=f'id,prompt\n1,"{secret}"\n')])

    stored_rows = rag.value_store.store_batch.call_args.args[0]
    assert len(stored_rows) == 1
    assert secret not in stored_rows[0]["sample_rows"]
    assert "<DATUS_SAMPLE_CELL_TRUNCATED chars=" in stored_rows[0]["sample_rows"]
