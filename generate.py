from pathlib import Path
from datetime import datetime, timedelta, timezone

import yaml
from ics import Calendar, Event


ROOT_DIR = Path(__file__).parent
CONFIG_PATH = ROOT_DIR / "config" / "tennis_players.yaml"
OUTPUT_DIR = ROOT_DIR / "docs"


def load_tennis_players():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return data.get("players", [])


def create_placeholder_event(player):
    player_name = player["full_name"]

    event = Event()
    event.name = f"{player_name} - next match pending confirmation"
    event.begin = datetime.now(timezone.utc) + timedelta(days=7)
    event.end = event.begin + timedelta(hours=2)
    event.description = (
        f"Player: {player_name}\n"
        f"Tour: {player['tour'].upper()}\n"
        "Opponent: TBD\n"
        "Tournament: TBD\n"
        "Round: TBD\n"
        "Court: TBD\n"
        "Live score: https://www.atptour.com/en/scores/current"
    )
    event.location = "TBD"

    return event


def generate_player_calendar(player):
    calendar = Calendar()
    event = create_placeholder_event(player)
    calendar.events.add(event)

    output_path = OUTPUT_DIR / player["output"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        file.writelines(calendar.serialize_iter())

    print(f"Generated: {output_path}")


def main():
    players = load_tennis_players()

    for player in players:
        generate_player_calendar(player)


if __name__ == "__main__":
    main()
