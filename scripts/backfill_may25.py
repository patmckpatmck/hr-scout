# scripts/backfill_may25.py
# One-off backfill for May 25, 2026: retroactively populates hitHR and
# autoResulted on public/history.json entries using the MLB Stats API.
# Reuses the schedule+boxscore fetch and name-matching logic from
# scripts/update_results.py.

import json
import unicodedata
import urllib.request
from datetime import datetime

TARGET_DATE_ISO = "2026-05-25"
HISTORY_PATH = "public/history.json"


def normalize(name):
    """Lowercase, strip accents for fuzzy matching. Mirrors update_results.py."""
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    return name.lower().strip()


def fetch_hr_hitters(date_str):
    """Schedule + boxscore walk. Returns (set of (norm_name, team_abbr),
    list of (orig_name, team_abbr, hr_count)).
    """
    headers = {"User-Agent": "HRScout/1.0"}

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
        return set(), []

    hitters = set()
    raw = []
    for pk in game_pks:
        try:
            bx_url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
            bx_req = urllib.request.Request(bx_url, headers=headers)
            with urllib.request.urlopen(bx_req, timeout=15) as resp:
                bx = json.loads(resp.read())
        except Exception as e:
            print(f"  Boxscore fetch failed for game {pk}: {e}")
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
                        raw.append((full_name, team_abbr, hr_count))

    return hitters, raw


def main():
    date_long = datetime.strptime(TARGET_DATE_ISO, "%Y-%m-%d").strftime("%B %d, %Y")

    print(f"Fetching HRs from MLB Stats API for {TARGET_DATE_ISO}...")
    hitters, raw_hitters = fetch_hr_hitters(TARGET_DATE_ISO)
    print(
        f"Found {len(raw_hitters)} HR-hitter records "
        f"({len(hitters)} unique normalized name+team)."
    )

    with open(HISTORY_PATH, "r") as f:
        history = json.load(f)

    target_day = None
    for day in history:
        if day.get("date") == date_long:
            target_day = day
            break

    if target_day is None:
        print(f"No entry for {date_long} in history.json — aborting (file unchanged).")
        return

    entries = target_day.get("players", [])
    matched_hitter_keys = set()
    matched_entries = []

    for entry in entries:
        name = entry.get("name", "")
        if not name:
            entry["hitHR"] = False
            entry["autoResulted"] = True
            continue

        player_norm = normalize(name)
        match_key = None

        for (hr_name, hr_team) in hitters:
            if player_norm == hr_name:
                match_key = (hr_name, hr_team)
                break
            player_last = player_norm.split()[-1] if player_norm.split() else ""
            hr_last = hr_name.split()[-1] if hr_name.split() else ""
            if player_last and hr_last and player_last == hr_last:
                match_key = (hr_name, hr_team)
                break

        if match_key:
            entry["hitHR"] = True
            entry["autoResulted"] = True
            matched_hitter_keys.add(match_key)
            matched_entries.append(entry)
        else:
            entry["hitHR"] = False
            entry["autoResulted"] = True

    unmatched = [
        (orig, team, n)
        for (orig, team, n) in raw_hitters
        if (normalize(orig), team) not in matched_hitter_keys
    ]

    print()
    print("=" * 60)
    print(f"Backfill summary for {date_long}")
    print("=" * 60)
    print(f"Total {date_long} entries in history.json:   {len(entries)}")
    print(f"Total HR-hitter records from MLB API:        {len(raw_hitters)}")
    print(f"Unique (normalized name, team) HR keys:      {len(hitters)}")
    print(f"Entries marked hitHR=true:                   {sum(1 for e in entries if e.get('hitHR') is True)}")
    print(f"Entries marked autoResulted=true:            {sum(1 for e in entries if e.get('autoResulted') is True)}")

    print()
    print(f"Unmatched MLB HR hitters ({len(unmatched)}) — Pat review:")
    if unmatched:
        for orig, team, n in unmatched:
            print(f"  {orig} ({team}) — {n} HR")
    else:
        print("  (none)")

    print()
    print("First 5 matched players (name, team, score, rank):")
    for e in matched_entries[:5]:
        print(f"  {e.get('name')} ({e.get('team')}) — score={e.get('score')} rank={e.get('rank')}")

    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

    print()
    print("DONE — review git diff before committing")


if __name__ == "__main__":
    main()
