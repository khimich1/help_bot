"""Тесты LangChain tools (projects)."""

import json

from interior_studio.agent.tools import make_tools


def test_list_projects_tool(db_session):
    from interior_studio.services import project_service

    project_service.create_project(db_session, "Ивановы")
    db_session.commit()

    tools = make_tools(db_session, user_id=111111111)
    list_tool = next(t for t in tools if t.name == "list_projects")
    raw = list_tool.invoke({})
    data = json.loads(raw)
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "Ивановы"


def test_set_active_project_tool(db_session):
    from interior_studio.services import project_service

    p = project_service.create_project(db_session, "Петровы")
    db_session.commit()

    tools = make_tools(db_session, user_id=111111111)
    set_tool = next(t for t in tools if t.name == "set_active_project")
    raw = set_tool.invoke({"project_id": p.id})
    data = json.loads(raw)
    assert data["ok"] is True
    assert data["project"]["name"] == "Петровы"
