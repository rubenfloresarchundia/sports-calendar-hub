import json

import requests


ESPN_MEXICO_SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/soccer/all/teams/203/schedule"
)


def main():
    params = {
        "season": 2026,
        "region": "us",
        "lang": "en",
    }

    response = requests.get(
        ESPN_MEXICO_SCHEDULE_URL,
        params=params,
        timeout=30,
    )

    print(
        "ESPN Mexico status:",
        response.status_code,
        flush=True,
    )

    print(
        "Final URL:",
        response.url,
        flush=True,
    )

    if response.status_code != 200:
        print(
            response.text[:3000],
            flush=True,
        )

        raise RuntimeError(
            f"ESPN Mexico error: "
            f"{response.status_code}"
        )

    data = response.json()

    print(
        "Top-level keys:",
        list(data.keys()),
        flush=True,
    )

    events = data.get("events", [])

    print(
        "Mexico events returned:",
        len(events),
        flush=True,
    )

    for event in events[:3]:
        print("=" * 80)
        print("MEXICO EVENT")
        print("ID:", event.get("id"))
        print("Date:", event.get("date"))
        print("Name:", event.get("name"))
        print("Short name:", event.get("shortName"))
        print("Season:", event.get("season"))

        competitions = (
            event.get("competitions")
            or []
        )

        if competitions:
            competition = competitions[0]

            print(
                "Competition type:",
                competition.get("type"),
            )

            print(
                "Alt game note:",
                competition.get(
                    "altGameNote"
                ),
            )

            print(
                "Notes:",
                competition.get("notes"),
            )

            competitors = (
                competition.get("competitors")
                or []
            )

            team_names = []

            for competitor in competitors:
                team = competitor.get("team") or {}

                team_name = (
                    team.get("displayName")
                    or team.get(
                        "shortDisplayName"
                    )
                    or team.get("name")
                    or team.get("abbreviation")
                    or "TBD"
                )

                team_names.append(team_name)

            print("Teams:", team_names)

        print("RAW EVENT:")
        print(
            json.dumps(
                event,
                indent=2,
                ensure_ascii=False,
            )[:10000]
        )

    if not events:
        print(
            "No Mexico events were returned.",
            flush=True,
        )


if __name__ == "__main__":
    main()
