# Interior Studio — Web Search (срез 4)

> Родительская идея: [`interior-studio-assistant.md`](interior-studio-assistant.md)  
> Связано с: [`interior-studio-knowledge.md`](interior-studio-knowledge.md)  
> Статус: **утверждено** (2026-07-02)  
> Спека: [`docs/specs/interior-studio-web-search.md`](../specs/interior-studio-web-search.md)  
> План: [`docs/plans/interior-studio-web-search.md`](../plans/interior-studio-web-search.md)

## Проблема (How Might We)

Как мы можем дать агенту доступ к внешней информации (интернет в ЖК, цены, нормы), которой нет в документах проекта — без самодеятельного поиска и без смешения с RAG по брифу/анкете?

## Рекомендуемое направление

**«Knowledge → Web cascade»** — отдельный tool `search_web` поверх существующего ReAct-агента (DeepSeek + LangGraph, паттерн `airline_react_agent.py`).

### Два search-tool'а

| Tool | Когда | Источник |
|------|-------|----------|
| `search_project_knowledge` | Факты проекта, **первым** | Chroma / документы |
| `search_web` | Явная просьба **или** пустой knowledge + внешний факт | DuckDuckGo |

### Каскад (happy path)

```
«Какой интернет есть в ЖК Шкиперский?»
  → search_project_knowledge
  → results пустые, тема = инфраструктура ЖК
  → search_web (сразу, без уточнения)
  → ответ: суть + «Источник: URL» + цитата до 200 символов
```

### Когда вызывать `search_web`

1. **Явная просьба:** «найди в интернете», «загугли», «поищи в сети» — на **любую** тему.
2. **Автоматически после пустого knowledge** — только для **узкого списка** внешних тем:
   - инфраструктура ЖК (интернет, парковка, УК);
   - цены, аналоги материалов, поставщики;
   - нормы, стандарты, технические регламенты.

### Когда НЕ вызывать `search_web`

- Операционные запросы (`list_tasks`, `create_tasks`, `complete_task`, …).
- Вопрос про согласованные решения клиента, если в документах пусто → «не нашёл в брифе, уточни раздел / Диск».
- **Создание задачи** («создай задачу узнать интернет в ЖК») → только `create_tasks`, **без** web.
- «На всякий случай» до `search_project_knowledge`.

### Задачи vs поиск

| Сценарий | Поведение |
|----------|-----------|
| «Создай задачу узнать интернет в ЖК» | `create_tasks` only |
| «Узнай про интернет по задаче #5» / вопрос по задаче | knowledge → web (каскад) |
| Прямой вопрос «какой интернет в ЖК?» | knowledge → web (каскад) |

### Стек

- **LLM:** DeepSeek (`LLM_PROVIDER=deepseek`) — tool calling, без встроенного browsing.
- **Web search:** DuckDuckGo (`duckduckgo-search`) — бесплатно для MVP.
- **Граф:** без изменений — ReAct + правила в system prompt + тесты tool calling.

## Допущения для проверки

- [ ] DeepSeek стабильно выбирает `search_web` после пустого knowledge на внешних темах — pytest (mock LLM)
- [ ] Пустой knowledge + «интернет в ЖК» → web; + «цвет дверей» → **без** web — negative test
- [ ] «Создай задачу узнать…» → только `create_tasks` — pytest
- [ ] DuckDuckGo даёт осмысленные результаты по 2–3 RU-запросам про ЖК — ручной smoke

## MVP (срез 4.0)

**В scope:**

- Tool `search_web(query, max_results=5)`
- Модуль клиента DuckDuckGo + конфиг `WEB_SEARCH_*` в `config.py`
- Правила каскада в `prompt.py`
- 5–7 тестов tool calling (как `test_knowledge_tool_calling.py`)

**Вне scope:** см. Not Doing

## Not Doing (и почему)

| Фича | Причина |
|------|---------|
| Rate limit на web | Два пользователя; не нужен (решение 2026-07-02) |
| Web при `create_tasks` | Задача = отложенное действие; поиск — когда спросят |
| Web при `list_tasks` / напоминаниях | Лишние вызовы, нет явного запроса |
| Web до knowledge | Документы проекта — источник истины |
| Web при пустом RAG для внутренних фактов | Риск галлюцинаций; «не нашёл в брифе» |
| Tavily / SerpAPI | MVP на DuckDuckGo; смена провайдера через абстракцию позже |
| Сохранение результатов web в Chroma | Отдельная фича |
| Подтверждение «искать в интернете?» | Решено: сразу, без лишнего шага |

## Открытые вопросы

- Нет блокирующих — готово к `spec-driven-development`.

## Следующий шаг

`incremental-implementation` — задача 1 из плана.
