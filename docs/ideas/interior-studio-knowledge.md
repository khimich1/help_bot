# Interior Studio — Project Knowledge (срез 3)

> Родительская идея: [`interior-studio-assistant.md`](interior-studio-assistant.md)  
> Статус: **утверждено** (2026-06-30)  
> Спека: [`docs/specs/interior-studio-knowledge.md`](../specs/interior-studio-knowledge.md)

## Проблема (How Might We)

Как мы можем дать двум дизайнерам в Telegram ответы по решениям, пожеланиям клиента и материалам проекта — без ручного поиска в папках Яндекс.Диска на сотни файлов?

## Рекомендуемое направление

**«Справочник» (направление A)** — один tool `search_project_knowledge` поверх существующего ReAct-агента (паттерн `airline_react_agent.py`).

- **Индекс Tier 1:** бриф, анкеты, отчёты по выездам (docx/pdf); metadata пути (этап, комната).
- **Пилот:** проект **ЖК Шкиперский**, локальная папка `ЖК Шкиперский/`; Яндекс.Диск API — срез 3.1.
- **Когда search:** **D с разумными границами** — при активном проекте search первым, кроме чисто операционных сообщений (см. спеку §7).
- **Формат ответа:** суть + путь к файлу + цитата до ~200 символов.
- **Пустой RAG:** честный отказ; `create_tasks` — только по явной просьбе пользователя.

**Happy path:**

> «По Шкиперскому — какой цвет дверей?»  
> → `search_project_knowledge` → ответ с источником из `Отчеты по выездам.docx`

> «Закажи ту плитку в мастер-с/у до пятницы»  
> → `search` (Equipe Artisan) → `create_tasks`

## Допущения для проверки

- [ ] 10 вопросов по Шкиперскому → ≥8 с верным источником (без OCR)
- [ ] D с границами не ломает операционку (`list_tasks`, `complete_task`) — pytest + ручной smoke
- [ ] Переиндексация вручную через CLI достаточна для пилота

## MVP (срез 3.0)

**В scope:** `search_project_knowledge`, ChromaDB + OpenAI embeddings, CLI `index_project`, промпт-правила D, тесты.

**Вне scope:** Яндекс.Диск API, `list_project_files`, OCR/vision, запись на Диск.

## Not Doing (и почему)

| Фича | Причина |
|------|---------|
| RAG по фото и чертежам | Низкий текст; OCR — срез 3.x |
| Ссылки на Я.Диск | Направление B |
| Search на каждое сообщение без исключений | Лишняя latency на «мои задачи» |
| Авто-create_tasks при пустом RAG | Только по явной просьбе |

## Открытые вопросы

- Срез 2 (`generate_client_report`) — до или после 3.0 (по умолчанию: после справочника)
- Единый шаблон папок на всех проектах студии
- Cron переиндексации на VPS

## Следующий шаг

`incremental-implementation` — [`docs/plans/interior-studio-knowledge.md`](../plans/interior-studio-knowledge.md)
