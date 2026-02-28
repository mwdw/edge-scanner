"""
Edge Scanner — Streamlit web app
Political market probability gaps between Polymarket and bookmakers.

Secrets required in Streamlit dashboard:
  APP_PASSWORD = "your-password"
  ODDS_API_KEY = "your-odds-api-key"
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from polymarket import fetch_political_markets, filter_markets
from oddsapi import fetch_all_political, fair_probabilities
from matcher import find_best_event, find_matching_outcome, find_poly_for_candidate

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Edge Scanner",
    page_icon="U0001f4e1",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password gate ─────────────────────────────────────────────────────────────
def _check_password() -> bool:
    expected = st.secrets.get("APP_PASSWORD", "")
    if not expected:
        return True
    if st.session_state.get("_auth"):
        return True
    st.markdown("## U0001f4e1 Edge Scanner")
    pw = st.text_input("Password", type="password", key="_pw_input")
    if st.button("Enter"):
        if pw == expected:
            st.session_state["_auth"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False

if not _check_password():
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Controls")
    min_delta = st.slider("Min edge (pp)", min_value=1, max_value=25, value=5, step=1) / 100
    min_liquidity = st.number_input(
        "Min Polymarket liquidity ($)", value=50_000, step=10_000, min_value=0
    )
    days_opts = {"7 days": 7, "14 days": 14, "30 days": 30, "60 days": 60, "90 days": 90, "Any": None}
    days_label = st.selectbox("Resolves within", list(days_opts.keys()), index=2)
    max_days = days_opts[days_label]
    direction = st.radio(
        "Direction filter",
        options=["Both", "Poly > Bookie (under-priced by bookie)", "Bookie > Poly (under-priced by Poly)"],
        index=0,
    )
    st.divider()
    do_refresh = st.button("U0001f504 Run scan", use_container_width=True)
    st.divider()
    st.markdown("**Data sources**")
    st.caption("U0001f7e2 Polymarket (public, no key needed)")
    odds_key = st.secrets.get("ODDS_API_KEY", "")
    if odds_key:
        st.caption("U0001f7e2 The Odds API — UK/EU/US bookmakers")
    else:
        st.caption("U0001f534 The Odds API — add ODDS_API_KEY in secrets")
    st.divider()
    st.caption("Cache: 30 min | Click 'Run scan' to force refresh")

# ── Core scan logic ───────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def _run_scan(odds_key: str, min_liq: float, max_days) -> tuple[list[dict], int, int, str]:
    """Returns (alerts, n_poly_markets, n_unmatched, timestamp)."""
    if not odds_key:
        return [], 0, 0, ""

    poly_all = fetch_political_markets()
    poly_mkts = filter_markets(poly_all, min_liquidity=min_liq)
    if max_days is not None:
        poly_mkts = [m for m in poly_mkts if m.get("days_to_end") is not None and 0 <= m["days_to_end"] <= max_days]
    odds_events = fetch_all_political(odds_key)

    alerts, n_unmatched = [], 0

    # Pass 1: h2h markets
    for pm in poly_mkts:
        event, match_score = find_best_event(pm, odds_events)
        if not event:
            n_unmatched += 1
            continue
        for bookmaker in event.get("bookmakers", []):
            bm_name = bookmaker["title"]
            for mkt in bookmaker.get("markets", []):
                if mkt["key"] != "h2h":
                    continue
                fair = fair_probabilities(mkt["outcomes"])
                for i, outcome in enumerate(pm["outcomes"]):
                    if i >= len(pm["probabilities"]):
                        continue
                    poly_prob = pm["probabilities"][i]
                    bm_out, dec_odds = find_matching_outcome(outcome, mkt["outcomes"])
                    if not bm_out or not dec_odds:
                        continue
                    bookie_prob = fair.get(bm_out, 0.0)
                    delta = poly_prob - bookie_prob
                    alerts.append({
                        "question": pm["question"],
                        "outcome": outcome,
                        "poly_prob": poly_prob,
                        "bookie_prob": bookie_prob,
                        "decimal_odds": dec_odds,
                        "delta": delta,
                        "bookmaker": bm_name,
                        "match_score": match_score,
                        "liquidity": pm["liquidity"],
                        "volume": pm["volume"],
                        "days_to_end": pm.get("days_to_end"),
                        "url": pm["url"],
                    })

    # Pass 2: outright markets
    for event in odds_events:
        for bookmaker in event.get("bookmakers", []):
            bm_name = bookmaker["title"]
            for mkt in bookmaker.get("markets", []):
                if mkt["key"] != "outrights":
                    continue
                fair = fair_probabilities(mkt["outcomes"])
                for bm_outcome in mkt["outcomes"]:
                    candidate = bm_outcome["name"]
                    dec_odds = bm_outcome["price"]
                    bookie_fair_prob = fair.get(candidate, 0.0)
                    poly_market, poly_prob = find_poly_for_candidate(candidate, poly_mkts)
                    if poly_market is None or poly_prob is None:
                        continue
                    delta = poly_prob - bookie_fair_prob
                    alerts.append({
                        "question": poly_market["question"],
                        "outcome": "Yes",
                        "poly_prob": poly_prob,
                        "bookie_prob": bookie_fair_prob,
                        "decimal_odds": dec_odds,
                        "delta": delta,
                        "bookmaker": bm_name,
                        "match_score": 0.9,
                        "liquidity": poly_market["liquidity"],
                        "volume": poly_market["volume"],
                        "days_to_end": poly_market.get("days_to_end"),
                        "url": poly_market["url"],
                    })

    alerts.sort(key=lambda x: abs(x["delta"]), reverse=True)
    seen, unique = set(), []
    for a in alerts:
        k = (a["question"], a["outcome"], a.get("bookmaker", ""))
        if k not in seen:
            seen.add(k)
            unique.append(a)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return unique, len(poly_mkts), n_unmatched, ts

# ── Main view ─────────────────────────────────────────────────────────────────
st.markdown("# U0001f4e1 Edge Scanner")
st.caption("Political market probability gaps between Polymarket and bookmakers")

if do_refresh:
    st.cache_data.clear()

if not odds_key:
    st.warning("Add your ODDS_API_KEY to Streamlit secrets to run live scans.")
    st.stop()

with st.spinner("Fetching markets and odds…"):
    alerts, n_poly, n_unmatched, scan_ts = _run_scan(odds_key, min_liquidity, max_days)

filtered = alerts
if "Poly > Bookie" in direction:
    filtered = [a for a in filtered if a["delta"] > 0]
elif "Bookie > Poly" in direction:
    filtered = [a for a in filtered if a["delta"] < 0]
filtered = [a for a in filtered if abs(a["delta"]) >= min_delta]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Poly markets", n_poly)
c2.metric("Edges found", len(filtered))
c3.metric("Min edge", f"{min_delta:.0%}")
c4.metric("Last scan", scan_ts or "—")
st.divider()

if not filtered:
    st.info(f"No edges ≥ {min_delta:.0%} found. Try lowering the threshold or adjusting filters.")
else:
    rows = []
    for a in filtered:
        dte = a.get("days_to_end")
        days_str = f"{dte}d" if dte is not None else "?"
        rows.append({
            "Market": a["question"][:60] + ("…" if len(a["question"]) > 60 else ""),
            "Resolves": days_str,
            "Outcome": a["outcome"],
            "Poly %": round(a["poly_prob"] * 100, 1),
            "Bookie %": round(a["bookie_prob"] * 100, 1),
            "Dec. odds": round(a["decimal_odds"], 2),
            "Edge (pp)": round(a["delta"] * 100, 1),
            "Bookmaker": a["bookmaker"],
            "Liquidity": f"${a['liquidity']:,.0f}",
            "URL": a["url"],
        })
    df = pd.DataFrame(rows)

    def _colour_edge(val):
        colour = "#2ecc71" if val > 0 else "#e74c3c"
        return f"color: {colour}; font-weight: bold"

    styled = (
        df.drop(columns=["URL"])
        .style
        .applymap(_colour_edge, subset=["Edge (pp)"])
        .format({"Poly %": "{:.1f}%", "Bookie %": "{:.1f}%"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=400)
    st.divider()

    st.subheader("Detail view")
    for i, a in enumerate(filtered):
        dte = a.get("days_to_end")
        days_str = f"{dte} days" if dte is not None else "unknown"
        edge_sign = "▲" if a["delta"] > 0 else "▼"
        edge_label = f"{edge_sign} {abs(a['delta'])*100:.1f}pp"
        direction_label = "POLY > BOOKIE" if a["delta"] > 0 else "BOOKIE > POLY"
        with st.expander(f"#{i+1} {a['question'][:68]} — {edge_label}"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Polymarket", f"{a['poly_prob']:.1%}")
            col2.metric("Bookie (fair)", f"{a['bookie_prob']:.1%}")
            col3.metric("Edge", edge_label)
            col4.metric("Resolves in", days_str)
            st.markdown(
                f"**Outcome:** {a['outcome']} \n"
                f"**Direction:** {direction_label} \n"
                f"**Bookmaker:** {a['bookmaker']} @ {a['decimal_odds']} \n"
                f"**Poly liquidity:** ${a['liquidity']:,.0f} | **Volume:** ${a['volume']:,.0f} \n"
                f"**Match confidence:** {a['match_score']:.0%}"
            )
            st.link_button("Open on Polymarket →", a["url"])
