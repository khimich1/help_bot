"""Тесты LangChain tools (tasks)."""

import json

from interior_studio.agent.tools import make_tools
from interior_studio.services import project_service


def test_create_tasks_tool(db_session):
    p = project_service.create_project(db_session, "Ивановы")
    db_session.commit()

    tools = make_tools(db_session, user_id=111111111)
    create_tool = next(t for t in tools if t.name == "create_tasks")
    raw = create_tool.invoke(
        {
            "project_id": p.id,
            "tasks": [
                {"title": "Заказать плитку", "due_date": "2026-07-04"},
                {"title": "Свет", "assignee_user_id": 222222222},
            ],
        }
    )
    data = json.loads(raw)
    assert data["count"] == 2


def test_complete_task_tool(db_session):
    from interior_studio.services import task_service

    p = project_service.create_project(db_session, "Ивановы")
    created = task_service.create_tasks(
        db_session,
        p.id,
        [{"title": "Плитку заказать"}],
        created_by=111111111,
    )
    db_session.commit()
    task_id = created.created[0].id

    tools = make_tools(db_session, user_id=111111111)
    complete_tool = next(t for t in tools if t.name == "complete_task")
    raw = complete_tool.invoke({"task_id": task_id})
    data = json.loads(raw)
    assert data["ok"] is True
    assert data["task"]["status"] == "done"
