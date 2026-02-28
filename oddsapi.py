"""The Odds API client — UK bookmakers.
Free tier: 500 req/month  |  https://the-odds-api.com
"""
import requests

BASE = "https://api.the-odds-api.com/v4"

POLITICAL_SPORT_KEYS = [
    "politics",
    "politics_us_presidential_election_winner",
    "politics_us_senate",
    "politics_us_house",
]


def fetch_sports(api_key):
    try:
        r = requests.get(f"{BASE}/sports", params={"apiKey": api_key, "all": "true"}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def fetch_odds(api_key, sport_key, regions="uk,us,eu"):
    try:
        r = requests.get(
            f"{BASE}/sports/{sport_key}/odds",
            params={"apiKey": api_key, "regions": regions, "markets": "h2h", "oddsFormat": "decimal"},
            timeout=15,
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def fetch_all_political(api_key, regions="uk,us,eu"):
    events = []
    for key in POLITICAL_SPORT_KEYS:
        events.extend(fetch_odds(api_key, key, regions))
    return events


def fair_probabilities(outcomes):
    """Strip overround and return fair implied probs."""
    raw   = {o["name"]: (1.0 / o["price"] if o["price"] > 1 else 0) for o in outcomes}
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()} if total > 0 else raw
