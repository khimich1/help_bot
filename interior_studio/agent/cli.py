"""CLI для локальной отладки агента без Telegram.

Примеры:
    python -m interior_studio.agent.cli --trace "Покажи все проекты"
    python -m interior_studio.agent.cli
    python -m interior_studio.agent.cli --user-id 222222222 "Работаем по Петровым"
"""

from __future__ import annotations

import argparse
import json
import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import sessionmaker

from interior_studio.agent.graph import create_studio_agent
from interior_studio.agent.prompt import build_system_prompt
from interior_studio.agent.tools import make_tools
from interior_studio.agent.tools.web_search import reset_web_search_guard
from interior_studio.config import AGENT_RECURSION_LIMIT, get_default_cli_user_id
from interior_studio.db.connection import create_db_engine, init_schema


def _agent_invoke_config() -> dict:
    return {"recursion_limit": AGENT_RECURSION_LIMIT}


def _print_trace_message(message, step_num: int, tool_count: int) -> int:
    """Печатает один шаг trace; возвращает обновлённый tool_count."""
    if isinstance(message, AIMessage):
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_count += 1
                print(f"\n--- Шаг TAO {step_num} ---")
                if message.content:
                    print(f"   МЫСЛЬ:      {str(message.content)[:200]}")
                args = json.dumps(tc["args"], ensure_ascii=False)
                print(f"   ДЕЙСТВИЕ:   {tc['name']}({args})")
        elif message.content:
            print("\n--- Финальный ответ ---")
            print(f"   {message.content[:500]}")
    elif isinstance(message, ToolMessage):
        preview = message.content[:150] if len(message.content) > 150 else message.content
        name = getattr(message, "name", "tool")
        print(f"   НАБЛЮДЕНИЕ ({name}): {preview}")
    return tool_count


def _print_step(message) -> None:
    if isinstance(message, AIMessage):
        if message.tool_calls:
            print("\n=== МЫСЛЬ ===")
            print(message.content or "(модель не написала текст рассуждения)")
            for tc in message.tool_calls:
                args = json.dumps(tc.get("args", {}), ensure_ascii=False)
                print(f"\n=== ДЕЙСТВИЕ ===\n{tc['name']}({args})")
        else:
            print("\n=== ФИНАЛЬНЫЙ ОТВЕТ ===")
            print(message.content)
    else:
        name = getattr(message, "name", "tool")
        print(f"\n=== НАБЛЮДЕНИЕ ({name}) ===")
        print(message.content)


def run_and_trace(agent, query: str, session, history: list | None = None):
    """Запуск с пошаговым выводом TAO-петли (stream — шаги видны до падения)."""
    print(f"Пользователь: {query}")
    print("=" * 60)

    messages = list(history or [])
    messages.append(HumanMessage(content=query))

    reset_web_search_guard(session)
    start_time = time.time()
    step_num = 0
    tool_count = 0
    result_messages = list(messages)

    for chunk in agent.stream(
        {"messages": messages},
        config=_agent_invoke_config(),
        stream_mode="updates",
    ):
        for node_name, update in chunk.items():
            if node_name == "agent":
                msg = update["messages"][-1]
                result_messages.append(msg)
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    step_num += 1
                tool_count = _print_trace_message(msg, step_num, tool_count)
            elif node_name == "tools":
                for msg in update["messages"]:
                    result_messages.append(msg)
                    tool_count = _print_trace_message(msg, step_num, tool_count)

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(
        f"Циклов TAO: {step_num} | Вызовов инструментов: {tool_count} "
        f"| Время: {elapsed:.2f}с"
    )
    return {"messages": result_messages}


def create_cli_session_and_agent(user_id: int):
    engine = create_db_engine()
    init_schema(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    tools = make_tools(session, user_id)
    prompt = build_system_prompt(user_id)
    agent = create_studio_agent(tools, prompt)
    return agent, session


def main() -> None:
    parser = argparse.ArgumentParser(description="Interior Studio Assistant CLI")
    parser.add_argument("--trace", action="store_true", help="Пошаговый вывод TAO")
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Telegram user_id (по умолчанию — Сеня из .env)",
    )
    parser.add_argument("query", nargs="*", help="Запрос пользователя")
    args = parser.parse_args()

    user_id = args.user_id or get_default_cli_user_id()
    query = " ".join(args.query).strip()
    agent, session = create_cli_session_and_agent(user_id)

    try:
        if args.trace and query:
            run_and_trace(agent, query, session)
            session.commit()
            return

        if query:
            reset_web_search_guard(session)
            result = agent.invoke(
                {"messages": [HumanMessage(content=query)]},
                config=_agent_invoke_config(),
            )
            session.commit()
            for msg in result["messages"]:
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    print(msg.content)
            return

        print(
            f"\nInterior Studio Assistant (CLI). Пользователь: user_id={user_id}. "
            "Введите запрос или 'exit' / 'выход'.\n"
        )
        history: list = []

        while True:
            user_input = input("Вы: ").strip()
            if user_input.lower() in {"exit", "quit", "выход"}:
                print("До свидания!")
                break
            if not user_input:
                continue

            history.append(HumanMessage(content=user_input))
            reset_web_search_guard(session)
            result = agent.invoke(
                {"messages": history},
                config=_agent_invoke_config(),
            )
            session.commit()

            new_messages = result["messages"][len(history) :]
            for msg in new_messages:
                _print_step(msg)

            history = result["messages"]
            print()
    except (KeyboardInterrupt, EOFError):
        print("\nДо свидания!")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
