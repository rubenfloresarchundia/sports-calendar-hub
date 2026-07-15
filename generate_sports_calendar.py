from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ics import Calendar


ROOT_DIR = Path(__file__).parent

SPORTS_OUTPUT_FILE = (
    ROOT_DIR
    / "docs"
    / "sports"
    / "sports-calendar.ics"
)

CDMX_TIMEZONE = ZoneInfo("America/Mexico_City")

SOURCE_CALENDARS = [
    "docs/f1/formula-1.ics",

    "docs/tennis/sinner.ics",
    "docs/tennis/alcaraz.ics",
    "docs/tennis/djokovic.ics",

    "docs/nfl/miami-dolphins.ics",
    "docs/nfl/estelares.ics",

    "docs/football/real-madrid-laliga.ics",
    "docs/football/real-madrid-champions.ics",
    "docs/football/champions-global.ics",
]


def load_calendar(path):
    filepath = ROOT_DIR / path

    if not filepath.exists():
        print("Missing:", filepath)
        return None

    with filepath.open(
        "r",
        encoding="utf-8",
    ) as file:
        return Calendar(file.read())


def get_week_window():
    now_utc = datetime.now(timezone.utc)
    now_cdmx = now_utc.astimezone(CDMX_TIMEZONE)

    days_until_monday = 7 - now_cdmx.weekday()

    next_monday_cdmx = (
        now_cdmx
        + timedelta(days=days_until_monday)
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    next_monday_utc = next_monday_cdmx
