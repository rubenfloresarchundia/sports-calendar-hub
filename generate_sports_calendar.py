from datetime import datetime, timezone
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


def get_next_event(calendar):
    now = datetime.now(timezone.utc)

    future_events = [
        event
        for event in calendar.events
        if event.begin.datetime > now
    ]

    if not future_events:
        return None

    future_events.sort(
        key=lambda event: event.begin.datetime
    )

    return future_events[0]


def generate_sports_calendar():
    sports_calendar = Calendar()

    for calendar_path in SOURCE_CALENDARS:
        calendar = load_calendar(calendar_path)

        if not calendar:
            continue

        next_event = get_next_event(calendar)

        if next_event:
            sports_calendar.events.add(
                next_event
            )

            print(
                "Added:",
                next_event.name,
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
        len(sports_calendar.events)
    )

    print(
        "Generated:",
        SPORTS_OUTPUT_FILE,
    )


if __name__ == "__main__":
    generate_sports_calendar()
