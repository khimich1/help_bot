---
name: using-agent-skills
description: Обнаруживает и применяет skills проекта help_agent. Использовать в начале сессии или когда нужно выбрать workflow для задачи. Мета-skill для всех остальных skills.
---

# Использование Agent Skills

## Дерево выбора skill

```
Задача
├── Запрос размыт («сделай бота»)? ───────→ interview-me
├── Идея есть, нужны варианты? ───────────→ idea-refine
├── Направление ясно, нужна спека? ───────→ spec-driven-development
├── Есть спека, нужен план? ──────────────→ planning-and-task-breakdown
├── Пишем код агента? ────────────────────→ langgraph-agent-development
│   └── + incremental-implementation
├── Важное решение (tools, security)? ────→ doubt-driven-development
├── Пишем/чиним логику? ──────────────────→ test-driven-development
├── Что-то сломалось? ────────────────────→ debugging-and-error-recovery
├── Ревью перед мержем? ──────────────────→ code-review-and-quality
├── Новая сессия / плохие ответы? ────────→ context-engineering
└── Проектирование архитектуры? ──────────→ agent-architect (персона)
```

## Базовые правила поведения

### 1. Озвучивай допущения
```
ДОПУЩЕНИЯ:
1. ...
2. ...
→ Поправь сейчас или продолжу с ними.
```

### 2. Останавливайся при путанице
Не угадывай — спроси на русском.

### 3. Не соглашайся с плохими идеями
Объясни риск, предложи альтернативу.

### 4. Простота
100 строк вместо 1000 — успех.

### 5. Scope
Только то, что просят.

### 6. Верификация
«Кажется работает» ≠ готово. Нужны тесты или запуск.

## Жизненный цикл фичи агента

```
interview-me → idea-refine → spec → plan → langgraph-dev → incremental → TDD
  → doubt (если нужно) → review
```

Короткие пути:
- **Баг:** `debugging` → `TDD` → `review`
- **Мелкий fix:** код + тест, без полного цикла
- **Ясная спека:** пропусти `interview-me` и `idea-refine`

## Адаптированные skills (`.cursor/skills/`)

| Skill | Фаза |
|-------|------|
| interview-me | Define |
| idea-refine | Define |
| spec-driven-development | Define |
| planning-and-task-breakdown | Plan |
| langgraph-agent-development | Build |
| incremental-implementation | Build |
| test-driven-development | Verify |
| doubt-driven-development | Build/Verify |
| debugging-and-error-recovery | Verify |
| code-review-and-quality | Review |
| context-engineering | Meta |

## Ещё не адаптировано (reference: `agent-skills-main/skills/`)

Можно переносить по необходимости:
- `security-and-hardening` — углублённый security (есть персона `security-auditor`)
- `code-simplification` — рефакторинг после фичи
- `git-workflow-and-versioning` — коммиты
- `documentation-and-adrs` — ADR решений по агентам
- `shipping-and-launch` — чеклист перед «релизом»
- `source-driven-development` — сверка с docs LangGraph/LangChain
- `api-and-interface-design` — если агент станет FastAPI-сервисом
- `performance-optimization` — latency, токены

## Правила skills

1. Проверь skill **до** кода
2. Skills — workflow, не советы. Шаги по порядку
3. Несколько skills могут идти цепочкой
4. При сомнении — `interview-me` или `idea-refine`, не сразу код
