"""Polymarket Gamma API client."""
import json
import requests

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
            markets.append({
                "id": m.get("id"),
                "question": m.get("question", "").strip(),
                "outcomes": outcomes,
                "probabilities": [float(p) for p in prices],
                "liquidity": float(m.get("liquidity") or 0),
                "volume": float(m.get("volume") or 0),
                "url": f"https://polymarket.com/event/{m.get('slug', '')}",
            })
        except Exception:
            continue
    return markets


def filter_markets(markets, min_liquidity=10_000, min_volume=0):
    """Filter to markets meeting BOTH liquidity and volume thresholds.

    Uses AND logic so a high-volume but illiquid market (thin book, stale)
    cannot slip through the liquidity gate.
    """
    return [
        m for m in markets
        if m["liquidity"] >= min_liquidity
        and (min_volume == 0 or m["volume"] >= min_volume)
    ]
