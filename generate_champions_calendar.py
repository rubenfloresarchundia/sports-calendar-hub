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


def normalize_text(value):
    return str(value or "").strip().lower()


def is_pending_event(event):
    title = normalize_text(event.name)
    description = normalize_text(event.description)

    pending_terms = [
        "pendiente",
        "pending",
        "opponent: tbd",
        "opponent: unknown",
        "rival por definir",
        "next match pending",
        "next game pending",
        "por confirmar",
    ]

    combined_text = f"{title} {description}"

    return any(
        term in combined_text
        for term in pending_terms
    )


def is_f1_event(event):
    title = normalize_text(event.name)

    return title.startswith("f1")


def is_allowed_f1_event(event):
    title = normalize_text(event.name)

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


def is_tennis_event(event):
    uid = normalize_text(event.uid)
    description = normalize_text(event.description)

    return (
        uid.startswith("tennis-")
        or "player:" in description
    )


def get_tennis_round(event):
    description = str(event.description or "")

    for line in description.splitlines():
        normalized_line = line.strip()

        if normalized_line.lower().startswith("round:"):
            return normalized_line.split(
                ":",
                1,
            )[1].strip()

    return ""


def is_allowed_tennis_round(event):
    round_name = normalize_text(
        get_tennis_round(event)
    )

    allowed_round_terms = [
        "1/8",
        "round of 16",
        "round 16",
        "last 16",
        "octavos",
        "octavo",
        "1/4",
        "quarterfinal",
        "quarter-final",
        "quarter final",
        "cuartos",
        "cuarto",
        "1/2",
        "semifinal",
        "semi-final",
        "semi final",
        "semifinales",
        "final",
    ]

    return any(
        term in round_name
        for term in allowed_round_terms
    )


def simplify_f1_title(title):
    title = str(title or "").strip()

    if title.startswith("F1 Gran Premio de "):
        location = title.replace(
            "F1 Gran Premio de ",
            "",
            1,
        )

        return f"F1 - {location} (Carrera)"

    
