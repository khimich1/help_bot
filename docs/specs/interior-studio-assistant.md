# Спека: Interior Studio Assistant (срез 1 — MVP)

> Источник идеи: `docs/ideas/interior-studio-assistant.md`  
> Статус: **утверждена** (2026-06-30)  
> План: [`docs/plans/interior-studio-assistant.md`](../plans/interior-studio-assistant.md)  
> Следующий шаг: `incremental-implementation` (задача 1)

---

## Допущения (явные)

| # | Допущение | Если неверно |
|---|-----------|--------------|
| 1 | Два дизайнера — единственные пользователи; whitelist по `telegram_user_id` в `.env` | Нужна модель ролей / регистрация |
| 2 | Проекты общие (оба видят все проекты и задачи) | Нужны права per-project |
| 3 | SQLite на одном VPS достаточно для нагрузки 2 человек | Переход на PostgreSQL |
| 4 | Голос → Whisper API (OpenAI), не локальная модель; при `LLM_PROVIDER=deepseek` чат — DeepSeek, Whisper — по-прежнему OpenAI | Меняем pipeline / провайдера |
| 5 | Часовой пояс напоминаний — **Europe/Moscow** (09:00 МСК) | Конфиг per-user TZ |
| 6 | `active_project_id` хранится per user в БД, не в state графа | Другая модель контекста |
| 7 | При старте 10–15 проектов вносятся вручную (seed-скрипт или admin-команда) | Импорт из CSV в v1.1 |
| 8 | Дедлайн задачи — опциональное поле `due_date`; «до пятницы» парсит LLM → ISO-дата | Отдельный date-parser tool |
| 9 | Исполнитель задачи — опционально (`assignee_user_id`); «Сеня/Рита сделает» → второй дизайнер | Только «мои задачи» без assignee |
| 10 | История чата per user в памяти процесса (без checkpointer) для MVP | LangGraph checkpointer + SQLite |

---

## 1. Цель

**Что строим:** Telegram-бот для студии из двух дизайнеров — фиксирует задачи по общим проектам (текст + голос), напоминает о дедлайнах, отвечает на запросы по задачам.

**Зачем:** убрать ручную сборку задач из голосовых заметок и папок на объекте.

**Для кого:** 2 внутренних пользователя (дизайнеры студии), не клиенты.

**Критерии успеха (срез 1):**

- Happy path из идеи работает end-to-end (голос → Whisper → `create_tasks` → ответ в TG).
- Дайджест в 09:00 МСК и напоминание за 1 день до дедлайна приходят обоим.
- LLM стабильно вызывает tools, а не «я бы создала…» (≥9/10 на тестовых фразах).
- Пилот 2 недели без возврата к заметкам (качественная метрика, вне автотестов).

---

## 2. Команды

```bash
# Установка (из корня help_agent, venv активирован)
pip install -r requirements.txt

# Миграция / инициализация БД
python -m interior_studio.db.init_db

# Seed проектов при первом запуске (10–15 названий)
python -m interior_studio.db.seed_projects --file data/initial_projects.txt

# Запуск Telegram-бота + scheduler в одном процессе (long polling, dev/prod)
python -m interior_studio.bot.main

# Тесты
pytest tests/interior_studio/ -v

# Локальная проверка агента без Telegram (как airline_react_agent CLI)
python -m interior_studio.agent.cli --trace "По Ивановым заказать плитку до пятницы"

# Деплой на VPS — см. deploy/README.md (Timeweb Cloud)
```

**Продакшен (VPS):**

```bash
# На сервере после клонирования репо и настройки .env
python -m interior_studio.db.init_db
python -m interior_studio.db.seed_projects --file data/initial_projects.txt
sudo cp deploy/interior-studio-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now interior-studio-bot
sudo systemctl status interior-studio-bot
```

**Переменные `.env` (новые):**

```
# ReAct-агент: openai | deepseek
LLM_PROVIDER=deepseek

# DeepSeek (официальный API — platform.deepseek.com)
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# OpenAI (альтернатива для агента; обязателен для Whisper при deepseek)
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321  # первый = Сеня, второй = Рита
DATABASE_URL=sqlite:///./data/studio.db
WHISPER_MODEL=whisper-1
```

**LLM:** переключатель `LLM_PROVIDER` в `interior_studio/config.py`; фабрика — `interior_studio/llm.py` (`create_chat_llm`). DeepSeek использует OpenAI-compatible API через `langchain_openai.ChatOpenAI` с `base_url` и `DEEPSEEK_API_KEY`. Голосовой pipeline (Whisper) всегда через OpenAI — отдельный ключ `OPENAI_API_KEY`.

---

## 3. Структура файлов

```
help_agent/
├── interior_studio/              # новый пакет агента
│   ├── __init__.py
│   ├── config.py                 # USER_ALIASES, ALLOWED_IDS, LLM_PROVIDER, settings
│   ├── llm.py                    # create_chat_llm (openai | deepseek)
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── main.py               # Application, handlers, whitelist
│   │   ├── voice.py              # voice.ogg → Whisper → текст
│   │   └── session.py            # история сообщений per user_id
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py              # create_react_agent (из паттерна airline)
│   │   ├── prompt.py             # STUDIO_SYSTEM_PROMPT
│   │   ├── cli.py                # ручная отладка без TG
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── projects.py       # list/create/get/set active project
│   │       └── tasks.py          # create/list/complete
│   ├── db/
│   │   ├── __init__.py
│   │   ├── init_db.py
│   │   ├── seed_projects.py
│   │   ├── connection.py         # SQLAlchemy 2.x engine + session
│   │   └── models.py             # ORM-модели
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── project.py            # Pydantic DTO
│   │   └── task.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── project_service.py
│   │   ├── task_service.py
│   │   └── user_context.py       # active_project per user
│   └── scheduler/
│       ├── __init__.py
│       └── jobs.py               # digest_09_00, deadline_reminder (старт из bot/main)
├── deploy/
│   ├── interior-studio-bot.service   # systemd unit
│   └── README.md                     # инструкция деплоя на Timeweb Cloud VPS
├── data/
│   ├── studio.db                 # gitignore
│   └── initial_projects.txt      # пример seed-файла
├── tests/
│   └── interior_studio/
│       ├── test_tools_projects.py
│       ├── test_tools_tasks.py
│       ├── test_tool_calling.py  # LLM вызывает create_tasks (mock или live)
│       ├── test_voice_pipeline.py
│       └── test_scheduler.py
├── docs/
│   ├── ideas/interior-studio-assistant.md
│   └── specs/interior-studio-assistant.md   # этот файл
└── airline_react_agent.py        # референс, не трогаем
```

**Слои и ответственность:**

| Слой | Модуль | Роль |
|------|--------|------|
| Telegram | `bot/` | Приём сообщений, whitelist, voice pipeline |
| Agent | `agent/` | ReAct-граф, промпт, tools |
| Services | `services/` | Бизнес-логика, не знает про LangChain |
| DB | `db/` | SQLite, модели, миграции |
| Scheduler | `scheduler/` | Фоновые напоминания |

---

## 4. Стиль кода

Следуем `airline_react_agent.py`:

- `@tool` с docstring (описание на русском в промпте; сигнатура tool — английские имена параметров).
- Return: `json.dumps({...}, ensure_ascii=False)`.
- `load_dotenv()`, секреты через `os.getenv`.
- `create_react_agent()` — `MessagesState`, `agent_node` ↔ `ToolNode`, `parallel_tool_calls=False`.
- Pydantic v2 для входных схем batch-создания задач внутри services.

**Пример tool (целевой стиль):**

```python
@tool
def create_tasks(
    project_id: int,
    tasks: list[dict],
    user_id: int,
) -> str:
    """Создать одну или несколько задач в проекте.

    Args:
        project_id: ID проекта
        tasks: Список задач: title (обяз.), assignee_user_id?, due_date? (YYYY-MM-DD), notes?
        user_id: Telegram user_id создателя
    """
    result = task_service.create_tasks(project_id, tasks, created_by=user_id)
    return json.dumps(result, ensure_ascii=False)
```

---

## 5. Схема БД (SQLite, срез 1)

```sql
-- users: только whitelist из .env, но строки создаём при первом сообщении
CREATE TABLE users (
    telegram_user_id INTEGER PRIMARY KEY,
    display_name     TEXT,
    active_project_id INTEGER REFERENCES projects(id),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'active',  -- active | archived
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    title           TEXT NOT NULL,
    notes           TEXT,
    status          TEXT NOT NULL DEFAULT 'open',  -- open | done
    assignee_user_id INTEGER REFERENCES users(telegram_user_id),
    created_by      INTEGER NOT NULL REFERENCES users(telegram_user_id),
    due_date        TEXT,  -- ISO date YYYY-MM-DD, nullable
    completed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date) WHERE status = 'open';
CREATE INDEX idx_tasks_assignee ON tasks(assignee_user_id, status);

-- напоминания: чтобы не слать дубликат «за день до»
CREATE TABLE sent_reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    reminder_type TEXT NOT NULL,  -- deadline_1d
    sent_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(task_id, reminder_type)
);
```

**Связи:**

- `users.active_project_id` → текущий проект пользователя.
- Задачи общие: оба пользователя видят все задачи всех проектов.
- `assignee_user_id` nullable — «без исполнителя» допустимо.

---

## 6. Пользовательские сценарии

### Срез 1 (MVP)

1. **Голосовая фиксация задач (happy path)**  
   Рита шлёт voice: «По Ивановым — заказать плитку, Сеня уточнит срок у поставщика, до пятницы скинуть варианты света»  
   → Whisper → агент определяет проект «Ивановы» → `set_active_project` (если нужно) → `create_tasks` (3 задачи, assignee=Сеня для второй) → «Создала 3 задачи по проекту Ивановы».

2. **Смена активного проекта**  
   «Работаем по Петровым» → `set_active_project` → подтверждение.

3. **Список задач**  
   «Что у меня на этой неделе?» → `list_tasks` (фильтр assignee=я, due в пределах недели).

4. **Просроченные**  
   «Что просрочено?» → `list_tasks(overdue=true)`.

5. **Завершение**  
   «Плитку заказали» → агент находит задачу → `complete_task`.

6. **Новый проект**  
   «Новый проект Сидоровы» → `create_project` → становится active.

7. **Дайджест 09:00**  
   Каждому: просроченные + задачи на сегодня + на неделю (свои и общие без assignee).

8. **Напоминание за день до дедлайна**  
   Разовое TG-сообщение assignee (или обоим, если assignee не указан).

### Срез 2 (вне этой спеки, только контур)

9. «Собери отчёт для клиента за неделю» → `generate_client_report` (5 блоков).

---

## 7. Tools (срез 1)

| Tool | Описание | Вход | Выход (JSON) |
|------|----------|------|--------------|
| `list_projects` | Активные проекты | `status?` (default active) | `{projects: [{id, name}]}` |
| `create_project` | Новый проект | `name: str` | `{id, name, status}` |
| `get_active_project` | Текущий проект пользователя | `user_id: int` | `{project_id, name}` или `{project_id: null}` |
| `set_active_project` | Установить активный проект | `user_id, project_id` | `{ok, project}` |
| `create_tasks` | Batch создание | `user_id, project_id, tasks[]` | `{created: [{id, title}], count}` |
| `list_tasks` | Список с фильтрами | `user_id, project_id?, mine_only?, status?, overdue?` | `{tasks: [...]}` |
| `complete_task` | Закрыть задачу | `user_id, task_id` | `{ok, task}` |

**Правила для агента (в промпте):**

- Упоминание фамилии клиента («Ивановы») → сопоставить с `list_projects`; при неоднозначности — см. **§7.1**.
- Голосовой batch → один вызов `create_tasks`, не три отдельных.
- Действия выполнять через tools, не описывать намерение текстом.
- Ответы пользователю — на русском, кратко.
- Сегодняшняя дата в промпте для парсинга «до пятницы».

### 7.1 Неоднозначный проект (гибрид C)

Логика выбора проекта (в порядке приоритета):

1. Если в сообщении явно назван проект и совпадение **одно** → использовать его.
2. Если совпадений **несколько** и есть **активный проект** среди кандидатов → использовать активный (без вопроса).
3. Если совпадений **несколько** и активный не помогает:
   - **Текстовое сообщение** → inline-кнопки с вариантами проектов (`CallbackQuery`).
   - **Голосовое** → текстовый вопрос: «Нашла N проектов: … Какой имеешь в виду?» (ответ текстом или голосом).

Состояние «ожидаем выбор проекта» хранится в `session` per user до ответа или таймаута (30 мин).

### 7.2 Алиасы дизайнеров

Два пользователя студии; `display_name` и алиасы в конфиге / БД:

| Имя в системе | Алиасы (распознавание в голосе/чате) | `telegram_user_id` |
|---------------|--------------------------------------|--------------------|
| Сеня | Сеня, Сенечка, Арсений | из `.env` (первый id) |
| Рита | Рита, Маргарита | из `.env` (второй id) |

- Конфиг: `interior_studio/config.py` → `USER_ALIASES: dict[str, int]` (алиас → `telegram_user_id`).
- При первом сообщении user upsert в `users` с `display_name` из маппинга.
- В system prompt: явный блок «Сеня = user_id X, Рита = user_id Y» для `assignee_user_id` в `create_tasks`.

---

## 8. Голосовой pipeline (вне графа)

```
Telegram voice.ogg
  → скачать файл
  → OpenAI Whisper API (whisper-1)
  → текст на русском
  → HumanMessage(content=transcript)
  → agent.invoke(messages + user_id в tool context)
  → ответ в Telegram
```

- Ошибка Whisper → «Не разобрал голосовое, напиши текстом».
- Лимит длины voice: стандартный TG (до ~1 мин) — достаточно для MVP.

---

## 9. Telegram-слой

- Библиотека: `python-telegram-bot` v21+ (async).
- Handlers: `MessageHandler` (text), `MessageHandler` (voice), `CallbackQueryHandler` (выбор проекта).
- Whitelist: если `user.id not in ALLOWED_IDS` → молча игнорировать или «Доступ закрыт».
- Одна сессия истории на `telegram_user_id` (список LangChain messages в памяти; лимит ~20 последних сообщений для контекста).
- `user_id` передаётся в tools через `InjectedToolArg` или closure при сборке графа per-request.

---

## 10. Напоминания (APScheduler)

| Job | Cron | Действие |
|-----|------|----------|
| `morning_digest` | `0 9 * * *` Europe/Moscow | Для каждого user: просроченные + today + week |
| `deadline_reminder` | `0 9 * * *` Europe/Moscow | Задачи с `due_date = tomorrow`, status=open, нет записи в `sent_reminders` |

- Отправка через тот же `TELEGRAM_BOT_TOKEN`.
- **Один процесс:** APScheduler стартует в `bot/main.py` при запуске приложения (`AsyncIOScheduler`), один systemd unit на VPS.
- Отдельный `scheduler/main.py` не нужен для MVP.

---

## 11. System prompt (контур)

Ключевые блоки (полный текст — в `agent/prompt.py` при реализации):

1. Роль: ассистент студии дизайна интерьера.
2. Сегодняшняя дата (ISO).
3. Список tools с кратким назначением.
4. Правила: русский UX, один tool за шаг, не выдумывать данные, создавать задачи сразу (без human gate).
5. Контекст проекта: сначала активный, иначе по имени в сообщении.
6. Сеня / Рита → `telegram_user_id` (алиасы из §7.2).

---

## 12. Тестирование

| Уровень | Что | Файлы |
|---------|-----|-------|
| Unit | services + парсинг дат | `test_tools_*.py` |
| Unit | scheduler: выборка задач для digest/reminder | `test_scheduler.py` |
| Integration | tools с тестовой SQLite in-memory | `test_tools_*.py` |
| Agent | tool calling: 10 типичных фраз → ожидаемый tool | `test_tool_calling.py` |
| Manual | Whisper на 10 реальных голосовых | чеклист в пилоте |

**`test_tool_calling.py` — обязательные кейсы:**

1. «По Ивановым заказать плитку» → `create_tasks`
2. «Работаем по Петровым» → `set_active_project`
3. «Что у меня на неделе?» → `list_tasks`
4. «Что просрочено?» → `list_tasks(overdue=true)`
5. «Плитку заказали» → `complete_task`
6. «Новый проект Сидоровы» → `create_project`
7. «Покажи все проекты» → `list_projects`
8. Batch из 3 задач в одной фразе → один `create_tasks`
9. Без указания проекта при установленном active → `create_tasks` с active project
10. Неясный проект (текст) → inline-кнопки, без tool до выбора
11. Неясный проект (голос) → текстовый уточняющий вопрос, без tool

Для CI без API: mock LLM с `AIMessage(tool_calls=[...])`. Опционально: маркер `@pytest.mark.live` для реального OpenAI.

---

## 13. Нефункциональные требования

- Язык ответов бота: **русский**.
- LLM ReAct-агента: `LLM_PROVIDER` (`openai` | `deepseek`), default `openai`.
  - OpenAI: `OPENAI_MODEL` (default `gpt-4o-mini`).
  - DeepSeek: `DEEPSEEK_MODEL` (default `deepseek-chat`), `DEEPSEEK_BASE_URL`, `DEEPSEEK_API_KEY`.
- Whisper (голос): всегда OpenAI (`OPENAI_API_KEY`, `WHISPER_MODEL`).
- Лимит итераций ReAct: **10** (recursion_limit в invoke).
- Температура LLM: **0**.
- Секреты только в `.env`, не в git.
- `data/studio.db` в `.gitignore`.
- Логирование: `logging` module, без PII в info-уровне.
- Деплой: **Timeweb Cloud VPS** (облачный сервер), один процесс бота+scheduler, systemd unit — см. §13.1.

### 13.1 Деплой (Timeweb Cloud VPS)

**Провайдер:** [Timeweb Cloud](https://timeweb.cloud) — раздел «Облачные серверы».

**Почему VPS, а не App Platform / Kubernetes:** бот работает через long polling + APScheduler 24/7; SQLite на локальном диске; один systemd-процесс — проще и дешевле для 2 пользователей.

| Параметр | Значение |
|----------|----------|
| Сервис Timeweb | Облачные серверы (VPS) |
| ОС | Ubuntu 22.04 LTS или 24.04 LTS |
| Минимум | 1 vCPU, 1 GB RAM, 10 GB SSD |
| Сеть | Исходящий HTTPS (443) к OpenAI, DeepSeek, Telegram API |
| Входящие порты | Не требуются (long polling, не webhook) |

**Структура на сервере:**

```
/opt/interior-studio/          # клон репозитория help_agent
├── .env                       # секреты, chmod 600, не в git
├── venv/                      # Python 3.11+
├── data/
│   └── studio.db              # персистентная БД
└── ...
```

**systemd unit** (`deploy/interior-studio-bot.service`):

- `Type=simple`
- `User=interior` (отдельный непривилегированный пользователь)
- `WorkingDirectory=/opt/interior-studio`
- `EnvironmentFile=/opt/interior-studio/.env`
- `ExecStart=/opt/interior-studio/venv/bin/python -m interior_studio.bot.main`
- `Restart=on-failure`, `RestartSec=10`
- `StandardOutput=journal`, `StandardError=journal`

**Первичная настройка сервера (чеклист):**

1. Создать VPS в Timeweb Cloud (Ubuntu, SSH-ключ).
2. `apt update && apt install -y python3 python3-venv python3-pip git`
3. Создать пользователя `interior`, клонировать репо в `/opt/interior-studio`.
4. `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
5. Скопировать `.env` с dev-машины (токены, user ids, API keys).
6. `init_db` + `seed_projects`.
7. Установить и запустить systemd unit.
8. Проверить: `systemctl status`, написать боту в Telegram.

**Обновление (redeploy):**

```bash
cd /opt/interior-studio
git pull
source venv/bin/activate && pip install -r requirements.txt
sudo systemctl restart interior-studio-bot
```

**Бэкап:** периодический копирующий бэкап `data/studio.db` (cron или ручной; Timeweb snapshot VPS — опционально).

**Мониторинг:** `journalctl -u interior-studio-bot -f`; при падении — auto-restart через systemd.

**Не в срезе 1:** CI/CD, Docker, webhook вместо polling, managed PostgreSQL.

---

## 14. Критерии приёмки (срез 1)

- [ ] Whitelist: третий user_id не может пользоваться ботом.
- [ ] Текст и голос обрабатываются; voice → Whisper → агент.
- [ ] Happy path (3 задачи по «Ивановым», assignee Сеня) работает.
- [ ] Гибрид C: текст → кнопки; голос → текстовый вопрос при неоднозначном проекте.
- [ ] Алиасы Сеня/Рита корректно проставляют `assignee_user_id`.
- [ ] `set_active_project` / авто-выбор проекта по имени.
- [ ] `list_tasks` с фильтрами mine / overdue / project.
- [ ] `complete_task` меняет status и `completed_at`.
- [ ] Дайджест 09:00 МСК приходит обоим пользователям.
- [ ] Напоминание за 1 день до дедлайна — один раз per task.
- [ ] `pytest tests/interior_studio/ -v` — зелёный.
- [ ] `test_tool_calling` — ≥9/10 на mock; live-тесты документированы.
- [ ] Бот запущен на Timeweb Cloud VPS через systemd; отвечает в Telegram после рестарта сервера.
- [ ] `deploy/README.md` и `deploy/interior-studio-bot.service` в репозитории.

---

## 15. Границы

**Всегда:**

- Тесты на новую логику.
- Секреты в `.env`.
- Русский UX.
- Паттерн `airline_react_agent.py` для графа.

**Никогда (срез 1):**

- Секреты в репозитории.
- Яндекс.Диск / RAG.
- PDF-отчёты, Google Calendar, human gate на создание задач.
- Клиентский доступ к боту.
- 15+ tools.

---

## 16. Вне scope (срез 1)

См. `docs/ideas/interior-studio-assistant.md` — без изменений:

- `generate_client_report` → **срез 2**
- RAG + Яндекс.Диск → **срез 3**
- Human gate, CSV-импорт, мульти-агент — отложено

---

## 17. Принятые решения

| Вопрос | Решение |
|--------|---------|
| ORM | **SQLAlchemy 2.x** |
| Дизайнеры | **Сеня** и **Рита**; алиасы — §7.2 |
| Неоднозначный проект | **Гибрид C:** текст → inline-кнопки; голос → текстовый вопрос |
| Scheduler | **Один процесс** с ботом (`AsyncIOScheduler` в `bot/main.py`) |
| LLM агента | **DeepSeek** по умолчанию в dev (`LLM_PROVIDER=deepseek`); OpenAI-compatible API через `ChatOpenAI` + `base_url` |
| Whisper | **OpenAI** независимо от `LLM_PROVIDER` |
| Хостинг / деплой | **Timeweb Cloud VPS** (облачные серверы), systemd unit — §13.1 |

---

## 18. Зависимости (предварительный список)

```
python-telegram-bot>=21.0
apscheduler>=3.10
sqlalchemy>=2.0
langchain-openai
langgraph
langchain-core
pydantic>=2
python-dotenv
pytest
pytest-asyncio
```

Существующие зависимости из `requirements.txt` проекта — переиспользовать.
