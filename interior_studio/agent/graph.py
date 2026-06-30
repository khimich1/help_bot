"""ReAct-граф Interior Studio Assistant (паттерн airline_react_agent)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, MessagesState, START, StateGraph
from langgraph.prebuilt import ToolNode

from interior_studio.llm import create_chat_llm


def create_studio_agent(tools: list[BaseTool], system_prompt: str):
    """Создаёт ReAct-агент с заданными tools и system prompt."""
    llm = create_chat_llm()
    llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)

    def agent_node(state: MessagesState):
        messages = state["messages"]
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            messages = [SystemMessage(content=system_prompt)] + messages
        response = llm_with_tools.invoke(messages)

        if response.tool_calls and not response.content:
            tool_info = ", ".join(tc["name"] for tc in response.tool_calls)
            thought = llm.invoke(
                messages
                + [
                    HumanMessage(
                        content=(
                            f"You chose to call: {tool_info}. "
                            "In 1 sentence, explain why this is the right next step. "
                            "Reply with ONLY your reasoning, no tool calls."
                        )
                    )
                ]
            )
            response.content = thought.content

        return {"messages": [response]}

    def should_continue(state: MessagesState):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()
