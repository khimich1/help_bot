"""ReAct-агент авиакомпании по скринам курса (TAO-loop, 5 τ-bench тулов).

Этот файл — учебная "минимальная" версия агента: только ReAct-петля и 5 тулов,
без guardrails/interrupt/checkpointer/persistence, как на скринах.
Полная версия с обвесом — рядом, в `airline_agent_from_screens.py`.
"""

import os
import sys
import json
import time
import copy
import datetime
from typing import List, Literal
from pydantic import BaseModel, Field
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv


load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ------------------------------
# 0.1) FLIGHTS_DB — список рейсов в схеме скринов курса
#      (departure / arrival / class / flight_number — плоский список dict)
#      Данные перенесены из старого бота airline_agent_from_screens.py.
# ------------------------------
FLIGHT_DATE = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()


def resolve_date(date_str: str) -> str:
    """Преобразует относительные даты в YYYY-MM-DD.

    Понимает: today/сегодня, tomorrow/завтра, next week/следующая неделя/через неделю,
    monday..sunday, понедельник..воскресенье, next monday..., следующий понедельник...
    Если строка не распознана — возвращает её без изменений (например, '2026-04-29').
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
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    ]
    ru_weekdays = [
        "понедельник", "вторник", "среда", "четверг",
        "пятница", "суббота", "воскресенье",
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


def _is_iso_date(value: str) -> bool:
    """True, если строка успешно парсится как ISO-дата (YYYY-MM-DD)."""
    try:
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


FLIGHTS_DB: List[dict] = [
    {
        "flight_number": "AF-201",
        "departure": "Moscow",
        "arrival": "Paris",
        "date": FLIGHT_DATE,
        "time": "08:00",
        "arrival_time": "11:30",
        "class": "economy",
        "stops": 0,
        "fare_rules": (
            "Тариф эконом: бесплатная смена даты до 24 ч до вылета. "
            "Штраф при отмене 25%."
        ),
        "seats": 3,
        "price": 290,
    },
    {
        "flight_number": "AF-202",
        "departure": "Moscow",
        "arrival": "Paris",
        "date": FLIGHT_DATE,
        "time": "17:00",
        "arrival_time": "20:00",
        "class": "business",
        "stops": 0,
        "fare_rules": (
            "Бизнес-класс: полный возврат, бесплатное перебронирование, "
            "приоритетная посадка и зал ожидания."
        ),
        "seats": 2,
        "price": 750,
    },
    {
        "flight_number": "AF-203",
        "departure": "Moscow",
        "arrival": "Paris",
        "date": FLIGHT_DATE,
        "time": "23:30",
        "arrival_time": "03:00",
        "class": "promo",
        "stops": 1,
        "fare_rules": (
            "Промо: без возврата, 1 пересадка в Берлине, смена даты $80."
        ),
        "seats": 4,
        "price": 160,
    },
    {
        "flight_number": "SU-101",
        "departure": "Moscow",
        "arrival": "London",
        "date": FLIGHT_DATE,
        "time": "06:30",
        "arrival_time": "09:30",
        "class": "economy",
        "stops": 0,
        "fare_rules": (
            "Тариф эконом: бесплатная смена даты до 24 ч до вылета. "
            "Штраф при отмене 25%."
        ),
        "seats": 3,
        "price": 320,
    },
    {
        "flight_number": "SU-104",
        "departure": "Moscow",
        "arrival": "London",
        "date": FLIGHT_DATE,
        "time": "10:45",
        "arrival_time": "13:45",
        "class": "economy",
        "stops": 0,
        "fare_rules": (
            "Тариф эконом: бесплатная смена даты до 24 ч до вылета. "
            "Штраф при отмене 25%."
        ),
        "seats": 4,
        "price": 335,
    },
    {
        "flight_number": "SU-102",
        "departure": "Moscow",
        "arrival": "London",
        "date": FLIGHT_DATE,
        "time": "14:00",
        "arrival_time": "17:00",
        "class": "business",
        "stops": 0,
        "fare_rules": (
            "Бизнес-класс: полный возврат, бесплатное перебронирование, "
            "приоритетная посадка и зал ожидания."
        ),
        "seats": 2,
        "price": 890,
    },
    {
        "flight_number": "SU-103",
        "departure": "Moscow",
        "arrival": "London",
        "date": FLIGHT_DATE,
        "time": "22:15",
        "arrival_time": "01:15",
        "class": "promo",
        "stops": 0,
        "fare_rules": (
            "Промо: без возврата, смена даты $100, выбор места недоступен."
        ),
        "seats": 5,
        "price": 185,
    },
]


# ------------------------------
# 0.2) BOOKINGS_DB — словарь бронирований (плоская схема, как на скрине get_booking)
# ------------------------------
BOOKINGS_DB: dict = {
    "BK-789": {
        "booking_id": "BK-789",
        "flight_number": "AF-201",
        "date": FLIGHT_DATE,
        "class": "economy",
        "passenger_name": "Jane Doe",
        "status": "confirmed",
    },
}


# ------------------------------
# 0.3) POLICIES_DB — словарь по типам политик (rebooking / cancellation / baggage)
#      Текст склеен из соответствующих разделов POLICIES старого бота.
#      `rebooking.fee` — числовое поле, как на скрине update_booking.
# ------------------------------
POLICIES_DB: dict = {
    "rebooking": {
        "fee": 50,
        "class_change_allowed": False,
        "description": (
            "Сборы за перебронирование. "
            "Сборы зависят от класса обслуживания. "
            "Эконом: $50 при смене более чем за 24 ч до вылета, $100 — в течение 24 ч до вылета. "
            "Бизнес: бесплатное перебронирование в любое время. "
            "Промо: $100 независимо от срока. "
            "При смене даты возможна доплата из-за разницы тарифов — "
            "если новый рейс дороже, пассажир оплачивает разницу.\n\n"
            "Смена даты вылета. "
            "Смена даты разрешена во всех классах при наличии мест и согласно сборам. "
            "Эконом и Промо: заявка не позднее чем за 2 ч до вылета. "
            "Бизнес: до 30 минут до вылета. "
            "Если новый рейс дороже — доплата по разнице тарифов. "
            "Если дешевле — разница не возвращается. "
            "Перебронирование выполняется в пределах того же класса обслуживания."
        ),
    },
    "cancellation": {
        "fee": 0,
        "description": (
            "Отмена рейса авиакомпанией. "
            "Если авиакомпания отменяет рейс, пассажиры вправе получить полный возврат стоимости билета "
            "или перебронирование на ближайший доступный рейс без доплаты. "
            "При уведомлении менее чем за 14 дней до вылета полагается дополнительная компенсация "
            "в размере 50% от стоимости билета. "
            "При ночном ожидании из-за отмены предоставляются отель и питание.\n\n"
            "Возврат по тарифу эконом. "
            "Билеты эконом возвратные со штрафом. "
            "Отмена более чем за 72 ч до вылета: удержание 25% от тарифа. "
            "Отмена в течение 72 ч до вылета: удержание 50%. "
            "Неявка без предварительной отмены: билет аннулируется без возмещения.\n\n"
            "Возврат по промо-тарифу. "
            "Билеты по промо-тарифу невозвратные. "
            "Денежная компенсация при отмене не предусмотрена. "
            "Исключение: при подтверждённом медицинском форс-маже можно подать заявление "
            "на полный возврат, приложив справку в течение 30 дней после даты рейса. "
            "Рассмотрение заявки — до 14 рабочих дней."
        ),
    },
    "baggage": {
        "fee": 15,
        "description": (
            "Норма зарегистрированного багажа. "
            "Норма по классу: Промо — 1 место до 20 кг; Эконом — 1 место до 23 кг; "
            "Бизнес — 2 места по 32 кг. "
            "Перевес: $15 за каждый кг сверх нормы. "
            "Негабарит (сумма трёх измерений свыше 158 см): $75 за место. "
            "Спортинвентарь (лыжи, велосипеды, гольф) декларируется при регистрации, "
            "возможны доп. сборы.\n\n"
            "Ручная кладь и ограничения. "
            "Разрешены одна сумка ручной клади (до 10 кг, габариты до 55×40×20 см) "
            "и один предмет личных вещей (сумка для ноутбука, дамская сумка). "
            "Жидкости — в ёмкостях до 100 мл, в прозрачном пакете (общий объём до 1 л). "
            "Острые предметы, легковоспламеняющиеся вещества и литиевые батареи свыше 100 Вт·ч "
            "в ручной клади запрещены."
        ),
    },
}


# ------------------------------
# 1) Тулы (1:1 со скринов курса)
# ------------------------------
CITY_ALIASES = {
    "москва": "moscow",
    "moscow": "moscow",
    "лондон": "london",
    "london": "london",
    "париж": "paris",
    "paris": "paris",
}


def _normalize_city_name(value: str) -> str:
    """Normalize city value to a canonical lowercase form for matching."""
    key = value.strip().lower()
    return CITY_ALIASES.get(key, key)


@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for flights by route and date.

    Args:
        origin: Departure city or airport code (e.g., 'Moscow', 'SVO')
        destination: Arrival city or airport code (e.g., 'Paris', 'CDG')
        date: Date in YYYY-MM-DD format. Relative phrases also accepted:
              'today', 'tomorrow', 'next week', weekday names (EN/RU).
    """
    resolved = resolve_date(date)

    available_dates = sorted({f["date"] for f in FLIGHTS_DB})
    used_date = resolved
    date_was_normalized = False

    if resolved not in available_dates and available_dates:
        if _is_iso_date(resolved):
            target = datetime.date.fromisoformat(resolved)
            closest = min(
                available_dates,
                key=lambda d: abs((datetime.date.fromisoformat(d) - target).days),
            )
        else:
            closest = available_dates[0]
        used_date = closest
        date_was_normalized = True

    normalized_origin = _normalize_city_name(origin)
    normalized_destination = _normalize_city_name(destination)

    results = [
        flight for flight in FLIGHTS_DB
        if normalized_origin in _normalize_city_name(flight["departure"])
        and normalized_destination in _normalize_city_name(flight["arrival"])
        and flight["date"] == used_date
    ]

    if not results:
        return json.dumps({
            "status": "no_results",
            "message": f"No flights from {origin} to {destination} on {used_date}",
            "available_dates": available_dates,
        }, ensure_ascii=False)

    payload: dict = {
        "status": "date_normalized" if date_was_normalized else "success",
        "count": len(results),
        "flights": results,
    }
    if date_was_normalized:
        payload["requested_date"] = date
        payload["resolved_date"] = used_date
        payload["note"] = (
            "Requested date is not in the catalog; results are shown for the "
            "closest available date. Inform the user."
        )
    return json.dumps(payload, ensure_ascii=False)


@tool
def get_flight_details(flight_number: str) -> str:
    """Get detailed information about a specific flight.

    Args:
        flight_number: Flight number (e.g., 'SU-101')
    """
    for flight in FLIGHTS_DB:
        if flight["flight_number"].upper() == flight_number.upper():
            return json.dumps({"status": "success", "flight": flight})

    return json.dumps({"status": "error", "message": f"Flight {flight_number} not found"})


@tool
def get_booking(booking_id: str) -> str:
    """Get booking information by ID.

    Args:
        booking_id: Booking identifier (e.g., 'BK-789')
    """
    booking = BOOKINGS_DB.get(booking_id)
    if booking:
        return json.dumps({"status": "success", "booking": booking})

    return json.dumps({"status": "error", "message": f"Booking {booking_id} not found"})


@tool
def get_policy(policy_type: str) -> str:
    """Get airline policies by type.

    Args:
        policy_type: Policy type ('rebooking', 'cancellation', 'baggage')
    """
    policy = POLICIES_DB.get(policy_type.lower().strip())
    if policy:
        return json.dumps({"status": "success", "policy_type": policy_type, "policy": policy})

    return json.dumps({
        "status": "error",
        "message": f"Policy '{policy_type}' not found. Available: {list(POLICIES_DB.keys())}",
    })


@tool
def update_booking(booking_id: str, new_flight_number: str, new_date: str) -> str:
    """Update a booking: rebook to a different flight.

    Args:
        booking_id: Booking ID (e.g., 'BK-789')
        new_flight_number: New flight number
        new_date: New date in YYYY-MM-DD format. Relative phrases like 'tomorrow'
                  or 'завтра' are also accepted and will be normalized.
    """
    resolved_new_date = resolve_date(new_date)

    booking = BOOKINGS_DB.get(booking_id)
    if not booking:
        return json.dumps({"status": "error", "message": f"Booking {booking_id} not found"})

    new_flight = None
    for f in FLIGHTS_DB:
        if (
            f["flight_number"].upper() == new_flight_number.upper()
            and f["date"] == resolved_new_date
        ):
            new_flight = f
            break

    if not new_flight:
        return json.dumps({
            "status": "error",
            "message": f"Flight {new_flight_number} on {resolved_new_date} not found",
        })

    if booking["class"] != new_flight["class"]:
        return json.dumps({
            "status": "error",
            "message": (
                f"Class mismatch: booking is {booking['class']}, "
                f"flight is {new_flight['class']}. Policy: same class only."
            ),
        })

    updated = dict(booking)
    updated["flight_number"] = new_flight_number
    updated["date"] = resolved_new_date
    updated["status"] = "rebooked"
    BOOKINGS_DB[booking_id] = updated

    rebooking_fee = POLICIES_DB["rebooking"]["fee"]

    return json.dumps({
        "status": "success",
        "message": f"Booking {booking_id} rebooked to {new_flight_number} on {resolved_new_date}",
        "fee_applied": rebooking_fee,
        "updated_booking": updated,
    })


ALL_TOOLS = [search_flights, get_flight_details, get_booking, get_policy, update_booking]

print("Инструменты:", [t.name for t in ALL_TOOLS])


# ------------------------------
# 2) System prompt for ReAct agent (TAO-loop, как на скрине)
# ------------------------------
REACT_SYSTEM_PROMPT = f"""Ты — агент службы поддержки авиакомпании. Следуй петле TAO.

Сегодняшняя дата: {datetime.date.today().isoformat()}. Используй её при обработке относительных дат ('завтра', 'следующая неделя', 'понедельник' и т.п.). Не подставляй устаревшие годы.

МЫСЛЬ (THOUGHT): проанализируй запрос, спланируй шаги.
ДЕЙСТВИЕ (ACTION): вызови подходящий инструмент, чтобы получить данные.
НАБЛЮДЕНИЕ (OBSERVATION): проанализируй результат и реши, нужны ли дальнейшие действия.

Доступные инструменты:
- search_flights: поиск рейсов по маршруту и дате
- get_flight_details: подробная информация о рейсе
- get_booking: информация о бронировании
- get_policy: политики авиакомпании (rebooking, cancellation, baggage)
- update_booking: перебронирование на другой рейс

ВАЖНО:
- Всегда отвечай пассажиру на русском языке.
- Вызывай не более ОДНОГО инструмента за шаг. Получи результат, проанализируй его и только затем решай, что делать дальше.
- Перед изменением бронирования всегда проверяй политики через get_policy.
- Не выдумывай данные — используй только то, что вернули инструменты.
- Перед перебронированием/отменой запрашивай явное подтверждение пользователя.
- Будь вежлив и помогай пассажиру.
"""

print("Системный промпт ReAct готов")


# ------------------------------
# 3) LLM и фабрика ReAct-агента
# ------------------------------
llm = ChatOpenAI(model=MODEL, temperature=0)


def create_react_agent(tools_list=None, system_prompt=None):
    """Creates a ReAct agent with the given tools.

    Includes an explicit THOUGHT step: if the model calls a tool
    without writing reasoning text (common with function-calling),
    we make an extra LLM call to extract the reasoning.
    """
    if tools_list is None:
        tools_list = ALL_TOOLS
    if system_prompt is None:
        system_prompt = REACT_SYSTEM_PROMPT

    # parallel_tool_calls=False — forces the model to call one tool per step,
    # making the TAO loop explicit: Thought -> Action -> Observation -> Thought -> ...
    llm_with_tools = llm.bind_tools(tools_list, parallel_tool_calls=False)

    def agent_node(state: MessagesState):
        messages = state["messages"]
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            messages = [SystemMessage(content=system_prompt)] + messages
        response = llm_with_tools.invoke(messages)

        if response.tool_calls and not response.content:
            tool_info = ", ".join(tc["name"] for tc in response.tool_calls)
            thought = llm.invoke(
                messages
                + [
                    HumanMessage(
                        content=(
                            f"You chose to call: {tool_info}. "
                            "In 1 sentence, explain why this is the right next step. "
                            "Reply with ONLY your reasoning, no tool calls."
                        )
                    )
                ]
            )
            response.content = thought.content

        return {"messages": [response]}

    def should_continue(state: MessagesState):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools_list))

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()


def run_and_trace(agent, query: str):
    """Запускает агента и пошагово показывает TAO-петлю.

    Возвращает (result, tao_steps) для программного использования
    (тесты, метрики, сравнение версий промпта).
    """
    print(f"Пользователь: {query}")
    print("=" * 60)

    start_time = time.time()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    elapsed = time.time() - start_time

    tao_steps: List[int] = []
    tool_count = 0
    step_num = 0
    for msg in result["messages"]:
        msg_type = type(msg).__name__

        if msg_type == "AIMessage" and getattr(msg, "tool_calls", None):
            step_num += 1
            for tc in msg.tool_calls:
                tool_count += 1
                print(f"\n--- Шаг TAO {step_num} ---")
                if msg.content:
                    print(f"   МЫСЛЬ:      {msg.content[:200]}")
                args = json.dumps(tc["args"], ensure_ascii=False)
                print(f"   ДЕЙСТВИЕ:   {tc['name']}({args})")
            tao_steps.append(step_num)

        elif msg_type == "ToolMessage":
            content_preview = (
                msg.content[:150] if len(msg.content) > 150 else msg.content
            )
            print(f"   НАБЛЮДЕНИЕ: {content_preview}")

        elif msg_type == "AIMessage" and not getattr(msg, "tool_calls", None):
            if msg.content and msg is not result["messages"][0]:
                print("\n--- Финальный ответ ---")
                print(f"   {msg.content[:500]}")

    print(f"\n{'=' * 60}")
    print(
        f"Циклов TAO: {step_num} | Вызовов инструментов: {tool_count} "
        f"| Время: {elapsed:.2f}с"
    )

    return result, tao_steps


react_agent = create_react_agent()
print("ReAct-агент создан")


# ------------------------------
# 4) CLI: ручная проверка ReAct-петли
# ------------------------------
def _print_step(message) -> None:
    """Печатает один шаг траектории: Мысль / Действие / Наблюдение / Финальный ответ."""
    if isinstance(message, AIMessage):
        if message.tool_calls:
            print("\n=== МЫСЛЬ ===")
            print(message.content or "(модель не написала текст рассуждения)")
            for tc in message.tool_calls:
                args = json.dumps(tc.get("args", {}), ensure_ascii=False)
                print(f"\n=== ДЕЙСТВИЕ ===\n{tc['name']}({args})")
        else:
            print("\n=== ФИНАЛЬНЫЙ ОТВЕТ ===")
            print(message.content)
    else:
        name = getattr(message, "name", "tool")
        print(f"\n=== НАБЛЮДЕНИЕ ({name}) ===")
        print(message.content)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--trace":
        query = " ".join(sys.argv[2:])
        run_and_trace(react_agent, query)
        sys.exit(0)

    print(
        "\nReAct-агент авиакомпании. Введите вопрос или 'exit' / 'выход' для завершения.\n"
    )
    history: list = []

    while True:
        user_input = input("Вы: ").strip()
        if user_input.lower() in {"exit", "quit", "выход"}:
            print("До свидания!")
            break
        if not user_input:
            continue

        history.append(HumanMessage(content=user_input))
        result = react_agent.invoke({"messages": history})

        new_messages = result["messages"][len(history):]
        for msg in new_messages:
            _print_step(msg)

        history = result["messages"]
        print()
