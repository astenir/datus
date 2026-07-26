"""Downstream tests for storage read-path extensions."""

import pytest

from datus.storage.embedding_store_backend_downstream import (
    apply_storage_key,
    ensure_persisted_unique_columns,
    storage_key_migration_expr,
)
from datus.utils.exceptions import DatusException, ErrorCode
from tests.unit_tests.storage.test_base import (
    TestReadOnlyPathsWithoutEmbedding as _TestReadOnlyPathsWithoutEmbedding,
)
from tests.unit_tests.storage.test_base import (
    _ReadOnlyTable,
    _ReadOnlyVectorDb,
)


class _TrackingReadOnlyTable(_ReadOnlyTable):
    def __init__(self, rows):
        super().__init__(rows)
        self.search_all_calls = []

    def search_all(self, where=None, select_fields=None, limit=None):
        self.search_all_calls.append({"where": where, "select_fields": select_fields, "limit": limit})
        return super().search_all(where=where, select_fields=select_fields, limit=limit)


class TestReadOnlyPathsWithoutEmbedding:
    def test_existing_table_read_path_does_not_fetch_vector_by_default(self):
        table = _TrackingReadOnlyTable(
            [
                {"name": "orders", "definition": "CREATE TABLE orders(id int)", "vector": [0.1, 0.2]},
            ]
        )
        db = _ReadOnlyVectorDb(exists=True, table=table)
        store = _TestReadOnlyPathsWithoutEmbedding()._make_store(db)

        result = store._search_all()

        assert result.to_pylist() == [{"name": "orders", "definition": "CREATE TABLE orders(id int)"}]
        assert table.search_all_calls == [{"where": None, "select_fields": ["name", "definition"], "limit": 1}]
        assert store._shared.initialized is False


class _UniqueRepairTable:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def ensure_unique_columns(self, columns):
        self.calls.append(columns)
        if self.error is not None:
            raise self.error


def test_ensure_persisted_unique_columns_delegates_to_backend() -> None:
    table = _UniqueRepairTable()

    ensure_persisted_unique_columns(table, ["storage_key"], table_name="schema_metadata")

    assert table.calls == [["storage_key"]]


def test_ensure_persisted_unique_columns_maps_backend_failure() -> None:
    table = _UniqueRepairTable(RuntimeError("repair failed"))

    with pytest.raises(DatusException) as exc_info:
        ensure_persisted_unique_columns(table, ["storage_key"], table_name="schema_metadata")

    assert exc_info.value.code == ErrorCode.STORAGE_TABLE_OPERATION_FAILED
    assert exc_info.value.message_args == {
        "operation": "ensure_unique_columns",
        "table_name": "schema_metadata",
        "error_message": "repair failed",
    }


def test_apply_storage_key_uses_configured_business_key_column() -> None:
    row = {"datasource_id": "sales", "identifier": "catalog.database.orders"}

    apply_storage_key(row, {"datasource_id", "identifier", "storage_key"}, "identifier")

    assert row["storage_key"] == "sales:catalog.database.orders"


def test_storage_key_migration_expr_rejects_unsafe_source_column() -> None:
    with pytest.raises(ValueError, match="Invalid storage key source column"):
        storage_key_migration_expr({"datasource_id", "unsafe-column", "storage_key"}, "unsafe-column")
