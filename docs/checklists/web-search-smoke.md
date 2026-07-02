# Smoke: Interior Studio Web Search (срез 4.0)

Ручная проверка с **реальным интернетом** и LLM (ключи в `.env`).

## Предусловия

- `pip install -r requirements.txt` (включая `duckduckgo-search`)
- В `.env`: `LLM_PROVIDER`, API-ключ, при необходимости `WEB_SEARCH_*`
- Активный проект в БД (например «ЖК Шкиперский»)

```bash
python -m interior_studio.agent.cli --trace "..."
```

## Сценарии

| # | Запрос | Ожидание |
|---|--------|----------|
| 1 | `Какой интернет есть в ЖК Шкиперский?` | Сначала `search_project_knowledge`, затем `search_web`; в ответе URL + цитата |
| 2 | `Найди в интернете аналоги плитки Kerama Marazzi 60x60` | Сразу `search_web`; в ответе URL |
| 3 | `Какой цвет дверей по Шкиперскому?` | Только `search_project_knowledge`; отказ без `search_web` |
| 4 | `Создай задачу узнать какой интернет в ЖК до пятницы` | Только `create_tasks`; без `search_web` |

## Критерии прохождения

- [ ] Сценарий 1: в trace виден каскад knowledge → web; финальный ответ содержит `Источник:` и `https://`
- [ ] Сценарий 2: первый tool — `search_web`; ответ с URL
- [ ] Сценарий 3: в trace нет `search_web`
- [ ] Сценарий 4: в trace только `create_tasks`

## При сбое DDG

Если `search_web` вернул `ok: false` — агент должен сообщить об ошибке поиска, без выдуманных фактов. Повторить позже или сузить запрос.

## Автотесты (без интернета)

```bash
pytest tests/interior_studio/test_web_search.py tests/interior_studio/test_web_tool_calling.py tests/interior_studio/test_tools_web_search.py -v
pytest tests/interior_studio/ -v
```
