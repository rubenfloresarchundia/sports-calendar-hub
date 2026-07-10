from pathlib import Path
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

import requests
from dateutil import parser
from ics import Calendar, Event


ROOT_DIR = Path(__file__).parent
OUTPUT_DIR = ROOT_DIR / "docs"

NFL_SEASON = 2026
EASTERN_TZ = ZoneInfo("America/New_York")

REGULAR_SEASON_TYPE = 2
POSTSEASON_TYPE = 3

REGULAR_SEASON_WEEKS = range(1, 19)
POSTSEASON_WEEKS = range(1, 6)


CALENDARS = [
    {
        "id": "miami-dolphins",
        "name": "Miami Dolphins",
        "output": "nfl/miami-dolphins.ics",
        "filter": "miami_dolphins",
    },
    {
        "id": "nfl-estelares",
        "name": "NFL Estelares",
        "output": "nfl/estelares.ics",
        "filter": "marquee",
    },
]


def cleanup_old_nfl_files():
    nfl_dir = OUTPUT_DIR / "nfl"
    nfl_dir.mkdir(parents=True, exist_ok=True)

    for file in nfl_dir.glob("*.ics"):
        file.unlink()
        print(f"Removed old NFL calendar: {file}")


def get_thanksgiving_date(year):
    november_first = date(year, 11, 1)
    days_until_thursday = (3 - november_first.weekday()) % 7
    first_thursday = november_first + timedelta(days=days_until_thursday)
    fourth_thursday = first_thursday + timedelta(days=21)
    return fourth_thursday


def fetch_espn_scoreboard(season_type, week):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

    params = {
        "seasontype": season_type,
        "week": week,
        "dates": NFL_SEASON,
    }

    response = requests.get(url, params=params, timeout=30)

    print(
        f"ESPN NFL status season_type={season_type}, week={week}:",
        response.status_code,
    )

    if response.status_code != 200:
        print(response.text[:1000])
        raise RuntimeError(f"ESPN NFL API error: {response.status_code}")

    data = response.json()
    return data.get("events", [])


def load_all_nfl_events():
    events = []

    for week in REGULAR_SEASON_WEEKS:
        events.extend(fetch_espn_scoreboard(REGULAR_SEASON_TYPE, week))

    for week in POSTSEASON_WEEKS:
        events.extend(fetch_espn_scoreboard(POSTSEASON_TYPE, week))

    unique = {}

    for event in events:
        event_id = event.get("id")
        if event_id:
            unique[event_id] = event

    all_events = list(unique.values())

    print("Total unique NFL events:", len(all_events))

    return all_events


def parse_event_datetime(event):
    raw_date = event.get("date")

    if not raw_date:
        return None

    parsed = parser.parse(raw_date)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def get_event_local_datetime(event):
    start_time = parse_event_datetime(event)

    if not start_time:
        return None

    return start_time.astimezone(EASTERN_TZ)


def get_competitors(event):
    competitions = event.get("competitions") or []

    if not competitions:
        return None, None

    competitors = competitions[0].get("competitors") or []

    home = None
    away = None

    for competitor in competitors:
        if competitor.get("homeAway") == "home":
            home = competitor.get("team") or {}
        elif competitor.get("homeAway") == "away":
            away = competitor.get("team") or {}

    return home, away


def get_venue(event):
    competitions = event.get("competitions") or []

    if not competitions:
        return "TBD"

    venue = competitions[0].get("venue") or {}
    return venue.get("fullName") or venue.get("name") or "TBD"


def get_broadcasts(event):
    competitions = event.get("competitions") or []

    if not competitions:
        return []

    broadcasts = competitions[0].get("broadcasts") or []
    flattened = []

    for broadcast in broadcasts:
        names = broadcast.get("names") or broadcast.get("name")

        if isinstance(names, list):
            flattened.extend(names)
        elif names:
            flattened.append(names)

    return flattened


def get_event_name(event):
    return event.get("name") or event.get("shortName") or "NFL Game"


def is_miami_dolphins(event):
    home, away = get_competitors(event)

    teams = [home or {}, away or {}]

    for team in teams:
        name = (team.get("displayName") or team.get("name") or "").lower()
        abbreviation = (team.get("abbreviation") or "").upper()

        if "miami dolphins" in name or abbreviation == "MIA":
            return True

    return False


def is_regular_season_event(event):
    season = event.get("season") or {}
    return str(season.get("type")) == str(REGULAR_SEASON_TYPE)


def is_postseason_event(event):
    season = event.get("season") or {}
    return str(season.get("type")) == str(POSTSEASON_TYPE)


def is_thursday_night_football(event):
    local_dt = get_event_local_datetime(event)

    if not local_dt or not is_regular_season_event(event):
        return False

    return local_dt.weekday() == 3


def is_sunday_night_football(event):
    local_dt = get_event_local_datetime(event)

    if not local_dt or not is_regular_season_event(event):
        return False

    return local_dt.weekday() == 6 and local_dt.hour >= 19


def is_monday_night_football(event):
    local_dt = get_event_local_datetime(event)

    if not local_dt or not is_regular_season_event(event):
        return False

    return local_dt.weekday() == 0


def is_thanksgiving(event):
    local_dt = get_event_local_datetime(event)

    if not local_dt:
        return False

    return local_dt.date() == get_thanksgiving_date(local_dt.year)


def is_black_friday(event):
    local_dt = get_event_local_datetime(event)

    if not local_dt:
        return False

    thanksgiving = get_thanksgiving_date(local_dt.year)
    return local_dt.date() == thanksgiving + timedelta(days=1)


def is_christmas(event):
    local_dt = get_event_local_datetime(event)

    if not local_dt:
        return False

    return local_dt.month == 12 and local_dt.day == 25


def is_super_bowl(event):
    name = get_event_name(event).lower()
    short_name = (event.get("shortName") or "").lower()

    if "super bowl" in name or "super bowl" in short_name:
        return True

    local_dt = get_event_local_datetime(event)

    if not local_dt:
        return False

    return is_postseason_event(event) and local_dt.month == 2


def get_marquee_categories(event):
    categories = []

    if is_thursday_night_football(event):
        categories.append("Thursday Night Football")

    if is_sunday_night_football(event):
        categories.append("Sunday Night Football")

    if is_monday_night_football(event):
        categories.append("Monday Night Football")

    if is_thanksgiving(event):
        categories.append("Thanksgiving")

    if is_black_friday(event):
        categories.append("Black Friday Game")

    if is_christmas(event):
        categories.append("Christmas")

    if is_postseason_event(event):
        categories.append("Playoffs")

    if is_super_bowl(event):
        categories.append("Super Bowl")

    return categories


def event_matches_filter(event, filter_name):
    if filter_name == "miami_dolphins":
        return is_miami_dolphins(event)

    if filter_name == "marquee":
        return len(get_marquee_categories(event)) > 0

    return False


def create_calendar_event(calendar_config, nfl_event):
    home, away = get_competitors(nfl_event)

    home_name = (home or {}).get("displayName") or "Home TBD"
    away_name = (away or {}).get("displayName") or "Away TBD"

    start_time = parse_event_datetime(nfl_event)

    if not start_time:
        start_time = datetime.now(timezone.utc) + timedelta(days=7)

    event_id = nfl_event.get("id", "unknown")
    status = ((nfl_event.get("status") or {}).get("type") or {}).get("description", "Scheduled")
    week = ((nfl_event.get("week") or {}).get("number")) or "TBD"
    venue = get_venue(nfl_event)
    broadcasts = get_broadcasts(nfl_event)
    categories = get_marquee_categories(nfl_event)

    event = Event()
    event.uid = f"nfl-{calendar_config['id']}-{event_id}@sports-calendar-hub"

    if calendar_config["id"] == "nfl-estelares" and categories:
        label = " / ".join(categories)
        event.name = f"{away_name} at {home_name} - {label}"
    else:
        event.name = f"{away_name} at {home_name} - {calendar_config['name']}"

    event.begin = start_time
    event.end = start_time + timedelta(hours=3, minutes=30)
    event.location = venue

    description_lines = [
        f"Calendar: {calendar_config['name']}",
        f"Game: {away_name} at {home_name}",
        f"Week: {week}",
        f"Status: {status}",
        f"Venue: {venue}",
    ]

    if categories:
        description_lines.append("Category: " + " / ".join(categories))

    if broadcasts:
        description_lines.append("Broadcast: " + ", ".join(broadcasts))

    description_lines.append("Source: ESPN NFL scoreboard")

    event.description = "\n".join(description_lines)

    return event


def create_fallback_event(calendar_config):
    event = Event()
    event.uid = f"nfl-{calendar_config['id']}-fallback@sports-calendar-hub"
    event.name = f"{calendar_config['name']} - next game pending confirmation"
    event.begin = datetime.now(timezone.utc) + timedelta(days=7)
    event.end = event.begin + timedelta(hours=3)
    event.description = (
        f"Calendar: {calendar_config['name']}\n"
        "Next game pending confirmation\n"
        "Source: ESPN NFL scoreboard"
    )
    event.location = "TBD"

    return event


def generate_nfl_calendar(calendar_config, all_events):
    calendar = Calendar()

    matched_events = []

    now = datetime.now(timezone.utc)

    for nfl_event in all_events:
        start_time = parse_event_datetime(nfl_event)

        if not start_time:
            continue

        if start_time < now - timedelta(hours=4):
            continue

        if event_matches_filter(nfl_event, calendar_config["filter"]):
            matched_events.append((start_time, nfl_event))

    matched_events.sort(key=lambda item: item[0])

    print("=" * 60)
    print("Calendar:", calendar_config["name"])
    print("Matched events:", len(matched_events))

    if matched_events:
        for start_time, nfl_event in matched_events:
            print(start_time.isoformat(), "-", get_event_name(nfl_event))
            calendar.events.add(create_calendar_event(calendar_config, nfl_event))
    else:
        calendar.events.add(create_fallback_event(calendar_config))

    output_path = OUTPUT_DIR / calendar_config["output"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        file.writelines(calendar.serialize_iter())

    print(f"Generated: {output_path}")


def main():
    cleanup_old_nfl_files()

    all_events = load_all_nfl_events()

    for calendar_config in CALENDARS:
        generate_nfl_calendar(calendar_config, all_events)


if __name__ == "__main__":
    main()
