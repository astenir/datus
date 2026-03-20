# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for exceptions module."""

import pytest
from datus_db_core.exceptions import DatusDbException, ErrorCode


class TestErrorCode:
    def test_error_code_has_code_and_desc(self):
        assert ErrorCode.COMMON_UNKNOWN.code == "100000"
        assert "Unknown error" in ErrorCode.COMMON_UNKNOWN.desc

    def test_all_error_codes_have_unique_codes(self):
        codes = [member.code for member in ErrorCode]
        assert len(codes) == len(set(codes)), f"Duplicate error codes found: {[c for c in codes if codes.count(c) > 1]}"

    def test_common_error_codes(self):
        assert ErrorCode.COMMON_FIELD_INVALID.code == "100001"
        assert ErrorCode.COMMON_FIELD_REQUIRED.code == "100003"
        assert ErrorCode.COMMON_UNSUPPORTED.code == "100004"
        assert ErrorCode.COMMON_CONFIG_ERROR.code == "100006"
        assert ErrorCode.COMMON_MISSING_DEPENDENCY.code == "100007"

    def test_db_error_codes(self):
        assert ErrorCode.DB_FAILED.code == "500000"
        assert ErrorCode.DB_CONNECTION_FAILED.code == "500001"
        assert ErrorCode.DB_EXECUTION_ERROR.code == "500006"
        assert ErrorCode.DB_CONSTRAINT_VIOLATION.code == "500011"


class TestDatusDbException:
    def test_basic_exception(self):
        exc = DatusDbException(ErrorCode.COMMON_UNKNOWN)
        assert "100000" in str(exc)
        assert "Unknown error" in str(exc)

    def test_exception_with_custom_message(self):
        exc = DatusDbException(ErrorCode.COMMON_UNKNOWN, message="Something went wrong")
        assert "Something went wrong" in str(exc)
        assert "100000" in str(exc)

    def test_exception_with_message_args(self):
        exc = DatusDbException(
            ErrorCode.COMMON_FIELD_REQUIRED,
            message_args={"field_name": "username"},
        )
        assert "username" in str(exc)
        assert "100003" in str(exc)

    def test_exception_is_exception(self):
        exc = DatusDbException(ErrorCode.COMMON_UNKNOWN)
        assert isinstance(exc, Exception)

    def test_exception_can_be_raised_and_caught(self):
        with pytest.raises(DatusDbException) as exc_info:
            raise DatusDbException(
                ErrorCode.DB_CONNECTION_FAILED,
                message_args={"error_message": "timeout"},
            )
        assert "500001" in str(exc_info.value)
        assert "timeout" in str(exc_info.value)

    def test_exception_code_attribute(self):
        exc = DatusDbException(ErrorCode.DB_FAILED)
        assert exc.code == ErrorCode.DB_FAILED

    def test_db_error_message_formatting(self):
        exc = DatusDbException(
            ErrorCode.DB_EXECUTION_SYNTAX_ERROR,
            message_args={"error_message": "near 'SELCT': syntax error"},
        )
        assert "syntax error" in str(exc)
