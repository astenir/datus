from datus.schemas.node_models import ExecuteSQLInput, ExecuteSQLResult
from datus.tools.base import BaseTool
from datus.tools.db_tools.base import BaseSqlConnector


class DBTool(BaseTool):
    DIALECT_SQLITE = "sqlite"
    DIALECT_SNOWFLAKE = "snowflake"

    def __init__(self, connector: BaseSqlConnector, **kwargs):
        super().__init__(**kwargs)
        self.connector = connector

    def execute(self, input_param: ExecuteSQLInput) -> ExecuteSQLResult:
        return self.connector.execute(input_param)
