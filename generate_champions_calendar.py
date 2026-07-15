import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dateutil import parser
from ics import Calendar, Event


ROOT_DIR = Path(__file__).parent

OUTPUT_FILE = (
    ROOT_DIR
    / "docs"
    / "football"
    / "champions-global.ics"
)

FOOTBALL_DATA_URL = (
    "https://api.football-data.org/v4/"
    "competitions/CL/matches"
)

ALLOWED_STAGES = {
    "QUARTER_FINALS",
    "SEMI_FINALS",
    "FINAL",
}

TEAM_SHORT_NAMES = {
    "Real Madrid CF": "Real Madrid",
    "FC Barcelona": "Barcelona",
    "Club Atletico de Madrid": "Atletico Madrid",
    "Club Atlético de Madrid": "Atletico Madrid",
    "Arsenal FC": "Arsenal",
    "Liverpool FC": "Liverpool",
    "Manchester City FC": "Manchester City",
    "Manchester United FC": "Manchester United",
    "Chelsea FC": "Chelsea",
    "Tottenham Hotspur FC": "Tottenham",
    "Paris Saint-Germain FC": "PSG",
    "Paris Saint-Germain": "PSG",
    "FC Bayern München": "Bayern",
    "FC Bayern Munich": "Bayern",
    "Borussia Dortmund": "Dortmund",
    "Bayer 04 Leverkusen": "Leverkusen",
    "Juventus FC": "Juventus",
    "FC Internazionale Milano": "Inter",
    "Inter Milan": "Inter",
    "AC Milan": "Milan",
    "SSC Napoli": "Napoli",
    "Atalanta BC": "Atalanta",
    "AS Roma": "Roma",
    "SL Benfica": "Benfica",
    "Sport Lisboa e Benfica": "Benfica",
    "FC Porto": "Porto",
    "Sporting Clube de Portugal": "Sporting",
    "AFC Ajax": "Ajax",
    "PSV": "PSV",
    "PSV Eindhoven": "PSV",
    "Feyenoord Rotterdam": "Feyenoord",
    "RB Leipzig": "Leipzig",
    "AS Monaco FC": "Monaco",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "LOSC Lille": "Lille",
    "Club Brugge KV": "Club Brugge",
    "Celtic FC": "Celtic",
    "Galatasaray SK": "Galatasaray",
    "Fenerbahçe SK": "Fenerbahce",
    "FK Crvena Zvezda": "Red Star",
    "FC Shakhtar Donetsk": "Shakhtar",
    "FC Dynamo Kyiv": "Dynamo Kyiv",
}


def get_api_headers():
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Missing FOOTBALL_DATA_API_KEY"
        )

    return {
        "X-Auth-Token": api_key,
    }


def fetch_champions_matches():
    headers = get_api_headers()

    response = requests.get(
        FOOTBALL_DATA_URL,
        headers=headers,
        timeout=30,
    )

    print(
        "football-data.org Champions status:",
        response.status_code,
    )

    if response.status_code == 429:
        print(
            "football-data.org quota exceeded. "
            "The calendar will not be replaced."
        )
        print(response.text[:1000])

        raise RuntimeError(
            "football-data.org quota exceeded"
        )

    if response.status_code != 200:
        print(response.text[:1000])

        raise RuntimeError(
            "football-data.org Champions error: "
            f"{response.status_code}"
        )

    data = response.json()
    matches = data.get("matches", [])

    print(
        "Champions matches returned:",
        len(matches),
    )

    return matches


def parse_match_datetime(match):
    raw_date = match.get("utcDate")

    if not raw_date:
        return None

    try:
        parsed_datetime = parser.parse(raw_date)

        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(
                tzinfo=timezone.utc
            )

        return parsed_datetime
    except (TypeError, ValueError, OverflowError):
        return None


def get_team_name(team):
    if not team:
        return "TBD"

    full_name = (
        team.get("name")
        or team.get("shortName")
        or team.get("tla")
        or "TBD"
    )

    return TEAM_SHORT_NAMES.get(
        full_name,
        full_name,
    )


def has_confirmed_teams(match):
    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}

    home_name = get_team_name(home_team)
    away_name = get_team_name(away_team)

    invalid_names = {
        "",
        "TBD",
        "To Be Determined",
        "Unknown",
        "Winner",
        "Loser",
        "Por confirmar",
    }

    if home_name in invalid_names:
        return False

    if away_name in invalid_names:
        return False

    return True


def is_allowed_stage(match):
    stage = str(
        match.get("stage") or ""
    ).strip().upper()

    return stage in ALLOWED_STAGES


def get_stage_label(stage):
    normalized_stage = str(
        stage or ""
    ).strip().upper()

    labels = {
        "QUARTER_FINALS": "Champ QF",
        "SEMI_FINALS": "Champ SF",
        "FINAL": "Final Champ",
    }

    return labels.get(
        normalized_stage,
        "Champ",
    )


def create_event_title(match):
    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}

    home_name = get_team_name(home_team)
    away_name = get_team_name(away_team)

    stage = str(
        match.get("stage") or ""
    ).strip().upper()

    stage_label = get_stage_label(stage)

    return (
        f"{home_name} vs {away_name} "
        f"({stage_label})"
    )


def create_champions_event(match):
    start_time = parse_match_datetime(match)

    if not start_time:
        return None

    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}

    home_name = get_team_name(home_team)
    away_name = get_team_name(away_team)

    match_id = match.get("id", "unknown")
    stage = match.get("stage", "UNKNOWN")
    stage_label = get_stage_label(stage)
    status = match.get("status", "SCHEDULED")

    matchday = match.get("matchday")

    competition = match.get("competition") or {}
    competition_name = (
        competition.get("name")
        or "UEFA Champions League"
    )

    event = Event()

    event.uid = (
        f"football-champions-global-{match_id}"
        "@sports-calendar-hub"
    )

    event.name = create_event_title(match)
    event.begin = start_time
    event.end = start_time + timedelta(hours=2)

    description_lines = [
        f"Competición: {competition_name}",
        f"Local: {home_name}",
        f"Visitante: {away_name}",
        f"Fase: {stage_label}",
        f"Estado: {status}",
    ]

    if matchday is not None:
        description_lines.append(
            f"Jornada: {matchday}"
        )

    description_lines.append(
        "Fuente: football-data.org"
    )

    event.description = "\n".join(
        description_lines
    )

    event.location = "Champions League"

    return event


def get_relevant_matches(matches):
    relevant_matches = []

    now = datetime.now(timezone.utc)

    for match in matches:
        if not is_allowed_stage(match):
            continue

        if not has_confirmed_teams(match):
            print(
                "Skipped undefined teams:",
                match.get("id"),
                match.get("stage"),
            )
            continue

        start_time = parse_match_datetime(match)

        if not start_time:
            continue

        if start_time < now - timedelta(hours=3):
            continue

        relevant_matches.append(
            (start_time, match)
        )

    relevant_matches.sort(
        key=lambda item: item[0]
    )

    return [
        match
        for _, match in relevant_matches
    ]


def generate_champions_calendar():
    matches = fetch_champions_matches()

    relevant_matches = get_relevant_matches(
        matches
    )

    calendar = Calendar()

    for match in relevant_matches:
        event = create_champions_event(match)

        if not event:
            continue

        calendar.events.add(event)

        print(
            "Added:",
            event.name,
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(
            calendar.serialize_iter()
        )

    print(
        "Champions events generated:",
        len(calendar.events),
    )

    print(
        "Generated:",
        OUTPUT_FILE,
    )


def main():
    generate_champions_calendar()


if __name__ == "__main__":
    main()
