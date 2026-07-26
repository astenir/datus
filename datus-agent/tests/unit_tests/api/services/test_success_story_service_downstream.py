# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Downstream success-story persistence coverage."""

import csv
from unittest.mock import MagicMock

import pytest

from datus.api.models.downstream import SuccessStorySource
from datus_enterprise.services.success_story_service import (
    EnterpriseSuccessStoryService,
    SuccessStoryCsvSchemaError,
)


def _make_config(tmp_path):
    cfg = MagicMock()
    cfg.path_manager = MagicMock()
    cfg.path_manager.benchmark_dir = tmp_path / "benchmark"
    return cfg


def _source(**updates):
    values = {
        "session_id": "chat_session_1",
        "call_tool_id": "call_1",
        "question": "show one",
        "sql": "SELECT 1",
        "datasource_id": "ccks_fund",
        "subagent_name": "gen_sql",
        "session_link": "/chat/chat_session_1",
    }
    values.update(updates)
    return SuccessStorySource(**values)


def _read_rows(csv_path):
    with open(csv_path, encoding="utf-8") as source:
        return list(csv.DictReader(source))


class TestSaveSuccessStory:
    def test_writes_canonical_csv_without_exposing_path(self, tmp_path):
        svc = EnterpriseSuccessStoryService(_make_config(tmp_path), project_id="project-1")

        data = svc.save(_source())

        csv_path = tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv"
        rows = _read_rows(csv_path)
        assert data.created is True
        assert data.story_id.startswith("ss_")
        assert data.datasource_id == "ccks_fund"
        assert data.storage_key == "ccks_fund/gen_sql/success_story.csv"
        assert not hasattr(data, "csv_path")
        assert list(rows[0]) == [
            "question",
            "sql",
            "datasource_id",
            "source_id",
            "session_id",
            "session_link",
            "subagent_name",
            "timestamp",
        ]
        assert rows[0]["question"] == "show one"
        assert rows[0]["sql"] == "SELECT 1"
        assert rows[0]["datasource_id"] == "ccks_fund"
        assert rows[0]["source_id"] == data.story_id

    def test_duplicate_source_is_idempotent(self, tmp_path):
        svc = EnterpriseSuccessStoryService(_make_config(tmp_path))
        first = svc.save(_source())
        second = svc.save(_source(question="changed client text", sql="SELECT 999"))

        rows = _read_rows(tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv")
        assert len(rows) == 1
        assert second.story_id == first.story_id
        assert second.created is False
        assert second.timestamp == first.timestamp
        assert rows[0]["question"] == "show one"

    def test_distinct_call_ids_append_without_duplicate_header(self, tmp_path):
        svc = EnterpriseSuccessStoryService(_make_config(tmp_path))
        svc.save(_source())
        svc.save(_source(call_tool_id="call_2", sql="SELECT 2"))

        csv_path = tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv"
        with open(csv_path, encoding="utf-8") as source:
            lines = source.readlines()
        assert len(lines) == 3
        assert lines[0].startswith("question,sql,datasource_id,source_id,")

    def test_migrates_old_api_header(self, tmp_path):
        csv_path = tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(
            "session_link,session_id,subagent_name,user_message,sql,timestamp\n"
            "/chat/old,s-old,gen_sql,old question,SELECT 0,2026-01-01T00:00:00Z\n",
            encoding="utf-8",
        )

        EnterpriseSuccessStoryService(_make_config(tmp_path)).save(_source())

        rows = _read_rows(csv_path)
        assert len(rows) == 2
        assert rows[0]["question"] == "old question"
        assert rows[0]["source_id"].startswith("legacy_")
        assert "user_message" not in rows[0]

    def test_migrates_minimal_question_sql_header(self, tmp_path):
        csv_path = tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text("question,sql\nold question,SELECT 0\n", encoding="utf-8")

        EnterpriseSuccessStoryService(_make_config(tmp_path)).save(_source())

        rows = _read_rows(csv_path)
        assert len(rows) == 2
        assert rows[0]["question"] == "old question"
        assert rows[0]["sql"] == "SELECT 0"

    def test_rejects_unknown_existing_schema_without_clobbering(self, tmp_path):
        csv_path = tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv"
        csv_path.parent.mkdir(parents=True)
        original = "unexpected,column\na,b\n"
        csv_path.write_text(original, encoding="utf-8")

        with pytest.raises(SuccessStoryCsvSchemaError):
            EnterpriseSuccessStoryService(_make_config(tmp_path)).save(_source())

        assert csv_path.read_text(encoding="utf-8") == original

    def test_sanitizes_csv_injection(self, tmp_path):
        svc = EnterpriseSuccessStoryService(_make_config(tmp_path))
        svc.save(_source(question="+HYPERLINK(...) ", sql="=cmd|'/c calc'!A1"))

        rows = _read_rows(tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv")
        assert rows[0]["sql"].startswith("'=")
        assert rows[0]["question"].startswith("'+")

    def test_isolates_datasources_and_subagents(self, tmp_path):
        svc = EnterpriseSuccessStoryService(_make_config(tmp_path))

        svc.save(_source())
        svc.save(_source(call_tool_id="call_2", datasource_id="datus_enterprise"))
        svc.save(_source(call_tool_id="call_3", subagent_name="chat"))

        assert (tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv").is_file()
        assert (tmp_path / "benchmark" / "datus_enterprise" / "gen_sql" / "success_story.csv").is_file()
        assert (tmp_path / "benchmark" / "ccks_fund" / "chat" / "success_story.csv").is_file()

    def test_encodes_unsafe_storage_segments_without_collision(self, tmp_path):
        svc = EnterpriseSuccessStoryService(_make_config(tmp_path))

        first = svc.save(_source(datasource_id="finance/prod"))
        second = svc.save(_source(call_tool_id="call_2", datasource_id="finance?prod"))

        assert first.storage_key != second.storage_key
        assert ".." not in first.storage_key
        assert (tmp_path / "benchmark" / first.storage_key).is_file()
        assert (tmp_path / "benchmark" / second.storage_key).is_file()

    def test_rejects_existing_file_for_another_datasource(self, tmp_path):
        csv_path = tmp_path / "benchmark" / "ccks_fund" / "gen_sql" / "success_story.csv"
        csv_path.parent.mkdir(parents=True)
        original = (
            "question,sql,datasource_id,source_id,session_id,session_link,subagent_name,timestamp\n"
            "q,SELECT 1,datus_enterprise,ss_old,s1,,gen_sql,2026-01-01T00:00:00Z\n"
        )
        csv_path.write_text(original, encoding="utf-8")

        with pytest.raises(SuccessStoryCsvSchemaError):
            EnterpriseSuccessStoryService(_make_config(tmp_path)).save(_source())

        assert csv_path.read_text(encoding="utf-8") == original


class TestMigrateLegacySuccessStory:
    def test_copies_legacy_rows_idempotently_without_deleting_source(self, tmp_path):
        source_path = tmp_path / "benchmark" / "chat" / "success_story.csv"
        source_path.parent.mkdir(parents=True)
        source_text = "question,sql\nold question,SELECT 0\n"
        source_path.write_text(source_text, encoding="utf-8")
        svc = EnterpriseSuccessStoryService(_make_config(tmp_path))

        first = svc.migrate_legacy_file(source_path, datasource_id="ccks_fund", subagent_name="chat")
        second = svc.migrate_legacy_file(source_path, datasource_id="ccks_fund", subagent_name="chat")

        target = tmp_path / "benchmark" / "ccks_fund" / "chat" / "success_story.csv"
        rows = _read_rows(target)
        assert first.migrated_rows == 1
        assert first.skipped_rows == 0
        assert second.migrated_rows == 0
        assert second.skipped_rows == 1
        assert rows[0]["datasource_id"] == "ccks_fund"
        assert rows[0]["subagent_name"] == "chat"
        assert source_path.read_text(encoding="utf-8") == source_text

    def test_rejects_migration_when_v2_file_declares_another_datasource(self, tmp_path):
        source_path = tmp_path / "story.csv"
        source_path.write_text(
            "question,sql,datasource_id,source_id,session_id,session_link,subagent_name,timestamp\n"
            "q,SELECT 1,datus_enterprise,ss_old,s1,,chat,2026-01-01T00:00:00Z\n",
            encoding="utf-8",
        )

        with pytest.raises(SuccessStoryCsvSchemaError):
            EnterpriseSuccessStoryService(_make_config(tmp_path)).migrate_legacy_file(
                source_path,
                datasource_id="ccks_fund",
                subagent_name="chat",
            )

    def test_deduplicates_source_rows_by_source_id(self, tmp_path):
        source_path = tmp_path / "story.csv"
        source_path.write_text(
            "question,sql,datasource_id,source_id,session_id,session_link,subagent_name,timestamp\n"
            "q,SELECT 1,ccks_fund,ss_old,s1,,chat,2026-01-01T00:00:00Z\n"
            "q,SELECT 1,ccks_fund,ss_old,s1,,chat,2026-01-01T00:00:00Z\n",
            encoding="utf-8",
        )

        result = EnterpriseSuccessStoryService(_make_config(tmp_path)).migrate_legacy_file(
            source_path,
            datasource_id="ccks_fund",
            subagent_name="chat",
        )

        target = tmp_path / "benchmark" / "ccks_fund" / "chat" / "success_story.csv"
        assert result.total_rows == 2
        assert result.migrated_rows == 1
        assert result.skipped_rows == 1
        assert [row["source_id"] for row in _read_rows(target)] == ["ss_old"]
