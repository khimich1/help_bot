"""Тесты слоя БД."""

from interior_studio.db.connection import init_schema
from interior_studio.db.models import Project, Task, User


def test_init_schema_creates_tables(db_engine):
    init_schema(db_engine)
    from sqlalchemy import inspect

    tables = inspect(db_engine).get_table_names()
    assert "users" in tables
    assert "projects" in tables
    assert "tasks" in tables
    assert "sent_reminders" in tables


def test_create_project_and_task(db_session):
    project = Project(name="Ивановы", status="active")
    db_session.add(project)
    db_session.flush()

    user = User(telegram_user_id=111111111, display_name="Сеня")
    db_session.add(user)
    db_session.flush()

    task = Task(
        project_id=project.id,
        title="Заказать плитку",
        created_by=user.telegram_user_id,
        status="open",
    )
    db_session.add(task)
    db_session.commit()

    assert task.id is not None
    assert project.name == "Ивановы"
