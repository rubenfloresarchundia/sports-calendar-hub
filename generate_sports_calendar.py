from datetime import datetime, timezone, timedelta
from pathlib import Path

from ics import Calendar


ROOT_DIR = Path(__file__).parent

SPORTS_OUTPUT_FILE = (
    ROOT_DIR
    / "docs"
    / "sports"
    / "sports-calendar.ics"
)

SOURCE_CALENDARS = [
    "docs/f1/formula-1.ics",

    "docs/tennis/sinner.ics",
    "docs/tennis/alcaraz.ics",
    "docs/tennis/djokovic.ics",

    "docs/nfl/miami-dolphins.ics",
    "docs/nfl/estelares.ics",

    "docs/football/real-madrid-laliga.ics",
    "docs/football/real-madrid-champions.ics",
]


def load_calendar(path):
    filepath = ROOT_DIR / path

    if not filepath.exists():
        print("Missing:", filepath)
        return None

    with open(
        filepath,
        "r",
        encoding="utf-8",
    ) as file:
        return Calendar(file.read())


def get_events_for_this_week(calendar):
    now = datetime.now(timezone.utc)

    days_until_monday = 7 - now.weekday()

    if days_until_monday == 0:
        days_until_monday = 7

    next_monday = (
        now + timedelta(days=days_until_monday)
    )

    events = []

    for event in calendar.events:

        event_date = event.begin.datetime

        if (
            event_date >= now
            and event_date < next_monday
        ):
            events.append(event)

    events.sort(
        key=lambda event: event.begin.datetime
    )

    return events


def generate_sports_calendar():
    sports_calendar = Calendar()

    total_events = 0

    for calendar_path in SOURCE_CALENDARS:

        calendar = load_calendar(
            calendar_path
        )

        if not calendar:
            continue

        events = get_events_for_this_week(
            calendar
        )

        for event in events:

            sports_calendar.events.add(
                event
            )

            total_events += 1

            print(
                "Added:",
                event.name,
            )

    SPORTS_OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        SPORTS_OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(
            sports_calendar.serialize_iter()
        )

    print(
        "Events:",
        total_events
    )

    print(
        "Generated:",
        SPORTS_OUTPUT_FILE,
    )


if __name__ == "__main__":
    generate_sports_calendar()
