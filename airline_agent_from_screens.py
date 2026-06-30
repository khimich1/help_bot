"""Демо-агент авиакомпании на LangGraph, собранный по скринам курса."""

import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ------------------------------
# Guardrails: PII в логах, релевантность запроса, защита от инъекций в выводе инструментов
# ------------------------------
PII_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b\d{4}\s\d{6}\b"),
        "[ПАСПОРТ]",
    ),
    (
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            re.IGNORECASE,
        ),
        "[EMAIL]",
    ),
    (
        re.compile(
            r"\b(?:\d[ -]*?){15,16}\d\b",
        ),
        "[КАРТА]",
    ),
    (
        re.compile(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{2}[-.\s]?\d{2}\b"
        ),
        "[ТЕЛЕФОН]",
    ),
]


def mask_pii(text: str) -> str:
    out = text
    for pattern, placeholder in PII_PATTERNS:
        out = pattern.sub(placeholder, out)
    return out


def log_message(role: str, content: str) -> None:
    masked = mask_pii(content)
    preview = masked if len(masked) <= 120 else masked[:120] + "…"
    print(f"[LOG] {role}: {preview}")


# Косвенные prompt injection в тексте правил тарифа (EN + RU)
INJECTION_PATTERNS = re.compile(
    r"(?:\[SYSTEM\]|"
    r"ignore\s+(?:all\s+)?(?:previous|prior)|disregard|"
    r"new\s+instructions?|override|you\s+are\s+now|forget\s+(?:all\s+)?"
    r"(?:previous|prior)?|"
    r"игнорируй(?:те)?\s+(?:все\s+)?(?:предыдущие|ранее)?|"
    r"забудь(?:те)?\s+(?:все\s+)?(?:предыдущие|инструкции)?|"
    r"нов(?:ые|ая)\s+инструкц|"
    r"теперь\s+ты\s+|"
    r"системн(?:ое|ая)\s+сообщен|"
    r"раскрой\s+секрет|"
    r"jailbreak)",
    re.IGNORECASE | re.DOTALL,
)


# ------------------------------
# 0) Небольшая in-memory "база данных"
# (рейсы как на скринах курса: 3× Москва → Париж, 4× Москва → Лондон; SU-104 добавлен по аналогии)
# ------------------------------
FLIGHT_DATE = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

DATABASE = {
    "flights": {
        f"AF-201_{FLIGHT_DATE}": {
            "flight_key": f"AF-201_{FLIGHT_DATE}",
            "flight_id": "AF-201",
            "from": "Moscow",
            "to": "Paris",
            "date": FLIGHT_DATE,
            "time": "08:00",
            "arrival_time": "11:30",
            "fare_class": "economy",
            "stops": 0,
            "fare_rules": (
                "Тариф эконом: бесплатная смена даты до 24 ч до вылета. "
                "Штраф при отмене 25%."
            ),
            "seats": 3,
            "price": 290,
        },
        f"AF-202_{FLIGHT_DATE}": {
            "flight_key": f"AF-202_{FLIGHT_DATE}",
            "flight_id": "AF-202",
            "from": "Moscow",
            "to": "Paris",
            "date": FLIGHT_DATE,
            "time": "17:00",
            "arrival_time": "20:00",
            "fare_class": "business",
            "stops": 0,
            "fare_rules": (
                "Бизнес-класс: полный возврат, бесплатное перебронирование, "
                "приоритетная посадка и зал ожидания."
            ),
            "seats": 2,
            "price": 750,
        },
        f"AF-203_{FLIGHT_DATE}": {
            "flight_key": f"AF-203_{FLIGHT_DATE}",
            "flight_id": "AF-203",
            "from": "Moscow",
            "to": "Paris",
            "date": FLIGHT_DATE,
            "time": "23:30",
            "arrival_time": "03:00",
            "fare_class": "promo",
            "stops": 1,
            "fare_rules": (
                "Промо: без возврата, 1 пересадка в Берлине, смена даты $80."
            ),
            "seats": 4,
            "price": 160,
        },
        f"SU-101_{FLIGHT_DATE}": {
            "flight_key": f"SU-101_{FLIGHT_DATE}",
            "flight_id": "SU-101",
            "from": "Moscow",
            "to": "London",
            "date": FLIGHT_DATE,
            "time": "06:30",
            "arrival_time": "09:30",
            "fare_class": "economy",
            "stops": 0,
            "fare_rules": (
                "Тариф эконом: бесплатная смена даты до 24 ч до вылета. "
                "Штраф при отмене 25%."
            ),
            "seats": 3,
            "price": 320,
        },
        f"SU-104_{FLIGHT_DATE}": {
            "flight_key": f"SU-104_{FLIGHT_DATE}",
            "flight_id": "SU-104",
            "from": "Moscow",
            "to": "London",
            "date": FLIGHT_DATE,
            "time": "10:45",
            "arrival_time": "13:45",
            "fare_class": "economy",
            "stops": 0,
            "fare_rules": (
                "Тариф эконом: бесплатная смена даты до 24 ч до вылета. "
                "Штраф при отмене 25%."
            ),
            "seats": 4,
            "price": 335,
        },
        f"SU-102_{FLIGHT_DATE}": {
            "flight_key": f"SU-102_{FLIGHT_DATE}",
            "flight_id": "SU-102",
            "from": "Moscow",
            "to": "London",
            "date": FLIGHT_DATE,
            "time": "14:00",
            "arrival_time": "17:00",
            "fare_class": "business",
            "stops": 0,
            "fare_rules": (
                "Бизнес-класс: полный возврат, бесплатное перебронирование, "
                "приоритетная посадка и зал ожидания."
            ),
            "seats": 2,
            "price": 890,
        },
        f"SU-103_{FLIGHT_DATE}": {
            "flight_key": f"SU-103_{FLIGHT_DATE}",
            "flight_id": "SU-103",
            "from": "Moscow",
            "to": "London",
            "date": FLIGHT_DATE,
            "time": "22:15",
            "arrival_time": "01:15",
            "fare_class": "promo",
            "stops": 0,
            "fare_rules": (
                "Промо: без возврата, смена даты $100, выбор места недоступен."
            ),
            "seats": 5,
            "price": 185,
        },
    },
    "bookings": {
        "BKG-123": {
            "booking_id": "BKG-123",
            "flight_key": f"AF-201_{FLIGHT_DATE}",
            "passenger_name": "Jane Doe",
            "status": "confirmed",
        }
    },
}

# Как в курсе: список рейсов для поиска (те же dict, что в DATABASE["flights"]).
FLIGHTS: List[dict] = list(DATABASE["flights"].values())

# ------------------------------
# Долгосрочная память: профиль пассажира на диске (как в курсе)
# ------------------------------
DATA_DIR = Path("data")
PROFILE_PATH = DATA_DIR / "passenger_profile.json"
BOOKINGS_PATH = DATA_DIR / "bookings.json"


def load_profile() -> dict:
    """Загрузить профиль из JSON; при отсутствии файла или битом JSON — пустой dict."""
    if not PROFILE_PATH.is_file():
        return {}
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        save_profile({})
        return {}


def save_profile(profile: dict) -> None:
    """Сохранить профиль в data/passenger_profile.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_bookings() -> dict:
    """Загрузить бронирования из JSON; при отсутствии файла или битом JSON — пустой dict."""
    if not BOOKINGS_PATH.is_file():
        return {}
    try:
        raw = json.loads(BOOKINGS_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        save_bookings({})
        return {}


def save_bookings(bookings: dict) -> None:
    """Сохранить бронирования в data/bookings.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BOOKINGS_PATH.write_text(
        json.dumps(bookings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _init_profile_store() -> None:
    if not PROFILE_PATH.is_file():
        save_profile({})


_init_profile_store()


def _sync_bookings_store() -> None:
    """Синхронизировать in-memory брони с файлом на диске."""
    loaded = load_bookings()
    merged = {**DATABASE["bookings"], **loaded}
    DATABASE["bookings"] = merged
    save_bookings(merged)


_sync_bookings_store()


def resolve_date(date_str: str) -> str:
    """Преобразует относительные даты в YYYY-MM-DD.

    Понимает: today, tomorrow, next week, monday … sunday, next monday … next sunday;
    строку уже в формате YYYY-MM-DD возвращает без изменений (если не совпала с ключевыми словами).
    """
    s = date_str.strip().lower()
    today = datetime.date.today()
    if s in ("today", "сегодня"):
        return today.isoformat()
    if s in ("tomorrow", "завтра"):
        return (today + datetime.timedelta(days=1)).isoformat()
    if s in ("next week", "следующая неделя", "через неделю"):
        return (today + datetime.timedelta(days=7)).isoformat()
    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    ru_weekdays = [
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    ]
    for prefix in ("next ", ""):
        for i, name in enumerate(weekdays):
            if s == prefix + name:
                days_ahead = (i - today.weekday()) % 7 or 7
                return (today + datetime.timedelta(days=days_ahead)).isoformat()
    for prefix in ("следующий ", ""):
        for i, name in enumerate(ru_weekdays):
            if s == prefix + name:
                days_ahead = (i - today.weekday()) % 7 or 7
                return (today + datetime.timedelta(days=days_ahead)).isoformat()
    return date_str


# ------------------------------
# 1) Инструменты
# ------------------------------
CITY_ALIASES = {
    "москва": "Moscow",
    "париж": "Paris",
    "лондон": "London",
    "moscow": "Moscow",
    "paris": "Paris",
    "london": "London",
}


def _normalize_city(name: str) -> str:
    key = name.strip().casefold()
    return CITY_ALIASES.get(key, name.strip())


@tool
def get_booking(booking_id: str) -> str:
    """Получить бронирование по ID."""
    print(f"[TOOL] get_booking(booking_id={booking_id!r})")
    booking_record = DATABASE["bookings"].get(booking_id)
    if not booking_record:
        return json.dumps(
            {"error": f"Бронирование {booking_id} не найдено"}, ensure_ascii=False
        )

    flight_record = DATABASE["flights"].get(booking_record["flight_key"], {})
    return json.dumps(
        {"booking_id": booking_id, **booking_record, "flight": flight_record},
        ensure_ascii=False,
    )


@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Найти доступные рейсы между двумя городами на дату.

    Параметр date: YYYY-MM-DD или фразы: завтра, сегодня, следующая неделя, понедельник …
    Города: Moscow / Москва, Paris / Париж, London / Лондон (регистр не важен).
    """
    print(
        f"[TOOL] search_flights(origin={origin!r}, destination={destination!r}, date={date!r})"
    )
    resolved = resolve_date(date)
    catalog_dates = {f["date"] for f in FLIGHTS}
    if catalog_dates and resolved not in catalog_dates:
        fallback_date = FLIGHT_DATE if FLIGHT_DATE in catalog_dates else min(catalog_dates)
        print(
            "[TOOL] search_flights -> normalized date "
            f"{resolved!r} -> {fallback_date!r} (catalog fallback)"
        )
        resolved = fallback_date
    o = _normalize_city(origin).casefold()
    d = _normalize_city(destination).casefold()
    results = [
        flight
        for flight in FLIGHTS
        if flight["from"].casefold() == o
        and flight["to"].casefold() == d
        and flight["date"] == resolved
        and flight["seats"] > 0
    ]
    results = sorted(results, key=lambda f: f["time"])
    print(f"[TOOL] search_flights -> found {len(results)} flights")
    if not results:
        return (
            f"Рейсов из {origin} в {destination} на дату {resolved} не найдено."
        )
    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def cancel_booking(booking_id: str) -> str:
    """Отменить бронирование."""
    print(f"[TOOL] cancel_booking(booking_id={booking_id!r})")
    booking_record = DATABASE["bookings"].get(booking_id)
    if not booking_record:
        return json.dumps({"error": "Бронирование не найдено"}, ensure_ascii=False)

    flight_record = DATABASE["flights"].get(booking_record["flight_key"])

    booking_record["status"] = "cancelled"
    if flight_record:
        flight_record["seats"] += 1

    save_bookings(DATABASE["bookings"])
    refund_amount = flight_record["price"] if flight_record else 0
    return json.dumps({"success": True, "refund": refund_amount}, ensure_ascii=False)


@tool
def update_passenger_profile(key: str, value: str) -> str:
    """Обновить поле постоянного профиля пассажира.

    Рекомендуемые поля: name, passport, email, seat_preference, meal_preference,
    dietary_preference.
    """
    print(f"[TOOL] update_passenger_profile(key={key!r}, value={value!r})")
    profile = load_profile()
    profile[key] = value
    save_profile(profile)
    return f"Профиль обновлён: {key} = «{value}»"


# ------------------------------
# 2) Промпт (системный)
# ------------------------------
AGENT_BEHAVIOR_RULES: List[str] = [
    "Всегда отвечай пользователю на русском языке.",
    "Используй инструменты, когда это нужно для точного ответа.",
    "Никогда не выдумывай детали брони, рейса, цены или статуса.",
    "Если данных недостаточно, задавай уточняющие вопросы.",
    "Перед отменой бронирования попроси явное подтверждение пользователя.",
    "Сначала получи текущее бронирование, и только потом предлагай изменения.",
]

POLICIES: List[Dict[str, str]] = [
    {
        "title": "Компенсация за задержку рейса",
        "content": (
            "Пассажиры имеют право на компенсацию, если рейс задержан более чем на 4 часа "
            "в пункте назначения. Размер компенсации: при задержке 4–8 часов — 25% от стоимости билета; "
            "при задержке более 8 часов — 50% от стоимости билета. Авиакомпания также предоставляет "
            "бесплатное питание, напитки и проживание в отеле при ночной задержке. Компенсация не полагается "
            "при форс-мажорных обстоятельствах (суровая погода, забастовки диспетчеров и т.п.)."
        ),
    },
    {
        "title": "Отмена рейса авиакомпанией",
        "content": (
            "Если авиакомпания отменяет рейс, пассажиры вправе получить полный возврат стоимости билета "
            "или перебронирование на ближайший доступный рейс без доплаты. При уведомлении менее чем за 14 дней "
            "до вылета полагается дополнительная компенсация в размере 50% от стоимости билета. "
            "При ночном ожидании из-за отмены предоставляются отель и питание."
        ),
    },
    {
        "title": "Сборы за перебронирование",
        "content": (
            "Сборы зависят от класса обслуживания. Эконом: $50 при смене более чем за 24 ч до вылета, "
            "$100 — в течение 24 ч до вылета. Бизнес: бесплатное перебронирование в любое время. "
            "Промо: $100 независимо от срока. При смене даты возможна доплата из-за разницы тарифов — "
            "если новый рейс дороже, пассажир оплачивает разницу."
        ),
    },
    {
        "title": "Возврат по промо-тарифу",
        "content": (
            "Билеты по промо-тарифу невозвратные. Денежная компенсация при отмене не предусмотрена. "
            "Исключение: при подтверждённом медицинском форс-маже можно подать заявление на полный возврат, "
            "приложив справку в течение 30 дней после даты рейса. Рассмотрение заявки — до 14 рабочих дней."
        ),
    },
    {
        "title": "Возврат по тарифу эконом",
        "content": (
            "Билеты эконом возвратные со штрафом. Отмена более чем за 72 ч до вылета: удержание 25% от тарифа. "
            "Отмена в течение 72 ч до вылета: удержание 50%. Неявка без предварительной отмены: билет "
            "аннулируется без возмещения."
        ),
    },
    {
        "title": "Норма зарегистрированного багажа",
        "content": (
            "Норма по классу: Промо — 1 место до 20 кг; Эконом — 1 место до 23 кг; Бизнес — 2 места по 32 кг. "
            "Перевес: $15 за каждый кг сверх нормы. Негабарит (сумма трёх измерений свыше 158 см): $75 за место. "
            "Спортинвентарь (лыжи, велосипеды, гольф) декларируется при регистрации, возможны доп. сборы."
        ),
    },
    {
        "title": "Ручная кладь и ограничения",
        "content": (
            "Разрешены одна сумка ручной клади (до 10 кг, габариты до 55×40×20 см) и один предмет личных вещей "
            "(сумка для ноутбука, дамская сумка). Жидкости — в ёмкостях до 100 мл, в прозрачном пакете "
            "(общий объём до 1 л). Острые предметы, легковоспламеняющиеся вещества и литиевые батареи "
            "свыше 100 Вт·ч в ручной клади запрещены."
        ),
    },
    {
        "title": "Начисление миль",
        "content": (
            "Мили начисляются за пройденное расстояние с коэффициентом по классу. Эконом: коэффициент 1× "
            "(1 миля за 1 км). Бизнес: 2×. Промо: 0,5×. Зачисление на счёт — в течение 72 ч после рейса. "
            "Рейсы партнёрских авиакомпаний: 0,5× независимо от класса."
        ),
    },
    {
        "title": "Списание миль при отмене",
        "content": (
            "Мили, оплаченные билет за вознаграждение, при отмене подлежат списанию. Отмена более чем за 30 дней: "
            "полное восстановление миль, сбор за обработку $25. Отмена в течение 30 дней: теряется 50% миль. "
            "Неявка: мили не возвращаются. Мили, начисленные за отменённый рейс, также сторнируются."
        ),
    },
    {
        "title": "Перевозка животных в салоне",
        "content": (
            "Мелкие животные (кошки и собаки) могут лететь в салоне, если суммарный вес с переноской не более 8 кг. "
            "Переноска должна помещаться под креслом (до 45×30×25 см). Один питомец на пассажира. "
            "Сбор $50 за рейс. Требуется предварительное бронирование — в салоне не более 2 мест для животных на рейс."
        ),
    },
    {
        "title": "Перевозка животных в багаже",
        "content": (
            "Крупные животные — в грузовом отсеке в контейнере по стандартам IATA. Максимальный вес (животное + контейнер): "
            "75 кг. Чувствительные к температуре породы и рептилии могут быть ограничены на отдельных направлениях. "
            "Нужна ветеринарная справка, выданная не ранее чем за 10 дней до вылета. Сбор: $100–200 в зависимости от размера."
        ),
    },
    {
        "title": "Смена даты вылета",
        "content": (
            "Смена даты разрешена во всех классах при наличии мест и согласно сборам. Эконом и Промо: заявка "
            "не позднее чем за 2 ч до вылета. Бизнес: до 30 минут до вылета. Если новый рейс дороже — доплата "
            "по разнице тарифов. Если дешевле — разница не возвращается."
        ),
    },
]


def _format_policies_for_prompt(policies: List[Dict[str, str]]) -> str:
    parts = []
    for item in policies:
        parts.append(f"### {item['title']}\n{item['content']}")
    return "\n\n".join(parts)


STOP_WORDS_EN = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
    "them", "their", "this", "that", "these", "those", "what", "which",
    "who", "whom", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "not",
    "only", "same", "so", "than", "too", "very", "just", "but", "and",
    "or", "if", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "up", "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again", "then",
    "once", "here", "there", "am", "also", "as",
}
STOP_WORDS_RU = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "её", "еще", "ещё", "мне", "было", "вот", "от",
    "меня", "о", "из", "ему", "если", "уже", "или", "быть", "был", "была",
    "были", "до", "вас", "ни", "себя", "при", "они", "там", "тут", "где",
    "есть", "ничего", "потом", "через", "это", "этот", "эта", "эти", "для",
    "без", "про", "над", "под", "мы", "оно", "будет", "мой", "твой",
    "наш", "ваш", "их", "свою", "который", "которая", "которые", "чтобы",
    "когда", "почему", "очень", "также", "лишь", "весь", "всего",
    "тоже", "ли", "либо", "нибудь", "какой", "какая", "какие",
}
STOP_WORDS = STOP_WORDS_EN | STOP_WORDS_RU

WORD_TOKEN_RE = re.compile(r"[a-zа-яё]+", re.IGNORECASE)

SCORE_THRESHOLD = 4  # Minimum keyword matches to include a chunk


def keyword_score(query: str, chunk: dict) -> int:
    """Считает совпадения слов запроса с заголовком и текстом чанка (EN/RU)."""
    raw = query.lower().replace("ё", "е")
    words = set(WORD_TOKEN_RE.findall(raw)) - STOP_WORDS
    text = (chunk["title"] + " " + chunk["content"]).lower().replace("ё", "е")
    return sum(1 for w in words if w in text)


@tool
def lookup_policy(query: str) -> str:
    """Поиск по справочнику политик авиакомпании.

    В `query` передай вопрос пассажира или (для вопросов о правилах, предпочтительно)
    короткий гипотетический отрывок в стиле политики (HyDE). Возвращает до двух
    разделов выше порога релевантности или сообщение, если ничего не найдено.
    """
    print(f"[TOOL] lookup_policy(query={query!r})")
    scored = [(chunk, keyword_score(query, chunk)) for chunk in POLICIES]
    hits = [(chunk, score) for chunk, score in scored if score > 0]
    hits_sorted = sorted(hits, key=lambda x: x[1], reverse=True)
    for chunk, score in hits_sorted:
        marker = "✅" if score >= SCORE_THRESHOLD else "X"
        print(f"  {marker} [{score}] {chunk['title']}")
    relevant = sorted(
        [(chunk, score) for chunk, score in scored if score >= SCORE_THRESHOLD],
        key=lambda x: x[1],
        reverse=True,
    )[:2]
    if not relevant:
        print("[TOOL] lookup_policy -> no results above threshold...")
        return "Подходящих разделов политики не найдено."
    titles = [chunk["title"] for chunk, _ in relevant]
    print(f"[TOOL] lookup_policy -> found: {titles}")
    parts = []
    for chunk, score in relevant:
        parts.append(f"### {chunk['title']}\n{chunk['content']}")
    return "\n\n".join(parts)


class BookingRequest(BaseModel):
    """Схема запроса на бронирование: LangChain передаёт её в LLM как JSON Schema инструмента;
    Pydantic проверяет аргументы до вызова функции."""

    flight_id: str = Field(
        description=(
            "Идентификатор рейса из результатов search_flights (например, SU-101)."
        )
    )
    passenger_name: str = Field(description="Полное имя пассажира.")
    email: str = Field(
        description=(
            "Электронная почта для подтверждения брони. Если в профиле нет — "
            "спросите у пассажира до вызова инструмента."
        )
    )
    passport: str = Field(
        description=(
            "Номер паспорта. Берите из профиля, если есть; иначе запросите до вызова инструмента."
        )
    )
    seat_preference: Optional[str] = Field(
        default=None,
        description="Предпочтение по месту (например, у окна, у прохода). Из профиля, если есть.",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Некорректный адрес электронной почты")
        return v.lower().strip()

    @field_validator("flight_id")
    @classmethod
    def validate_flight_id(cls, v: str) -> str:
        flight_ids = [f["flight_id"] for f in FLIGHTS]
        if v not in flight_ids:
            raise ValueError(
                f"Неизвестный flight_id «{v}». Доступные: {flight_ids}"
            )
        return v


def _approval_confirmed(approval: object) -> bool:
    s = str(approval).strip().lower()
    return s in ("approved", "одобрено", "да", "ok", "yes")


@tool(args_schema=BookingRequest)
def book_flight(
    flight_id: str,
    passenger_name: str,
    email: str,
    passport: str,
    seat_preference: Optional[str] = None,
) -> str:
    """Забронировать рейс для пассажира.

    Аргументы уже проверены схемой BookingRequest. Если email или паспорт отсутствуют
    в профиле пассажира — сначала запросите их у пользователя, затем вызывайте инструмент.
    """
    print(
        f"[TOOL] book_flight(flight_id={flight_id!r}, passenger_name={passenger_name!r}, "
        f"email={email!r}, passport={passport!r}, seat_preference={seat_preference!r})"
    )
    flight = next(f for f in FLIGHTS if f["flight_id"] == flight_id)
    approval = interrupt(
        {
            "action": "book_flight",
            "действие": "бронирование рейса",
            "flight_id": flight_id,
            "пассажир": passenger_name,
            "email": email,
            "паспорт": passport,
            "предпочтение_места": seat_preference,
            "детали_рейса": {
                "откуда": flight["from"],
                "куда": flight["to"],
                "дата": flight["date"],
                "время_вылета": flight["time"],
                "класс": flight["fare_class"],
                "цена_usd": flight["price"],
            },
        }
    )

    if not _approval_confirmed(approval):
        return f"Бронирование отменено оператором: {approval}"

    ref = "BK" + hashlib.md5(f"{flight_id}{email}".encode()).hexdigest()[:6].upper()
    flight_key = flight["flight_key"]
    DATABASE["bookings"][ref] = {
        "booking_id": ref,
        "flight_key": flight_key,
        "passenger_name": passenger_name,
        "status": "confirmed",
    }
    save_bookings(DATABASE["bookings"])
    if flight.get("seats", 0) > 0:
        flight["seats"] -= 1

    passport_line = f"\n  Паспорт: {passport}"
    seat_line = seat_preference or "нет предпочтений"

    return (
        f"✅ Бронирование подтверждено!\n"
        f"  Код бронирования: {ref}\n"
        f"  Рейс: {flight_id} — {flight['from']} → {flight['to']}\n"
        f"  Дата: {flight['date']}  Вылет: {flight['time']}\n"
        f"  Класс: {flight['fare_class']}  Цена: ${flight['price']}\n"
        f"  Пассажир: {passenger_name}{passport_line}\n"
        f"  Электронная почта: {email}\n"
        f"  Предпочтение по месту: {seat_line}"
    )


TOOLS = [
    get_booking,
    search_flights,
    cancel_booking,
    update_passenger_profile,
    lookup_policy,
    book_flight,
]


SYSTEM_PROMPT_CLI = (
    "Ты полезный ассистент службы поддержки авиакомпании.\n"
    "Отвечай пассажиру на русском языке.\n\n"
    "## Поведение\n"
    + "\n".join(f"- {p}" for p in AGENT_BEHAVIOR_RULES)
    + "\n\n"
    "## Использование инструментов\n"
    "- Для фактов о рейсах, брони, цене и правилах всегда вызывай инструменты, не придумывай данные.\n"
    "- Если пользователь называет личные данные (имя, email, паспорт, предпочтения), сразу сохраняй их через update_passenger_profile.\n"
    "- Для вопросов о правилах авиакомпании используй lookup_policy. В query можно передавать короткий HyDE-отрывок по теме запроса.\n"
    "- Для бронирования используй book_flight только когда известны flight_id, passenger_name, email и passport.\n"
    "- При поиске рейсов передавай в date исходный запрос пользователя (например, «сегодня», «завтра») или валидную актуальную дату в формате YYYY-MM-DD; не выдумывай прошлые годы.\n"
    "- Перед отменой бронирования сначала вызови get_booking по booking_id и запроси явное подтверждение пользователя; после подтверждения вызывай cancel_booking.\n"
    "- Подтверждение от оператора для book_flight обрабатывается системой через interrupt/resume, не проси лишнего подтверждения у пользователя до вызова инструмента.\n\n"
    "## Политики авиакомпании\n"
    + _format_policies_for_prompt(POLICIES)
).strip()


# ------------------------------
# 4) LLM и узлы основного графа
# ------------------------------
llm = ChatOpenAI(model=MODEL, temperature=0)


def is_on_topic(user_message: str) -> bool:
    """Классификация: относится ли запрос к авиаподдержке (один вызов LLM)."""
    system = (
        "Ты классификатор релевантности. Определи, относится ли сообщение пользователя "
        "к теме поддержки авиакомпании: рейсы, бронирование, багаж, правила перевозки, "
        "возвраты, задержки, мили, путешествия, данные пассажира, отмена рейса.\n"
        "Ответь ровно одним словом: да — если тема подходит, нет — если запрос про другое "
        "(рецепты, код, политику, произвольный чат и т.п.)."
    )
    resp = llm.invoke(
        [SystemMessage(content=system), HumanMessage(content=user_message)]
    )
    answer = (resp.content or "").strip().lower()
    print(f"[GUARD] is_on_topic -> {answer!r}")
    return answer.startswith("да") or answer.startswith("yes")


def input_guard(state: MessagesState) -> dict:
    """Безопасное логирование (PII), проверка релевантности только для первого сообщения."""
    messages = state["messages"]
    if not messages:
        return {}
    last_msg = messages[-1]
    if not isinstance(last_msg, HumanMessage):
        return {}
    content = last_msg.content
    if not isinstance(content, str):
        content = str(content)
    log_message("user", content)

    has_history = len(messages) > 1
    if not has_history and not is_on_topic(content):
        snippet = mask_pii(content)[:60]
        print(f"[GUARD] Off-topic заблокирован: {snippet!r}…")
        block_msg = AIMessage(
            content=(
                "Я помощник службы поддержки авиакомпании. Помогаю только с вопросами "
                "о рейсах, бронировании, багаже, правилах перевозки и всём, что связано "
                "с перелётами. Задайте вопрос по этим темам."
            )
        )
        return {"messages": [block_msg]}
    return {}


def route_after_input_guard(state: MessagesState):
    """Если input_guard вернул ответ-заглушку (AIMessage) — конец; иначе — к агенту."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage):
        return END
    return "agent"


def tool_output_guard(state: MessagesState) -> dict:
    """Удаляет рейсы с подозрительным fare_rules (indirect injection), подменяет ToolMessage."""
    messages = state["messages"]
    if not messages:
        return {}
    last_msg = messages[-1]
    if not isinstance(last_msg, ToolMessage):
        return {}
    if last_msg.name != "search_flights":
        return {}
    raw = last_msg.content
    if not isinstance(raw, str):
        return {}
    try:
        flights = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(flights, list):
        return {}

    clean_flights: List[dict] = []
    for flight in flights:
        if not isinstance(flight, dict):
            continue
        fare_rules = str(flight.get("fare_rules", "") or "")
        flight_id = flight.get("flight_id", "?")
        if INJECTION_PATTERNS.search(fare_rules):
            print(
                f"[GUARD] Рейс {flight_id}: подозрительные fare_rules, "
                f"рейс исключён из выдачи."
            )
            continue
        clean_flights.append(flight)

    if len(clean_flights) == len(flights):
        return {}

    cleaned_msg = ToolMessage(
        content=json.dumps(clean_flights, ensure_ascii=False, indent=2),
        tool_call_id=last_msg.tool_call_id,
        name=last_msg.name,
        id=getattr(last_msg, "id", None),
    )
    return {"messages": [cleaned_msg]}


def make_agent_node_with_profile(system_prompt: str, tools_list: List):
    """Узел агента с подстановкой актуального профиля в system prompt."""
    bound = llm.bind_tools(tools_list, parallel_tool_calls=False)

    def agent_node(state: MessagesState) -> MessagesState:
        profile = load_profile()
        if profile:
            profile_lines = "\n".join(
                f"- {k}: {v}" for k, v in sorted(profile.items(), key=lambda x: x[0])
            )
            full_prompt = (
                f"{system_prompt}\n\n## Профиль пассажира\n{profile_lines}"
            )
        else:
            full_prompt = (
                f"{system_prompt}\n\n## Профиль пассажира\n"
                "(пусто — данные ещё не сохранялись)"
            )
        messages = [SystemMessage(content=full_prompt)] + list(state["messages"])
        response = bound.invoke(messages)
        return {"messages": [response]}

    return agent_node


def route_after_agent(state: MessagesState):
    """После узла agent: вызов tools или завершение."""
    last = state["messages"][-1]
    has_tool_calls = getattr(last, "tool_calls", None)
    return "tools" if has_tool_calls else END


def build_graph_with_profile(system_prompt: str, tools_list: List):
    """Основной граф: guard -> agent -> tools -> guard, с памятью по thread_id."""
    tool_node = ToolNode(tools_list)
    agent_node = make_agent_node_with_profile(system_prompt, tools_list)
    builder = StateGraph(MessagesState)
    builder.add_node("input_guard", input_guard)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("tool_output_guard", tool_output_guard)
    builder.add_edge(START, "input_guard")
    builder.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {END: END, "agent": "agent"},
    )
    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "tool_output_guard")
    builder.add_edge("tool_output_guard", "agent")
    return builder.compile(checkpointer=memory_cli)


memory_cli = MemorySaver()
graph_full = build_graph_with_profile(SYSTEM_PROMPT_CLI, TOOLS)


def _resume_interrupts_cli(app, config: dict, out: dict) -> dict:
    """Дожимает граф после interrupt (например, book_flight): ввод оператора в консоли."""
    while "__interrupt__" in out and out.get("__interrupt__"):
        intr = out["__interrupt__"]
        payload = intr[0].value if intr else None
        print("\n--- Ожидание решения оператора (бронирование) ---")
        if isinstance(payload, dict):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload)
        resume = input(
            "Введите «approved» или «одобрено» для подтверждения; любой другой текст — отказ: "
        ).strip()
        out = app.invoke(Command(resume=resume), config=config)
    return out


def invoke_graph(graph, user_message: str, thread_id: str = "demo") -> str:
    """Один шаг диалога: HumanMessage → текст последнего ответа.

    Один и тот же thread_id восстанавливает историю в рамках процесса.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config=config,
    )
    if "__interrupt__" in result and result.get("__interrupt__"):
        raise RuntimeError(
            "Граф приостановлен (interrupt, например book_flight). "
            "Продолжите вызовом graph.invoke(Command(resume=ответ_оператора), config) "
            "или используйте Chat.ask с use_checkpoint=True."
        )
    return result["messages"][-1].content


class Chat:
    def __init__(
        self,
        app,
        *,
        thread_id: str = "demo",
        use_checkpoint: bool = False,
    ):
        """use_checkpoint=True — состояние ведёт checkpointer графа."""
        self.app = app
        self.thread_id = thread_id
        self.use_checkpoint = use_checkpoint
        self.state: dict = {"messages": []}

    def ask(self, user_text: str) -> str:
        print("\nЗАПРОС")
        print("-" * 50)
        print(user_text)

        if self.use_checkpoint:
            config = {"configurable": {"thread_id": self.thread_id}}
            out = self.app.invoke(
                {"messages": [HumanMessage(content=user_text)]},
                config=config,
            )
            out = _resume_interrupts_cli(self.app, config, out)
        else:
            self.state["messages"].append(HumanMessage(content=user_text))
            out = self.app.invoke(self.state)
            self.state = out

        msgs = out.get("messages") or []
        if not msgs:
            answer = ""
        else:
            answer = msgs[-1].content

        print("\nОТВЕТ АССИСТЕНТА")
        print("-" * 50)
        print(answer)
        print()
        return answer


if __name__ == "__main__":
    # Основной боевой граф: все инструменты + профиль + interrupt для book_flight.
    chat = Chat(graph_full, thread_id="cli", use_checkpoint=True)
    print(
        "Ассистент авиакомпании запущен. Введите вопрос или «выход» / exit для завершения.\n"
    )
    while True:
        user_input = input("Вы: ").strip()
        if user_input.lower() in {"exit", "quit", "выход", "стоп"}:
            print("До свидания!")
            break
        if not user_input:
            continue
        chat.ask(user_input)
