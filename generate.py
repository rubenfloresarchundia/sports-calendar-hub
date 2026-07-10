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


def parse_event_datetime(fixture):
    raw_date = fixture.get("timeGame") or fixture.get("date")

    tournament = fixture.get("tournament") or {}
    raw_tournament_date = tournament.get("date")

    if raw_date:
        return parser.parse(raw_date)

    if raw_tournament_date:
        return parser.parse(raw_tournament_date)

    return datetime.now(timezone.utc) + timedelta(days=7)


def get_player_fixtures(player):
    api_host, headers = get_api_headers()

    tour = player["tour"]
    player_id = player["player_id"]

    url = f"https://{api_host}/tennis/v2/{tour}/fixtures/player/{player_id}"

    params = {
        "include": "round,tournament,tournament.country",
        "pageSize": 5,
        "pageNo": 1,
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    print(f"{player['full_name']} API status:", response.status_code)

    if response.status_code != 200:
        print(response.text[:1000])
        return []

    data = response.json()

    if isinstance(data, dict):
        return data.get("data", [])

    if isinstance(data, list):
        return data

    return []


def get_opponent_name(player, fixture):
    player_name = player["full_name"]

    player1 = fixture.get("player1") or {}
    player2 = fixture.get("player2") or {}

    player1_name = player1.get("name", "TBD")
    player2_name = player2.get("name", "TBD")

    if player1_name == player_name:
        return player2_name

    if player2_name == player_name:
        return player1_name

    if player1_name != "TBD":
        return player1_name

    if player2_name != "TBD":
        return player2_name

    return "TBD"


def create_real_event(player, fixture):
    player_name = player["full_name"]
    opponent = get_opponent_name(player, fixture)

    tournament = fixture.get("tournament") or {}
    round_data = fixture.get("round") or {}

    tournament_name = tournament.get("name", "Tournament TBD")
    round_name = round_data.get("name", "Round TBD")

    country = tournament.get("country") or {}
    country_name = country.get("name") or tournament.get("countryAcr") or "Country TBD"

    start_time = parse_event_datetime(fixture)

    event = Event()
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

    fixtures = get_player_fixtures(player)

    if fixtures:
        event = create_real_event(player, fixtures[0])
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
