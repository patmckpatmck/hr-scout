"""
HR Favorites Backtest — "Did the chalk ever sweep?"
====================================================
For every day of the 2026 MLB season, identifies the single best HR threat
per game (proxy for the FanDuel sub-+300 favorite), checks whether each
favorite actually homered that day, and reports:

  - Whether any day was a full sweep (all favorites homered)
  - The best days (highest hit count / rate)
  - Overall favorite hit rate

Proxy logic: real historical FanDuel lines aren't public, so the "favorite"
for each game is the batter with the highest entering-day HR-per-game rate
(min games threshold), and he "qualifies" as a sub-+300 analog if that rate
clears QUALIFY_RATE (~22% ≈ +300 line after vig).

Requires:  pip install MLB-StatsAPI pandas
Run:       python hr_favorites_backtest.py
Output:    hr_favorites_daily.csv + console summary
"""

from datetime import date, datetime, timedelta
from collections import defaultdict
import os
import time

import pandas as pd
import statsapi

# ----------------------------- CONFIG ---------------------------------
SEASON_START = date(2026, 3, 26)   # adjust to actual Opening Day
SEASON_END = date.today() - timedelta(days=1)
MIN_GAMES = 15         # games played before a player's rate is trusted
QUALIFY_RATE = 0.22    # HR/G proxy for a sub-+300 FanDuel line
SLEEP = 0.25           # be polite to the MLB Stats API
OUT_CSV = "analysis/hr_favorites_daily.csv"   # written under analysis/ to keep repo root clean
# -----------------------------------------------------------------------

# Cumulative season-to-date stats, updated day by day (no lookahead)
cum = defaultdict(lambda: {"g": 0, "hr": 0, "name": ""})

daily_rows = []


def batters_from_boxscore(box):
    """Yield (player_id, name, hr_today) for every batter who appeared."""
    for side in ("home", "away"):
        team = box[side]
        for pid_key, pdata in team["players"].items():
            batting = pdata.get("stats", {}).get("batting", {})
            if not batting:
                continue  # pitcher who didn't bat / did not play
            pid = pdata["person"]["id"]
            name = pdata["person"]["fullName"]
            hr = batting.get("homeRuns", 0)
            yield pid, name, hr


def process_day(d: date):
    datestr = d.strftime("%m/%d/%Y")
    try:
        sched = statsapi.schedule(date=datestr, sportId=1)
    except Exception as e:
        print(f"  schedule error {d}: {e}")
        return

    games = [g for g in sched if g["status"] in ("Final", "Game Over", "Completed Early")]
    if not games:
        return

    day_favorites = []          # (name, rate, hr_today)
    day_updates = []            # boxscore stats to apply AFTER picking favorites

    for g in games:
        try:
            box = statsapi.boxscore_data(g["game_id"])
        except Exception as e:
            print(f"  boxscore error {g['game_id']}: {e}")
            continue
        time.sleep(SLEEP)

        batters = list(batters_from_boxscore(box))
        day_updates.extend(batters)

        # Pick this game's favorite using ENTERING-DAY rates only
        best = None
        for pid, name, hr_today in batters:
            s = cum[pid]
            if s["g"] < MIN_GAMES:
                continue
            rate = s["hr"] / s["g"]
            if best is None or rate > best[1]:
                best = (name, rate, hr_today)

        if best and best[1] >= QUALIFY_RATE:
            day_favorites.append(best)

    # Apply today's stats to cumulative totals (after favorite selection)
    for pid, name, hr_today in day_updates:
        cum[pid]["g"] += 1
        cum[pid]["hr"] += hr_today
        cum[pid]["name"] = name

    if not day_favorites:
        return

    n = len(day_favorites)
    hits = sum(1 for _, _, hr in day_favorites if hr > 0)
    daily_rows.append({
        "date": d.isoformat(),
        "qualifying_favorites": n,
        "favorites_homered": hits,
        "sweep": hits == n,
        "hit_rate": round(hits / n, 3),
        "favorites": "; ".join(
            f"{name} ({rate:.0%}){' *HR*' if hr > 0 else ''}"
            for name, rate, hr in sorted(day_favorites, key=lambda x: -x[1])
        ),
    })
    print(f"{d}  favorites: {n:2d}  homered: {hits:2d}"
          f"{'  <<< SWEEP' if hits == n else ''}")


def main():
    d = SEASON_START
    while d <= SEASON_END:
        process_day(d)
        d += timedelta(days=1)

    if not daily_rows:
        print("No qualifying days found — check SEASON_START / MIN_GAMES.")
        return

    df = pd.DataFrame(daily_rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    sweeps = df[df["sweep"]]
    total_favs = df["qualifying_favorites"].sum()
    total_hits = df["favorites_homered"].sum()

    print("\n" + "=" * 60)
    print(f"Days with qualifying favorites : {len(df)}")
    print(f"Total favorite slots           : {total_favs}")
    print(f"Overall favorite hit rate      : {total_hits / total_favs:.1%}")
    print(f"SWEEP DAYS (all favorites HR'd): {len(sweeps)}")
    if len(sweeps):
        for _, r in sweeps.iterrows():
            print(f"  {r['date']} — {r['qualifying_favorites']} for "
                  f"{r['qualifying_favorites']}: {r['favorites']}")
    best = df.sort_values(["favorites_homered", "hit_rate"],
                          ascending=False).head(5)
    print("\nTop 5 days by favorites homered:")
    for _, r in best.iterrows():
        print(f"  {r['date']}: {r['favorites_homered']}/"
              f"{r['qualifying_favorites']} ({r['hit_rate']:.0%})")
    print(f"\nDaily detail written to {OUT_CSV}")


if __name__ == "__main__":
    main()
