import json

import requests


ESPN_LIGA_MX_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/soccer/mex.1/scoreboard"
)

DATE_RANGE = "20260701-20270601"


def get_team_name(competitor):
    team = competitor.get("team") or {}

    return (
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("name")
        or team.get("abbreviation")
        or "TBD"
    )


def is_america_name(name):
    normalized_name = str(name or "").strip().lower()

    america_names = {
        "club américa",
        "club america",
        "cf américa",
        "cf america",
        "américa",
        "america",
    }

    return normalized_name in america_names


def main():
    params = {
        "dates": DATE_RANGE,
        "limit": 1000,
    }

    response = requests.get(
        ESPN_LIGA_MX_URL,
        params=params,
        timeout=30,
    )

    print("ESPN Liga MX status:", response.status_code)

    if response.status_code != 200:
        print(response.text[:2000])
        raise RuntimeError(
            f"ESPN Liga MX error: {response.status_code}"
        )

    data = response.json()
    events = data.get("events", [])

    print("Liga MX events returned:", len(events))
    print("=" * 80)

    america_events = []

    for event in events:
        competitions = event.get("competitions") or []

        if not competitions:
            continue

        competition = competitions[0]
        competitors = competition.get("competitors") or []

        team_names = [
            get_team_name(competitor)
            for competitor in competitors
        ]

        if not any(
            is_america_name(team_name)
            for team_name in team_names
        ):
            continue

        america_events.append(event)

        print("AMERICA EVENT FOUND")
        print("Event ID:", event.get("id"))
        print("Date:", event.get("date"))
        print("Name:", event.get("name"))
        print("Short name:", event.get("shortName"))
        print("Teams:", team_names)
        print("Event week:", event.get("week"))
        print("Event matchday:", event.get("matchday"))
        print("Season:", event.get("season"))
        print("Competition matchday:", competition.get("matchday"))
        print("Competition week:", competition.get("week"))
        print("Alt game note:", competition.get("altGameNote"))
        print("Notes:", competition.get("notes"))
        print("Status:", competition.get("status"))

        print("RAW EVENT:")
        print(
            json.dumps(
                event,
                indent=2,
                ensure_ascii=False,
            )[:12000]
        )

        print("=" * 80)

        if len(america_events) >= 3:
            break

    print("America events inspected:", len(america_events))

    if not america_events:
        print(
            "No Club America events were found "
            "with the current team-name rules."
        )


if __name__ == "__main__":
    main()
