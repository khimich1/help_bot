---
name: langgraph-agent-development
description: Разрабатывает AI-агентов на LangGraph/LangChain с ReAct-петлёй, tools и русскоязычным UX. Использовать при создании или доработке агентов в help_agent.
---

# Разработка LangGraph-агентов

Стандарт проекта help_agent для LLM-агентов.

## Стек

```
Python 3 + venv (Windows)
langchain-openai, langchain-core
langgraph (StateGraph, ToolNode, MessagesState)
pydantic v2, python-dotenv
```

## Референсные файлы

| Файл | Назначение |
|------|------------|
| `airline_react_agent.py` | Минимальный ReAct, 5 tools, без guardrails |
| `airline_agent_from_screens.py` | Полная версия с обвесом |

**Перед новым агентом — прочитай референс и повтори паттерны.**

## Архитектура ReAct (минимум)

```
START → agent (LLM) → [tool calls?] → tools → agent → ... → END
```

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(tools))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")
app = graph.compile()
```

## Шаблон нового агента

### 1. Конфиг

```python
from dotenv import load_dotenv
import os

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
```

### 2. Tools

```python
from langchain_core.tools import tool

@tool
def my_tool(arg: str) -> str:
    """Краткое описание на русском для LLM.

    Args:
        arg: что ожидается
    """
    # валидация
    # бизнес-логика
    return json.dumps({"status": "ok", "data": ...}, ensure_ascii=False)
```

Правила tools:
- Возвращай **строку** (JSON для структуры)
- `ensure_ascii=False` для кириллицы
- Ошибки — в ответе, не exception (чтобы LLM мог исправиться)
- Один tool = одна операция

### 3. System prompt

```python
SYSTEM_PROMPT = """Ты — [роль]. Отвечай пользователю на русском.

Правила:
- Используй tools для [когда]
- Если данных не хватает — спроси
- Не выдумывай факты вне tool results
"""
```

### 4. Agent node

```python
def call_model(state: MessagesState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm.bind_tools(tools).invoke(messages)
    return {"messages": [response]}
```

### 5. LLM

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model=MODEL, temperature=0)
```

## Русскоязычный UX

- System prompt: явно «отвечай на русском»
- Tool docstrings: русский + примеры аргументов
- Парсинг дат/дней недели: ru + en (`resolve_date` в референсе)
- JSON ответы tools: `ensure_ascii=False`

## Безопасность (LLM Top 10)

| Риск | Митигация |
|------|-----------|
| Prompt injection | Не доверять user input; permissions в коде tools |
| Excessive agency | Минимальный набор tools; confirm для destructive |
| Unbounded consumption | `recursion_limit` при compile, max tokens |
| Sensitive disclosure | Не класть секреты в prompt/context |

```python
app = graph.compile()  # invoke с config
# result = app.invoke(input, config={"recursion_limit": 25})
```

## Инкрементальный порядок реализации

1. Данные / mock DB (если нужны)
2. Вспомогательные функции + unit-тесты
3. Tools по одному + тесты
4. Граф с mock LLM
5. System prompt, русский UX
6. Интеграция с реальным LLM
7. Guardrails (recursion_limit, interrupt — по необходимости)

## Структура файлов (рекомендация)

Пока проект маленький — один файл допустим. При росте:

```
app/
  agents/
    airline/
      graph.py      # StateGraph
      tools.py      # @tool functions
      prompts.py    # SYSTEM_PROMPT
      state.py      # кастомный state если нужен
  core/
    config.py       # Settings из .env
tests/
  test_tools.py
  test_graph.py
```

## Верификация

```bash
# venv
python -m pytest tests/ -v

# ручной прогон
python your_agent.py
```

## Частые ошибки

- Забыли `bind_tools(tools)` на LLM
- Tool возвращает dict вместо str
- Нет SystemMessage в начале messages
- Цикл без recursion_limit
- API key не в `.env`

## Связанные skills

- Проектирование → персона `agent-architect` + `spec-driven-development`
- Реализация → `incremental-implementation` + `test-driven-development`
- Баги → `debugging-and-error-recovery`
