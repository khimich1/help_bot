---
name: debugging-and-error-recovery
description: Систематическая отладка. Использовать при падении тестов, ошибках LangGraph, неверных tool calls, traceback Python.
---

# Отладка и восстановление

При сбое — стоп фичам, сохрани evidence, найди root cause.

## Stop-the-Line

```
1. СТОП — не добавляй фичи
2. СОХРАНИ — traceback, логи, шаги воспроизведения
3. ДИАГНОСТИКА — чеклист ниже
4. FIX — root cause, не симптом
5. GUARD — тест против регрессии
6. ПРОДОЛЖИ — только после зелёных тестов
```

## Чеклист

### 1. Воспроизведение
```bash
pytest tests/test_xxx.py -v
python airline_react_agent.py
```

### 2. Локализация (типично для агентов)

| Симптом | Где искать |
|---------|------------|
| Tool не вызывается | system prompt, tool docstring, model |
| Неверные аргументы tool | Pydantic schema, описание в @tool |
| Бесконечный цикл | conditional edges, max iterations |
| API error | `.env`, OPENAI_API_KEY, MODEL |
| Import error | venv, requirements |

### 3. Гипотеза → проверка
Одна гипотеза за раз. Логируй, что проверил.

### 4. Fix + guard
Добавь тест (Prove-It), который ловит этот баг.

## Типичные ошибки LangGraph

- Забыли `compile()` графа
- Неверный тип state (MessagesState vs custom)
- ToolNode не подключён к графу
- `return_direct` / routing bug

## Правила

1. Не чини вслепую по stack trace без понимания
2. Объясняй пользователю на русском: что сломалось, почему, как починил
3. После fix — прогон тестов
