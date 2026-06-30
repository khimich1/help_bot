---
name: test-driven-development
description: Разработка через тесты. Использовать при новой логике, багах, изменении поведения tools и вспомогательных функций агента.
---

# Test-Driven Development

Падающий тест → минимальный код → рефакторинг. «Кажется работает» — не готово.

## Цикл RED → GREEN → REFACTOR

1. **RED** — тест падает (доказывает пробел или баг)
2. **GREEN** — минимальный код для прохождения
3. **REFACTOR** — улучшение без смены поведения

## Prove-It для багов

```
Баг → тест воспроизводит → FAIL → fix → PASS
```

Не чини баг без воспроизводящего теста.

## Примеры для help_agent

```python
# tests/test_resolve_date.py
def test_resolve_date_tomorrow_ru():
    result = resolve_date("завтра")
    assert result == (date.today() + timedelta(days=1)).isoformat()
```

```python
# tests/test_tools.py — mock, без реального LLM
def test_search_flights_empty_origin():
    result = search_flights.invoke({"origin": "", "destination": "LED"})
    assert "error" in result.lower() or result.startswith("{")
```

## Уровни

| Что | Как |
|-----|-----|
| `resolve_date`, валидация | unit, pytest |
| Tool functions | unit + mock данных |
| Граф LangGraph | integration, mock ChatOpenAI |
| Полный диалог | E2E, редко |

## Правила

1. pytest в `tests/`
2. Имена: `test_<что>_<условие>_<ожидание>`
3. Один концепт на тест
4. Mock LLM API, не внутренние функции
5. Сообщай пользователю на русском результат прогона
