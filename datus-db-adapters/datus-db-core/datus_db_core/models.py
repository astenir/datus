# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TABLE_TYPE = Literal["table", "view", "mv", "full"]

MAX_SQL_RESULT_LENGTH = int(os.getenv("MAX_SQL_RESULT_LENGTH", 2000))


class BaseInput(BaseModel):
    """Base class for node input data validation."""

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_str(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_str(cls, json_str: str) -> "BaseInput":
        return cls.model_validate_json(json_str)


class BaseResult(BaseModel):
    """Base class for node result data validation."""

    success: bool = Field(..., description="Indicates whether the operation was successful")
    error: Optional[str] = Field(None, description="Error message if operation failed")

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class ExecuteSQLInput(BaseInput):
    """Input model for SQL execution."""

    database_name: str = Field(default="", description="The name of the database")
    sql_query: str = Field(..., description="The SQL query to execute")
    result_format: str = Field(default="csv", description="Format of the result: 'csv' or 'arrow' or 'list'")


class ExecuteSQLResult(BaseResult):
    """Result model for SQL execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    sql_query: Optional[str] = Field("", description="The SQL query to execute")
    row_count: Optional[int] = Field(None, description="The number of rows returned")
    sql_return: Any = Field(default=None, description="The result of SQL execution (string or Arrow data)")
    result_format: str = Field(default="", description="Format of the result: 'csv' or 'arrow' or 'pandas' or 'list'")

    def compact_result(self) -> str:
        sql_result = ""
        if hasattr(self.sql_return, "to_csv"):
            sql_result = self.sql_return.to_csv(index=False)
        else:
            sql_result = str(self.sql_return)
        truncated_return = (
            (sql_result[:MAX_SQL_RESULT_LENGTH] + "...")
            if sql_result and len(sql_result) > MAX_SQL_RESULT_LENGTH
            else sql_result
        )
        return f"Row count: {self.row_count}\nResult:\n{truncated_return}"
