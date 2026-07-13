# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""The OSI package registers an `osi` semantic adapter."""

from datus_semantic_core.registry import SemanticAdapterRegistry


def test_register_adds_osi_adapter(monkeypatch):
    import datus_semantic_osi

    monkeypatch.setattr(
        SemanticAdapterRegistry,
        "_adapters",
        {
            key: value
            for key, value in SemanticAdapterRegistry._adapters.items()
            if key != "osi"
        },
    )
    monkeypatch.setattr(
        SemanticAdapterRegistry,
        "_factories",
        {
            key: value
            for key, value in SemanticAdapterRegistry._factories.items()
            if key != "osi"
        },
    )
    monkeypatch.setattr(
        SemanticAdapterRegistry,
        "_metadata",
        {
            key: value
            for key, value in SemanticAdapterRegistry._metadata.items()
            if key != "osi"
        },
    )

    assert not SemanticAdapterRegistry.is_registered("osi")
    datus_semantic_osi.register()
    assert SemanticAdapterRegistry.is_registered("osi")
