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
    / "mexico-national-team.ics"
)

ESPN_MEXICO_SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/soccer/all/teams/203/schedule"
)

MEXICO_TEAM_NAMES = {
    "mexico",
    "méxico",
    "mex",
}

TEAM_SHORT_NAMES = {
    "Mexico": "México",
    "México": "México",
    "United States": "Estados Unidos",
    "United States of America": "Estados Unidos",
    "USA": "Estados Unidos",
    "Canada": "Canadá",
    "Argentina": "Argentina",
    "Brazil": "Brasil",
    "England": "Inglaterra",
    "Germany": "Alemania",
    "France": "Francia",
    "Spain": "España",
    "Italy": "Italia",
    "Portugal": "Portugal",
    "Netherlands": "Países Bajos",
    "Belgium": "Bélgica",
    "Japan": "Japón",
    "South Korea": "Corea del Sur",
    "Korea Republic": "Corea del Sur",
    "Australia": "Australia",
    "South Africa": "Sudáfrica",
    "Serbia": "Serbia",
    "Ghana": "Ghana",
    "Costa Rica": "Costa Rica",
    "Panama": "Panamá",
    "Honduras": "Honduras",
    "Jamaica": "Jamaica",
    "Guatemala": "Guatemala",
    "El Salvador": "El Salvador",
    "Colombia": "Colombia",
    "Uruguay": "Uruguay",
    "Chile": "Chile",
    "Ecuador": "Ecuador",
    "Czechia": "Chequia",
    "Czech Republic": "Chequia",
}


COMPETITION_LABELS = {
    "fifa world cup": "Mundial",
    "world cup": "Mundial",
    "fifa world cup qualifying": "Eliminatorias",
    "world cup qualifying": "Eliminatorias",
    "concacaf gold cup": "Copa Oro",
    "gold cup": "Copa Oro",
    "concacaf nations league": "Nations League",
    "nations league": "Nations League",
    "copa america": "Copa América",
    "copa américa": "Copa América",
    "international friendly": "Amistoso",
    "international friendlies": "Amistoso",
    "friendlies": "Amistoso",
    "friendly": "Amistoso",
}


def normalize_text(value):
    return str(value or "").strip().lower()


def fetch_mexico_schedule():
    params = {
        "season": 2026,
        "region": "us",
        "lang": "en",
    }

    response = requests.get(
        ESPN_MEXICO_SCHEDULE_URL,
        params=params,
        timeout=30,
    )

    print(
        "ESPN Mexico status:",
        response.status_code,
        flush=True,
    )

    if response.status_code != 200:
        print(
            response.text[:2000],
            flush=True,
        )

        raise RuntimeError(
            f"ESPN Mexico error: "
            f"{response.status_code}"
        )

    data = response.json()
    events = data.get("events", [])

    print(
        "Mexico events returned:",
        len(events),
        flush=True,
    )

    return events


def parse_event_datetime(espn_event):
    raw_date = espn_event.get("date")

    if not raw_date:
        competitions = (
            espn_event.get("competitions")
            or []
        )

        if competitions:
            raw_date = competitions[0].get(
                "date"
            )

    if not raw_date:
        return None

    try:
        event_datetime = parser.parse(
            raw_date
        )

        if event_datetime.tzinfo is None:
            event_datetime = (
                event_datetime.replace(
                    tzinfo=timezone.utc
                )
            )

        return event_datetime.astimezone(
            timezone.utc
        )

    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None


def get_competition(espn_event):
    competitions = (
        espn_event.get("competitions")
        or []
    )

    if not competitions:
        return {}

    return competitions[0]


def get_competitors(espn_event):
    competition = get_competition(
        espn_event
    )

    competitors = (
        competition.get("competitors")
        or []
    )

    home_team = None
    away_team = None

    for competitor in competitors:
        team = competitor.get("team") or {}

        if competitor.get("homeAway") == "home":
            home_team = team

        if competitor.get("homeAway") == "away":
            away_team = team

    return home_team, away_team


def get_full_team_name(team):
    if not team:
        return "TBD"

    return (
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("name")
        or team.get("abbreviation")
        or "TBD"
    )


def get_short_team_name(team):
    full_name = get_full_team_name(team)

    return TEAM_SHORT_NAMES.get(
        full_name,
        full_name,
    )


def has_confirmed_teams(espn_event):
    home_team, away_team = get_competitors(
        espn_event
    )

    home_name = normalize_text(
        get_full_team_name(home_team)
    )

    away_name = normalize_text(
        get_full_team_name(away_team)
    )

    invalid_names = {
        "",
        "tbd",
        "to be determined",
        "unknown",
        "winner",
        "loser",
        "por confirmar",
    }

    return (
        home_name not in invalid_names
        and away_name not in invalid_names
    )


def is_mexico_team(team):
    full_name = normalize_text(
        get_full_team_name(team)
    )

    abbreviation = normalize_text(
        team.get("abbreviation")
        if team
        else ""
    )

    return (
        full_name in MEXICO_TEAM_NAMES
        or abbreviation in MEXICO_TEAM_NAMES
    )


def is_mexico_match(espn_event):
    home_team, away_team = get_competitors(
        espn_event
    )

    return (
        is_mexico_team(home_team)
        or is_mexico_team(away_team)
    )


def get_competition_name(espn_event):
    possible_names = []

    season = espn_event.get("season") or {}

    possible_names.extend(
        [
            season.get("displayName"),
            season.get("name"),
            season.get("slug"),
        ]
    )

    league = espn_event.get("league") or {}

    possible_names.extend(
        [
            league.get("name"),
            league.get("abbreviation"),
        ]
    )

    competition = get_competition(
        espn_event
    )

    possible_names.extend(
        [
            competition.get("altGameNote"),
            competition.get("type"),
        ]
    )

    for possible_name in possible_names:
        normalized_name = normalize_text(
            possible_name
        )

        if not normalized_name:
            continue

        for key, label in COMPETITION_LABELS.items():
            if key in normalized_name:
                return label

    return "Selección"


def get_venue(espn_event):
    competition = get_competition(
        espn_event
    )

    venue = competition.get("venue") or {}

    return (
        venue.get("fullName")
        or venue.get("name")
        or "Por confirmar"
    )


def get_status(espn_event):
    competition = get_competition(
        espn_event
    )

    status = competition.get("status") or {}
    status_type = status.get("type") or {}

    return (
        status_type.get("description")
        or status_type.get("detail")
        or "Scheduled"
    )


def create_event_title(espn_event):
    home_team, away_team = get_competitors(
        espn_event
    )

    home_name = get_short_team_name(
        home_team
    )

    away_name = get_short_team_name(
        away_team
    )

    competition_label = get_competition_name(
        espn_event
    )

    return (
        f"{home_name} vs {away_name} "
        f"({competition_label})"
    )


def create_calendar_event(espn_event):
    start_time = parse_event_datetime(
        espn_event
    )

    if not start_time:
        return None

    home_team, away_team = get_competitors(
        espn_event
    )

    home_name = get_short_team_name(
        home_team
    )

    away_name = get_short_team_name(
        away_team
    )

    event_id = espn_event.get(
        "id",
        "unknown",
    )

    competition_label = get_competition_name(
        espn_event
    )

    venue = get_venue(
        espn_event
    )

    status = get_status(
        espn_event
    )

    event = Event()

    event.uid = (
        f"football-mexico-{event_id}"
        "@sports-calendar-hub"
    )

    event.name = create_event_title(
        espn_event
    )

    event.begin = start_time

    event.end = (
        start_time
        + timedelta(hours=2)
    )

    event.location = venue

    event.description = (
        f"Competición: {competition_label}\n"
        f"Local: {home_name}\n"
        f"Visitante: {away_name}\n"
        f"Estado: {status}\n"
        f"Estadio: {venue}\n"
        "Fuente: ESPN México"
    )

    return event


def get_future_mexico_matches(events):
    selected_events = []

    now = datetime.now(timezone.utc)

    for espn_event in events:
        if not is_mexico_match(
            espn_event
        ):
            continue

        if not has_confirmed_teams(
            espn_event
        ):
            print(
                "Skipped undefined opponent:",
                espn_event.get("name"),
                flush=True,
            )
            continue

        start_time = parse_event_datetime(
            espn_event
        )

        if not start_time:
            continue

        if start_time < now - timedelta(
            hours=3
        ):
            continue

        selected_events.append(
            (
                start_time,
                espn_event,
            )
        )

    selected_events.sort(
        key=lambda item: item[0]
    )

    return [
        espn_event
        for _, espn_event in selected_events
    ]


def generate_mexico_calendar():
    espn_events = fetch_mexico_schedule()

    future_matches = (
        get_future_mexico_matches(
            espn_events
        )
    )

    calendar = Calendar()

    for espn_event in future_matches:
        event = create_calendar_event(
            espn_event
        )

        if not event:
            continue

        calendar.events.add(event)

        print(
            "Added:",
            event.name,
            flush=True,
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
        "Mexico events generated:",
        len(calendar.events),
        flush=True,
    )

    print(
        "Generated:",
        OUTPUT_FILE,
        flush=True,
    )


def main():
    generate_mexico_calendar()


if __name__ == "__main__":
    main()
