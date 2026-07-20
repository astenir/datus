from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parents[4]


def _load_yaml(relative_path: str):
    return yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def _env_keys(relative_path: str) -> set[str]:
    keys = set()
    for line in (REPO_ROOT / relative_path).read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0])
    return keys


def test_root_compose_defaults_to_loopback_and_wires_credential_secrets():
    compose = _load_yaml("docker-compose.yml")
    services = compose["services"]

    for service_name in ("postgres", "userinfo", "api", "web"):
        for published_port in services[service_name]["ports"]:
            assert published_port.startswith("${DATUS_BIND_ADDRESS:-127.0.0.1}:")

    api_environment = services["api"]["environment"]
    assert "DATUS_USER_MODEL_CREDENTIAL_SECRET" in api_environment
    assert "DATUS_USER_DATASOURCE_SECRET" in api_environment
    assert "DATUS_EMBEDDING_MODEL_KEY" in api_environment
    assert "DATUS_EMBEDDING_MODEL_NAME" in api_environment
    assert "DATUS_EMBEDDING_DIM_SIZE" in api_environment
    assert "migrate_compose_credential_secrets.py" in services["api"]["command"][2]
    assert "validate_compose_config.py" in services["api"]["command"][2]


def test_compose_environment_template_and_gitignore_contract():
    env_keys = _env_keys(".env.compose.example")
    gitignore_lines = set((REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())

    assert "DATUS_BIND_ADDRESS" in env_keys
    assert "DATUS_EMBEDDING_MODEL_NAME" in env_keys
    assert "DATUS_EMBEDDING_DIM_SIZE" in env_keys
    assert "/.env" in gitignore_lines


def test_compose_embedding_configuration_uses_deployment_values():
    agent = _load_yaml("datus-agent/conf/agent.compose.yml")["agent"]
    storage = agent["storage"]["database"]

    assert storage["model_name"] == "${DATUS_EMBEDDING_MODEL_NAME:-Qwen/Qwen3-Embedding-0.6B}"
    assert storage["dim_size"] == "${DATUS_EMBEDDING_DIM_SIZE:-1024}"
    assert storage["target_model"] == "${DATUS_EMBEDDING_MODEL_KEY:-compose_embedding}"


def test_packaged_provider_catalog_matches_source_catalog():
    assert (REPO_ROOT / "datus-agent/conf/providers.yml").read_bytes() == (
        REPO_ROOT / "datus-agent/datus/conf/providers.yml"
    ).read_bytes()
