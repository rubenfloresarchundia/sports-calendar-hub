import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

PLAYER_SHORT_NAMES = {
    "Jannik Sinner": "Sinner",
    "Carlos Alcaraz": "Alcaraz",
    "Novak Djokovic": "Djokovic",
}

# Reglas independientes por jugador.
# Estas reglas solo afectan el calendario individual del jugador indicado.
PLAYER_RULES = {
    "Jannik Sinner": {
        "allowed_rounds": {"R4", "QF", "SF", "F"},
    },
    "Carlos Alcaraz": {
        "allowed_rounds": {"R4", "QF", "SF", "F"},
    },
    "Novak Djokovic": {
        "allowed_rounds": {"R4", "QF", "SF", "F"},
    },
}

DEFAULT_PLAYER_RULES = {
    "allowed_rounds": {"R4", "QF", "SF", "F"},
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


def get_player_short_name(name):
    if not name:
        return "TBD"

    name = clean_name(name)
    if name == "TBD":
        return "TBD"

    if name in PLAYER_SHORT_NAMES:
        return PLAYER_SHORT_NAMES[name]

    parts = name.split()
    if len(parts) >= 2:
        return parts[-1]

    return name


def simplify_tournament_name(name):
    if not name:
        return "TBD"

    name = str(name).strip()

    replacements = {
        "Wimbledon - London": "Wimbledon",
        "Australian Open - Melbourne": "Australian Open",
        "French Open - Paris": "Roland Garros",
        "US Open - New York": "US Open",
        "National Bank Open - Toronto": "Toronto",
        "National Bank Open - Montreal": "Montreal",
        "BNP Paribas Open - Indian Wells": "Indian Wells",
        "Miami Open - Miami": "Miami Open",
        "Rolex Monte-Carlo Masters - Monte Carlo": "Monte Carlo",
        "Mutua Madrid Open - Madrid": "Madrid Open",
        "Internazionali BNL d'Italia - Rome": "Rome",
        "Cincinnati Open - Cincinnati": "Cincinnati",
        "Rolex Shanghai Masters - Shanghai": "Shanghai",
        "Rolex Paris Masters - Paris": "Paris Masters",
    }

    return replacements.get(name, name)


def parse_fixture_datetime(fixture):
    raw_date = fixture.get("timeGame") or fixture.get("date")
    if not raw_date:
        return None

    try:
        parsed = parser.parse(raw_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError, OverflowError):
        return None


def get_date_range_fixtures(tour):
    api_host, headers = get_api_headers()

    today = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=LOOKAHEAD_DAYS)
    start_text = today.isoformat()
    end_text = end_date.isoformat()

    url = (
        f"https://{api_host}/tennis/v2/"
        f"{tour}/fixtures/{start_text}/{end_text}"
    )

    all_fixtures = []
    page = 1

    while True:
        params = {
            "include": "round,tournament,tournament.country",
            "pageSize": 100,
            "pageNo": page,
        }

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        print(
            f"Date range API status ({tour}, page {page}):",
            response.status_code,
        )
        print(f"Date range: {start_text} to {end_text}")

        if response.status_code == 429:
            print(
                "API daily quota exceeded. "
                "Stopping without updating calendars."
            )
            print(response.text[:1000])
            raise RuntimeError("Tennis API daily quota exceeded")

        if response.status_code != 200:
            print(response.text[:1000])
            raise RuntimeError(
                f"Tennis API error: {response.status_code}"
            )

        data = response.json()

        if isinstance(data, dict):
            fixtures = data.get("data", [])
            has_next_page = data.get("hasNextPage", False)
        elif isinstance(data, list):
            fixtures = data
            has_next_page = False
        else:
            fixtures = []
            has_next_page = False

        all_fixtures.extend(fixtures)

        if not has_next_page:
            break

        page += 1
        if page > 10:
            print("Stopped pagination after 10 pages.")
            break

    print(
        f"Total fixtures returned for {tour}: "
        f"{len(all_fixtures)}"
    )

    return all_fixtures


def fixture_has_player(fixture, player_id):
    return (
        fixture.get("player1Id") == player_id
        or fixture.get("player2Id") == player_id
    )


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


def get_tournament_name(fixture):
    tournament = fixture.get("tournament") or {}
    return simplify_tournament_name(tournament.get("name"))


def get_round_name(fixture):
    round_data = fixture.get("round") or {}
    round_name = round_data.get("name")

    if not round_name:
        return "TBD"

    return str(round_name).strip()


def normalize_round_name(round_name):
    value = str(round_name or "").strip().lower()
    value = re.sub(r"[_-]+", " ", value)
    value = re.sub(r"\s+", " ", value)

    exact_rounds = {
        "r4": "R4",
        "round 4": "R4",
        "round of 16": "R4",
        "round 16": "R4",
        "last 16": "R4",
        "1/8": "R4",
        "octavos": "R4",
        "octavos de final": "R4",
        "qf": "QF",
        "quarterfinal": "QF",
        "quarter final": "QF",
        "quarterfinals": "QF",
        "quarter finals": "QF",
        "1/4": "QF",
        "cuartos": "QF",
        "cuartos de final": "QF",
        "sf": "SF",
        "semifinal": "SF",
        "semi final": "SF",
        "semifinals": "SF",
        "semi finals": "SF",
        "1/2": "SF",
        "semifinales": "SF",
        "f": "F",
        "final": "F",
        "championship": "F",
    }

    return exact_rounds.get(value)


def get_player_rules(player):
    return PLAYER_RULES.get(
        player["full_name"],
        DEFAULT_PLAYER_RULES,
    )


def is_confirmed_allowed_fixture(player, fixture):
    fixture_id = fixture.get("id", "unknown")
    start_time = parse_fixture_datetime(fixture)
    opponent = get_opponent_name(player, fixture)
    tournament_name = get_tournament_name(fixture)
    round_name = get_round_name(fixture)
    normalized_round = normalize_round_name(round_name)
    allowed_rounds = get_player_rules(player)["allowed_rounds"]

    if not start_time:
        print(f"Skipped fixture {fixture_id}: missing valid date/time")
        return False

    if opponent == "TBD":
        print(f"Skipped fixture {fixture_id}: opponent is not confirmed")
        return False

    if tournament_name == "TBD":
        print(f"Skipped fixture {fixture_id}: tournament is not confirmed")
        return False

    if round_name == "TBD":
        print(f"Skipped fixture {fixture_id}: round is not confirmed")
        return False

    if normalized_round not in allowed_rounds:
        print(
            f"Skipped fixture {fixture_id}: round {round_name!r} "
            "is not allowed"
        )
        return False

    return True


def get_player_upcoming_fixtures(player, fixtures):
    player_id = player["player_id"]
    player_fixtures = []
    now = datetime.now(timezone.utc)

    for fixture in fixtures:
        if not fixture_has_player(fixture, player_id):
            continue

        start_time = parse_fixture_datetime(fixture)
        if not start_time:
            continue

        if start_time < now - timedelta(hours=2):
            continue

        if not is_confirmed_allowed_fixture(player, fixture):
            continue

        player_fixtures.append((start_time, fixture))

    player_fixtures.sort(key=lambda item: item[0])

    if not player_fixtures:
        print(
            "No publishable upcoming fixture found for "
            f"{player['full_name']}"
        )
        return []

    print("=" * 60)
    print(f"Selected fixtures for: {player['full_name']}")

    for start_time, fixture in player_fixtures:
        print("Date:", start_time.isoformat())
        print("Tournament:", get_tournament_name(fixture))
        print("Round:", get_round_name(fixture))
        print("Opponent:", get_opponent_name(player, fixture))
        print("---")

    return [fixture for _, fixture in player_fixtures]


def get_country_name(fixture):
    tournament = fixture.get("tournament") or {}
    country = tournament.get("country") or {}

    return (
        country.get("name")
        or tournament.get("countryAcr")
        or "Country TBD"
    )


def create_simple_title(player, fixture):
    player_short = get_player_short_name(player["full_name"])
    opponent_full = get_opponent_name(player, fixture)
    opponent_short = get_player_short_name(opponent_full)
    tournament_name = get_tournament_name(fixture)

    return (
        f"{player_short} vs {opponent_short} - "
        f"{tournament_name}"
    )


def create_real_event(player, fixture):
    player_name = player["full_name"]
    opponent = get_opponent_name(player, fixture)
    tournament_name = get_tournament_name(fixture)
    round_name = get_round_name(fixture)
    country_name = get_country_name(fixture)
    start_time = parse_fixture_datetime(fixture)

    if not start_time:
        raise RuntimeError(
            f"Fixture {fixture.get('id')} has no valid start time"
        )

    fixture_id = fixture.get("id", "unknown")

    event = Event()
    event.uid = (
        f"tennis-{player['tour']}-"
        f"{player['player_id']}-{fixture_id}"
        "@sports-calendar-hub"
    )
    event.name = create_simple_title(player, fixture)
    event.begin = start_time
    event.end = start_time + timedelta(hours=2)
    event.description = (
        f"Player: {player_name}\n"
        f"Opponent: {opponent}\n"
        f"Tournament: {tournament_name}\n"
        f"Round: {round_name}\n"
        f"Country: {country_name}\n"
        "Source: Tennis API"
    )
    event.location = tournament_name

    return event


def generate_player_calendar(player, all_fixtures_by_tour):
    calendar = Calendar()
    tour = player["tour"]
    fixtures = all_fixtures_by_tour.get(tour, [])

    player_fixtures = get_player_upcoming_fixtures(
        player,
        fixtures,
    )

    for fixture in player_fixtures:
        calendar.events.add(create_real_event(player, fixture))

    output_path = OUTPUT_DIR / player["output"]
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open("w", encoding="utf-8") as file:
        file.writelines(calendar.serialize_iter())

    print(
        f"Generated: {output_path} "
        f"({len(player_fixtures)} events)"
    )


def main():
    players = load_tennis_players()
    tours = sorted({player["tour"] for player in players})
    all_fixtures_by_tour = {}

    for tour in tours:
        all_fixtures_by_tour[tour] = get_date_range_fixtures(tour)

    for player in players:
        generate_player_calendar(
            player,
            all_fixtures_by_tour,
        )


if __name__ == "__main__":
    main()
