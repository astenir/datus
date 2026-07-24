"""Downstream regression tests for subject tree embedding stores."""

from unittest.mock import MagicMock

import pyarrow as pa

from datus.storage.subject_tree.store import BaseSubjectEmbeddingStore


class TestBaseSubjectEmbeddingStoreReadOnlyListing:
    """Regression tests for listing entries without loading embeddings."""

    @staticmethod
    def _make_store(db: MagicMock) -> BaseSubjectEmbeddingStore:
        embedding_model = MagicMock()
        embedding_model.batch_size = 16
        store = BaseSubjectEmbeddingStore(
            table_name="test_subject_entries",
            embedding_model=embedding_model,
            datasource_id="california_schools",
            db=db,
            schema=pa.schema(
                [
                    pa.field("name", pa.string()),
                    pa.field("subject_node_id", pa.int64()),
                    pa.field("created_at", pa.string()),
                    pa.field("definition", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), list_size=2)),
                ]
            ),
        )
        store.subject_tree = MagicMock()
        store.subject_tree.get_full_path.return_value = ["frpm", "nutrition"]
        store._check_embedding_model_ready = MagicMock(side_effect=AssertionError("embedding must stay lazy"))
        return store

    def test_list_entries_reads_existing_table_without_loading_embedding(self):
        db = MagicMock()
        table = MagicMock()
        db.table_exists.return_value = True
        db.open_table.return_value = table
        table.count_rows.return_value = 1
        table.search_all.return_value = pa.table(
            {
                "name": ["free_meal_rate"],
                "subject_node_id": [42],
                "created_at": ["2026-07-24T00:00:00+00:00"],
                "definition": ["Free meal eligibility rate"],
                "datasource_id": ["california_schools"],
            }
        )
        store = self._make_store(db)

        results = store.list_entries(node_id=42)

        assert results == [
            {
                "name": "free_meal_rate",
                "created_at": "2026-07-24T00:00:00+00:00",
                "definition": "Free meal eligibility rate",
                "datasource_id": "california_schools",
                "subject_path": ["frpm", "nutrition"],
            }
        ]
        store._check_embedding_model_ready.assert_not_called()
        db.create_table.assert_not_called()
        assert store._shared.initialized is False

    def test_list_entries_returns_empty_for_missing_table_without_loading_embedding(self):
        db = MagicMock()
        db.table_exists.return_value = False
        store = self._make_store(db)

        assert store.list_entries(node_id=42) == []

        store._check_embedding_model_ready.assert_not_called()
        db.open_table.assert_not_called()
        db.create_table.assert_not_called()
        assert store._shared.initialized is False
