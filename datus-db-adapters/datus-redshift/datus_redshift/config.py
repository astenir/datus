
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RedshiftConfig(BaseModel):
    """
    Configuration class for Amazon Redshift database connections.
    
    This class uses Pydantic for validation and configuration management.
    It defines all the parameters needed to connect to a Redshift cluster.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    
    host: str = Field(..., description="Redshift cluster endpoint")
    
    
    username: str = Field(..., description="Redshift username")
    
    
    password: str = Field(..., description="Redshift password")

    
    
    
    port: int = Field(default=5439, description="Redshift server port")
    
    
    database: Optional[str] = Field(default=None, description="Default database name")
    
    
    schema_name: Optional[str] = Field(default=None, alias="schema", description="Default schema name")
    
    
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")
    
    
    ssl: bool = Field(default=True, description="Enable SSL connection")
    
    
    iam: bool = Field(default=False, description="Use IAM authentication")
    
    
    cluster_identifier: Optional[str] = Field(default=None, description="Redshift cluster identifier for IAM auth")
    
    
    region: Optional[str] = Field(default=None, description="AWS region for IAM auth")
    
    
    access_key_id: Optional[str] = Field(default=None, description="AWS access key ID for IAM auth")
    secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key for IAM auth")

