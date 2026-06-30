# Персоны агентов

Специализированные роли для Cursor. Каждая персона — один Markdown-файл с системным промптом.

| Персона | Роль | Когда использовать |
|---------|------|-------------------|
| [agent-architect](agent-architect.md) | Архитектор AI-агентов | Проектирование графа, tools, state, guardrails |
| [code-reviewer](code-reviewer.md) | Staff Engineer | Ревью по 5 осям перед мержем |
| [security-auditor](security-auditor.md) | Security Engineer | Уязвимости, OWASP, LLM Top 10 |
| [test-engineer](test-engineer.md) | QA Engineer | Тесты, coverage, Prove-It |

## Как использовать в Cursor

1. **Прямой вызов:** «Проверь этот PR как code-reviewer» — вставь содержимое `code-reviewer.md` или укажи `@.cursor/agents/code-reviewer.md`
2. **Subagent:** Task tool с описанием роли из файла персоны
3. **Параллельный fan-out:** запусти 3 персоны параллельно → синтезируй отчёты в главном агенте

## Правила

1. Одна персона = одна роль. Не смешивай.
2. Персоны **не вызывают** другие персоны.
3. Персона **может** применять skills из `.cursor/skills/`.
4. Отчёты персон — **на русском**.
