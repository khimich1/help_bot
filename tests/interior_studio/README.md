# Тесты Interior Studio Assistant

## Запуск

```bash
pytest tests/interior_studio/ -v
```

Все тесты используют in-memory SQLite (fixture `db_session` в `conftest.py`).

## Структура

| Файл | Покрывает |
|------|-----------|
| `test_db.py` | ORM, init_schema |
| `test_project_service.py` | Проекты, active project |
| `test_task_service.py` | Задачи, batch, overdue |
| `test_tools_*.py` | LangChain tools |
| `test_graph.py` | Компиляция ReAct-графа |
| `test_llm.py` | `create_chat_llm()` openai/deepseek |
| `test_bot_handlers.py` | Whitelist, текст, история |
| `test_disambiguation.py` | Гибрид C (кнопки / голос) |
| `test_voice_pipeline.py` | Whisper (mock) |
| `test_scheduler.py` | Дайджест, дедлайны |
| `test_tool_calling.py` | 11 кейсов tool calling (mock LLM) |
| `test_web_search.py` | Web search service (mock client) |
| `test_tools_web_search.py` | Tool `search_web` |
| `test_web_tool_calling.py` | Web cascade / negative (mock LLM) |
| `test_knowledge_tool_calling.py` | Knowledge vs операционка (mock LLM) |

## Live-тесты (опционально)

Mock-тесты в `test_tool_calling.py` покрывают все 11 кейсов из спеки §12 без реального API.

Для проверки с живым LLM (требуются ключи в `.env`):

```bash
# Пример: CLI с trace (не pytest)
python -m interior_studio.agent.cli --trace "По Ивановым: заказать плитку, договориться с плиточником, купить клей"
python -m interior_studio.agent.cli --trace "Что просрочено?"
python -m interior_studio.agent.cli --trace "Покажи проекты"
```

Web search (срез 4.0, нужен интернет для DDG):

```bash
python -m interior_studio.agent.cli --trace "Какой интернет есть в ЖК Шкиперский?"
python -m interior_studio.agent.cli --trace "Найди в интернете аналоги плитки Kerama Marazzi 60x60"
```

Чеклист ручного smoke: [`docs/checklists/web-search-smoke.md`](../../docs/checklists/web-search-smoke.md).

Рекомендуемые фразы для ручной live-проверки:

1. Batch 3 задачи по проекту с assignee «Сеня» на одной.
2. «Работаем по Ивановым» → `set_active_project`.
3. «Что просрочено?» → `list_tasks(overdue=True)`.

Чтобы добавить pytest live-маркер в будущем:

```python
@pytest.mark.live
def test_live_create_tasks():
    ...
```

Запуск только live: `pytest -m live` (маркер нужно зарегистрировать в `pytest.ini`).

## Чеклист ручной приёмки (задача 12)

См. [`docs/plans/interior-studio-assistant.md`](../../docs/plans/interior-studio-assistant.md) — таблица «Чеклист ручной приёмки».

Автоматизированная часть (pytest) должна быть зелёной перед ручным прогоном в Telegram.
