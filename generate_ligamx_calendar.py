from collections import defaultdict
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

AMERICA_MINIMUM_MATCHDAY = 12

AMERICA_TEAM_NAMES = {
    "club america",
    "club américa",
    "cf america",
    "cf américa",
    "america",
    "américa",
}

TEAM_SHORT_NAMES = {
    "Club América": "América",
    "Club America": "América",
    "CF América": "América",
    "CF America": "América",
    "América": "América",
    "America": "América",
    "Guadalajara": "Chivas",
    "CD Guadalajara": "Chivas",
    "Chivas": "Chivas",
    "Cruz Azul": "Cruz Azul",
    "Cruz Azul FC": "Cruz Azul",
    "Pumas UNAM": "Pumas",
    "UNAM": "Pumas",
    "Tigres UANL": "Tigres",
    "UANL": "Tigres",
    "CF Monterrey": "Monterrey",
    "Monterrey": "Monterrey",
    "Deportivo Toluca": "Toluca",
    "Toluca": "Toluca",
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
    "FC Juarez": "Juárez",
    "Juárez": "Juárez",
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
        flush=True,
    )

    if response.status_code != 200:
        print(
            response.text[:1000],
            flush=True,
        )

        raise RuntimeError(
            f"ESPN Liga MX error: "
            f"{response.status_code}"
        )

    data = response.json()
    events = data.get("events", [])

    print(
        "Liga MX events returned:",
        len(events),
        flush=True,
    )

    return events


def parse_event_datetime(espn_event):
    raw_date = espn_event.get("date")

    if not raw_date:
        competition = get_competition(
            espn_event
        )
        raw_date = competition.get("date")

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

        return parsed_datetime.astimezone(
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

        home_away = competitor.get(
            "homeAway"
        )

        if home_away == "home":
            home_team = team

        if home_away == "away":
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


def is_america_team(team):
    full_name = normalize_text(
        get_full_team_name(team)
    )

    short_name = normalize_text(
        get_short_team_name(team)
    )

    return (
        full_name in AMERICA_TEAM_NAMES
        or short_name in AMERICA_TEAM_NAMES
    )


def is_america_match(espn_event):
    home_team, away_team = get_competitors(
        espn_event
    )

    return (
        is_america_team(home_team)
        or is_america_team(away_team)
    )


def get_season_key(espn_event):
    season = espn_event.get("season") or {}

    season_year = season.get(
        "year",
        "unknown",
    )

    season_type = season.get(
        "type",
        "unknown",
    )

    season_slug = season.get(
        "slug",
        "unknown",
    )

    return (
        str(season_year),
        str(season_type),
        str(season_slug),
    )


def get_tournament_label(espn_event):
    season = espn_event.get("season") or {}

    season_slug = normalize_text(
        season.get("slug")
    )

    if "apertura" in season_slug:
        return "Apertura"

    if "clausura" in season_slug:
        return "Clausura"

    return "Liga MX"


def get_explicit_matchday(espn_event):
    week = espn_event.get("week") or {}
    competition = get_competition(
        espn_event
    )

    possible_values = [
        week.get("number"),
        espn_event.get("matchday"),
        competition.get("matchday"),
        competition.get("week"),
    ]

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

    return normalize_text(
        " ".join(
            str(part)
            for part in context_parts
            if part
        )
    )


def get_knockout_stage(espn_event):
    context = get_event_context(
        espn_event
    )

    play_in_terms = [
        "play-in",
        "play in",
        "playin",
        "reclasificación",
        "reclasificacion",
    ]

    quarter_terms = [
        "quarterfinal",
        "quarter-final",
        "quarter final",
        "cuartos",
        "cuarto de final",
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
        "final vuelta",
        "final ida",
    ]

    if any(
        term in context
        for term in play_in_terms
    ):
        return "PLAY_IN"

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


def assign_america_matchdays(
    espn_events,
):
    regular_matches_by_season = (
        defaultdict(list)
    )

    for espn_event in espn_events:
        if not is_america_match(
            espn_event
        ):
            continue

        if not has_confirmed_teams(
            espn_event
        ):
            continue

        if get_knockout_stage(
            espn_event
        ):
            continue

        start_time = parse_event_datetime(
            espn_event
        )

        if not start_time:
            continue

        season_key = get_season_key(
            espn_event
        )

        regular_matches_by_season[
            season_key
        ].append(
            (
                start_time,
                espn_event,
            )
        )

    calculated_matchdays = {}

    for (
        season_key,
        season_matches,
    ) in regular_matches_by_season.items():
        season_matches.sort(
            key=lambda item: item[0]
        )

        print(
            "Calculating America matchdays for:",
            season_key,
            flush=True,
        )

        for index, (
            start_time,
            espn_event,
        ) in enumerate(
            season_matches,
            start=1,
        ):
            event_id = str(
                espn_event.get(
                    "id",
                    "unknown",
                )
            )

            explicit_matchday = (
                get_explicit_matchday(
                    espn_event
                )
            )

            calculated_matchday = (
                explicit_matchday
                if explicit_matchday is not None
                else index
            )

            calculated_matchdays[
                event_id
            ] = calculated_matchday

            print(
                "America match:",
                calculated_matchday,
                "-",
                espn_event.get("name"),
                "-",
                start_time.isoformat(),
                flush=True,
            )

    return calculated_matchdays


def should_include_america_match(
    espn_event,
    america_matchdays,
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

    if knockout_stage in {
        "PLAY_IN",
        "QF",
        "SF",
        "FINAL",
    }:
        return True

    event_id = str(
        espn_event.get(
            "id",
            "unknown",
        )
    )

    calculated_matchday = (
        america_matchdays.get(
            event_id
        )
    )

    if calculated_matchday is None:
        return False

    return (
        calculated_matchday
        >= AMERICA_MINIMUM_MATCHDAY
    )


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
    calculated_matchday=None,
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

    tournament_label = get_tournament_label(
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
        f"Competición: Liga MX {tournament_label}",
        f"Local: {home_name}",
        f"Visitante: {away_name}",
        f"Estado: {status_description}",
        f"Estadio: {venue}",
    ]

    if calculated_matchday is not None:
        description_lines.append(
            f"Jornada: {calculated_matchday}"
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


def generate_america_calendar(
    espn_events,
    america_matchdays,
):
    calendar = Calendar()
    selected_events = []

    for espn_event in espn_events:
        if not should_include_america_match(
            espn_event,
            america_matchdays,
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
        event_id = str(
            espn_event.get(
                "id",
                "unknown",
            )
        )

        calculated_matchday = (
            america_matchdays.get(
                event_id
            )
        )

        event = create_calendar_event(
            espn_event=espn_event,
            calendar_id="club-america",
            global_calendar=False,
            calculated_matchday=(
                calculated_matchday
            ),
        )

        if not event:
            continue

        calendar.events.add(event)

        print(
            "Added America:",
            event.name,
            "- Jornada:",
            calculated_matchday,
            flush=True,
        )

    AMERICA_OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with AMERICA_OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(
            calendar.serialize_iter()
        )

    print(
        "club-america events generated:",
        len(calendar.events),
        flush=True,
    )

    print(
        "Generated:",
        AMERICA_OUTPUT_FILE,
        flush=True,
    )


def generate_global_liga_mx_calendar(
    espn_events,
):
    calendar = Calendar()
    selected_events = []

    for espn_event in espn_events:
        if not should_include_global_liga_mx(
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
            calendar_id="liga-mx-global",
            global_calendar=True,
        )

        if not event:
            continue

        calendar.events.add(event)

        print(
            "Added Liga MX global:",
            event.name,
            flush=True,
        )

    LIGA_MX_GLOBAL_OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LIGA_MX_GLOBAL_OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(
            calendar.serialize_iter()
        )

    print(
        "liga-mx-global events generated:",
        len(calendar.events),
        flush=True,
    )

    print(
        "Generated:",
        LIGA_MX_GLOBAL_OUTPUT_FILE,
        flush=True,
    )


def main():
    espn_events = fetch_liga_mx_events()

    america_matchdays = (
        assign_america_matchdays(
            espn_events
        )
    )

    print("=" * 60)
    print(
        "Generating Club America calendar",
        flush=True,
    )

    generate_america_calendar(
        espn_events,
        america_matchdays,
    )

    print("=" * 60)
    print(
        "Generating global Liga MX calendar",
        flush=True,
    )

    generate_global_liga_mx_calendar(
        espn_events
    )


if __name__ == "__main__":
    main()
