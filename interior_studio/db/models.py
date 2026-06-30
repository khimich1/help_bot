"""SQLAlchemy ORM-модели Interior Studio."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    active_project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, default=lambda: datetime.utcnow().isoformat(timespec="seconds")
    )

    active_project: Mapped["Project | None"] = relationship(
        "Project", foreign_keys=[active_project_id]
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, default=lambda: datetime.utcnow().isoformat(timespec="seconds")
    )

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_project_status", "project_id", "status"),
        Index("idx_tasks_assignee", "assignee_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    assignee_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.telegram_user_id"), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.telegram_user_id"), nullable=False
    )
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, default=lambda: datetime.utcnow().isoformat(timespec="seconds")
    )

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")


class SentReminder(Base):
    __tablename__ = "sent_reminders"
    __table_args__ = (
        UniqueConstraint("task_id", "reminder_type", name="uq_task_reminder"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String, nullable=False)
    sent_at: Mapped[str] = mapped_column(
        String, nullable=False, default=lambda: datetime.utcnow().isoformat(timespec="seconds")
    )
