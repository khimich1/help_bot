# Спека: Interior Studio — Web Search (срез 4.0)

> Источник идеи: [`docs/ideas/interior-studio-web-search.md`](../ideas/interior-studio-web-search.md)  
> Базовый агент: [`interior-studio-assistant.md`](interior-studio-assistant.md) (срез 1)  
> Зависит от: [`interior-studio-knowledge.md`](interior-studio-knowledge.md) (срез 3) — `search_project_knowledge`  
> Статус: **утверждена** (2026-07-02)  
> План: [`docs/plans/interior-studio-web-search.md`](../plans/interior-studio-web-search.md)  
> Следующий шаг: `incremental-implementation` (задача 1)

---

## Допущения (явные)

| # | Допущение | Если неверно |
|---|-----------|--------------|
| 1 | Срез 3 (knowledge tool + prompt D) уже работает | Сначала закрыть срез 3 |
| 2 | LLM — **DeepSeek** (`LLM_PROVIDER=deepseek`); tool calling стабилен | Fallback на OpenAI для отладки |
| 3 | Провайдер web MVP — **DuckDuckGo** (`duckduckgo-search`), без API-ключа | Tavily / SerpAPI в срезе 4.1 |
| 4 | Rate limit на web **не нужен** (2 дизайнера) | Добавить счётчик в SQLite |
| 5 | Граф ReAct **не меняется** — только новый tool + prompt | Dynamic bind / router |
| 6 | Один tool за шаг — без изменений | Мульти-tool за ход |
| 7 | Web **не** вызывается при `create_tasks`, даже если title про «узнать в интернете» | Автопоиск при создании задачи |
| 8 | Подтверждение «искать в интернете?» **не** нужно — каскад сразу | UX с «да/нет» |

---

## 1. Цель

**Что строим:** tool `search_web` — поиск в интернете через DuckDuckGo в существующем Telegram-боте / CLI.

**Зачем:** ответы на внешние вопросы (интернет в ЖК, цены, нормы), которых нет в документах проекта.

**Для кого:** те же 2 дизайнера (whitelist).

**Критерии успеха (срез 4.0):**

- Каскад knowledge → web на внешних темах при пустом RAG (≥4/5 mock tool-calling сценариев).
- Явная просьба «найди в интернете» → `search_web` без предварительного knowledge (≥3/3).
- Внутренние факты при пустом RAG → **без** web (≥3/3 negative tests).
- «Создай задачу узнать…» → только `create_tasks` (≥2/2).
- Ответы: суть + URL + цитата ≤200 символов; без выдуманных фактов.
- `pytest tests/interior_studio/test_web*.py -v` зелёный.

---

## 2. Команды

```bash
# Тесты web search
pytest tests/interior_studio/test_web_search.py tests/interior_studio/test_web_tool_calling.py tests/interior_studio/test_tools_web_search.py -v

# Smoke через CLI (нужен интернет)
python -m interior_studio.agent.cli --trace "Какой интернет есть в ЖК Шкиперский?"

# Явный web
python -m interior_studio.agent.cli --trace "Найди в интернете аналоги плитки Kerama Marazzi 60x60"
```

**Новые переменные `.env`:**

```
WEB_SEARCH_PROVIDER=duckduckgo
WEB_SEARCH_MAX_RESULTS=5
WEB_SEARCH_REGION=ru-ru
```

API-ключ для DuckDuckGo **не требуется**.

---

## 3. Структура файлов

```
help_agent/
├── interior_studio/
│   ├── web/
│   │   ├── __init__.py
│   │   ├── client.py           # абстракция провайдера (DuckDuckGo MVP)
│   │   └── search.py           # search_web(query) → JSON
│   ├── agent/
│   │   ├── tools/
│   │   │   └── web_search.py   # schema + impl для графа
│   │   └── prompt.py           # правила каскада + формат ответа
│   └── config.py               # WEB_SEARCH_*
└── tests/interior_studio/
    ├── test_web_search.py        # unit: client mock, JSON формат
    ├── test_tools_web_search.py  # tool impl
    └── test_web_tool_calling.py  # LLM mock: когда search_web / когда нет
```

---

## 4. Tool: `search_web`

| Поле | Тип | Описание |
|------|-----|----------|
| `query` | str | Поисковый запрос (на русском или английском) |
| `max_results` | int, opt | Число результатов; default из `WEB_SEARCH_MAX_RESULTS` (5) |

**Description для LLM (кратко):**

> Поиск в интернете. Только когда пользователь явно просит «найди в интернете» / «загугли», **или** после пустого `search_project_knowledge` на внешнюю тему (инфраструктура ЖК, цены, нормы). Не для фактов из брифа/анкеты.

**Выход (JSON):**

```json
{
  "ok": true,
  "query": "интернет провайдеры ЖК Шкиперский",
  "results": [
    {
      "title": "…",
      "url": "https://…",
      "snippet": "…фрагмент текста…"
    }
  ]
}
```

**Ошибки (в JSON, не exception):**

```json
{"ok": false, "message": "Web search failed: …"}
```

Пустой результат: `{"ok": true, "query": "…", "results": []}` — агент формулирует отказ сам.

---

## 5. Провайдер DuckDuckGo

**Библиотека:** `duckduckgo-search>=6.0` (пакет `ddgs`).

**Интерфейс `WebSearchClient` (в `client.py`):**

```python
def search(self, query: str, *, max_results: int = 5, region: str = "ru-ru") -> list[dict]:
    """Returns [{"title", "url", "snippet"}, ...]"""
```

MVP — одна реализация `DuckDuckGoClient`. Смена на Tavily — новый класс + `WEB_SEARCH_PROVIDER=tavily` (срез 4.1).

**Поведение при сбое сети / блокировке DDG:**

- Tool возвращает `ok: false` с message.
- Агент сообщает пользователю: «Не удалось выполнить поиск в интернете. Попробуй позже или уточни запрос.»

---

## 6. Формат ответа пользователю

Порядок в сообщении Telegram (аналог knowledge, §6 knowledge-spec):

1. **Суть** — 1–3 предложения, своими словами, только из `results`.
2. **Источник** — `Источник: {url}` (первый релевантный результат).
3. **Цитата** — фрагмент из `results[0].snippet`, до 200 символов, `…` при обрезке.

Если несколько источников полезны — до 2 URL, без дублирования цитат.

**Запрещено:** выдумывать факты, не подкреплённые `results`; подменять URL.

---

## 7. Когда вызывать `search_web` (каскад с knowledge)

### 7.1. Общее правило (в `prompt.py`)

> `search_project_knowledge` — **первым** для вопросов о проекте (правила D из knowledge-spec, без изменений).  
> `search_web` — **после** knowledge или **сразу** при явной просьбе про интернет.

### 7.2. Явная просьба → `search_web` (knowledge не обязателен)

| Пример | Первый tool |
|--------|-------------|
| «Найди в интернете аналоги плитки Kerama Marazzi» | `search_web` |
| «Загугли норму освещённости для кухни» | `search_web` |
| «Поищи в сети провайдеров интернета в ЖК Символ» | `search_web` |

Триггерные фразы (не исчерпывающий список): «найди в интернете», «загугли», «поищи в сети», «поищи в интернете».

### 7.3. Каскад: пустой knowledge + внешняя тема → `search_web`

| Пример | Шаг 1 | Шаг 2 |
|--------|-------|-------|
| «Какой интернет есть в ЖК Шкиперский?» | `search_project_knowledge` → `results=[]` | `search_web` |
| «Сколько стоит плитка Equipe Artisan?» | knowledge → пусто | `search_web` |
| «Какая управляющая компания у ЖК?» | knowledge → пусто | `search_web` |

**Узкий список внешних тем** (автоматический web после пустого knowledge):

- инфраструктура ЖК / дома: интернет, парковка, УК, застройщик;
- цены, аналоги материалов, поставщики, наличие;
- нормы, ГОСТ, СП, технические регламенты.

### 7.4. Пустой knowledge + внутренняя тема → **без** web

| Пример | Поведение |
|--------|-----------|
| «Какой цвет дверей по Шкиперскому?» → пусто | «В документах не нашёл…» (knowledge-spec §7) |
| «Какой ковёр в кабинете?» → пусто | то же, **без** web |
| «Что согласовали с клиентом по люстре?» → пусто | то же, **без** web |

### 7.5. Операционка и задачи → **без** web

| Пример | Первый tool |
|--------|-------------|
| «Мои задачи на неделю» | `list_tasks` |
| «Создай задачу узнать интернет в ЖК» | `create_tasks` |
| «Закрой задачу 12» | `complete_task` / `list_tasks` |
| «Узнай про интернет по задаче #5» | `search_project_knowledge` → при пусто `search_web` |

### 7.6. Обновление knowledge-spec §7 (пустой RAG)

Дополнение к тексту отказа:

- **Внутренний факт:** «По документам проекта «…» этого не нашёл. Уточни раздел (бриф / анкета / выезд) или посмотри на Диске.»
- **Внешний факт (узкий список):** не останавливаться на отказе — вызвать `search_web`, затем ответ с URL.

---

## 8. Пользовательские сценарии

### 8.1 Инфраструктура ЖК (каскад)

```
Пользователь: Какой интернет есть в ЖК Шкиперский?
→ search_project_knowledge(query="интернет провайдеры ЖК")
→ results=[]
→ search_web(query="интернет провайдеры ЖК Шкиперский")
→ Ответ: провайдеры + Источник: URL + цитата
```

### 8.2 Явный web без knowledge

```
Пользователь: Найди в интернете аналоги плитки Kerama Marazzi 60x60
→ search_web(query="Kerama Marazzi 60x60 аналог")
→ Ответ с URL
```

### 8.3 Внутренний факт — web не нужен

```
Пользователь: Какой цвет дверей по Шкиперскому?
→ search_project_knowledge → results=[]
→ «В документах не нашёл…» (без search_web)
```

### 8.4 Задача без web

```
Пользователь: Создай задачу узнать какой интернет в ЖК до пятницы
→ create_tasks(tasks=[{title: "Узнать интернет в ЖК", due_date: …}])
→ «Создала задачу.» (без search_web)
```

### 8.5 Вопрос по существующей задаче

```
Пользователь: Узнай про интернет в ЖК — это по задаче про провайдеров
→ search_project_knowledge → пусто
→ search_web
→ Ответ с URL
```

### 8.6 Смешанный: knowledge нашёл + задача

```
Пользователь: Закажи плитку в мастер-с/у как договаривались
→ search_project_knowledge (как в knowledge-spec 8.2)
→ create_tasks
(без search_web — факт из документов)
```

---

## 9. Интеграция в агент

### 9.1 `make_tools`

Добавить в `tool_defs` в `interior_studio/agent/tools/__init__.py`:

```python
("search_web", web_search_tools.search_web_impl, web_search_tools.SEARCH_WEB_SCHEMA),
```

Порядок в списке: после `search_project_knowledge`.

### 9.2 `prompt.py`

- Добавить `search_web` в блок «Доступные инструменты».
- Добавить секцию «Поиск в интернете» с правилами §7.
- Обновить блок «Пустой RAG» — различие внутренний / внешний факт (§7.6).

### 9.3 Граф

Без изменений (`interior_studio/agent/graph.py`).

---

## 10. Тестирование

| Файл | Что проверяет |
|------|----------------|
| `test_web_search.py` | `search_web()` с mock client; JSON ok/error; пустой results |
| `test_tools_web_search.py` | tool impl через `StructuredTool`; валидация args |
| `test_web_tool_calling.py` | LLM mock (паттерн `test_knowledge_tool_calling.py`) |

**Сценарии tool calling (mock LLM, parametrized):**

| Запрос | Ожидаемый первый tool | Примечание |
|--------|----------------------|------------|
| «Какой интернет в ЖК Шкиперский?» | `search_project_knowledge` | второй шаг mock: `search_web` |
| «Найди в интернете цену на …» | `search_web` | без knowledge |
| «Какой цвет дверей?» (mock empty RAG) | `search_project_knowledge` | финал **без** search_web |
| «Создай задачу узнать интернет в ЖК» | `create_tasks` | |
| «Мои задачи» | `list_tasks` | |

**Интеграционный smoke (ручной, с интернетом):**

1. «Какой интернет в ЖК Шкиперский?» — ответ с URL.
2. «Найди в интернете …» — ответ с URL.
3. «Создай задачу узнать …» — только задача.

---

## 11. Нефункциональные требования

- Язык ответов: **русский**
- `WEB_SEARCH_MAX_RESULTS`: 5 (конфиг)
- Latency web: &lt; 10 с (зависит от DDG / сети)
- Не логировать полные snippet в production (только query + url)
- DeepSeek: `temperature=0` (как сейчас)
- Ошибки провайдера — в JSON tool, не падение графа

---

## 12. Критерии приёмки (срез 4.0)

- [ ] `duckduckgo-search` в `requirements.txt`; `pip install` без ошибок
- [ ] `interior_studio/web/` + `search_web` tool в графе
- [ ] `config.py` + `.env.example`: `WEB_SEARCH_*`
- [ ] Промпт: правила §7 + формат ответа §6
- [ ] `test_web_search.py`, `test_tools_web_search.py`, `test_web_tool_calling.py` — зелёные
- [ ] Negative: внутренний факт + пустой RAG → без web
- [ ] «Создай задачу узнать…» → только `create_tasks`
- [ ] Ручной smoke: 2 запроса с URL в ответе

---

## 13. Границы

**Всегда:**

- Тесты с mock client (CI без интернета)
- Секреты в `.env` (для DDG не нужны)
- Knowledge **до** web (кроме явной просьбы про интернет)
- Цитата + URL в ответах на web-факты
- Честный отказ при `results=[]` после web

**Спросить перед merge:**

- Новая зависимость `duckduckgo-search` — **да, в scope MVP**

**Никогда (срез 4.0):**

- Rate limit
- Web при `create_tasks`
- Web при `list_tasks` / напоминаниях
- Web до knowledge (кроме явного триггера)
- Web при пустом RAG для согласований клиента
- Сохранение web-результатов в Chroma
- Подтверждение «искать?»

---

## 14. Вне scope (срез 4.x)

| Фича | Срез |
|------|------|
| Tavily / SerpAPI провайдер | 4.1 |
| Rate limit / quota per user | — (не планируется) |
| Кэш web-результатов | 4.x |
| Запись результатов web в задачу / комментарий | 4.x |
| Dynamic bind (tool только при триггере) | 4.x при проблемах с compliance |

---

## 15. Зависимости (дополнение)

```
duckduckgo-search>=6.0
```

---

## 16. Принятые решения

| Вопрос | Решение |
|--------|---------|
| Провайдер MVP | DuckDuckGo, без API-ключа |
| Триггер web | Явная просьба **или** пустой knowledge + внешняя тема |
| Пустой knowledge, внешняя тема | Сразу web, без «разрешите?» |
| Задача «узнать…» | Только `create_tasks`; web — когда спросят |
| Rate limit | Нет |
| LLM | DeepSeek (ReAct без изменений графа) |
| Формат ответа | Суть + URL + цитата ≤200 (как knowledge) |

---

## 17. Связь с knowledge-spec

| Документ | Изменение при реализации 4.0 |
|----------|------------------------------|
| `prompt.py` | Новая секция web + уточнение пустого RAG |
| `interior-studio-knowledge.md` §7 | Дополнение §7.6 (опционально, cross-link) |
| `test_knowledge_tool_calling.py` | Без изменений; web — отдельный файл |
