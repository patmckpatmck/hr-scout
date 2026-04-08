# scripts/update_results.py
# Run each evening: python3 scripts/update_results.py
# Fetches today's HRs from onlyhomers.com and updates history.json automatically

import json
import re
import sys
import time
import unicodedata
import urllib.request
from datetime import date, datetime, timedelta

if len(sys.argv) > 1 and sys.argv[1] != "backfill":
    TODAY = sys.argv[1]
else:
    TODAY = (date.today() - timedelta(days=1)).isoformat()


def normalize(name):
    """Lowercase, strip accents, remove punctuation for fuzzy matching."""
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    return name.lower().strip()


def fetch_todays_hr_hitters(date_str):
    """Fetch HR hitters for date_str (YYYY-MM-DD) from MLB Stats API.

    Two-step process:
      1. Get the date's gamePks from /api/v1/schedule
      2. For each game, fetch /api/v1/game/{gamePk}/boxscore and walk
         teams.{home,away}.players for any batter with stats.batting.homeRuns >= 1.

    Returns a set of (normalized_name, team_abbreviation) tuples.
    """
    headers = {"User-Agent": "HRScout/1.0"}

    # Step 1: game IDs for the date
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    sched_req = urllib.request.Request(sched_url, headers=headers)
    with urllib.request.urlopen(sched_req, timeout=15) as resp:
        sched_data = json.loads(resp.read())

    game_pks = []
    for date_entry in sched_data.get("dates", []):
        for game in date_entry.get("games", []):
            pk = game.get("gamePk")
            if pk:
                game_pks.append(pk)

    if not game_pks:
        print(f"  No games scheduled for {date_str}.")
        return set()

    # Step 2: walk every boxscore and collect HR hitters
    hitters = set()
    for pk in game_pks:
        try:
            bx_url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
            bx_req = urllib.request.Request(bx_url, headers=headers)
            with urllib.request.urlopen(bx_req, timeout=15) as resp:
                bx = json.loads(resp.read())
        except Exception as e:
            print(f"  ⚠️  Boxscore fetch failed for game {pk}: {e}")
            continue

        teams = bx.get("teams", {})
        for side in ("home", "away"):
            side_data = teams.get(side, {})
            team_abbr = side_data.get("team", {}).get("abbreviation", "")
            players = side_data.get("players", {}) or {}
            for player_obj in players.values():
                batting = player_obj.get("stats", {}).get("batting", {}) or {}
                hr_raw = batting.get("homeRuns", 0)
                try:
                    hr_count = int(hr_raw or 0)
                except (TypeError, ValueError):
                    hr_count = 0
                if hr_count >= 1:
                    full_name = player_obj.get("person", {}).get("fullName", "")
                    if full_name:
                        hitters.add((normalize(full_name), team_abbr))
                        print(f"  Found: {full_name} ({team_abbr}) — {hr_count} HR")

    return hitters


def update_history(hitters, date_str):
    """Load history.json, mark date_str's players as hit/miss, write back.

    date_str is YYYY-MM-DD; converted to "Month DD, YYYY" to match history.json keys.
    """
    history_path = "public/history.json"
    date_long = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")

    with open(history_path, "r") as f:
        history = json.load(f)

    updated = 0
    target_day = None
    for day in history:
        if day.get("date") == date_long:
            target_day = day
            break

    if target_day is None:
        print(f"⚠️  No entry for {date_long} in history.json — run generate.py first.")
        return

    for entry in target_day.get("players", []):
        name = entry.get("name", "")
        if not name:
            continue
        player_norm = normalize(name)
        matched = False

        for (hr_name, hr_team) in hitters:
            if player_norm == hr_name:
                matched = True
                break
            # Last-name fallback to handle "J.T. Realmuto" vs "Realmuto" etc.
            player_last = player_norm.split()[-1] if player_norm.split() else ""
            hr_last = hr_name.split()[-1] if hr_name.split() else ""
            if player_last and hr_last and player_last == hr_last:
                matched = True
                break

        if matched:
            entry["hitHR"] = True
            entry["autoResulted"] = True
            updated += 1
            print(f"  Matched: {name}")
        else:
            entry["hitHR"] = False
            entry["autoResulted"] = True

    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nDone. {updated} HR hitters marked for {date_long}.")
    print("Next: git add public/history.json && git commit -m 'results update' && git push")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        start = date(2026, 4, 1)
        end = date.today() - timedelta(days=1)
        cur = start
        while cur <= end:
            date_str = cur.isoformat()
            print(f"\n=== Backfilling {date_str} ===")
            print(f"Fetching HRs from MLB Stats API for {date_str}...")
            hitters = fetch_todays_hr_hitters(date_str)
            print(f"Found {len(hitters)} HR hitters.")
            if hitters:
                update_history(hitters, date_str)
            cur += timedelta(days=1)
            time.sleep(1)
    else:
        print(f"Fetching HRs from MLB Stats API for {TODAY}...")
        hitters = fetch_todays_hr_hitters(TODAY)
        print(f"Found {len(hitters)} HR hitters today.")
        if not hitters:
            print("No results yet — try again after games finish (11pm ET recommended).")
        else:
            update_history(hitters, TODAY)
