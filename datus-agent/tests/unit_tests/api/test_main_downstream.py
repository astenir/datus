"""Downstream API server lifecycle configuration tests."""

import argparse
from unittest.mock import patch

import pytest

from datus.api.main import _build_parser, _run_server


def _server_args(**overrides) -> argparse.Namespace:
    values = {
        "host": "127.0.0.1",
        "port": 8000,
        "reload": False,
        "workers": 1,
        "log_level": "INFO",
        "timeout_graceful_shutdown": 17,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_graceful_shutdown_timeout_defaults_to_ten_seconds():
    assert _build_parser().parse_args([]).timeout_graceful_shutdown == 10


@pytest.mark.parametrize(
    ("overrides", "uses_import_target"),
    [
        ({"reload": True}, True),
        ({"workers": 4}, True),
        ({}, False),
    ],
)
def test_run_server_forwards_graceful_shutdown_timeout(overrides, uses_import_target):
    args = _server_args(**overrides)

    with (
        patch("datus.api.service.create_app", return_value=object()),
        patch("datus.api.main.uvicorn.run") as run,
        patch("datus.api.main.uvicorn.Config") as config,
        patch("datus.api.main.uvicorn.Server") as server,
        patch("datus.api.main.asyncio.run"),
    ):
        _run_server(args, argparse.Namespace())

    if uses_import_target:
        assert run.call_args.kwargs["timeout_graceful_shutdown"] == 17
    else:
        assert config.call_args.kwargs["timeout_graceful_shutdown"] == 17
        server.assert_called_once_with(config.return_value)
