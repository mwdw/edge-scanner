"""Polymarket Gamma API client."""
import json
import requests
from datetime import datetime, timezone

POLY_API_BASE = "https://gamma-api.polymarket.com"


def fetch_political_markets(limit=200):
    url = f"{POLY_API_BASE}/markets"
    params = {"active": "true", "closed": "false", "limit": limit, "tag_slug": "politics"}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()
    except Exception:
        return []

    now = datetime.now(timezone.utc)
    markets = []
    for m in raw:
        try:
            outcomes = m.get("outcomes", [])
            prices = m.get("outcomePrices", [])
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if isinstance(prices, str):
                prices = json.loads(prices)
            if not outcomes or not prices or len(outcomes) != len(prices):
                continue

            # Parse end date
            end_date_raw = m.get("endDate") or m.get("end_date_iso") or m.get("endDateIso")
            end_date = None
            days_to_end = None
            if end_date_raw:
                try:
                    dt = datetime.fromisoformat(end_date_raw.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    end_date = dt.isoformat()
                    days_to_end = (dt - now).days
                except Exception:
                    pass

            markets.append({
                "id": m.get("id"),
                "question": m.get("question", "").strip(),
                "outcomes": outcomes,
                "probabilities": [float(p) for p in prices],
                "liquidity": float(m.get("liquidity") or 0),
                "volume": float(m.get("volume") or 0),
                "end_date": end_date,
                "days_to_end": days_to_end,
                "url": f"https://polymarket.com/event/{m.get('slug', '')}",
            })
        except Exception:
            continue
    return markets


def filter_markets(markets, min_liquidity=50_000, max_days=None):
    """Filter markets by liquidity and optional days-to-resolution cap.

    Args:
        min_liquidity: Minimum current liquidity (strict AND gate).
        max_days: Only include markets resolving within this many days.
                  None = no date filter.
    """
    result = []
    for m in markets:
        if m["liquidity"] < min_liquidity:
            continue
        if max_days is not None:
            d = m.get("days_to_end")
            if d is None or d < 0 or d > max_days:
                continue
        result.append(m)
    return result
    
