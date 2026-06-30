# help_agent

Лаборатория для разработки AI-агентов на Python (LangGraph, LangChain).

## Быстрый старт

```bash
python -m venv venv
venv\Scripts\activate
pip install langchain-openai langchain-core langgraph pydantic python-dotenv pytest

# .env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

```bash
python airline_react_agent.py
```

## Cursor: агенты и skills

В `.cursor/` — адаптированный набор из [agent-skills-main](agent-skills-main/):

| Путь | Что внутри |
|------|------------|
| `.cursor/AGENTS.md` | Оркестрация, маппинг intent → skill |
| `.cursor/agents/` | Персоны: architect, reviewer, security, QA |
| `.cursor/skills/` | Workflows на русском |
| `.cursor/rules/` | Постоянные правила (русский язык, стек) |

### Как пользоваться

1. **Общайся на русском** — правила в `.cursor/rules/russian-and-project.mdc`
2. **Размытая идея:** `interview-me` → `idea-refine` → one-pager в `docs/ideas/`
3. **Новый агент (направление ясно):** `agent-architect` + `spec-driven-development`
4. **Реализация:** `langgraph-agent-development` + `incremental-implementation`
5. **Важные решения:** `doubt-driven-development` + `security-auditor`
6. **Ревью:** `code-reviewer` + `security-auditor` + `test-engineer`

### Примеры запросов

```
# Фаза Define — уточнение идеи
Поговори со мной: хочу агента для техподдержки магазина (interview-me)
Уточни идею агента бронирования отелей — накидай варианты (idea-refine)

# Фаза Build
Спроектируй агента поддержки с 3 tools: поиск FAQ, создание тикета, статус тикета
Реализуй tool search_faq по инкрементальному подходу

# Verify / Review
Напиши тесты для resolve_date — Prove-It стиль
Проведи ревью airline_react_agent.py перед коммитом
```

## Skills (адаптированные)

| Skill | Фаза | Назначение |
|-------|------|------------|
| `interview-me` | Define | Размытый запрос → ясный intent |
| `idea-refine` | Define | Варианты агента → one-pager в `docs/ideas/` |
| `spec-driven-development` | Define | Спека до кода |
| `planning-and-task-breakdown` | Plan | Декомпозиция |
| `langgraph-agent-development` | Build | **Главный** — LangGraph/ReAct/tools |
| `incremental-implementation` | Build | Вертикальные срезы |
| `doubt-driven-development` | Build | Stress-test важных решений |
| `test-driven-development` | Verify | pytest, Prove-It |
| `debugging-and-error-recovery` | Verify | Отладка |
| `code-review-and-quality` | Review | Ревью |
| `context-engineering` | Meta | Настройка контекста сессии |
| `using-agent-skills` | Meta | Выбор workflow |

### Ещё можно адаптировать (пока только в `agent-skills-main/`)

| Skill | Зачем для help_agent |
|-------|---------------------|
| `security-and-hardening` | Углублённый hardening (дополняет `security-auditor`) |
| `code-simplification` | Упростить разросшийся агент |
| `source-driven-development` | Сверка с официальными docs LangGraph |
| `documentation-and-adrs` | ADR: почему такой граф/tools |
| `shipping-and-launch` | Чеклист перед деплоем API-агента |
| `git-workflow-and-versioning` | Атомарные коммиты |
| `api-and-interface-design` | Когда обернёте агента в FastAPI |

Полный оригинал (английский): `agent-skills-main/skills/`

## Персоны

| Персона | Роль |
|---------|------|
| `agent-architect` | Архитектура графа, tools, prompts |
| `code-reviewer` | 5-осевое ревью |
| `security-auditor` | OWASP + LLM Top 10 |
| `test-engineer` | Стратегия тестов |

## Структура репозитория

```
help_agent/
├── .cursor/              # Cursor config (русский)
├── docs/ideas/           # one-pagers из idea-refine
├── agent-skills-main/    # Исходный reference
├── airline_react_agent.py
├── airline_agent_from_screens.py
└── tests/                # создавать по мере роста
```
