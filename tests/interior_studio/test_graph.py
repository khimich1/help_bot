"""Smoke-тесты ReAct-графа."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from interior_studio.agent.graph import create_studio_agent
from interior_studio.agent.prompt import build_system_prompt
from interior_studio.agent.tools import make_tools


def test_graph_compiles_and_invokes_with_mock_llm(db_session):
    tools = make_tools(db_session, user_id=111111111)
    prompt = build_system_prompt(111111111)

    final = AIMessage(content="Готово, показала проекты.")
    mock_llm = MagicMock()
    mock_bound = MagicMock()
    mock_bound.invoke.return_value = final
    mock_llm.bind_tools.return_value = mock_bound
    mock_llm.invoke.return_value = AIMessage(content="reasoning")

    with patch("interior_studio.agent.graph.create_chat_llm", return_value=mock_llm):
        agent = create_studio_agent(tools, prompt)
        result = agent.invoke(
            {"messages": [HumanMessage(content="Привет")]},
            config={"recursion_limit": 10},
        )

    assert result["messages"]
    assert any(isinstance(m, AIMessage) for m in result["messages"])
