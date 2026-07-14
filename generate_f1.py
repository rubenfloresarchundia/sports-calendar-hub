from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dateutil import parser
from ics import Calendar, Event


ROOT_DIR = Path(__file__).parent
OUTPUT_DIR = ROOT_DIR / "docs"
OUTPUT_FILE = OUTPUT_DIR / "f1" / "formula-1.ics"

F1_API_URL = "https://api.jolpi.ca/ergast/f1/current.json"


GRAND_PRIX_NAMES = {
    "Australian Grand Prix": "Australia",
    "Chinese Grand Prix": "China",
    "Japanese Grand Prix": "Japón",
    "Bahrain Grand Prix": "Bahréin",
    "Saudi Arabian Grand Prix": "Arabia Saudita",
    "Miami Grand Prix": "Miami",
    "Emilia Romagna Grand Prix": "Emilia-Romaña",
    "Monaco Grand Prix": "Mónaco",
    "Spanish Grand Prix": "España",
    "Canadian Grand Prix": "Canadá",
    "Austrian Grand Prix": "Austria",
    "British Grand Prix": "Gran Bretaña",
    "Belgian Grand Prix": "Bélgica",
    "Hungarian Grand Prix": "Hungría",
    "Dutch Grand Prix": "Países Bajos",
    "Italian Grand Prix": "Italia",
    "Azerbaijan Grand Prix": "Azerbaiyán",
    "Singapore Grand Prix": "Singapur",
    "United States Grand Prix": "Estados Unidos",
    "Mexico City Grand Prix": "México",
    "Mexican Grand Prix": "México",
    "São Paulo Grand Prix": "São Paulo",
    "Sao Paulo Grand Prix": "São Paulo",
    "Brazilian Grand Prix": "São Paulo",
    "Las Vegas Grand Prix": "Las Vegas",
    "Qatar Grand Prix": "Qatar",
    "Abu Dhabi Grand Prix": "Abu Dabi",
    "Madrid Grand Prix": "Madrid",
}


def fetch_f1_schedule():
    response = requests.get(F1_API_URL, timeout=30)

    print("Jolpica F1 API status:", response.status_code)

    if response.status_code != 200:
        print(response.text[:1000])
        raise RuntimeError(
            f"Jolpica F1 API error: {response.status_code}"
        )

    data = response.json()

    races = (
        data.get("MRData", {})
        .get("RaceTable", {})
        .get("Races", [])
    )

    print("F1 races returned:", len(races))

    return races


def parse_datetime(date_text, time_text):
    if not date_text:
        return None

    normalized_time = time_text or "00:00:00Z"
    raw_datetime = f"{date_text}T{normalized_time}"

    try:
        parsed_datetime = parser.parse(raw_datetime)

        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(
                tzinfo=timezone.utc
            )

        return parsed_datetime
    except (TypeError, ValueError, OverflowError):
        return None


def get_grand_prix_name(race):
    original_name = race.get("raceName", "Formula 1")

    if original_name in GRAND_PRIX_NAMES:
        return GRAND_PRIX_NAMES[original_name]

    cleaned_name = original_name.replace(
        " Grand Prix",
        "",
    )

    if cleaned_name == "Brazilian":
        return "São Paulo"

    return cleaned_name


def get_circuit_details(race):
    circuit = race.get("Circuit") or {}
    location = circuit.get("Location") or {}

    circuit_name = (
        circuit.get("circuitName")
        or "Circuito por confirmar"
    )
    city = (
        location.get("locality")
        or "Ciudad por confirmar"
    )
    country = (
        location.get("country")
        or "País por confirmar"
    )

    return circuit_name, city, country


def create_session_event(
    race,
    session_key,
    title_prefix,
    duration,
):
    session = race.get(session_key)

    if not session:
        return None

    start_time = parse_datetime(
        session.get("date"),
        session.get("time"),
    )

    if not start_time:
        return None

    grand_prix_name = get_grand_prix_name(race)
    circuit_name, city, country = get_circuit_details(race)

    season = race.get("season", "current")
    round_number = race.get("round", "unknown")

    event = Event()
    event.uid = (
        f"f1-{season}-{round_number}-"
        f"{session_key.lower()}"
        "@sports-calendar-hub"
    )
    event.name = f"{title_prefix} {grand_prix_name}"
    event.begin = start_time
    event.end = start_time + duration
    event.location = circuit_name

    event.description = (
        f"Evento: {title_prefix} {grand_prix_name}\n"
        f"Circuito: {circuit_name}\n"
        f"Ciudad: {city}\n"
        f"País: {country}\n"
        f"Ronda: {round_number}\n"
        "Fuente: Jolpica F1"
    )

    return event


def create_race_event(race):
    start_time = parse_datetime(
        race.get("date"),
        race.get("time"),
    )

    if not start_time:
        return None

    grand_prix_name = get_grand_prix_name(race)
    circuit_name, city, country = get_circuit_details(race)

    season = race.get("season", "current")
    round_number = race.get("round", "unknown")

    event = Event()
    event.uid = (
        f"f1-{season}-{round_number}-race"
        "@sports-calendar-hub"
    )
    event.name = f"F1 Gran Premio de {grand_prix_name}"
    event.begin = start_time
    event.end = start_time + timedelta(hours=2)
    event.location = circuit_name

    event.description = (
        f"Evento: F1 Gran Premio de {grand_prix_name}\n"
        f"Circuito: {circuit_name}\n"
        f"Ciudad: {city}\n"
        f"País: {country}\n"
        f"Ronda: {round_number}\n"
        "Fuente: Jolpica F1"
    )

    return event


def add_event_if_available(calendar, event):
    if not event:
        return

    calendar.events.add(event)
    print("Added:", event.name)


def add_race_weekend_events(calendar, race):
    qualifying_event = create_session_event(
        race=race,
        session_key="Qualifying",
        title_prefix="F1 Qualy GP de",
        duration=timedelta(hours=1),
    )
    add_event_if_available(
        calendar,
        qualifying_event,
    )

    sprint_qualifying_event = create_session_event(
        race=race,
        session_key="SprintQualifying",
        title_prefix="F1 Qualy Sprint GP de",
        duration=timedelta(minutes=45),
    )
    add_event_if_available(
        calendar,
        sprint_qualifying_event,
    )

    sprint_event = create_session_event(
        race=race,
        session_key="Sprint",
        title_prefix="F1 Sprint GP de",
        duration=timedelta(hours=1),
    )
    add_event_if_available(
        calendar,
        sprint_event,
    )

    race_event = create_race_event(race)
    add_event_if_available(
        calendar,
        race_event,
    )


def generate_f1_calendar():
    races = fetch_f1_schedule()
    calendar = Calendar()

    now = datetime.now(timezone.utc)

    for race in races:
        race_start = parse_datetime(
            race.get("date"),
            race.get("time"),
        )

        if not race_start:
            continue

        if race_start < now - timedelta(hours=4):
            continue

        add_race_weekend_events(calendar, race)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(calendar.serialize_iter())

    print("Generated:", OUTPUT_FILE)
    print("Events generated:", len(calendar.events))


def main():
    generate_f1_calendar()


if __name__ == "__main__":
    main()
