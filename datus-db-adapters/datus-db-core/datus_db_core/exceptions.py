# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from enum import Enum
from typing import Any, Optional


class ErrorCode(Enum):
    """Error codes for Datus database exceptions."""

    # Common errors
    COMMON_UNKNOWN = ("100000", "Unknown error occurred")
    COMMON_FIELD_INVALID = (
        "100001",
        "Unexpected value of {field_name}, expected value: {expected_values}, your value: {your_value}",
    )
    COMMON_INVALID_PARAMETER = ("100002", "Invalid parameter: {error_message}")
    COMMON_FIELD_REQUIRED = ("100003", "Missing required field: {field_name}")
    COMMON_UNSUPPORTED = ("100004", "Unsupported value `{your_value}` for field `{field_name}`")
    COMMON_CONFIG_ERROR = ("100006", "Configuration error: {config_error}")
    COMMON_MISSING_DEPENDENCY = ("100007", "Missing required dependency: {dependency}")

    # Database errors
    DB_FAILED = ("500000", "Database operation failed. Error details: {error_message}")
    DB_CONNECTION_FAILED = ("500001", "Failed to establish connection to database. Error details: {error_message}")
    DB_CONNECTION_TIMEOUT = ("500002", "Connection to database timed out. Error details: {error_message}")
    DB_AUTHENTICATION_FAILED = (
        "500003",
        "Authentication failed for database. Please check your credentials. Error details: {error_message}",
    )
    DB_PERMISSION_DENIED = (
        "500004",
        "Permission denied when performing '{operation}' on database. Error details: {error_message}",
    )
    DB_EXECUTION_SYNTAX_ERROR = ("500005", "Invalid SQL syntax in query. Error details: {error_message}")
    DB_EXECUTION_ERROR = ("500006", "Failed to execute query on database. Error details: {error_message}")
    DB_EXECUTION_TIMEOUT = ("500007", "Query execution timed out on database. Error details: {error_message}")
    DB_QUERY_METADATA_FAILED = ("500008", "Failed to retrieve metadata for query. Error details: {error_message}")
    DB_CONSTRAINT_VIOLATION = ("500011", "Database constraint violation occurred. Error details: {error_message}")
    DB_TRANSACTION_FAILED = ("500009", "Database transaction failed. Error details: {error_message}")
    DB_TABLE_NOT_EXISTS = ("500010", "Table {table_name} does not exist.")

    def __init__(self, code: str, desc: str):
        self.code = code
        self.desc = desc


class DatusException(Exception):
    """Datus custom exception with error code."""

    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        message_args: Optional[dict[str, Any]] = None,
        *args: object,
    ):
        self.code = code
        self.message_args = message_args or {}
        self.message = self._build_msg(message, message_args)
        super().__init__(self.message, *args)

    def __str__(self):
        return self.message

    def _build_msg(self, message: Optional[str] = None, message_args: Optional[dict[str, Any]] = None) -> str:
        if message:
            final_message = message
        elif message_args:
            final_message = self.code.desc.format(**message_args)
        else:
            final_message = self.code.desc
        return f"error_code={self.code.code}, error_message={final_message}"
