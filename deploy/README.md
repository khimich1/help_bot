# Деплой Interior Studio Assistant на Timeweb Cloud VPS

Бот работает через **long polling** (входящие порты не нужны) + **APScheduler** в том же процессе (`interior_studio.bot.main`).

Спека: [`docs/specs/interior-studio-assistant.md`](../docs/specs/interior-studio-assistant.md) §13.1.

---

## Требования

| Параметр | Значение |
|----------|----------|
| Провайдер | [Timeweb Cloud](https://timeweb.cloud) → Облачные серверы |
| ОС | Ubuntu 22.04 LTS или 24.04 LTS |
| Минимум | 1 vCPU, 1 GB RAM, 10 GB SSD |
| Исходящий трафик | HTTPS (443) к Telegram API, OpenAI, DeepSeek |
| Входящие порты | **Не открывать** (не webhook) |

---

## 1. Создать VPS в Timeweb

1. Панель Timeweb Cloud → **Облачные серверы** → Создать сервер.
2. ОС: Ubuntu 22.04 или 24.04.
3. Конфигурация: минимум 1 vCPU / 1 GB RAM.
4. Добавить SSH-ключ (рекомендуется) или задать пароль root.
5. Записать публичный IP.

Firewall: разрешить только SSH (22) с вашего IP. Порты 80/443 для **входящих** не нужны.

---

## 2. Первичная настройка сервера

Подключиться по SSH:

```bash
ssh root@<VPS_IP>
```

Установить зависимости:

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git
```

Создать непривилегированного пользователя:

```bash
useradd -m -s /bin/bash interior
mkdir -p /opt/interior-studio
chown interior:interior /opt/interior-studio
```

Клонировать репозиторий (от root, затем передать владельца):

```bash
cd /opt
git clone <URL_РЕПОЗИТОРИЯ> interior-studio
chown -R interior:interior /opt/interior-studio
```

Переключиться на пользователя `interior`:

```bash
su - interior
cd /opt/interior-studio
```

Создать venv и установить зависимости:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Настроить `.env`

Скопировать с dev-машины (не коммитить в git):

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

Обязательные переменные:

```env
TELEGRAM_BOT_TOKEN=<токен от @BotFather>
TELEGRAM_ALLOWED_USER_IDS=<id_Сени>,<id_Риты>
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...          # Whisper всегда через OpenAI
DATABASE_URL=sqlite:///./data/studio.db
```

Первый id в `TELEGRAM_ALLOWED_USER_IDS` — **Сеня**, второй — **Рита**.

---

## 4. Инициализация БД

```bash
source venv/bin/activate
cd /opt/interior-studio
python -m interior_studio.db.init_db
python -m interior_studio.db.seed_projects --file data/initial_projects.txt
```

Повторный `seed_projects` безопасен (idempotent).

---

## 5. Установить systemd unit

Выйти из сессии `interior` (Ctrl+D) и выполнить от root:

```bash
cp /opt/interior-studio/deploy/interior-studio-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable interior-studio-bot
systemctl start interior-studio-bot
```

Проверка:

```bash
systemctl status interior-studio-bot
journalctl -u interior-studio-bot -n 50 --no-pager
```

Ожидаемо: `active (running)`, в логах `Starting Interior Studio bot (long polling)...`.

---

## 6. Проверка в Telegram

1. Написать боту с аккаунта Сени или Риты: «Покажи проекты».
2. Убедиться, что третий user_id игнорируется.
3. После `sudo reboot` бот должен подняться сам (`systemctl enable`).

---

## Обновление (redeploy)

```bash
su - interior
cd /opt/interior-studio
git pull
source venv/bin/activate
pip install -r requirements.txt
exit
sudo systemctl restart interior-studio-bot
sudo journalctl -u interior-studio-bot -n 30 --no-pager
```

---

## Бэкап `studio.db`

SQLite-файл: `/opt/interior-studio/data/studio.db`.

Ручной бэкап:

```bash
cp /opt/interior-studio/data/studio.db \
   /opt/interior-studio/data/studio.db.bak.$(date +%Y%m%d)
```

Cron (пример, от root — ежедневно в 03:00):

```cron
0 3 * * * cp /opt/interior-studio/data/studio.db /opt/interior-studio/data/backups/studio.db.$(date +\%Y\%m\%d) 2>/dev/null
```

Дополнительно: snapshot VPS в панели Timeweb.

---

## Мониторинг и отладка

| Команда | Назначение |
|---------|------------|
| `systemctl status interior-studio-bot` | Статус сервиса |
| `journalctl -u interior-studio-bot -f` | Логи в реальном времени |
| `journalctl -u interior-studio-bot -n 100` | Последние 100 строк |
| `systemctl restart interior-studio-bot` | Перезапуск после изменений |

При падении процесса systemd перезапустит сервис (`Restart=on-failure`, `RestartSec=10`).

---

## Локальная отладка (без VPS)

```bash
python -m interior_studio.db.init_db
python -m interior_studio.db.seed_projects --file data/initial_projects.txt
python -m interior_studio.bot.main
```

CLI-агент без Telegram:

```bash
python -m interior_studio.agent.cli --trace "Покажи проекты"
```

Тесты:

```bash
pytest tests/interior_studio/ -v
```
