"""The Odds API client — UK bookmakers.
Free tier: 500 req/month  |  https://the-odds-api.com
"""
import requests

BASE = "https://api.the-odds-api.com/v4"

# Only sport keys with currently active markets
POLITICAL_SPORT_KEYS = [
    "politics_us_presidential_election_winner",
]


def fetch_sports(api_key):
    try:
        r = requests.get(f"{BASE}/sports", params={"apiKey": api_key, "all": "true"}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def fetch_odds(api_key, sport_key, regions="uk,us,eu", market_type="outrights"):
    try:
        r = requests.get(
            f"{BASE}/sports/{sport_key}/odds",
            params={
                "apiKey": api_key,
                "regions": regions,
                "markets": market_type,
                "oddsFormat": "decimal",
            },
            timeout=15,
        )
        if r.status_code in (400, 404, 422):
            return []
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_all_political(api_key, regions="uk,us,eu"):
    # Dynamically discover all active political sport keys
    all_sports = fetch_sports(api_key)
    political_keys = [s["key"] for s in all_sports if s.get("group") == "Politics" and s.get("active")]
    if not political_keys:
        political_keys = POLITICAL_SPORT_KEYS  # fallback if discovery fails
    events = []
    for key in political_keys:
        events.extend(fetch_odds(api_key, key, regions, market_type="outrights"))
    return events


def fair_probabilities(outcomes):
    """Strip overround and return fair implied probs."""
    raw = {o["name"]: (1.0 / o["price"] if o["price"] > 1 else 0) for o in outcomes}
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()} if total > 0 else raw
