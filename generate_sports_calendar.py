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

    next_monday_utc = next_monday_cdmx.astimezone(
        timezone.utc
    )

    print(
        "Week starts now:",
        now_cdmx.isoformat(),
    )
    print(
        "Week ends:",
        next_monday_cdmx.isoformat(),
    )

    return now_utc, next_monday_utc


def is_pending_event(event):
    title = str(event.name or "").strip().lower()

    pending_terms = [
        "pendiente",
        "pending",
        "tbd",
        "por confirmar",
        "rival por definir",
    ]

    return any(
        term in title
        for term in pending_terms
    )


def is_f1_event(event):
    title = str(event.name or "").strip().lower()

    return title.startswith("f1")


def is_allowed_f1_event(event):
    title = str(event.name or "").strip().lower()

    if "qualy" in title:
        return False

    if "qualifying" in title:
        return False

    if "practice" in title:
        return False

    if "práctica" in title:
        return False

    if "sprint" in title:
        return True

    if "gran premio" in title:
        return True

    if "(carrera)" in title:
        return True

    return False


def simplify_f1_title(title):
    title = str(title or "").strip()

    if title.startswith("F1 Gran Premio de "):
        location = title.replace(
            "F1 Gran Premio de ",
            "",
            1,
        )

        return f"F1 - {location} (Carrera)"

    if title.startswith("F1 Sprint GP de "):
        location = title.replace(
            "F1 Sprint GP de ",
            "",
            1,
        )

        return f"F1 - {location} (Sprint)"

    return title


def simplify_football_title(title):
    title = str(title or "").strip()

    if title.endswith(" - LaLiga"):
        title = title.removesuffix(" - LaLiga")
        return f"{title} (Liga)"

    if title.endswith(" - Champions"):
        title = title.removesuffix(" - Champions")
        return f"{title} (Champ)"

    if title.endswith(" - Champions League"):
        title = title.removesuffix(
            " - Champions League"
        )
        return f"{title} (Champ)"

    return title


def simplify_event_title(event):
    title = str(event.name or "").strip()

    if is_f1_event(event):
        return simplify_f1_title(title)

    return simplify_football_title(title)


def should_include_event(
    event,
    window_start,
    window_end,
):
    event_datetime = event.begin.datetime

    if event_datetime.tzinfo is None:
        event_datetime = event_datetime.replace(
            tzinfo=timezone.utc
        )

    if not (
        window_start
        <= event_datetime
        < window_end
    ):
        return False

    if is_pending_event(event):
        print(
            "Skipped pending:",
            event.name,
        )
        return False

    if is_f1_event(event):
        if not is_allowed_f1_event(event):
            print(
                "Skipped F1 session:",
                event.name,
            )
            return False

    return True


def get_events_for_this_week(
    calendar,
    window_start,
    window_end,
):
    week_events = []

    for event in calendar.events:
        if should_include_event(
            event,
            window_start,
            window_end,
        ):
            week_events.append(event)

    week_events.sort(
        key=lambda event: event.begin.datetime
    )

    return week_events


def add_event_to_sports_calendar(
    sports_calendar,
    event,
    existing_uids,
):
    event_uid = str(event.uid or "")

    if event_uid and event_uid in existing_uids:
        print(
            "Skipped duplicate:",
            event.name,
        )
        return False

    original_title = event.name
    event.name = simplify_event_title(event)

    sports_calendar.events.add(event)

    if event_uid:
        existing_uids.add(event_uid)

    if original_title != event.name:
        print(
            "Added:",
            original_title,
            "->",
            event.name,
        )
    else:
        print(
            "Added:",
            event.name,
        )

    return True


def generate_sports_calendar():
    sports_calendar = Calendar()
    existing_uids = set()

    window_start, window_end = get_week_window()

    total_events = 0

    for calendar_path in SOURCE_CALENDARS:
        print("=" * 60)
        print("Reading:", calendar_path)

        calendar = load_calendar(calendar_path)

        if not calendar:
            continue

        events = get_events_for_this_week(
            calendar,
            window_start,
            window_end,
        )

        for event in events:
            was_added = add_event_to_sports_calendar(
                sports_calendar,
                event,
                existing_uids,
            )

            if was_added:
                total_events += 1

    SPORTS_OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SPORTS_OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.writelines(
            sports_calendar.serialize_iter()
        )

    print("=" * 60)
    print("Events:", total_events)
    print("Generated:", SPORTS_OUTPUT_FILE)


if __name__ == "__main__":
    generate_sports_calendar()
