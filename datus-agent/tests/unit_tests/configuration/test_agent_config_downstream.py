"""
Additional unit tests for datus/configuration/agent_config.py

Covers: resolve_env, file_stem_from_uri, DbConfig.filter_kwargs,
BenchmarkConfig.validate, DocumentConfig.from_dict/merge_cli_args,
load_model_config, AgentConfig helper methods.

CI-level: zero external deps, zero network.
"""

import pytest

from datus.configuration.agent_config import (
    AgentConfig,
    DbConfig,
    NodeConfig,
    _parse_single_file_db,
)
from datus.utils.exceptions import DatusException

pytestmark = pytest.mark.ci


class TestResolveEnvDownstream:
    def test_file_db_preserves_full_config_fields(self, tmp_path):
        sqlite_path = tmp_path / "california_schools.sqlite"
        sqlite_path.touch()
        cfg = _parse_single_file_db(
            {
                "type": "sqlite",
                "display_name": "加州学校",
                "path_pattern": "",
                "uri": f"sqlite:///{sqlite_path}",
                "database": "california_schools",
                "enumerate_databases": False,
                "extra": None,
            },
            "sqlite",
        )
        assert cfg.display_name == "加州学校"
        assert cfg.database == "california_schools"
        assert cfg.extra is None


class TestDbConfigFilterKwargsDownstream:
    def test_structured_extra_remains_a_mapping(self, monkeypatch):
        monkeypatch.setenv("DB_SSLMODE", "prefer")
        cfg = DbConfig.filter_kwargs(
            DbConfig, {"type": "postgresql", "extra": {"sslmode": "${DB_SSLMODE}", "timeout_seconds": 30}}
        )
        assert cfg.extra == {"sslmode": "prefer", "timeout_seconds": 30}

    def test_extra_rejects_string_values(self):
        with pytest.raises(DatusException, match="Datasource extra must be a mapping"):
            DbConfig.filter_kwargs(DbConfig, {"type": "postgresql", "extra": "sslmode=prefer"})

    def test_enumerate_databases_is_first_class_bool(self):
        cfg = DbConfig.filter_kwargs(DbConfig, {"type": "postgresql", "enumerate_databases": "true"})
        assert cfg.enumerate_databases is True
        assert not cfg.extra or "enumerate_databases" not in cfg.extra

    def test_enumerate_databases_string_false_is_false(self):
        cfg = DbConfig.filter_kwargs(DbConfig, {"type": "postgresql", "enumerate_databases": "false"})
        assert cfg.enumerate_databases is False


class TestAgentConfigServiceSelectorsDownstream:
    def _make(self, tmp_path, *, services=None, agentic_nodes=None):
        return AgentConfig(
            nodes={"test": NodeConfig(model="test-model", input=None)},
            home=str(tmp_path / "h"),
            target="mock",
            models={"mock": {"type": "openai", "api_key": "k", "model": "m", "base_url": "http://localhost:0"}},
            services=services or {"datasources": {}},
            agentic_nodes=agentic_nodes or {},
            skip_init_dirs=True,
        )

    def test_empty_file_path_pattern_falls_back_to_uri(self, tmp_path):
        sqlite_path = tmp_path / "california_schools.sqlite"
        sqlite_path.touch()
        cfg = self._make(
            tmp_path,
            services={
                "datasources": {
                    "california_schools": {
                        "type": "sqlite",
                        "path_pattern": "",
                        "uri": f"sqlite:///{sqlite_path}",
                        "display_name": "加州学校",
                    }
                }
            },
        )
        datasource = cfg.services.datasources["california_schools"]
        assert datasource.uri == f"sqlite:///{sqlite_path}"
        assert datasource.database == "california_schools"

    def test_non_empty_file_path_pattern_takes_precedence_over_uri(self, tmp_path):
        glob_path = tmp_path / "*.sqlite"
        (tmp_path / "school_a.sqlite").touch()
        cfg = self._make(
            tmp_path,
            services={
                "datasources": {
                    "schools": {"type": "sqlite", "path_pattern": str(glob_path), "uri": "sqlite:///ignored.sqlite"}
                }
            },
        )
        datasource = cfg.services.datasources["schools"]
        assert datasource.path_pattern == str(glob_path)
        assert datasource.uri == ""

    def test_datasources_file_adds_and_overrides_inline_datasources(self, tmp_path):
        datasources_file = tmp_path / "datasources.yml"
        datasources_file.write_text(
            '\ndatasources:\n  inline_pg:\n    type: postgresql\n    host: override-host\n    database: overridden\n    default: false\n  mysql_sales:\n    type: mysql\n    host: mysql-host\n    port: "3306"\n    username: readonly\n    password: secret\n    database: sales\n    default: true\n',
            encoding="utf-8",
        )
        cfg = self._make(
            tmp_path,
            services={
                "datasources_file": str(datasources_file),
                "datasources": {
                    "inline_pg": {"type": "postgresql", "host": "inline-host", "database": "inline", "default": True}
                },
            },
        )
        assert cfg.services.datasources["inline_pg"].host == "override-host"
        assert cfg.services.datasources["inline_pg"].database == "overridden"
        assert cfg.services.datasources["inline_pg"].default is False
        assert cfg.services.datasources["mysql_sales"].type == "mysql"
        assert cfg.services.default_datasource == "mysql_sales"

    def test_datasources_file_accepts_full_agent_fragment(self, tmp_path):
        datasources_file = tmp_path / "datasources.yml"
        datasources_file.write_text(
            "\nagent:\n  services:\n    datasources:\n      warehouse:\n        type: postgresql\n        host: pg-host\n        database: warehouse\n",
            encoding="utf-8",
        )
        cfg = self._make(tmp_path, services={"datasources_file": str(datasources_file), "datasources": {}})
        assert cfg.services.datasources["warehouse"].host == "pg-host"


class TestAgentConfigApiSectionDownstream:
    def _make(self, tmp_path, api=None, enterprise=None):
        from datus.configuration.agent_config import AgentConfig, NodeConfig

        kwargs = dict(
            nodes={"test": NodeConfig(model="test-model", input=None)},
            home=str(tmp_path / "h"),
            target="mock",
            models={"mock": {"type": "openai", "api_key": "k", "model": "m", "base_url": "http://localhost:0"}},
            skip_init_dirs=True,
        )
        if api is not None:
            kwargs["api"] = api
        if enterprise is not None:
            kwargs["enterprise"] = enterprise
        return AgentConfig(**kwargs)

    def test_api_config_resolves_nested_env_values(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATUS_ENTERPRISE_USERINFO_URL", "http://127.0.0.1:8010/userinfo")
        api = {
            "auth_provider": {
                "class": "datus_enterprise.auth_provider:UserInfoBearerAuthProvider",
                "kwargs": {
                    "userinfo_url": "${DATUS_ENTERPRISE_USERINFO_URL}",
                    "principal_fields": ["username", "${DATUS_EXTRA_PRINCIPAL:-department}"],
                },
            }
        }
        cfg = self._make(tmp_path, api=api)
        assert cfg.api_config["auth_provider"]["kwargs"]["userinfo_url"] == "http://127.0.0.1:8010/userinfo"
        assert cfg.api_config["auth_provider"]["kwargs"]["principal_fields"] == ["username", "department"]

    def test_enterprise_config_parsed(self, tmp_path):
        enterprise = {"enabled": True, "authorization_provider": {"class": "pkg.Authz"}}
        cfg = self._make(tmp_path, enterprise=enterprise)
        assert cfg.enterprise_config == enterprise

    def test_enterprise_config_resolves_nested_env_values(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATUS_ENTERPRISE_PG_DSN", "postgresql://datus:datus@127.0.0.1:5433/datus_enterprise")
        enterprise = {
            "enabled": True,
            "audit_sink": {
                "class": "datus_enterprise.postgres_stores:PgAuditSink",
                "kwargs": {"dsn": "${DATUS_ENTERPRISE_PG_DSN}", "min_size": 1},
            },
        }
        cfg = self._make(tmp_path, enterprise=enterprise)
        assert (
            cfg.enterprise_config["audit_sink"]["kwargs"]["dsn"]
            == "postgresql://datus:datus@127.0.0.1:5433/datus_enterprise"
        )
        assert cfg.enterprise_config["audit_sink"]["kwargs"]["min_size"] == 1

    def test_enterprise_config_rejects_non_mapping(self, tmp_path):
        from datus.utils.exceptions import DatusException

        with pytest.raises(DatusException, match="agent.enterprise must be a mapping"):
            self._make(tmp_path, enterprise=True)


class TestProviderConfigurationDispatchDownstream:
    """Cover ``ProviderConfig`` + the three-way dispatch in ``active_model()``.

    Scenarios exercised:
      - legacy string ``target`` continues to index ``agent.models``.
      - structured ``(provider, model)`` synthesizes a ``ModelConfig``
        from ``agent.providers`` plus the injected catalog.
      - ``set_active_*`` helpers mutate in-memory state and persist to
        ``./.datus/config.yml``.
      - ``provider_available`` returns ``True`` when credentials are
        present in overrides or env.
    """

    def _stub_catalog(self):
        return {
            "providers": {
                "openai": {
                    "type": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "default_model": "gpt-4.1",
                    "models": ["gpt-4.1", "gpt-4o"],
                },
                "kimi": {
                    "type": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "api_key_env": "KIMI_API_KEY",
                    "default_model": "kimi-k2.5",
                },
                "openrouter": {
                    "type": "openrouter",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                    "default_model": "anthropic/claude-sonnet-4",
                    "models": ["anthropic/claude-sonnet-4", "openai/gpt-4o"],
                },
            },
            "model_overrides": {"kimi-k2.5": {"temperature": 1.0, "top_p": 0.95}},
        }

    def _make(self, tmp_path, **extra):
        """Build an :class:`AgentConfig` with the stub catalog pre-injected."""
        kwargs = dict(
            nodes={"test": NodeConfig(model="test-model", input=None)},
            home=str(tmp_path / "datus_home"),
            target="legacy",
            models={
                "legacy": {
                    "type": "openai",
                    "api_key": "legacy-key",
                    "model": "legacy-model",
                    "base_url": "https://legacy.example.com",
                }
            },
            project_root=str(tmp_path),
            skip_init_dirs=True,
        )
        kwargs.update(extra)
        cfg = AgentConfig(**kwargs)
        cfg.set_provider_catalog(self._stub_catalog())
        return cfg

    def test_models_file_adds_providers_and_custom_models(self, tmp_path):
        models_file = tmp_path / "models.yml"
        models_file.write_text(
            "\nproviders:\n  openai:\n    api_key: sk-file\n    base_url: https://gateway.example.com/v1\nmodels:\n  private_model:\n    type: openai\n    api_key: private-key\n    model: qwen-plus\n    base_url: https://private.example.com/v1\nmodel_extras:\n  private_model:\n    owner: compose\n",
            encoding="utf-8",
        )
        cfg = self._make(tmp_path, models_file=str(models_file), target_provider="openai", target_model="gpt-4.1")
        active = cfg.active_model()
        assert active.api_key == "sk-file"
        assert active.base_url == "https://gateway.example.com/v1"
        assert cfg.models["private_model"].model == "qwen-plus"
        assert cfg.get_model_extra("private_model") == {"owner": "compose"}

    def test_models_file_can_select_custom_target(self, tmp_path):
        models_file = tmp_path / "models.yml"
        models_file.write_text(
            "\ntarget: private_model\nmodels:\n  private_model:\n    type: openai\n    api_key: private-key\n    model: qwen-plus\n    base_url: https://private.example.com/v1\n",
            encoding="utf-8",
        )
        cfg = self._make(tmp_path, models_file=str(models_file), target="", models={})
        active = cfg.active_model()
        assert active.api_key == "private-key"
        assert active.model == "qwen-plus"

    def test_storage_target_model_resolves_env_key(self, tmp_path, monkeypatch):
        from datus.storage.embedding_models import EMBEDDING_MODELS

        original_models = dict(EMBEDDING_MODELS)
        EMBEDDING_MODELS.clear()
        monkeypatch.setenv("DATUS_TEST_EMBEDDING_KEY", "custom_embedding")
        try:
            cfg = self._make(
                tmp_path,
                models={
                    "legacy": {
                        "type": "openai",
                        "api_key": "legacy-key",
                        "model": "legacy-model",
                        "base_url": "https://legacy.example.com",
                    },
                    "custom_embedding": {
                        "type": "openai",
                        "api_key": "embedding-key",
                        "model": "embedding-model",
                        "base_url": "https://embedding.example.com",
                    },
                },
                storage={
                    "database": {
                        "registry_name": "openai",
                        "model_name": "embedding-model",
                        "dim_size": "1024",
                        "target_model": "${DATUS_TEST_EMBEDDING_KEY}",
                    }
                },
                skip_init_dirs=False,
            )
            assert cfg.storage_configs["database"].openai_config.api_key == "embedding-key"
            assert cfg.storage_configs["database"].dim_size == 1024
        finally:
            EMBEDDING_MODELS.clear()
            EMBEDDING_MODELS.update(original_models)

    def test_metadata_sample_limits_default_and_allow_storage_overrides(self, tmp_path):
        default_cfg = self._make(tmp_path)
        custom_cfg = self._make(
            tmp_path, storage={"database": {"sample_cell_max_chars": "256", "sample_max_chars": "2048"}}
        )
        assert default_cfg.metadata_sample_cell_max_chars == 1000
        assert default_cfg.metadata_sample_max_chars == 8000
        assert custom_cfg.metadata_sample_cell_max_chars == 256
        assert custom_cfg.metadata_sample_max_chars == 2048

    @pytest.mark.parametrize("key,value", [("sample_cell_max_chars", 0), ("sample_max_chars", "invalid")])
    def test_metadata_sample_limits_must_be_positive_integers(self, tmp_path, key, value):
        with pytest.raises(DatusException, match=f"storage.database.{key} must be a positive integer"):
            self._make(tmp_path, storage={"database": {key: value}})
