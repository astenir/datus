"""Downstream request-scoped prompt isolation coverage."""

from types import SimpleNamespace

import pytest

from datus.prompts.prompt_manager import PromptManager, get_prompt_manager
from datus.utils.path_manager import DatusPathManager, reset_path_manager


@pytest.fixture(autouse=True)
def reset_prompt_context():
    reset_path_manager()
    PromptManager.clear_env_cache()
    yield
    reset_path_manager()
    PromptManager.clear_env_cache()


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
