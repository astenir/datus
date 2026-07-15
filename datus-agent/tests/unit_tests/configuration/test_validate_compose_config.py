from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "validate_compose_config.py"
SPEC = importlib.util.spec_from_file_location("validate_compose_config", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
validate_compose_config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_compose_config)


def _write_models_file(tmp_path: Path, *, deepseek_key: str = "real-key", embedding_model: str = "embed-v1") -> Path:
    path = tmp_path / "models.yml"
    path.write_text(
        f"""
providers:
  deepseek:
    api_key: {deepseek_key}
models:
  compose_embedding:
    type: openai
    model: {embedding_model}
    api_key: real-embedding-key
""",
        encoding="utf-8",
    )
    return path


def _environment(**overrides: str) -> dict[str, str]:
    env = {
        "DATUS_TARGET_PROVIDER": "deepseek",
        "DATUS_TARGET_MODEL": "deepseek-v4-flash",
        "DATUS_EMBEDDING_MODEL_KEY": "compose_embedding",
        "DATUS_EMBEDDING_MODEL_NAME": "embed-v1",
        "DATUS_EMBEDDING_DIM_SIZE": "1024",
    }
    env.update(overrides)
    return env


def test_validate_models_file_accepts_complete_configuration(tmp_path):
    errors = validate_compose_config.validate_models_file(_write_models_file(tmp_path), _environment())

    assert errors == []


def test_validate_models_file_rejects_placeholder_credentials(tmp_path):
    errors = validate_compose_config.validate_models_file(
        _write_models_file(tmp_path, deepseek_key="change-me"),
        _environment(),
    )

    assert "placeholder or empty credential: providers.deepseek.api_key" in errors


def test_validate_models_file_rejects_embedding_name_mismatch(tmp_path):
    errors = validate_compose_config.validate_models_file(
        _write_models_file(tmp_path, embedding_model="other-embedding"),
        _environment(),
    )

    assert any("must match DATUS_EMBEDDING_MODEL_NAME" in error for error in errors)


def test_validate_models_file_rejects_missing_file_and_invalid_dimension(tmp_path):
    missing_errors = validate_compose_config.validate_models_file(tmp_path / "missing.yml", _environment())
    dimension_errors = validate_compose_config.validate_models_file(
        _write_models_file(tmp_path),
        _environment(DATUS_EMBEDDING_DIM_SIZE="0"),
    )

    assert missing_errors == [f"model configuration file not found: {tmp_path / 'missing.yml'}"]
    assert "DATUS_EMBEDDING_DIM_SIZE must be a positive integer" in dimension_errors
