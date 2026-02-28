"""Fuzzy market matching — stdlib difflib only."""
from difflib import SequenceMatcher


def _sim(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _event_text(event):
    return " ".join(filter(None, [
        event.get("sport_title", ""),
        event.get("home_team", ""),
        event.get("away_team", ""),
    ]))


def find_best_event(poly_market, odds_events, threshold=0.28):
    question = poly_market["question"]
    best, best_score = None, 0.0
    for event in odds_events:
        text = _event_text(event)
        score = max(
            _sim(question, text),
            _sim(question, event.get("home_team", "")),
            _sim(question, event.get("away_team", "")),
            _sim(question, event.get("sport_title", "")),
        )
        if any(o.lower() in text.lower() for o in poly_market.get("outcomes", []) if len(o) > 3):
            score += 0.12
        if score > best_score:
            best_score, best = score, event
    return (best, best_score) if best_score >= threshold else (None, 0.0)


def find_matching_outcome(poly_outcome, bm_outcomes, threshold=0.38):
    best_name, best_score = None, 0.0
    for o in bm_outcomes:
        s = _sim(poly_outcome, o["name"])
        if s > best_score:
            best_score, best_name = s, o["name"]
    if best_score >= threshold or poly_outcome.lower() in ("yes", "no"):
        if best_name:
            price = next((o["price"] for o in bm_outcomes if o["name"] == best_name), None)
            return best_name, price
    return None, None
