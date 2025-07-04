from pydantic import BaseModel, Field

from datus.schemas.base import BaseInput, BaseResult
from datus.schemas.node_models import SqlTask


class SemanticModelMeta(BaseModel):
    """
    Meta data for semantic model.
    """

    catalog_name: str = Field(default="", description="The catalog name of the semantic model")
    database_name: str = Field(default="", description="The database name of the semantic model")
    schema_name: str = Field(default="", description="The schema name of the semantic model")
    table_name: str = Field(default="", description="The table name of the semantic model")
    layer1: str = Field(default="", description="The layer1 of the semantic model")
    layer2: str = Field(default="", description="The layer2 of the semantic model")
    domain: str = Field(default="", description="The domain of the semantic model")


class GenerateSemanticModelInput(BaseInput):
    """
    Input model for generating semantic model.
    """

    sql_task: SqlTask = Field(..., description="The SQL task to generate semantic model from")
    sql_query: str = Field(..., description="The SQL query to generate semantic model from")
    semantic_model_meta: SemanticModelMeta = Field(..., description="The semantic model meta of this request")
    prompt_version: str = Field(default="1.0", description="Version for prompt")


class GenerateSemanticModelResult(BaseResult):
    """
    Result model for generating semantic model.
    """

    semantic_model_meta: SemanticModelMeta = Field(..., description="The semantic model meta of this request")
    semantic_model_file: str = Field(..., description="The semantic model file of this request")
