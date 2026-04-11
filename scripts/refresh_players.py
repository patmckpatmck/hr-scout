#!/usr/bin/env python3
"""
HR Scout player database refresher.

Run manually each Monday morning BEFORE the daily run.sh workflow.
Fetches the top ~200 HR hitters from the MLB Stats API, enriches with
Baseball Savant xHR data via Claude web search, and writes data/players.json.

Usage: python3 scripts/refresh_players.py
Requires: ANTHROPIC_API_KEY environment variable
"""

import json
import os
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env.local (then .env) so the key works without manual export
_env_dir = Path(__file__).resolve().parent.parent
load_dotenv(_env_dir / ".env.local")
load_dotenv(_env_dir / ".env")

import anthropic

client = anthropic.Anthropic()

YEAR = datetime.now().year

DATA_DIR = _env_dir / "data"
PLAYERS_PATH = DATA_DIR / "players.json"

# MLB Stats API team ID → abbreviation
MLB_TEAM_ABBR = {
    108: "LAA", 109: "AZ",  110: "BAL", 111: "BOS", 112: "CHC", 113: "CIN",
    114: "CLE", 115: "COL", 116: "DET", 117: "HOU", 118: "KC",  119: "LAD",
    120: "WSH", 121: "NYM", 133: "ATH", 134: "PIT", 135: "SD",  136: "SEA",
    137: "SF",  138: "STL", 139: "TB",  140: "TEX", 141: "TOR", 142: "MIN",
    143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA", 147: "NYY", 158: "MIL",
}

# Bat side codes from the MLB API → our format
BAT_SIDE_MAP = {"R": "R", "L": "L", "S": "B"}


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE HELPERS (same pattern as generate.py)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_json(text):
    """Try to parse JSON from Claude's response text."""
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    arr_i = text.find("[")
    obj_i = text.find("{")
    if arr_i == -1 and obj_i == -1:
        return None
    start = arr_i if obj_i == -1 else obj_i if arr_i == -1 else min(arr_i, obj_i)
    is_arr = text[start] == "["
    end = text.rfind("]") if is_arr else text.rfind("}")
    if end == -1:
        return None
    json_str = text[start:end + 1]
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def call_claude(prompt, retries=4, max_searches=3):
    """Call Claude with web search, extract JSON. Retries on failure."""
    json_system = (
        "You are a structured data API. After performing any web searches, "
        "your FINAL text response must be ONLY valid JSON — "
        "no markdown fences, no commentary, no explanation. "
        "If you cannot find data, return [] or {} as appropriate."
    )
    for attempt in range(retries + 1):
        try:
            print(f"  [Claude] Calling API (attempt {attempt + 1})...")
            result = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=json_system,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}],
                messages=[{"role": "user", "content": prompt}],
            )

            text_blocks = [b.text for b in result.content if b.type == "text"]

            for block in text_blocks:
                parsed = extract_json(block)
                if parsed is not None:
                    return parsed

            all_text = "\n".join(text_blocks)
            parsed = extract_json(all_text)
            if parsed is not None:
                return parsed

            # Reformat: second call WITHOUT web search, just text-to-JSON.
            print("  [Claude] Response wasn't valid JSON, asking for reformat...")
            reformat_input = all_text or "No data found."
            fmt = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=(
                    "You convert research notes into JSON. Output ONLY raw valid JSON. "
                    "No markdown, no code fences, no explanation, no preamble. "
                    "Your entire response must be parseable by json.loads()."
                ),
                messages=[
                    {"role": "user", "content": (
                        f"Research notes:\n\n{reformat_input}\n\n"
                        f"Original request: {prompt}\n\n"
                        "Convert the above into ONLY the JSON structure from the original request. "
                        "Your entire response must start with [ or {{ and be valid JSON. Nothing else."
                    )},
                ],
            )
            fmt_text = "\n".join(b.text for b in fmt.content if b.type == "text")
            parsed = extract_json(fmt_text)
            if parsed is not None:
                return parsed

            print(f"  [Claude] Could not parse JSON (attempt {attempt + 1})")
            if attempt < retries:
                time.sleep(5)

        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                wait = 30 * (2 ** attempt)
                print(f"  [Claude] API overloaded (529), waiting {wait}s...")
                time.sleep(wait)
            elif e.status_code == 429:
                print(f"  [Claude] Rate limited (429), waiting 60s...")
                time.sleep(60)
            else:
                print(f"  [Claude] API error {e.status_code}: {e}")
                if attempt < retries:
                    time.sleep(5)
        except Exception as e:
            print(f"  [Claude] Error: {e}")
            if attempt < retries:
                time.sleep(5)

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Fetch HR leaders from MLB Stats API
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_bat_sides(player_ids):
    """Batch-fetch bat side for a list of player IDs from the MLB people API."""
    bat_sides = {}
    # API accepts comma-separated IDs, batch in groups of 50
    batch_size = 50
    for i in range(0, len(player_ids), batch_size):
        batch = player_ids[i:i + batch_size]
        ids_param = ",".join(str(pid) for pid in batch)
        url = (
            f"https://statsapi.mlb.com/api/v1/people?"
            f"personIds={ids_param}&fields=people,id,batSide,code"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HRScout/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            for p in data.get("people", []):
                code = p.get("batSide", {}).get("code", "R")
                bat_sides[p["id"]] = BAT_SIDE_MAP.get(code, "R")
        except Exception as e:
            print(f"  ⚠️  Failed to fetch bat sides for batch: {e}")
    return bat_sides


def fetch_hr_leaders():
    """Fetch top 200 HR hitters from the MLB Stats API for the current season."""
    print(f"⚾ Fetching {YEAR} HR leaders from MLB Stats API...")
    url = (
        f"https://statsapi.mlb.com/api/v1/stats?"
        f"stats=season&group=hitting&season={YEAR}&sportId=1"
        f"&sortStat=homeRuns&order=desc&limit=200"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "HRScout/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    raw_players = []
    seen = set()
    player_ids = []

    for stat_group in data.get("stats", []):
        for split in stat_group.get("splits", []):
            player_info = split.get("player", {})
            stat = split.get("stat", {})
            team_info = split.get("team", {})

            name = player_info.get("fullName", "")
            pid = player_info.get("id", 0)
            if not name or name in seen:
                continue
            seen.add(name)

            team_id = team_info.get("id", 0)
            team_abbr = MLB_TEAM_ABBR.get(team_id, "")

            hr = stat.get("homeRuns", 0)
            gp = stat.get("gamesPlayed", 0)

            raw_players.append({
                "name": name,
                "pid": pid,
                "team": team_abbr,
                "hr": hr,
                "gp": gp,
            })
            player_ids.append(pid)

    # Batch-fetch bat side (not available on the stats endpoint)
    print(f"  🔍 Fetching handedness for {len(player_ids)} players...")
    bat_sides = fetch_bat_sides(player_ids)

    players = []
    for p in raw_players:
        hand = bat_sides.get(p["pid"], "R")
        players.append({
            "name": p["name"],
            "team": p["team"],
            "hand": hand,
            "hr": p["hr"],
            "gp": p["gp"],
        })

    print(f"  ✅ Found {len(players)} players ({players[0]['name']} leads with {players[0]['hr']} HR)" if players else "  ⚠️  No players found")
    return players


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Fetch xHR & barrel rate from Baseball Savant via Claude
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_savant_data(player_names):
    """Batch-query Claude for Baseball Savant xHR and barrel rate data."""
    print(f"\n🎯 Fetching Savant xHR & barrel rates for {len(player_names)} players...")
    batch_size = 20
    savant_map = {}

    prompt_tmpl = (
        "Search Baseball Savant for current {year} expected home runs (xHR per 600 PA) "
        "and barrel rate % for these MLB hitters: {names}. "
        'Return ONLY JSON using the EXACT player names I gave you as keys: '
        '{{"Aaron Judge":{{"xhrPer600":8.2,"barrelPct":18.5}},...}}. '
        "xhrPer600 = expected HRs per 600 PA from Statcast. "
        "barrelPct = barrel percentage from Statcast. "
        "Default: xhrPer600:3.0, barrelPct:6.0 if no data found."
    )

    num_batches = (len(player_names) + batch_size - 1) // batch_size
    for i in range(0, len(player_names), batch_size):
        batch = player_names[i:i + batch_size]
        batch_num = i // batch_size + 1
        print(f"  🎯 Batch {batch_num}/{num_batches} ({len(batch)} players)...")

        result = call_claude(
            prompt_tmpl.format(year=YEAR, names=", ".join(batch)),
            max_searches=5,
        )
        if isinstance(result, dict):
            savant_map.update(result)
            print(f"      Got data for {len(result)} players")
        else:
            print(f"      ⚠️  No data returned for this batch")

        if i + batch_size < len(player_names):
            time.sleep(3)

    print(f"  ✅ Savant data for {len(savant_map)} / {len(player_names)} players\n")
    return savant_map


def xhr_to_score(xhr_per_600):
    """Convert xHR per 600 PA to a 1–10 score."""
    if xhr_per_600 is None:
        return 5
    # Scale: 0 xHR → 1, 5 → 5, 12+ → 10
    v = float(xhr_per_600)
    if v >= 12:
        return 10
    if v >= 10:
        return 9
    if v >= 8:
        return 8
    if v >= 6:
        return 7
    if v >= 5:
        return 6
    if v >= 4:
        return 5
    if v >= 3:
        return 4
    if v >= 2:
        return 3
    if v >= 1:
        return 2
    return 1


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Build & write player database
# ═══════════════════════════════════════════════════════════════════════════════

def load_existing():
    """Load the existing players.json if it exists."""
    if PLAYERS_PATH.exists():
        with open(PLAYERS_PATH) as f:
            existing = json.load(f)
        return {p["n"]: p for p in existing}
    return {}


def build_database(api_players, savant_map, existing_db):
    """Merge API data, Savant data, and existing curated values into the player DB."""
    players = []

    for p in api_players:
        name = p["name"]
        team = p["team"]
        hand = p["hand"]
        hr = p["hr"]

        # Look up Savant data (fuzzy match on name)
        savant = savant_map.get(name, {})
        xhr_val = savant.get("xhrPer600")
        xhr = xhr_to_score(xhr_val)

        # Preserve curated sR, sL, h values from existing DB if available
        prev = existing_db.get(name, {})
        sR = prev.get("sR", 5.0)
        sL = prev.get("sL", 5.0)
        h = prev.get("h", 5)

        players.append({
            "n": name,
            "t": team,
            "hand": hand,
            "xhr": xhr,
            "sR": sR,
            "sL": sL,
            "h": h,
            "hr25": hr,
        })

    return players


def print_summary(new_db, existing_db):
    """Print a summary of changes vs the previous version."""
    new_names = {p["n"] for p in new_db}
    old_names = set(existing_db.keys())

    added = new_names - old_names
    removed = old_names - new_names
    updated = new_names & old_names

    print("=" * 60)
    print(f"📊 REFRESH SUMMARY")
    print(f"   Total players: {len(new_db)}")
    print(f"   Added:         {len(added)}")
    print(f"   Updated:       {len(updated)}")
    print(f"   Removed:       {len(removed)}")
    print("=" * 60)

    if added:
        print(f"\n   ➕ New players ({len(added)}):")
        for n in sorted(added)[:20]:
            entry = next(p for p in new_db if p["n"] == n)
            print(f"      {n} ({entry['t']}) — {entry['hr25']} HR, xhr={entry['xhr']}")
        if len(added) > 20:
            print(f"      ... and {len(added) - 20} more")

    if removed:
        print(f"\n   ➖ Removed players ({len(removed)}):")
        for n in sorted(removed)[:10]:
            print(f"      {n}")
        if len(removed) > 10:
            print(f"      ... and {len(removed) - 10} more")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n🔄 HR Scout Player Database Refresh — {YEAR} Season")
    print("=" * 60)

    # Step 1: Fetch HR leaders
    api_players = fetch_hr_leaders()
    if not api_players:
        print("❌ No players fetched from MLB Stats API. Aborting.")
        return

    # Step 2: Fetch Savant data (batched)
    names = [p["name"] for p in api_players]
    savant_map = fetch_savant_data(names)

    # Step 3: Load existing DB and build new one
    existing_db = load_existing()
    new_db = build_database(api_players, savant_map, existing_db)

    # Step 4: Write output
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLAYERS_PATH, "w") as f:
        json.dump(new_db, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Wrote {len(new_db)} players to {PLAYERS_PATH}")

    # Step 5: Summary
    print_summary(new_db, existing_db)


if __name__ == "__main__":
    main()
