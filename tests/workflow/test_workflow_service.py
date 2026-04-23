"""Unit tests for Phase 3 workflow service helpers."""

import pytest

from openagentic.workflow import service


def test_validate_definition_accepts_valid_dag():
    definition = {
        "nodes": [
            {"id": "input_node", "type": "value", "config": {"value": "hello"}},
            {"id": "tool_node", "type": "tool", "config": {"tool_name": "echo", "arg": "{{nodes.input_node}}"}},
        ],
        "edges": [{"from": "input_node", "to": "tool_node"}],
    }
    service.validate_definition(definition)


def test_validate_definition_rejects_cycle():
    definition = {
        "nodes": [
            {"id": "a", "type": "value", "config": {"value": "1"}},
            {"id": "b", "type": "value", "config": {"value": "2"}},
        ],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }
    with pytest.raises(ValueError, match="cycle"):
        service.validate_definition(definition)


def test_render_template_supports_input_and_node_refs():
    rendered = service._render_template(  # noqa: SLF001
        "user={{input.user}};answer={{nodes.calc}}",
        {"input": {"user": "allen"}, "nodes": {"calc": "42"}},
    )
    assert rendered == "user=allen;answer=42"


@pytest.mark.asyncio
async def test_execute_node_tool_and_value():
    value_output = await service._execute_node("value", {"value": "ok"})  # noqa: SLF001
    assert value_output == "ok"

    tool_output = await service._execute_node(  # noqa: SLF001
        "tool", {"tool_name": "echo", "arg": "ping"}
    )
    assert tool_output == "ping"

