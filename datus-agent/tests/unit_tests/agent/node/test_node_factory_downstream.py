"""Downstream node factory coverage kept out of the upstream test file."""

from unittest.mock import MagicMock, patch

from datus.agent.node.node_factory import create_interactive_node


def _mock_agent_config(**kwargs):
    config = MagicMock()
    config.agentic_nodes = kwargs.get("agentic_nodes", None)
    return config


@patch("datus.agent.node.chat_agentic_node.ChatAgenticNode.__init__", return_value=None)
def test_custom_chat_node_uses_chat_agentic_node(mock_init):
    config = _mock_agent_config(agentic_nodes={"custom_chat": {"node_class": "chat", "mcp": "filesystem"}})

    create_interactive_node("custom_chat", config, node_id="session-1")

    mock_init.assert_called_once()
    call_kwargs = mock_init.call_args[1]
    assert call_kwargs["node_id"] == "session-1"
    assert call_kwargs["node_type"] == "chat"
    assert call_kwargs["node_name"] == "custom_chat"
