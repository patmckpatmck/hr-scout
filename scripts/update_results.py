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

if len(sys.argv) > 1 and sys.argv[1] not in ("backfill", "test"):
    TODAY = sys.argv[1]
else:
    TODAY = (date.today() - timedelta(days=1)).isoformat()


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize(name):
    """Lowercase, strip accents, remove punctuation, collapse whitespace."""
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)   # drop periods/apostrophes/etc.
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def name_key(norm_name):
    """(last_name, first_initial) after dropping a trailing generational suffix.

    Used only by the disambiguating fallback — NOT the primary match. e.g.
    "jazz chisholm jr" -> ("chisholm", "j"); "j t realmuto" -> ("realmuto", "j").
    """
    tokens = norm_name.split()
    if tokens and tokens[-1] in SUFFIXES:
        tokens = tokens[:-1]
    if not tokens:
        return ("", "")
    last = tokens[-1]
    first_initial = tokens[0][0] if tokens[0] else ""
    return (last, first_initial)


def is_match(player_norm, player_team, hr_name, hr_team):
    """True if a scored entry matches an actual HR hitter.

    Primary: exact normalized full-name equality (accent/punctuation-insensitive).
    Fallback: suffix-stripped last name + first initial + team abbreviation must
    ALL agree. The team requirement is what stops the Jr./Jr. and same-last-name
    collisions (Chisholm Jr. vs Witt Jr., the Contreras brothers, the Cruzes).
    """
    if player_norm == hr_name:
        return True
    p_last, p_init = name_key(player_norm)
    h_last, h_init = name_key(hr_name)
    if not (p_last and p_init):
        return False
    return (
        p_last == h_last
        and p_init == h_init
        and bool(player_team)
        and player_team == hr_team
    )


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
        player_team = entry.get("team", "")
        matched = any(
            is_match(player_norm, player_team, hr_name, hr_team)
            for (hr_name, hr_team) in hitters
        )

        if matched:
            entry["hitHR"] = True
            entry["autoResulted"] = True
            updated += 1
            print(f"  Matched: {name}")
        else:
            entry["hitHR"] = False
            entry["autoResulted"] = True

    with open(history_path, "w") as f:
        # ensure_ascii=False preserves raw UTF-8 accents (José, Suárez) to match
        # how generate.py writes the file — otherwise every accented name churns
        # into \uXXXX escapes and the diff becomes unreviewable.
        json.dump(history, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {updated} HR hitters marked for {date_long}.")

    # Phantom-bug guard: the old last-name-only matcher inflated hit rates to
    # ~30%+ by cross-crediting every shared surname. A clean day sits near the
    # ~10-11% league rate; anything above 25% pool-wide is the signature of a
    # matcher regression and should be loud in the Actions logs.
    n_players = len(target_day.get("players", []))
    hit_rate = updated / n_players if n_players else 0.0
    if hit_rate > 0.25:
        print("=" * 60)
        print(f"⚠️  WARNING: {date_long} pool hit rate {hit_rate:.1%} "
              f"({updated}/{n_players}) exceeds 25% — possible matcher "
              f"regression (phantom-bug signature). Verify before trusting.")
        print("=" * 60)

    print("Next: git add public/history.json && git commit -m 'results update' && git push")


def run_tests():
    """Quick assertion block for the matcher. Run: python3 scripts/update_results.py test"""

    def m(entry_name, entry_team, hr_full, hr_team):
        # Mirrors how update_history builds inputs: entry normalized on the fly,
        # HR hitter stored pre-normalized in the hitters set.
        return is_match(normalize(entry_name), entry_team, normalize(hr_full), hr_team)

    # --- Must NOT cross-match: same suffix / same last name, different player ---
    assert not m("Jazz Chisholm Jr.", "NYY", "Bobby Witt Jr.", "KC"), \
        "Chisholm Jr. must not match Witt Jr."
    assert not m("Bobby Witt Jr.", "KC", "Jazz Chisholm Jr.", "NYY"), \
        "Witt Jr. must not match Chisholm Jr."
    assert not m("Willson Contreras", "STL", "William Contreras", "MIL"), \
        "Willson must not match William Contreras (different team)"
    assert not m("William Contreras", "MIL", "Willson Contreras", "STL"), \
        "William must not match Willson Contreras (different team)"
    assert not m("Oneil Cruz", "PIT", "Elly De La Cruz", "CIN"), \
        "Oneil Cruz must not match Elly De La Cruz"

    # --- Must match: formatting / accent / nickname variants of the SAME player ---
    assert m("J.T. Realmuto", "PHI", "J.T. Realmuto", "PHI"), "exact Realmuto"
    assert m("JT Realmuto", "PHI", "J.T. Realmuto", "PHI"), \
        "punctuation variant J.T. vs JT should match"
    assert m("Vladimir Guerrero Jr.", "TOR", "Vladimir Guerrero Jr.", "TOR"), \
        "legit Jr. self-match must still work"
    assert m("Ronald Acuna Jr.", "ATL", "Ronald Acuña Jr.", "ATL"), \
        "accent variant should match"
    assert m("Michael Harris II", "ATL", "Mike Harris", "ATL"), \
        "nickname + suffix fallback (last+initial+team) should match"

    # --- Guard: fallback (non-exact names) must respect the team requirement ---
    # Same last name + initial but different team => fallback must NOT fire.
    assert not m("Mike Harris", "ATL", "M Harris", "NYM"), \
        "fallback must not match same last+initial across different teams"
    # Same last+initial, same team, non-identical strings => fallback SHOULD fire.
    assert m("Mike Harris", "ATL", "M Harris", "ATL"), \
        "fallback should match same last+initial+team"

    # Known residual (accepted, not a bug): two DISTINCT players sharing an
    # identical normalized full name on different teams (e.g. the two Will Smiths)
    # will still collide via the required exact-full-name primary path. Name-only
    # matching cannot resolve this; it is out of scope for this fix.
    assert m("Will Smith", "LAD", "Will Smith", "KC"), \
        "documents the accepted identical-full-name residual"

    print("All matcher assertions passed.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_tests()
    elif len(sys.argv) > 1 and sys.argv[1] == "backfill":
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
