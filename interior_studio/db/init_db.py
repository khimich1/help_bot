"""Создание таблиц в SQLite."""

from interior_studio.db.connection import create_db_engine, init_schema


def main() -> None:
    engine = create_db_engine()
    init_schema(engine)
    print(f"Database initialized: {engine.url}")


if __name__ == "__main__":
    main()
