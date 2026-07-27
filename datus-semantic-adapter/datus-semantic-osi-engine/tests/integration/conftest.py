# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Integration fixtures. Gating (integration marker + skip conditions) lives
in the test module — a ``pytestmark`` in a conftest is not applied by pytest."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "orders"


@pytest.fixture(scope="session")
def model_path() -> str:
    return str(FIXTURES / "model.yaml")


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory) -> str:
    db = tmp_path_factory.mktemp("osi") / "orders.db"
    subprocess.run(
        ["duckdb", str(db)],
        input=(FIXTURES / "seed.sql").read_bytes(),
        check=True,
        capture_output=True,
    )
    return str(db)
