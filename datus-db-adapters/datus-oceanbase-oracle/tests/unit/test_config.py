from datus_oceanbase_oracle import OceanBaseOracleConfig


def test_config_accepts_schema_alias_and_uppercases_default_schema():
    config = OceanBaseOracleConfig(
        username="app@oracle_tenant#obcluster",
        password="secret",
        schema="app",
        jar_path="/opt/oceanbase-client.jar",
    )

    assert config.schema_name == "APP"


def test_config_defaults_schema_to_base_username():
    config = OceanBaseOracleConfig(
        username="app@oracle_tenant#obcluster",
        password="secret",
        jar_path="/opt/oceanbase-client.jar",
    )

    assert config.schema_name == "APP"
