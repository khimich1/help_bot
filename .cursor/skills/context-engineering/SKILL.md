---
name: context-engineering
description: Настраивает контекст для Cursor при работе над агентами. Использовать в новой сессии, при падении качества ответов, при смене задачи или настройке .cursor/rules.
---

# Context Engineering

Правильный контекст = меньше галлюцинаций и правильные паттерны LangGraph.

## Иерархия (от постоянного к временному)

```
1. .cursor/rules/*.mdc     — всегда (русский, стек)
2. .cursor/AGENTS.md       — оркестрация skills
3. docs/ideas/, спеки      — на фичу
4. airline_react_agent.py  — референс кода
5. traceback, pytest       — на итерацию
6. История чата            — накапливается
```

## Что уже настроено в help_agent

| Файл | Роль |
|------|------|
| `russian-and-project.mdc` | alwaysApply: RU, стек |
| `langgraph-python.mdc` | для `*.py` |
| `.cursor/skills/` | workflows по фазам |
| `.cursor/agents/` | персоны для ревью |

## Чеклист новой сессии

1. Открой референс: `@airline_react_agent.py` или нужный файл
2. Укажи skill: `@.cursor/skills/langgraph-agent-development/SKILL.md`
3. Если идея сырая → `interview-me` или `idea-refine`
4. Не грузи все 20 skills из `agent-skills-main/` — только нужные

## Признаки плохого контекста

- Агент предлагает FastAPI там, где CLI-агент
- Игнорирует `@tool` и `MessagesState`
- Пишет на английском с пользователем
- Выдумывает API LangGraph

**Fix:** явный `@` на skill + референс-файл; сузить задачу.

## Добавление контекста под задачу

| Задача | Подключить |
|--------|------------|
| Новый агент | `idea-refine` one-pager, `langgraph-agent-development` |
| Новый tool | фрагмент существующих tools из airline |
| Баг | traceback + `debugging-and-error-recovery` |
| Ревью | diff + `code-reviewer` persona |

## Правила

- Меньше текста, больше **релевантного** кода
- Один skill на фазу, не все сразу
- Спеки в `docs/ideas/` после `idea-refine`
