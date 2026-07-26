"""Enterprise CLI command for migrating legacy success-story CSV files."""

from __future__ import annotations

import argparse
from typing import Any


def register_parser(subparsers: Any, global_parser: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "migrate-success-stories",
        help="Copy a legacy success-story CSV into the datasource-isolated layout",
        parents=[global_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Path to the legacy success-story CSV",
    )
    parser.add_argument(
        "--datasource",
        type=str,
        required=True,
        help="Canonical datasource shared by every row in the legacy CSV",
    )
    parser.add_argument(
        "--subagent",
        type=str,
        default="chat",
        help="Subagent storage group for the migrated rows (default: chat)",
    )


def run(args: argparse.Namespace, agent_config: Any) -> int:
    from rich.console import Console

    from datus.cli.cli_styles import print_error, print_success
    from datus_enterprise.services.success_story_service import EnterpriseSuccessStoryService

    try:
        migration = EnterpriseSuccessStoryService(
            agent_config,
            project_id=getattr(agent_config, "project_name", "default"),
        ).migrate_legacy_file(
            args.source,
            datasource_id=args.datasource,
            subagent_name=args.subagent,
        )
    except OSError as exc:
        print_error(Console(), str(exc))
        return 1

    print_success(
        Console(),
        (
            f"Migrated {migration.migrated_rows}/{migration.total_rows} rows to "
            f"{migration.storage_key}; skipped {migration.skipped_rows} existing rows."
        ),
        symbol=True,
    )
    return 0
