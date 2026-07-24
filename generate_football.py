import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
import yaml
from dateutil import parser
from ics import Calendar, Event


ROOT_DIR = Path(__file__).parent
CONFIG_PATH = ROOT_DIR / "config" / "football_calendars.yaml"
OUTPUT_DIR = ROOT_DIR / "docs"


TEAM_SHORT_NAMES = {
    "Real Madrid CF": "Real Madrid",
    "FC Barcelona": "Barcelona",
    "Club Atlético de Madrid": "Atlético Madrid",
    "Atlético Madrid": "Atlético Madrid",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "RCD Espanyol de Barcelona": "Espanyol",
    "Málaga CF": "Málaga",
    "Real Betis Balompié": "Real Betis",
    "Rayo Vallecano de Madrid": "Rayo Vallecano",
    "Elche CF": "Elche",
    "Villarreal CF": "Villarreal",
    "Sevilla FC": "Sevilla",
    "Racing de Santander": "Racing Santander",
    "Real Racing Club de Santander": "Racing Santander",
    "Valencia CF": "Valencia",
    "RC Celta de Vigo": "Celta de Vigo",
    "Celta de Vigo": "Celta de Vigo",
    "Deportivo Alavés": "Alavés",
    "Athletic Club": "Athletic",
    "Athletic Bilbao": "Athletic",
    "CA Osasuna": "Osasuna",
    "RC Deportivo La Coruña": "Deportivo",
    "Getafe CF": "Getafe",
    "Levante UD": "Levante",
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
    "Juventus FC": "Juventus",
    "FC Internazionale Milano": "Inter",
    "AC Milan": "Milan",
    "SSC Napoli": "Napoli",
    "SL Benfica": "Benfica",
    "FC Porto": "Porto",
    "Sporting Clube de Portugal": "Sporting",
    "AFC Ajax": "Ajax",
    "PSV": "PSV",
}


CHAMPIONS_LEAGUE_PHASE_MATCHDAYS = {
    6,
    7,
    8,
}


CHAMPIONS_KNOCKOUT_STAGES = {
    "PLAYOFFS",
    "KNOCKOUT_PLAYOFFS",
    "KNOCKOUT_STAGE_PLAY_OFFS",
    "LAST_16",
    "ROUND_OF_16",
    "QUARTER_FINALS",
    "SEMI_FINALS",
    "FINAL",
}


INVALID_TEAM_NAMES = {
    "",
    "tbd",
    "to be determined",
    "unknown",
    "winner",
    "loser",
    "por confirmar",
}


def load_football_calendars():
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    return data.get("calendars", [])


def get_api_headers():
    api_key = os.environ.get(
        "FOOTBALL_DATA_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "Missing FOOTBALL_DATA_API_KEY"
        )

    return {
        "X-Auth-Token": api_key
    }


def normalize_name(name):
    return str(name or "").strip().lower()


def get_team_short_name(team_name):
    if not team_name:
        return "TBD"

    return TEAM_SHORT_NAMES.get(
        team_name,
        team_name,
    )


def get_competition_label(calendar_config):
    calendar_id = calendar_config.get(
        "id",
        "",
    )

    name = calendar_config.get(
        "name",
        "",
    )

    if (
        "laliga" in calendar_id.lower()
        or "laliga" in name.lower()
    ):
        return "LaLiga"

    if (
        "champions" in calendar_id.lower()
        or "champions" in name.lower()
    ):
        return "Champions"

    return name


def is_champions_calendar(
    calendar_config,
):
    calendar_id = str(
        calendar_config.get(
            "id",
            "",
        )
    ).lower()

    competition_code = str(
        calendar_config.get(
            "competition_code",
            "",
        )
    ).upper()

    return (
        "champions" in calendar_id
        or competition_code == "CL"
    )


def team_matches_calendar_team(
    match,
    team_names,
):
    home_team = (
        match.get("homeTeam")
        or {}
    )

    away_team = (
        match.get("awayTeam")
        or {}
    )

    home_name = normalize_name(
        home_team.get("name")
    )

    away_name = normalize_name(
        away_team.get("name")
    )

    normalized_targets = [
        normalize_name(name)
        for name in team_names
    ]

    for target in normalized_targets:
        if (
            target == home_name
            or target == away_name
        ):
            return True

    for target in normalized_targets:
        if (
            target in home_name
            or target in away_name
        ):
            return True

    return False


def has_confirmed_teams(match):
    home_team = (
        match.get("homeTeam")
        or {}
    )

    away_team = (
        match.get("awayTeam")
        or {}
    )

    home_name = normalize_name(
        home_team.get("name")
    )

    away_name = normalize_name(
        away_team.get("name")
    )

    return (
        home_name not in INVALID_TEAM_NAMES
        and away_name not in INVALID_TEAM_NAMES
    )


def parse_match_datetime(match):
    raw_date = match.get("utcDate")

    if not raw_date:
        return None

    try:
        parsed = parser.parse(raw_date)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None


def get_competition_matches(
    competition_code,
):
    headers = get_api_headers()

    url = (
        "https://api.football-data.org/v4/"
        f"competitions/{competition_code}/matches"
    )

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    print(
        f"football-data.org status "
        f"({competition_code}):",
        response.status_code,
    )

    if response.status_code == 429:
        print(
            "football-data.org quota exceeded. "
            "Stopping without updating calendars."
        )

        print(response.text[:1000])

        raise RuntimeError(
            "football-data.org quota exceeded"
        )

    if response.status_code != 200:
        print(response.text[:1000])

        raise RuntimeError(
            "football-data.org error: "
            f"{response.status_code}"
        )

    data = response.json()
    matches = data.get("matches", [])

    print(
        f"Matches returned for "
        f"{competition_code}: "
        f"{len(matches)}"
    )

    return matches


def should_include_champions_match(
    match,
):
    stage = str(
        match.get("stage")
        or ""
    ).strip().upper()

    matchday = match.get("matchday")

    if stage in CHAMPIONS_KNOCKOUT_STAGES:
        return True

    if stage in {
        "LEAGUE_STAGE",
        "REGULAR_SEASON",
    }:
        return (
            matchday
            in CHAMPIONS_LEAGUE_PHASE_MATCHDAYS
        )

    return False


def get_upcoming_team_matches(
    calendar_config,
    all_matches_by_competition,
):
    competition_code = (
        calendar_config[
            "competition_code"
        ]
    )

    team_names = calendar_config[
        "team_names"
    ]

    matches = (
        all_matches_by_competition.get(
            competition_code,
            [],
        )
    )

    now = datetime.now(
        timezone.utc
    )

    upcoming_matches = []

    for match in matches:
        if not team_matches_calendar_team(
            match,
            team_names,
        ):
            continue

        if not has_confirmed_teams(match):
            print(
                "Skipped undefined teams:",
                match.get("id"),
                match.get("stage"),
            )

            continue

        if is_champions_calendar(
            calendar_config
        ):
            if not should_include_champions_match(
                match
            ):
                continue

        start_time = parse_match_datetime(
            match
        )

        if not start_time:
            continue

        if start_time < (
            now - timedelta(hours=3)
        ):
            continue

        upcoming_matches.append(
            (
                start_time,
                match,
            )
        )

    upcoming_matches.sort(
        key=lambda item: item[0]
    )

    if not upcoming_matches:
        print(
            "No upcoming matches found for "
            f"{calendar_config['name']}"
        )

        return []

    print("=" * 60)

    print(
        "Selected matches for:",
        calendar_config["name"],
    )

    for (
        start_time,
        match,
    ) in upcoming_matches:
        home_team = (
            match.get("homeTeam")
            or {}
        )

        away_team = (
            match.get("awayTeam")
            or {}
        )

        print(
            "Date:",
            start_time.isoformat(),
        )

        print(
            "Home:",
            home_team.get("name"),
        )

        print(
            "Away:",
            away_team.get("name"),
        )

        print(
            "Status:",
            match.get("status"),
        )

        print(
            "Matchday:",
            match.get("matchday"),
        )

        print(
            "Stage:",
            match.get("stage"),
        )

        print("---")

    return [
        match
        for _, match in upcoming_matches
    ]


def create_match_event(
    calendar_config,
    match,
):
    competition_label = (
        get_competition_label(
            calendar_config
        )
    )

    home_team = (
        match.get("homeTeam")
        or {}
    )

    away_team = (
        match.get("awayTeam")
        or {}
    )

    home_full = home_team.get(
        "name",
        "Home TBD",
    )

    away_full = away_team.get(
        "name",
        "Away TBD",
    )

    home_short = get_team_short_name(
        home_full
    )

    away_short = get_team_short_name(
        away_full
    )

    start_time = parse_match_datetime(
        match
    )

    if not start_time:
        raise RuntimeError(
            f"Match {match.get('id')} "
            "has no valid start time"
        )

    match_id = match.get(
        "id",
        "unknown",
    )

    matchday = match.get("matchday")
    stage = match.get("stage")

    status = match.get(
        "status",
        "SCHEDULED",
    )

    event = Event()

    event.uid = (
        f"football-"
        f"{calendar_config['id']}-"
        f"{match_id}"
        "@sports-calendar-hub"
    )

    if is_champions_calendar(
        calendar_config
    ):
        event.name = (
            f"{home_short} vs "
            f"{away_short} (Champ)"
        )
    else:
        event.name = (
            f"{home_short} vs "
            f"{away_short} - "
            f"{competition_label}"
        )

    event.begin = start_time

    event.end = (
        start_time
        + timedelta(hours=2)
    )

    description_lines = [
        (
            "Competition: "
            f"{calendar_config['name']}"
        ),
        f"Home: {home_full}",
        f"Away: {away_full}",
        f"Status: {status}",
    ]

    if matchday is not None:
        description_lines.append(
            f"Matchday: {matchday}"
        )

    if stage:
        description_lines.append(
            f"Stage: {stage}"
        )

    description_lines.append(
        "Source: football-data.org"
    )

    event.description = "\n".join(
        description_lines
    )

    event.location = competition_label

    return event


def create_fallback_event(
    calendar_config,
):
    event = Event()

    event.uid = (
        f"football-"
        f"{calendar_config['id']}-fallback"
        "@sports-calendar-hub"
    )

    event.name = (
        f"{calendar_config['name']} "
        "- pendiente"
    )

    event.begin = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    event.end = (
        event.begin
        + timedelta(hours=2)
    )

    event.description = (
        f"Calendar: "
        f"{calendar_config['name']}\n"
        "Next match pending confirmation\n"
        "Source: football-data.org"
    )

    event.location = "TBD"

    return event


def generate_football_calendar(
    calendar_config,
    all_matches_by_competition,
):
    calendar = Calendar()

    matches = get_upcoming_team_matches(
        calendar_config,
        all_matches_by_competition,
    )

    if matches:
        for match in matches:
            calendar.events.add(
                create_match_event(
                    calendar_config,
                    match,
                )
            )

    elif not is_champions_calendar(
        calendar_config
    ):
        calendar.events.add(
            create_fallback_event(
                calendar_config
            )
        )

    else:
        print(
            "Champions calendar has no "
            "confirmed relevant matches. "
            "No fallback event will be created."
        )

    output_path = (
        OUTPUT_DIR
        / calendar_config["output"]
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(
            calendar.serialize_iter()
        )

    print(
        "Generated:",
        output_path,
    )

    print(
        "Events generated:",
        len(calendar.events),
    )


def main():
    calendars = (
        load_football_calendars()
    )

    competition_codes = sorted(
        {
            calendar["competition_code"]
            for calendar in calendars
        }
    )

    all_matches_by_competition = {}

    for competition_code in (
        competition_codes
    ):
        all_matches_by_competition[
            competition_code
        ] = get_competition_matches(
            competition_code
        )

    for calendar_config in calendars:
        generate_football_calendar(
            calendar_config,
            all_matches_by_competition,
        )


if __name__ == "__main__":
    main()
