"""Downstream CSV hardening coverage kept out of the upstream test file."""

from datus.utils.csv_utils import sanitize_csv_field


def test_sanitize_csv_field_prefixes_formula_after_leading_padding():
    assert sanitize_csv_field("\t=SUM(A1:A3)") == "'\t=SUM(A1:A3)"
    assert sanitize_csv_field("\r=SUM(A1:A3)") == "'\r=SUM(A1:A3)"
    assert sanitize_csv_field("\n=SUM(A1:A3)") == "'\n=SUM(A1:A3)"
    assert sanitize_csv_field(" =SUM(A1:A3)") == "' =SUM(A1:A3)"
