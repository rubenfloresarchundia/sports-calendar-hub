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


def load_football_calendars():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return data.get("calendars", [])


def get_api_headers():
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")

    if not api_key:
        raise RuntimeError("Missing FOOTBALL_DATA_API_KEY")

    return {
        "X-Auth-Token": api_key
    }


def normalize_name(name):
    return str(name or "").strip().lower()


def team_matches_calendar_team(match, team_names):
    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}

    home_name = normalize_name(home_team.get("name"))
    away_name = normalize_name(away_team.get("name"))

    normalized_targets = [normalize_name(name) for name in team_names]

    for target in normalized_targets:
        if target == home_name or target == away_name:
            return True

    for target in normalized_targets:
        if target in home_name or target in away_name:
            return True

    return False


def parse_match_datetime(match):
    raw_date = match.get("utcDate")

    if not raw_date:
        return None

    try:
        parsed = parser.parse(raw_date)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed
    except Exception:
        return None


def get_competition_matches(competition_code):
    headers = get_api_headers()

    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches"

    response = requests.get(url, headers=headers, timeout=30)

    print(f"football-data.org status ({competition_code}):", response.status_code)

    if response.status_code == 429:
        print("football-data.org quota exceeded. Stopping without updating calendars.")
        print(response.text[:1000])
        raise RuntimeError("football-data.org quota exceeded")

    if response.status_code != 200:
        print(response.text[:1000])
        raise RuntimeError(f"football-data.org error: {response.status_code}")

    data = response.json()
    matches = data.get("matches", [])

    print(f"Matches returned for {competition_code}: {len(matches)}")

    return matches


def get_upcoming_team_matches(calendar_config, all_matches_by_competition):
    competition_code = calendar_config["competition_code"]
    team_names = calendar_config["team_names"]

    matches = all_matches_by_competition.get(competition_code, [])

    now = datetime.now(timezone.utc)
    upcoming_matches = []

    for match in matches:
        if not team_matches_calendar_team(match, team_names):
            continue

        start_time = parse_match_datetime(match)

        if not start_time:
            continue

        # Keep recently started matches and future matches.
        if start_time < now - timedelta(hours=3):
            continue

        upcoming_matches.append((start_time, match))

    upcoming_matches.sort(key=lambda item: item[0])

    if not upcoming_matches:
        print(f"No upcoming matches found for {calendar_config['name']}")
        return []

    print("=" * 60)
    print(f"Selected matches for: {calendar_config['name']}")

    for start_time, match in upcoming_matches:
        home_team = match.get("homeTeam") or {}
        away_team = match.get("awayTeam") or {}

        print("Date:", start_time.isoformat())
        print("Home:", home_team.get("name"))
        print("Away:", away_team.get("name"))
        print("Status:", match.get("status"))
        print("Matchday:", match.get("matchday"))
        print("Stage:", match.get("stage"))
        print("---")

    return [match for _, match in upcoming_matches]


def create_match_event(calendar_config, match):
    competition_name = calendar_config["name"]

    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}

    home_name = home_team.get("name", "Home TBD")
    away_name = away_team.get("name", "Away TBD")

    start_time = parse_match_datetime(match)

    if not start_time:
        start_time = datetime.now(timezone.utc) + timedelta(days=7)

    match_id = match.get("id", "unknown")
    matchday = match.get("matchday")
    stage = match.get("stage")
    status = match.get("status", "SCHEDULED")

    event = Event()
    event.uid = f"football-{calendar_config['id']}-{match_id}@sports-calendar-hub"
    event.name = f"{home_name} vs {away_name} - {competition_name}"
    event.begin = start_time
    event.end = start_time + timedelta(hours=2)

    description_lines = [
        f"Competition: {competition_name}",
        f"Home: {home_name}",
        f"Away: {away_name}",
        f"Status: {status}",
    ]

    if matchday is not None:
        description_lines.append(f"Matchday: {matchday}")

    if stage:
        description_lines.append(f"Stage: {stage}")

    description_lines.append("Source: football-data.org")

    event.description = "\n".join(description_lines)
    event.location = competition_name

    return event


def create_fallback_event(calendar_config):
    event = Event()
    event.uid = f"football-{calendar_config['id']}-fallback@sports-calendar-hub"
    event.name = f"{calendar_config['name']} - next match pending confirmation"
    event.begin = datetime.now(timezone.utc) + timedelta(days=7)
    event.end = event.begin + timedelta(hours=2)
    event.description = (
        f"Calendar: {calendar_config['name']}\n"
        "Next match pending confirmation\n"
        "Source: football-data.org"
    )
    event.location = "TBD"

    return event


def generate_football_calendar(calendar_config, all_matches_by_competition):
    calendar = Calendar()

    matches = get_upcoming_team_matches(calendar_config, all_matches_by_competition)

    if matches:
        for match in matches:
            calendar.events.add(create_match_event(calendar_config, match))
    else:
        calendar.events.add(create_fallback_event(calendar_config))

    output_path = OUTPUT_DIR / calendar_config["output"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        file.writelines(calendar.serialize_iter())

    print(f"Generated: {output_path}")


def main():
    calendars = load_football_calendars()

    competition_codes = sorted({calendar["competition_code"] for calendar in calendars})
    all_matches_by_competition = {}

    for competition_code in competition_codes:
        all_matches_by_competition[competition_code] = get_competition_matches(competition_code)

    for calendar_config in calendars:
        generate_football_calendar(calendar_config, all_matches_by_competition)


if __name__ == "__main__":
    main()
