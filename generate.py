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

    all_fixtures = []
    page = 1

    while True:
        params = {
            "include": "round,tournament,tournament.country",
            "pageSize": 100,
            "pageNo": page,
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)

        print(f"Date range API status ({tour}, page {page}):", response.status_code)
        print(f"Date range: {start_text} to {end_text}")

        if response.status_code != 200:
            print(response.text[:1000])
            break

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
            break

    print(f"Total fixtures returned for {tour}: {len(all_fixtures)}")
    return all_fixtures


def fixture_has_player
