"""Тесты task_service."""

import datetime

from interior_studio.schemas.task import TaskInput
from interior_studio.services import project_service, task_service


def _setup_project(db_session, name="Ивановы"):
    p = project_service.create_project(db_session, name)
    db_session.commit()
    return p


def test_create_tasks_batch(db_session):
    p = _setup_project(db_session)
    user_id = 111111111
    assignee = 222222222

    result = task_service.create_tasks(
        db_session,
        p.id,
        [
            TaskInput(title="Заказать плитку", due_date="2026-07-04"),
            TaskInput(title="Уточнить срок", assignee_user_id=assignee),
        ],
        created_by=user_id,
    )
    db_session.commit()

    assert result.count == 2
    assert result.created[0].title == "Заказать плитку"
    assert result.created[1].assignee_user_id == assignee


def test_list_tasks_mine_only(db_session):
    p = _setup_project(db_session)
    senya, rita = 111111111, 222222222

    task_service.create_tasks(
        db_session,
        p.id,
        [TaskInput(title="Моя задача", assignee_user_id=senya)],
        created_by=senya,
    )
    task_service.create_tasks(
        db_session,
        p.id,
        [TaskInput(title="Чужая задача", assignee_user_id=rita)],
        created_by=rita,
    )
    db_session.commit()

    mine = task_service.list_tasks(db_session, senya, mine_only=True)
    assert len(mine) == 1
    assert mine[0].title == "Моя задача"


def test_list_tasks_overdue(db_session):
    p = _setup_project(db_session)
    user_id = 111111111
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    task_service.create_tasks(
        db_session,
        p.id,
        [
            TaskInput(title="Просрочено", due_date=yesterday),
            TaskInput(title="В срок", due_date=tomorrow),
        ],
        created_by=user_id,
    )
    db_session.commit()

    overdue = task_service.list_tasks(db_session, user_id, overdue=True)
    assert len(overdue) == 1
    assert overdue[0].title == "Просрочено"


def test_complete_task(db_session):
    p = _setup_project(db_session)
    user_id = 111111111
    created = task_service.create_tasks(
        db_session,
        p.id,
        [TaskInput(title="Плитку заказать")],
        created_by=user_id,
    )
    db_session.commit()
    task_id = created.created[0].id

    result = task_service.complete_task(db_session, user_id, task_id)
    db_session.commit()

    assert result.ok is True
    assert result.task is not None
    assert result.task.status == "done"
    assert result.task.completed_at is not None
