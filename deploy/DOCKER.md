# Деплой через Docker

Бот работает через **long polling** — входящие порты на сервере не нужны.

---

## Требования к VPS

| Параметр | Значение |
|----------|----------|
| ОС | Ubuntu 22.04 / 24.04 LTS |
| RAM | минимум 1 GB (рекомендуется 2 GB если `EMBEDDING_PROVIDER=local`) |
| CPU | 1 vCPU |
| Диск | 10 GB SSD |
| Исходящий трафик | HTTPS 443 (Telegram, OpenAI, DeepSeek) |
| Входящие порты | только SSH (22) |

---

## 1. Подготовка сервера (один раз)

```bash
ssh root@<VPS_IP>

apt update && apt upgrade -y
apt install -y docker.io docker-compose-plugin git
systemctl enable --now docker
```

---

## 2. Клонировать репозиторий

```bash
git clone https://github.com/khimich1/help_bot.git /opt/interior-studio
cd /opt/interior-studio
```

---

## 3. Настроить `.env`

```bash
cp .env.example .env
nano .env          # вставить реальные токены
chmod 600 .env
```

Обязательные переменные:

```env
TELEGRAM_BOT_TOKEN=<токен от @BotFather>
TELEGRAM_ALLOWED_USER_IDS=<id1>,<id2>    # первый = Сеня, второй = Рита

LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...                    # нужен для Whisper (голосовые сообщения)

DATABASE_URL=sqlite:///./data/studio.db
CHROMA_PERSIST_DIR=./data/chroma
EMBEDDING_PROVIDER=openai                # openai безопаснее при 1 GB RAM
```

---

## 4. Создать папки для данных

```bash
mkdir -p data/chroma
```

---

## 5. Собрать образ и запустить

```bash
docker compose build
docker compose up -d
```

Проверить логи:

```bash
docker compose logs -f
```

Ожидаемо в логах: `Starting Interior Studio bot (long polling)...`

При первом запуске `entrypoint.sh` автоматически:
- создаёт таблицы БД (`init_db`)
- засевает начальные проекты из `data/initial_projects.txt`

---

## 6. Проверка

Написать боту с разрешённого Telegram-аккаунта: `Покажи проекты`.

---

## Обновление (redeploy)

```bash
cd /opt/interior-studio
git pull
docker compose build
docker compose up -d
docker compose logs --tail=50
```

---

## Полезные команды

| Команда | Назначение |
|---------|-----------|
| `docker compose logs -f` | Логи в реальном времени |
| `docker compose restart bot` | Перезапустить бот |
| `docker compose down` | Остановить и удалить контейнер |
| `docker compose exec bot python -m interior_studio.agent.cli "Покажи проекты"` | CLI без Telegram |
| `docker ps` | Статус контейнера |

---

## Индексация knowledge (RAG, если нужна)

После запуска — один раз для каждого проекта:

```bash
docker compose exec bot python -m interior_studio.knowledge.index_project \
  --project "Название проекта" \
  --path /app/data/knowledge/название
```

Файлы проекта нужно предварительно положить в `./data/knowledge/` на сервере (монтируется в volume).

---

## Бэкап данных

Все данные (SQLite + Chroma) хранятся в `./data/` на хосте.

```bash
tar czf ~/backup-$(date +%Y%m%d).tar.gz /opt/interior-studio/data
```

Можно добавить в cron (ежедневно в 03:00):

```cron
0 3 * * * tar czf /root/backups/studio-$(date +\%Y\%m\%d).tar.gz /opt/interior-studio/data 2>/dev/null
```
