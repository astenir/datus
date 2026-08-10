"""Downstream request-scoped prompt and template identity coverage."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from datus.prompts.prompt_manager import PromptManager, capture_prompt_template_identities, get_prompt_manager
from datus.utils.path_manager import DatusPathManager, reset_path_manager


@pytest.fixture(autouse=True)
def reset_prompt_context():
    reset_path_manager()
    PromptManager.clear_env_cache()
    yield
    reset_path_manager()
    PromptManager.clear_env_cache()


def _write_template(directory: Path, template_name: str, version: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{template_name}_{version}.j2"
    path.write_text(content, encoding="utf-8")
    return path


def _make_manager(
    tmp_path: Path,
    *,
    path_manager: DatusPathManager | None = None,
    agent_config: object | None = None,
) -> PromptManager:
    manager = PromptManager(path_manager=path_manager, agent_config=agent_config)
    manager.default_templates_dir = tmp_path / "default_templates"
    manager.default_templates_dir.mkdir(parents=True, exist_ok=True)
    return manager


def test_render_template_uses_request_scoped_agent_prompt_content(tmp_path):
    path_manager = DatusPathManager(tmp_path / "tenant_home")
    agent_config = SimpleNamespace(
        path_manager=path_manager,
        agentic_nodes={
            "chat_custom": {
                "system_prompt": "chat_custom",
                "prompt_template": "Custom prompt for {{ audience }}",
                "prompt_version": "1.0",
            }
        },
    )

    manager = get_prompt_manager(agent_config=agent_config)

    assert manager.render_template("chat_custom_system", "1.0", audience="analysts") == "Custom prompt for analysts"


def test_request_scoped_agent_prompt_does_not_leak_between_configs(tmp_path):
    path_manager = DatusPathManager(tmp_path / "tenant_home")
    first_config = SimpleNamespace(
        path_manager=path_manager,
        agentic_nodes={
            "chat_custom": {
                "system_prompt": "chat_custom",
                "prompt_template": "First request",
                "prompt_version": "1.0",
            }
        },
    )
    second_config = SimpleNamespace(path_manager=path_manager, agentic_nodes={})

    assert get_prompt_manager(agent_config=first_config).render_template("chat_custom_system", "1.0") == "First request"
    with pytest.raises(FileNotFoundError):
        get_prompt_manager(agent_config=second_config).render_template("chat_custom_system", "1.0")


def test_template_identity_tracks_resolved_version_source_and_content(tmp_path):
    path_manager = DatusPathManager(tmp_path / "tenant_home")
    manager = _make_manager(tmp_path, path_manager=path_manager)
    _write_template(manager.default_templates_dir, "greet", "1.0", "v1")
    user_path = _write_template(manager.user_templates_dir, "greet", "1.1", "v1.1")

    identity = manager.get_template_identity("greet", None)

    assert identity["template_name"] == "greet"
    assert identity["requested_version"] == ""
    assert identity["resolved_version"] == "1.1"
    assert identity["source"] == "user"
    assert identity["content_sha256"]
    assert identity["revision_sha256"]

    user_path.write_text("v1.1 changed", encoding="utf-8")
    changed = manager.get_template_identity("greet", None)
    assert changed["content_sha256"] != identity["content_sha256"]
    assert changed["revision_sha256"] != identity["revision_sha256"]


def test_template_identity_includes_static_jinja_dependencies(tmp_path):
    path_manager = DatusPathManager(tmp_path / "tenant_home")
    manager = _make_manager(tmp_path, path_manager=path_manager)
    _write_template(manager.default_templates_dir, "greet", "1.0", "{% include '_shared.j2' %}")
    partial = manager.default_templates_dir / "_shared.j2"
    partial.write_text("shared v1", encoding="utf-8")

    before = manager.get_template_identity("greet", "1.0")
    partial.write_text("shared v2", encoding="utf-8")
    after = manager.get_template_identity("greet", "1.0")

    assert before["content_sha256"] == after["content_sha256"]
    assert before["revision_sha256"] != after["revision_sha256"]


def test_render_template_reloads_user_override_for_cached_include(tmp_path):
    path_manager = DatusPathManager(tmp_path / "tenant_home")
    manager = _make_manager(tmp_path, path_manager=path_manager)
    _write_template(manager.default_templates_dir, "greet", "1.0", "{% include '_shared.j2' %}")
    (manager.default_templates_dir / "_shared.j2").write_text("builtin", encoding="utf-8")

    assert manager.render_template("greet", "1.0") == "builtin"

    manager.user_templates_dir.mkdir(parents=True, exist_ok=True)
    (manager.user_templates_dir / "_shared.j2").write_text("user override", encoding="utf-8")

    assert manager.render_template("greet", "1.0") == "user override"


def test_capture_records_actual_runtime_template_resolution(tmp_path):
    path_manager = DatusPathManager(tmp_path / "tenant_home")
    agent_config = SimpleNamespace(
        path_manager=path_manager,
        agentic_nodes={
            "chat_custom": {
                "system_prompt": "chat_custom",
                "prompt_template": "Custom {{ audience }}",
                "prompt_version": "7.0",
            }
        },
    )
    manager = _make_manager(tmp_path, agent_config=agent_config)

    with capture_prompt_template_identities() as identities:
        rendered = manager.render_template("chat_custom_system", "7.0", audience="analysts")

    assert rendered == "Custom analysts"
    assert identities == [
        {
            "template_name": "chat_custom_system",
            "requested_version": "7.0",
            "resolved_version": "7.0",
            "source": "runtime",
            "content_sha256": identities[0]["content_sha256"],
            "revision_sha256": identities[0]["revision_sha256"],
        }
    ]


def test_capture_records_raw_template_resolution(tmp_path):
    path_manager = DatusPathManager(tmp_path / "tenant_home")
    manager = _make_manager(tmp_path, path_manager=path_manager)
    _write_template(manager.default_templates_dir, "raw_system", "1.0", "raw prompt")

    with capture_prompt_template_identities() as identities:
        content = manager.get_raw_template("raw_system", "1.0")

    assert content == "raw prompt"
    assert identities[0]["template_name"] == "raw_system"
    assert identities[0]["resolved_version"] == "1.0"
    assert identities[0]["source"] == "builtin"
    assert identities[0]["content_sha256"]
