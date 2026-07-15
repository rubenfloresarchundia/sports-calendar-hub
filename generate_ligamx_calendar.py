from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dateutil import parser
from ics import Calendar, Event


ROOT_DIR = Path(__file__).parent

AMERICA_OUTPUT_FILE = (
    ROOT_DIR
    / "docs"
    / "football"
    / "club-america.ics"
)

LIGA_MX_GLOBAL_OUTPUT_FILE = (
    ROOT_DIR
    / "docs"
    / "football"
    / "liga-mx-global.ics"
)

ESPN_LIGA_MX_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/soccer/mex.1/scoreboard"
)

DATE_RANGE = "20260701-20270601"

AMERICA_TEAM_NAMES = {
    "club america",
    "club américa",
    "america",
    "américa",
    "cf america",
    "cf américa",
}

TEAM_SHORT_NAMES = {
    "Club América": "América",
    "Club America": "América",
    "CF América": "América",
    "CF America": "América",
    "Guadalajara": "Chivas",
    "CD Guadalajara": "Chivas",
    "Cruz Azul": "Cruz Azul",
    "Cruz Azul FC": "Cruz Azul",
    "Pumas UNAM": "Pumas",
    "UNAM": "Pumas",
    "Tigres UANL": "Tigres",
    "UANL": "Tigres",
    "CF Monterrey": "Monterrey",
    "Monterrey": "Monterrey",
    "Toluca": "Toluca",
    "Deportivo Toluca": "Toluca",
    "Club León": "León",
    "Leon": "León",
    "León": "León",
    "Pachuca": "Pachuca",
    "Atlas": "Atlas",
    "Atlas FC": "Atlas",
    "Santos Laguna": "Santos",
    "Club Tijuana": "Tijuana",
    "Tijuana": "Tijuana",
    "Necaxa": "Necaxa",
    "Puebla": "Puebla",
    "Puebla FC": "Puebla",
    "Querétaro": "Querétaro",
    "Queretaro": "Querétaro",
    "FC Juárez": "Juárez",
    "Juarez": "Juárez",
    "Atlético San Luis": "San Luis",
    "Atletico San Luis": "San Luis",
    "Mazatlán FC": "Mazatlán",
    "Mazatlan FC": "Mazatlán",
    "Atlante": "Atlante",
    "Atlante FC": "Atlante",
}


def normalize_text(value):
    return str(value or "").strip().lower()


def fetch_liga_mx_events():
    params = {
        "dates": DATE_RANGE,
        "limit": 1000,
    }

    response = requests.get(
        ESPN_LIGA_MX_URL,
        params=params,
        timeout=30,
    )

    print(
        "ESPN Liga MX status:",
        response.status_code,
    )

    if response.status_code != 200:
        print(response.text[:1000])

        raise RuntimeError(
            f"ESPN Liga MX error: "
            f"{response.status_code}"
        )

    data = response.json()
    events = data.get("events", [])

    print(
        "Liga MX events returned:",
        len(events),
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
        parsed_datetime = parser.parse(
            raw_date
        )

        if parsed_datetime.tzinfo is None:
            parsed_datetime = (
                parsed_datetime.replace(
                    tzinfo=timezone.utc
                )
            )

        return parsed_datetime
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
        "por confirmar",
        "winner",
        "loser",
    }

    return (
        home_name not in invalid_names
        and away_name not in invalid_names
    )


def is_america_match(espn_event):
    home_team, away_team = get_competitors(
        espn_event
    )

    team_names = {
        normalize_text(
            get_full_team_name(home_team)
        ),
        normalize_text(
            get_short_team_name(home_team)
        ),
        normalize_text(
            get_full_team_name(away_team)
        ),
        normalize_text(
            get_short_team_name(away_team)
        ),
    }

    return bool(
        team_names.intersection(
            AMERICA_TEAM_NAMES
        )
    )


def get_matchday(espn_event):
    week = espn_event.get("week") or {}

    possible_values = [
        week.get("number"),
        espn_event.get("matchday"),
    ]

    competition = get_competition(
        espn_event
    )

    possible_values.extend(
        [
            competition.get("matchday"),
            competition.get("week"),
        ]
    )

    for value in possible_values:
        if isinstance(value, int):
            return value

        if isinstance(value, str):
            digits = "".join(
                character
                for character in value
                if character.isdigit()
            )

            if digits:
                return int(digits)

    return None


def get_event_context(espn_event):
    context_parts = [
        espn_event.get("name"),
        espn_event.get("shortName"),
    ]

    season = espn_event.get("season") or {}

    context_parts.extend(
        [
            season.get("slug"),
            season.get("name"),
            season.get("displayName"),
        ]
    )

    competition = get_competition(
        espn_event
    )

    context_parts.extend(
        [
            competition.get("altGameNote"),
            competition.get("type"),
        ]
    )

    status = competition.get("status") or {}
    status_type = status.get("type") or {}

    context_parts.extend(
        [
            status_type.get("description"),
            status_type.get("detail"),
            status_type.get("shortDetail"),
        ]
    )

    notes = competition.get("notes") or []

    for note in notes:
        if isinstance(note, dict):
            context_parts.extend(
                [
                    note.get("headline"),
                    note.get("text"),
                    note.get("type"),
                ]
            )
        else:
            context_parts.append(note)

    return " ".join(
        str(part)
        for part in context_parts
        if part
    ).lower()


def get_knockout_stage(espn_event):
    context = get_event_context(
        espn_event
    )

    quarter_terms = [
        "quarterfinal",
        "quarter-final",
        "quarter final",
        "cuartos",
        "cuarto de final",
        "liguilla quarter",
    ]

    semifinal_terms = [
        "semifinal",
        "semi-final",
        "semi final",
        "semifinales",
    ]

    final_terms = [
        "grand final",
        "championship final",
        "liga mx final",
        "final",
    ]

    play_in_terms = [
        "play-in",
        "play in",
        "playin",
        "reclasificación",
        "reclasificacion",
    ]

    if any(
        term in context
        for term in quarter_terms
    ):
        return "QF"

    if any(
        term in context
        for term in semifinal_terms
    ):
        return "SF"

    if any(
        term in context
        for term in final_terms
    ):
        return "FINAL"

    if any(
        term in context
        for term in play_in_terms
    ):
        return "PLAY_IN"

    return None


def is_future_event(espn_event):
    start_time = parse_event_datetime(
        espn_event
    )

    if not start_time:
        return False

    now = datetime.now(timezone.utc)

    return start_time >= (
        now - timedelta(hours=3)
    )


def should_include_america_match(
    espn_event,
):
    if not has_confirmed_teams(
        espn_event
    ):
        return False

    if not is_america_match(
        espn_event
    ):
        return False

    if not is_future_event(
        espn_event
    ):
        return False

    knockout_stage = get_knockout_stage(
        espn_event
    )

    if knockout_stage:
        return True

    matchday = get_matchday(
        espn_event
    )

    if (
        matchday is not None
        and matchday >= 12
    ):
        return True

    return False


def should_include_global_liga_mx(
    espn_event,
):
    if not has_confirmed_teams(
        espn_event
    ):
        return False

    if not is_future_event(
        espn_event
    ):
        return False

    knockout_stage = get_knockout_stage(
        espn_event
    )

    return knockout_stage in {
        "QF",
        "SF",
        "FINAL",
    }


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


def create_event_title(
    espn_event,
    global_calendar,
):
    home_team, away_team = get_competitors(
        espn_event
    )

    home_name = get_short_team_name(
        home_team
    )
    away_name = get_short_team_name(
        away_team
    )

    base_title = (
        f"{home_name} vs {away_name}"
    )

    if not global_calendar:
        return base_title

    stage = get_knockout_stage(
        espn_event
    )

    if stage == "QF":
        return (
            f"{base_title} (Liga MX QF)"
        )

    if stage == "SF":
        return (
            f"{base_title} (Liga MX SF)"
        )

    if stage == "FINAL":
        return (
            f"{base_title} "
            f"(Final Liga MX)"
        )

    return base_title


def create_calendar_event(
    espn_event,
    calendar_id,
    global_calendar,
):
    start_time = parse_event_datetime(
        espn_event
    )

    if not start_time:
        return None

    competition = get_competition(
        espn_event
    )

    event_id = espn_event.get(
        "id",
        "unknown",
    )

    home_team, away_team = get_competitors(
        espn_event
    )

    home_name = get_short_team_name(
        home_team
    )
    away_name = get_short_team_name(
        away_team
    )

    stage = get_knockout_stage(
        espn_event
    )

    matchday = get_matchday(
        espn_event
    )

    venue = get_venue(
        espn_event
    )

    status = competition.get(
        "status"
    ) or {}

    status_type = status.get(
        "type"
    ) or {}

    status_description = (
        status_type.get("description")
        or "Scheduled"
    )

    event = Event()

    event.uid = (
        f"football-ligamx-"
        f"{calendar_id}-{event_id}"
        "@sports-calendar-hub"
    )

    event.name = create_event_title(
        espn_event,
        global_calendar,
    )

    event.begin = start_time

    event.end = (
        start_time
        + timedelta(hours=2)
    )

    event.location = venue

    description_lines = [
        "Competición: Liga MX",
        f"Local: {home_name}",
        f"Visitante: {away_name}",
        f"Estado: {status_description}",
        f"Estadio: {venue}",
    ]

    if matchday is not None:
        description_lines.append(
            f"Jornada: {matchday}"
        )

    if stage:
        description_lines.append(
            f"Fase: {stage}"
        )

    description_lines.append(
        "Fuente: ESPN Liga MX"
    )

    event.description = "\n".join(
        description_lines
    )

    return event


def generate_calendar(
    espn_events,
    output_file,
    calendar_id,
    include_function,
    global_calendar,
):
    calendar = Calendar()

    selected_events = []

    for espn_event in espn_events:
        if not include_function(
            espn_event
        ):
            continue

        start_time = parse_event_datetime(
            espn_event
        )

        if not start_time:
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

    for _, espn_event in selected_events:
        event = create_calendar_event(
            espn_event=espn_event,
            calendar_id=calendar_id,
            global_calendar=global_calendar,
        )

        if not event:
            continue

        calendar.events.add(event)

        print(
            "Added:",
            event.name,
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(
            calendar.serialize_iter()
        )

    print(
        f"{calendar_id} events generated:",
        len(calendar.events),
    )

    print(
        "Generated:",
        output_file,
    )


def main():
    espn_events = fetch_liga_mx_events()

    print("=" * 60)
    print("Generating Club America calendar")

    generate_calendar(
        espn_events=espn_events,
        output_file=AMERICA_OUTPUT_FILE,
        calendar_id="club-america",
        include_function=(
            should_include_america_match
        ),
        global_calendar=False,
    )

    print("=" * 60)
    print("Generating global Liga MX calendar")

    generate_calendar(
        espn_events=espn_events,
        output_file=(
            LIGA_MX_GLOBAL_OUTPUT_FILE
        ),
        calendar_id="liga-mx-global",
        include_function=(
            should_include_global_liga_mx
        ),
        global_calendar=True,
    )


if __name__ == "__main__":
    main()
