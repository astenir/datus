# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Half-open time_end contract: the OSI-family exclusive upper bound is
translated once at the query entry point to the inclusive bound MetricFlow
and the adapter's own SQL/row filters expect."""

import pytest

from datus_semantic_osi.adapter import DatusOSIAdapter


def test_exclusive_end_becomes_previous_day():
    assert DatusOSIAdapter._exclusive_end_to_inclusive("2025-10-01") == "2025-09-30"


def test_exclusive_end_crosses_month_and_year_boundaries():
    assert DatusOSIAdapter._exclusive_end_to_inclusive("2025-03-01") == "2025-02-28"
    assert DatusOSIAdapter._exclusive_end_to_inclusive("2026-01-01") == "2025-12-31"


def test_datetime_literal_is_day_truncated():
    assert DatusOSIAdapter._exclusive_end_to_inclusive("2025-10-01 00:00:00") == "2025-09-30"


def test_absent_bound_passes_through():
    assert DatusOSIAdapter._exclusive_end_to_inclusive(None) is None
    assert DatusOSIAdapter._exclusive_end_to_inclusive("") == ""


def test_invalid_literal_is_rejected():
    with pytest.raises(ValueError, match="time_end"):
        DatusOSIAdapter._exclusive_end_to_inclusive("last month")
