import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
import yaml
from dateutil import parser
from ics import Calendar, Event


ROOT_DIR = Path(__file__).parent
CONFIG_PATH = ROOT_DIR / "config" / "tennis_players.yaml"
OUTPUT_DIR = ROOT_DIR / "docs"

LOOKAHEAD_DAYS = 21

UNKNOWN_NAMES = {
    "",
    "TBD",
    "Unknown",
    "Unknown Player",
    "Qualifier",
    "Q",
}


def load_tennis_players():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return data.get("players", [])


def get_api_headers():
    api_key = os.environ.get("TENNIS_API_KEY")
    api_host = os.environ.get("TENNIS_API_HOST")

    if not api_key or not api_host:
        raise RuntimeError("Missing TENNIS_API_KEY or TENNIS_API_HOST")

    return api_host, {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": api_host,
        "Content-Type": "application/json",
    }


def clean_name(name):
    if not name:
        return "TBD"

    name = str(name).strip()

    if name in UNKNOWN_NAMES:
        return "TBD"

    return name


def parse_fixture_datetime(fixture):
    raw_date = fixture.get("timeGame") or fixture.get("date")

    if not raw_date:
        return None

    try:
        parsed = parser.parse(raw_date)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed
    except Exception:
        return None


def get_date_range_fixtures(tour):
    api_host, headers = get_api_headers()

    today = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=LOOKAHEAD_DAYS)

    start_text = today.isoformat()
    end_text = end_date.isoformat()

    url = f"https://{api_host}/tennis/v2/{tour}/fixtures/{start_text}/{end_text}"

    params = {
        "include": "round,tournament,tournament.country",
        "pageSize": 100,
        "pageNo": 1,
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)

    print(f"Date range API status ({tour}):", response.status_code)
    print(f"Date range:", start_text, "to", end_text)

    if response.status_code != 200:
        print(response.text[:1000])
        return []

    data = response.json()

    if isinstance(data, dict):
        return data.get("data", [])

    if isinstance(data, list):
        return data

    return []


def fixture_has_player(fixture, player_id):
    return fixture.get("player1Id") == player_id or fixture.get("player2Id") == player_id


def get_next_confirmed_fixture(player):
    tour = player["tour"]
    player_id = player["player_id"]

    fixtures = get_date_range_fixtures(tour)

    player_fixtures = []

    for fixture in fixtures:
        if not fixture_has_player(fixture, player_id):
            continue

        start_time = parse_fixture_datetime(fixture)

        if not start_time:
            continue

        player_fixtures.append((start_time, fixture))

    player_fixtures.sort(key=lambda item: item[0])

    now = datetime.now(timezone.utc)

    future_fixtures = [
        (start_time, fixture)
        for start_time, fixture in player_fixtures
        if start_time >= now - timedelta(hours=6)
    ]

    if not future_fixtures:
        print(f"No confirmed upcoming fixture found for {player['full_name']}")
        return None

    selected_time, selected_fixture = future_fixtures[0]

    tournament = selected_fixture.get("tournament") or {}
    round_data = selected_fixture.get("round") or {}

    print("Selected fixture for:", player["full_name"])
    print("Date:", selected_time.isoformat())
    print("Tournament:", tournament.get("name"))
    print("Round:", round_data.get("name"))
    print("Player 1:", (selected_fixture.get("player1") or {}).get("name"))
    print("Player 2:", (selected_fixture.get("player2") or {}).get("name"))

    return selected_fixture


def get_opponent_name(player, fixture):
    player_name = player["full_name"]

    player1 = fixture.get("player1") or {}
    player2 = fixture.get("player2") or {}

    player1_name = clean_name(player1.get("name"))
    player2_name = clean_name(player2.get("name"))

    if player1_name == player_name:
        return player2_name

    if player2_name == player_name:
        return player1_name

    if player1_name != "TBD" and player1_name != player_name:
        return player1_name

    if player2_name != "TBD" and player2_name != player_name:
        return player2_name

    return "TBD"


def get_country_name(fixture):
    tournament = fixture.get("tournament") or {}
    country = tournament.get("country") or {}

    return country.get("name") or tournament.get("countryAcr") or "Country TBD"


def create_real_event(player, fixture):
    player_name = player["full_name"]
    opponent = get_opponent_name(player, fixture)

    tournament = fixture.get("tournament") or {}
    round_data = fixture.get("round") or {}

    tournament_name = tournament.get("name", "Tournament TBD")
    round_name = round_data.get("name", "Round TBD")
    country_name = get_country_name(fixture)

    start_time = parse_fixture_datetime(fixture)

    if not start_time:
        start_time = datetime.now(timezone.utc) + timedelta(days=7)

    event = Event()

    if opponent == "TBD":
        event.name = f"{player_name} - {tournament_name} (opponent TBD)"
    else:
        event.name = f"{player_name} vs {opponent} - {tournament_name}"

    event.begin = start_time
    event.end = start_time + timedelta(hours=2)

    event.description = (
        f"Player: {player_name}\n"
        f"Opponent: {opponent}\n"
        f"Tournament: {tournament_name}\n"
        f"Round: {round_name}\n"
        f"Country: {country_name}\n"
        f"Source: Tennis API"
    )

    event.location = country_name

    return event


def create_fallback_event(player):
    player_name = player["full_name"]

    event = Event()
    event.name = f"{player_name} - next match pending confirmation"
    event.begin = datetime.now(timezone.utc) + timedelta(days=7)
    event.end = event.begin + timedelta(hours=2)
    event.description = (
        f"Player: {player_name}\n"
        f"Tour: {player['tour'].upper()}\n"
        "Opponent: TBD\n"
        "Tournament: TBD\n"
        "Round: TBD"
    )
    event.location = "TBD"

    return event


def generate_player_calendar(player):
    calendar = Calendar()

    fixture = get_next_confirmed_fixture(player)

    if fixture:
        event = create_real_event(player, fixture)
    else:
        event = create_fallback_event(player)

    calendar.events.add(event)

    output_path = OUTPUT_DIR / player["output"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        file.writelines(calendar.serialize_iter())

    print(f"Generated: {output_path}")


def main():
    players = load_tennis_players()

    for player in players:
        generate_player_calendar(player)


if __name__ == "__main__":
    main()
