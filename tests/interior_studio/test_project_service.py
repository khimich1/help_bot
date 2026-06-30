"""Тесты project_service и user_context."""

import pytest

from interior_studio.services import project_service, user_context


def test_list_and_create_project(db_session):
    p1 = project_service.create_project(db_session, "Ивановы")
    p2 = project_service.create_project(db_session, "Петровы")
    db_session.commit()

    projects = project_service.list_projects(db_session)
    assert len(projects) == 2
    assert projects[0].name == "Ивановы"
    assert projects[1].name == "Петровы"
    assert p1.id != p2.id


def test_create_duplicate_project_raises(db_session):
    project_service.create_project(db_session, "Ивановы")
    db_session.commit()
    with pytest.raises(project_service.ProjectAlreadyExistsError):
        project_service.create_project(db_session, "Ивановы")


def test_find_matching_projects(db_session):
    project_service.create_project(db_session, "Ивановы")
    project_service.create_project(db_session, "Ивановы дача")
    project_service.create_project(db_session, "Петровы")
    db_session.commit()

    matches = project_service.find_matching_projects(db_session, "Иванов")
    assert len(matches) == 2


def test_active_project_flow(db_session):
    p = project_service.create_project(db_session, "Сидоровы")
    db_session.commit()

    user_id = 111111111
    active = user_context.get_active_project(db_session, user_id)
    assert active.project_id is None

    ok, err = user_context.set_active_project(db_session, user_id, p.id)
    assert ok is True
    assert err is None
    db_session.commit()

    active = user_context.get_active_project(db_session, user_id)
    assert active.project_id == p.id
    assert active.name == "Сидоровы"
