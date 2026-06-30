"""LangChain tools для Interior Studio Assistant."""

from __future__ import annotations

import json
from typing import Callable

from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy.orm import Session

from interior_studio.agent.tools import projects as project_tools
from interior_studio.agent.tools import tasks as task_tools


def make_tools(session: Session, user_id: int) -> list[BaseTool]:
    """Собирает tools с инъекцией session и user_id (LLM их не видит)."""

    def bind(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return fn(session, user_id, *args, **kwargs)

        return wrapper

    tool_defs = [
        ("list_projects", project_tools.list_projects_impl, project_tools.LIST_PROJECTS_SCHEMA),
        ("create_project", project_tools.create_project_impl, project_tools.CREATE_PROJECT_SCHEMA),
        ("get_active_project", project_tools.get_active_project_impl, project_tools.GET_ACTIVE_PROJECT_SCHEMA),
        ("set_active_project", project_tools.set_active_project_impl, project_tools.SET_ACTIVE_PROJECT_SCHEMA),
        ("create_tasks", task_tools.create_tasks_impl, task_tools.CREATE_TASKS_SCHEMA),
        ("list_tasks", task_tools.list_tasks_impl, task_tools.LIST_TASKS_SCHEMA),
        ("complete_task", task_tools.complete_task_impl, task_tools.COMPLETE_TASK_SCHEMA),
    ]

    tools: list[BaseTool] = []
    for name, impl, schema in tool_defs:
        tools.append(
            StructuredTool.from_function(
                func=bind(impl),
                name=name,
                description=schema["description"],
                args_schema=schema["args_schema"],
            )
        )
    return tools
