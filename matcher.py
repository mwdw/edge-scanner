"""Fuzzy market matching — stdlib difflib only."""
from difflib import SequenceMatcher


def _sim(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _clean(text):
    """Lowercase, remove punctuation noise."""
    return text.lower().replace(".", "").replace(",", "").replace("  ", " ").strip()


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


def find_poly_for_candidate(candidate_name, poly_markets, threshold=0.40):
    """For a bookmaker outright candidate, find the matching Polymarket binary Yes/No market.

    Strategy: check whether all significant parts of the candidate's name appear
    in the Polymarket question text, then also score with fuzzy similarity.

    Returns (poly_market, yes_probability) or (None, None).
    """
    candidate_clean = _clean(candidate_name)
    # Significant name tokens (skip single chars like middle initials after clean)
    name_parts = [w for w in candidate_clean.split() if len(w) > 1]

    best_market, best_prob, best_score = None, None, 0.0

    for pm in poly_markets:
        q_clean = _clean(pm["question"])

        # Fraction of candidate name parts found verbatim in the question
        parts_hit = sum(1 for p in name_parts if p in q_clean)
        part_ratio = parts_hit / len(name_parts) if name_parts else 0.0

        # Fuzzy similarity between candidate name and question
        fuzz = _sim(candidate_clean, q_clean)

        score = max(fuzz, part_ratio)

        if score > best_score:
            outcomes = pm.get("outcomes", [])
            probs = pm.get("probabilities", [])
            # Must be a binary Yes/No market
            if "Yes" in outcomes:
                yes_idx = outcomes.index("Yes")
                if yes_idx < len(probs):
                    best_score = score
                    best_market = pm
                    best_prob = probs[yes_idx]

    if best_score >= threshold and best_market is not None:
        return best_market, best_prob
    return None, None
