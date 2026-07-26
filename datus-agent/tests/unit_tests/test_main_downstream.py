"""Downstream CLI coverage for success-story migration."""

import sys
from unittest.mock import MagicMock, patch

from datus.main import create_parser, main


def test_migrate_success_stories_action_parsed():
    parser = create_parser()
    args = parser.parse_args(
        [
            "migrate-success-stories",
            "--source",
            "/tmp/story.csv",
            "--datasource",
            "ccks_fund",
            "--subagent",
            "chat",
        ]
    )
    assert args.action == "migrate-success-stories"
    assert args.source == "/tmp/story.csv"
    assert args.datasource == "ccks_fund"
    assert args.subagent == "chat"


def test_migration_runs_before_agent_initialization():
    mock_config = MagicMock(project_name="demo")
    mock_migration = MagicMock(
        migrated_rows=2,
        total_rows=3,
        storage_key="ccks_fund/chat/success_story.csv",
        skipped_rows=1,
    )
    mock_service = MagicMock()
    mock_service.migrate_legacy_file.return_value = mock_migration

    with (
        patch("datus.main.configure_logging"),
        patch("datus.main.setup_exception_handler"),
        patch("datus.main.load_agent_config", return_value=mock_config),
        patch("datus.main.Agent") as mock_agent,
        patch(
            "datus_enterprise.services.success_story_service.EnterpriseSuccessStoryService",
            return_value=mock_service,
        ) as mock_service_class,
        patch("datus.cli.cli_styles.print_success") as mock_print_success,
        patch.object(
            sys,
            "argv",
            [
                "datus",
                "migrate-success-stories",
                "--source",
                "/tmp/story.csv",
                "--datasource",
                "ccks_fund",
                "--subagent",
                "chat",
            ],
        ),
    ):
        result = main()

    assert result == 0
    mock_service_class.assert_called_once_with(mock_config, project_id="demo")
    mock_service.migrate_legacy_file.assert_called_once_with(
        "/tmp/story.csv",
        datasource_id="ccks_fund",
        subagent_name="chat",
    )
    mock_print_success.assert_called_once()
    mock_agent.assert_not_called()


def test_migration_os_error_returns_one_without_agent_initialization():
    mock_config = MagicMock(project_name="demo")
    mock_service = MagicMock()
    mock_service.migrate_legacy_file.side_effect = OSError("legacy file is missing")

    with (
        patch("datus.main.configure_logging"),
        patch("datus.main.setup_exception_handler"),
        patch("datus.main.load_agent_config", return_value=mock_config),
        patch("datus.main.Agent") as mock_agent,
        patch(
            "datus_enterprise.services.success_story_service.EnterpriseSuccessStoryService",
            return_value=mock_service,
        ),
        patch("datus.cli.cli_styles.print_error") as mock_print_error,
        patch.object(
            sys,
            "argv",
            [
                "datus",
                "migrate-success-stories",
                "--source",
                "/tmp/missing.csv",
                "--datasource",
                "ccks_fund",
            ],
        ),
    ):
        result = main()

    assert result == 1
    mock_print_error.assert_called_once()
    mock_agent.assert_not_called()
