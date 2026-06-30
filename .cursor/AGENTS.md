# AGENTS.md — help_agent

Руководство для AI-агентов Cursor при работе с этим репозиторием.

## О проекте

**help_agent** — лаборатория для разработки AI-агентов на Python (LangChain, LangGraph, OpenAI).  
Примеры: `airline_react_agent.py`, `airline_agent_from_screens.py`.

## Язык общения

- **С пользователем — всегда на русском.** Объяснения, вопросы, отчёты, спеки, планы.
- Код, имена переменных, коммиты — на английском (стандарт проекта).
- Комментарии в коде — русский или английский, в стиле существующих файлов.

## Три слоя оркестрации

| Слой | Где | Роль |
|------|-----|------|
| **Skills** | `.cursor/skills/<name>/SKILL.md` | *Как* делать — workflow с шагами и критериями выхода |
| **Personas** | `.cursor/agents/<role>.md` | *Кто* делает — роль, перспектива, формат отчёта |
| **Rules** | `.cursor/rules/*.mdc` | Постоянный контекст проекта |

Правило композиции: **пользователь — оркестратор**. Персоны не вызывают другие персоны. Персона может применять skills.

## Маппинг намерений → skills

Перед работой проверь, подходит ли skill (даже с вероятностью 1%):

| Намерение | Skill |
|-----------|-------|
| Запрос размыт («сделай агента») | `interview-me` |
| Идея есть, нужны варианты | `idea-refine` |
| Новый агент / фича (направление ясно) | `spec-driven-development` → `planning-and-task-breakdown` |
| Реализация кода | `incremental-implementation` + `test-driven-development` |
| LangGraph / ReAct / tools / guardrails | `langgraph-agent-development` |
| Важное архитектурное решение | `doubt-driven-development` |
| Планирование задач | `planning-and-task-breakdown` |
| Баг / ошибка / неожиданное поведение | `debugging-and-error-recovery` |
| Ревью кода | `code-review-and-quality` |
| Новая сессия / плохой контекст | `context-engineering` |
| Старт / выбор workflow | `using-agent-skills` |

## Жизненный цикл разработки агента

```
УТОЧНЕНИЕ → ИДЕЯ → СПЕЦИФИКАЦИЯ → ПЛАН → СБОРКА → ПРОВЕРКА → РЕВЬЮ
     │         │          │          │        │          │         │
     ▼         ▼          ▼          ▼        ▼          ▼         ▼
interview  idea-refine  spec-     planning incremental debug  code-review
  -me                  driven     -and-    +langgraph  -and-
                       dev        task-    agent-dev   error
                                  breakdown            recovery
```

One-pagers идей: `docs/ideas/[имя].md` (после `idea-refine`).

## Персоны (subagents)

| Персона | Когда использовать |
|---------|-------------------|
| `agent-architect` | Проектирование архитектуры агента, граф, tools, state |
| `code-reviewer` | Ревью перед мержем (5 осей) |
| `security-auditor` | Безопасность, OWASP, LLM Top 10 |
| `test-engineer` | Стратегия тестов, Prove-It для багов |

Параллельный fan-out (как `/ship` в agent-skills): `code-reviewer` + `security-auditor` + `test-engineer` → синтез в главном агенте.

## Структура проекта

```
help_agent/
├── .cursor/
│   ├── AGENTS.md          ← этот файл
│   ├── agents/            ← персоны
│   ├── skills/            ← workflows
│   └── rules/             ← постоянные правила
├── agent-skills-main/     ← исходный набор (reference)
├── docs/ideas/            ← one-pagers из idea-refine
├── airline_react_agent.py
├── airline_agent_from_screens.py
└── tests/                 ← тесты (создавать по мере роста)
```

## Антирационализация

Неправильные мысли — игнорировать:

- «Это слишком мелко для skill»
- «Быстро напишу код без спеки»
- «Сначала соберу контекст, skill потом»

Правильно: проверить skills → следовать workflow → затем код.

## Создание нового skill

```
.cursor/skills/{skill-name}/
  SKILL.md              # обязательно
  reference.md          # опционально
  examples.md           # опционально
  scripts/              # опционально
```

Формат frontmatter: `name`, `description` (на русском, third person для description).
