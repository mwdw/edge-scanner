"""Betfair Exchange API client — political markets.

Secrets required (add to Streamlit dashboard):
    BETFAIR_APP_KEY  = "your-app-key"
    BETFAIR_USERNAME = "your-betfair-username"
    BETFAIR_PASSWORD = "your-betfair-password"

Free developer access: https://developer.betfair.com/
"""
import requests
from typing import Optional

_LOGIN_URL = "https://identitysso.betfair.com/api/login"
_API_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"
_POLITICS_TYPE_ID = "2378961"


def _login(username: str, password: str, app_key: str) -> Optional[str]:
    """Non-interactive login — returns session token or None."""
    try:
        r = requests.post(
            _LOGIN_URL,
            data={"username": username, "password": password},
            headers={
                "X-Application": app_key,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=10,
        )
        data = r.json()
        if data.get("status") == "SUCCESS":
            return data["token"]
    except Exception:
        pass
    return None


def _rpc(method: str, params: dict, session: str, app_key: str):
    """Single JSON-RPC call to Betfair Exchange API."""
    try:
        r = requests.post(
            _API_URL,
            json=[{
                "jsonrpc": "2.0",
                "method": f"SportsAPING/v1.0/{method}",
                "params": params,
                "id": 1,
            }],
            headers={
                "X-Authentication": session,
                "X-Application": app_key,
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        return r.json()[0].get("result", [])
    except Exception:
        return []


def fetch_political_events(app_key: str, username: str, password: str) -> list[dict]:
    """Fetch Betfair Exchange political markets normalised to The Odds API format.

    Returns a list of event dicts compatible with:
      - matcher.find_best_event()      (Pass 1 — direct h2h matching)
      - matcher.find_poly_for_candidate() (Pass 2 — outright runner matching)

    Each dict has the shape:
      {
        "sport_title": "<market name e.g. 'Next UK Prime Minister'>",
        "home_team":   "<event name e.g. 'UK Politics 2026'>",
        "away_team":   "",
        "bookmakers":  [{"key": "betfair_exchange",
                         "title": "Betfair Exchange",
                         "markets": [{"key": "outrights",
                                      "outcomes": [{"name": ..., "price": ...}]}]}]
      }
    """
    session = _login(username, password, app_key)
    if not session:
        return []

    # 1. Market catalogue — metadata + runner names
    catalogue = _rpc("listMarketCatalogue", {
        "filter": {"eventTypeIds": [_POLITICS_TYPE_ID]},
        "marketProjection": ["EVENT", "RUNNER_DESCRIPTION"],
        "maxResults": 200,
        "sort": "FIRST_TO_START",
    }, session, app_key)

    if not catalogue:
        return []

    market_ids = [m["marketId"] for m in catalogue]

    # 2. Best back prices for every runner
    books_raw = _rpc("listMarketBook", {
        "marketIds": market_ids,
        "priceProjection": {"priceData": ["EX_BEST_OFFERS"]},
    }, session, app_key)

    book_by_id = {b["marketId"]: b for b in (books_raw or [])}

    events = []
    for market in catalogue:
        mid = market["marketId"]
        book = book_by_id.get(mid, {})
        runners_meta = {
            r["selectionId"]: r["runnerName"]
            for r in market.get("runners", [])
        }

        outcomes = []
        for runner in book.get("runners", []):
            sid = runner["selectionId"]
            name = runners_meta.get(sid, str(sid))
            backs = runner.get("ex", {}).get("availableToBack", [])
            if backs and backs[0].get("price"):
                outcomes.append({"name": name, "price": backs[0]["price"]})

        # Skip suspended / illiquid markets
        if len(outcomes) < 2:
            continue

        event_name = market.get("event", {}).get("name", "")
        market_name = market.get("marketName", "")

        events.append({
            "sport_title": market_name,
            "home_team": event_name,
            "away_team": "",
            "title": f"{event_name} \u2014 {market_name}",
            "bookmakers": [{
                "key": "betfair_exchange",
                "title": "Betfair Exchange",
                "markets": [{"key": "outrights", "outcomes": outcomes}],
            }],
        })

    return events
