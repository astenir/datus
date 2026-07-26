"""Downstream request-contract tests for KB bootstrap models."""

import pytest
from pydantic import ValidationError

from datus.api.models.kb_downstream import BootstrapKbInput


def test_datasource_id_is_required():
    with pytest.raises(ValidationError):
        BootstrapKbInput(components=["metadata"])


def test_datasource_id_is_trimmed():
    request = BootstrapKbInput(datasource_id="  ccks_fund  ", components=["metadata"])

    assert request.datasource_id == "ccks_fund"


def test_blank_datasource_id_is_rejected():
    with pytest.raises(ValidationError):
        BootstrapKbInput(datasource_id="   ", components=["metadata"])


def test_refresh_profile_strategy_accepts_semantic_yaml():
    request = BootstrapKbInput(
        datasource_id="demo",
        components=["semantic_model"],
        strategy="refresh-profile",
        success_story="stories.csv",
        semantic_yaml="semantic/orders.yml",
    )

    assert request.strategy == "refresh-profile"
    assert request.semantic_yaml == "semantic/orders.yml"
