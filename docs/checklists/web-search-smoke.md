# Smoke: Interior Studio Web Search (срез 4.0)

Ручная проверка с **реальным интернетом** и LLM (ключи в `.env`).

## Предусловия

- `pip install -r requirements.txt` (включая `ddgs`)
- В `.env`: `LLM_PROVIDER`, API-ключ, при необходимости `WEB_SEARCH_*`, `AGENT_RECURSION_LIMIT`
- Активный проект в БД (например «ЖК Шкиперский»):

```bash
python -m interior_studio.agent.cli --trace "Работаем по ЖК Шкиперский"
```

## Сценарии

| # | Запрос | Ожидание |
|---|--------|----------|
| 0 | `Работаем по ЖК Шкиперский` | `set_active_project` или эквивалент; проект активен |
| 1 | `Какой интернет есть в ЖК Шкиперский?` | Сначала `search_project_knowledge`, затем `search_web` (один раз); в ответе URL + цитата или честный отказ |
| 2 | `Найди в интернете аналоги плитки Kerama Marazzi 60x60` | Сразу `search_web`; в ответе URL |
| 3 | `Какой цвет дверей по Шкиперскому?` | Только `search_project_knowledge`; отказ без `search_web` |
| 4 | `Создай задачу узнать какой интернет в ЖК до пятницы` | Только `create_tasks`; без `search_web` |

## Критерии прохождения

- [ ] Сценарий 1: в trace виден каскад knowledge → web (не более одного `search_web`); финальный ответ содержит `Источник:` и `https://` или сообщение об ошибке поиска
- [ ] Сценарий 2: первый tool — `search_web`; ответ с URL
- [ ] Сценарий 3: в trace нет `search_web`
- [ ] Сценарий 4: в trace только `create_tasks`
- [ ] Нет `GraphRecursionError` и нет `RuntimeWarning` про `duckduckgo_search`

## При сбое DDG

Если `search_web` вернул `ok: false` или `results=[]` — агент должен сообщить об ошибке поиска **одним финальным ответом**, без повторных вызовов `search_web`.

## Автотесты (без интернета)

```bash
pytest tests/interior_studio/test_web_search.py tests/interior_studio/test_web_tool_calling.py tests/interior_studio/test_tools_web_search.py -v
pytest tests/interior_studio/ -v
```
