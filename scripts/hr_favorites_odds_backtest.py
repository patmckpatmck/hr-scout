"""
HR Favorites Backtest — REAL ODDS EDITION (v2: consensus US books)
===================================================================
v2 changes after testing against live cache:
  - FanDuel/DraftKings HR props aren't in the historical feed; coverage is
    BetMGM, BetRivers, Caesars, BetOnline. We now pull ALL US books and use
    a consensus (average implied probability) per player.
  - Favorite per game = highest consensus implied prob; qualifies if the
    consensus is shorter than +300.
  - P/L is simulated at the BEST available price across books (line-shopper
    assumption). Same credit cost as before (10/game).
  - Snapshot moved to 15 min before first pitch (props confirmed posted).
  - Cache keys changed (odds_us_*) so stale FanDuel-only files are ignored.

Requires:  pip install requests pandas   (MLB-StatsAPI already installed)
Setup:     paste key into API_KEY below or `export ODDS_API_KEY=...`
Run:       python scripts/hr_favorites_odds_backtest.py
Output:    analysis/hr_favorites_odds_daily.csv, analysis/hr_favorites_odds_picks.csv
"""

import json
import os
import time
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import statsapi

# ----------------------------- CONFIG ---------------------------------
# API key comes ONLY from the environment — never hardcode it (this file is
# committed). Run with:  export ODDS_API_KEY=... && python scripts/hr_favorites_odds_backtest.py
API_KEY = os.environ.get("ODDS_API_KEY", "")
SEASON_START = date(2026, 3, 26)
SEASON_END = date.today() - timedelta(days=1)
MARKET = "batter_home_runs"
MAX_AMERICAN_ODDS = 300               # consensus must be shorter than +300
SNAPSHOT_MINUTES_BEFORE = 15          # props confirmed posted by T-15min
STAKE = 10.0                          # flat bet size for ROI sim
CACHE_DIR = Path("odds_cache")
SLEEP = 0.3
BASE = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb"
# -----------------------------------------------------------------------

QUALIFY_IMPLIED = 100 / (MAX_AMERICAN_ODDS + 100)   # +300 -> 0.25

CACHE_DIR.mkdir(exist_ok=True)
session = requests.Session()


def cached_get(url: str, params: dict, cache_key: str):
    """GET with disk caching + retries so interrupted runs never re-spend credits."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    for attempt in range(4):
        try:
            resp = session.get(url, params=params, timeout=30)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            wait = 5 * (attempt + 1)
            print(f"  network hiccup ({e.__class__.__name__}), "
                  f"retrying in {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 401:
            raise SystemExit("401 Unauthorized — check API_KEY / plan tier.")
        if resp.status_code == 429:
            print("  rate limited, sleeping 60s...")
            time.sleep(60)
            continue
        resp.raise_for_status()
        remaining = resp.headers.get("x-requests-remaining")
        if remaining:
            cached_get.remaining = remaining
        data = resp.json()
        cache_file.write_text(json.dumps(data))
        time.sleep(SLEEP)
        return data
    raise SystemExit(f"Giving up after 4 attempts: {url}")


cached_get.remaining = "?"


def norm_name(name: str) -> str:
    """Normalize player names for matching across the two APIs."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", "").replace(",", "")
    for suffix in (" jr", " sr", " ii", " iii"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s.strip()


def american_implied(price: int) -> float:
    return 100 / (price + 100) if price > 0 else -price / (-price + 100)


def american_profit(price: int, stake: float) -> float:
    return stake * price / 100 if price > 0 else stake * 100 / -price


def get_events_for_day(d: date):
    """Historical events list as of noon ET that day."""
    snapshot = f"{d.isoformat()}T16:00:00Z"  # ~noon ET
    data = cached_get(
        f"{BASE}/events",
        {"apiKey": API_KEY, "date": snapshot},
        f"events_{d.isoformat()}",
    )
    events = data.get("data", [])
    return [e for e in events if e.get("commence_time", "").split("T")[0]
            in (d.isoformat(), (d + timedelta(days=1)).isoformat())]


def get_hr_odds_for_event(event: dict):
    """All US books' Over 0.5 HR lines shortly before first pitch.
    Returns {player_name: [price, price, ...]} across books."""
    commence = datetime.fromisoformat(
        event["commence_time"].replace("Z", "+00:00"))
    snap = commence - timedelta(minutes=SNAPSHOT_MINUTES_BEFORE)
    snap_str = snap.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        data = cached_get(
            f"{BASE}/events/{event['id']}/odds",
            {
                "apiKey": API_KEY,
                "regions": "us",
                "markets": MARKET,
                "oddsFormat": "american",
                "date": snap_str,
            },
            f"odds_us_{event['id']}",
        )
    except requests.HTTPError as e:
        print(f"  odds fetch failed {event['id']}: {e}")
        return {}

    prices = defaultdict(list)
    for book in (data.get("data") or {}).get("bookmakers", []):
        for market in book.get("markets", []):
            if market.get("key") != MARKET:
                continue
            for o in market.get("outcomes", []):
                if o.get("name") != "Over":
                    continue
                if o.get("point") not in (None, 0.5):
                    continue
                prices[o.get("description", "")].append(int(o["price"]))
    return prices


def pick_favorite(prices: dict):
    """Return (player, consensus_implied, best_price) for the game's
    shortest consensus price, or None if nobody is sub-+300."""
    best = None
    for player, plist in prices.items():
        consensus = sum(american_implied(p) for p in plist) / len(plist)
        if best is None or consensus > best[1]:
            best = (player, consensus, max(plist, key=lambda p: american_profit(p, 1)))
    if best and best[1] >= QUALIFY_IMPLIED:
        return best
    return None


def build_hr_results(d: date):
    """Set of normalized names of every player who homered on date d."""
    homered = set()
    try:
        sched = statsapi.schedule(date=d.strftime("%m/%d/%Y"), sportId=1)
    except Exception as e:
        print(f"  statsapi schedule error {d}: {e}")
        return homered
    for g in sched:
        if g["status"] not in ("Final", "Game Over", "Completed Early"):
            continue
        try:
            box = statsapi.boxscore_data(g["game_id"])
        except Exception:
            continue
        time.sleep(0.2)
        for side in ("home", "away"):
            for pdata in box[side]["players"].values():
                batting = pdata.get("stats", {}).get("batting", {})
                if batting.get("homeRuns", 0) > 0:
                    homered.add(norm_name(pdata["person"]["fullName"]))
    return homered


def main():
    if not API_KEY:
        raise SystemExit("Set the ODDS_API_KEY environment variable first.")

    daily_rows, pick_rows = [], []
    d = SEASON_START
    while d <= SEASON_END:
        events = get_events_for_day(d)
        favorites = []
        for ev in events:
            prices = get_hr_odds_for_event(ev)
            if not prices:
                continue
            fav = pick_favorite(prices)
            if fav:
                favorites.append(fav)

        if not favorites:
            d += timedelta(days=1)
            continue

        homered = build_hr_results(d)
        hits, day_pl = 0, 0.0
        for player, consensus, best_price in favorites:
            hit = norm_name(player) in homered
            hits += hit
            pl = american_profit(best_price, STAKE) if hit else -STAKE
            day_pl += pl
            pick_rows.append({
                "date": d.isoformat(), "player": player,
                "consensus_implied": round(consensus, 3),
                "best_price": best_price,
                "homered": hit, "flat_bet_pl": round(pl, 2),
            })

        n = len(favorites)
        daily_rows.append({
            "date": d.isoformat(), "favorites": n, "homered": hits,
            "sweep": hits == n, "hit_rate": round(hits / n, 3),
            "flat_bet_pl": round(day_pl, 2),
        })
        print(f"{d}  favorites: {n:2d}  homered: {hits:2d}  "
              f"P/L: {day_pl:+7.2f}  credits left: {cached_get.remaining}"
              f"{'  <<< SWEEP' if hits == n else ''}")
        d += timedelta(days=1)

    if not daily_rows:
        print("No data returned — inspect odds_cache/ files.")
        return

    df = pd.DataFrame(daily_rows)
    picks = pd.DataFrame(pick_rows)
    Path("analysis").mkdir(exist_ok=True)
    df.to_csv("analysis/hr_favorites_odds_daily.csv", index=False)
    picks.to_csv("analysis/hr_favorites_odds_picks.csv", index=False)

    total = len(picks)
    hits = picks["homered"].sum()
    pl = picks["flat_bet_pl"].sum()
    avg_implied = picks["consensus_implied"].mean()
    sweeps = df[df["sweep"]]

    print("\n" + "=" * 62)
    print(f"Days analyzed                    : {len(df)}")
    print(f"Total favorite bets              : {total}")
    print(f"Favorites who homered            : {hits} ({hits/total:.1%})")
    print(f"Avg consensus implied prob       : {avg_implied:.1%}")
    print(f"Edge vs implied                  : {hits/total - avg_implied:+.1%}")
    print(f"Flat ${STAKE:.0f}/bet P/L (best price): ${pl:+,.2f} "
          f"(ROI {pl/(total*STAKE):+.1%})")
    print(f"SWEEP DAYS                       : {len(sweeps)}")
    for _, r in sweeps.iterrows():
        print(f"  {r['date']} — {r['homered']}/{r['favorites']}")
    best = df.sort_values(["homered", "hit_rate"], ascending=False).head(5)
    print("\nTop 5 days:")
    for _, r in best.iterrows():
        print(f"  {r['date']}: {r['homered']}/{r['favorites']} "
              f"({r['hit_rate']:.0%}, P/L {r['flat_bet_pl']:+.2f})")
    print("\nWrote analysis/hr_favorites_odds_daily.csv and "
          "analysis/hr_favorites_odds_picks.csv")


if __name__ == "__main__":
    main()
