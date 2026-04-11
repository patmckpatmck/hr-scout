#!/usr/bin/env python3
"""
One-time migration: merge hand-tuned player values from the hardcoded
_HARDCODED_PLAYERS list in generate.py back into data/players.json.

Usage: python3 scripts/migrate_curated_scores.py
"""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATE_PY = ROOT / "scripts" / "generate.py"
PLAYERS_JSON = ROOT / "data" / "players.json"


def parse_hardcoded_players():
    """Extract _HARDCODED_PLAYERS list from generate.py source without importing it."""
    source = GENERATE_PY.read_text()

    # Find the assignment: _HARDCODED_PLAYERS = [ ... ]
    match = re.search(r"^_HARDCODED_PLAYERS\s*=\s*\[", source, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find _HARDCODED_PLAYERS in generate.py")

    start = match.start()
    # Walk forward to find the matching closing bracket
    bracket_depth = 0
    i = source.index("[", start)
    for j in range(i, len(source)):
        if source[j] == "[":
            bracket_depth += 1
        elif source[j] == "]":
            bracket_depth -= 1
            if bracket_depth == 0:
                end = j + 1
                break
    else:
        raise RuntimeError("Could not find end of _HARDCODED_PLAYERS list")

    list_source = source[i:end]
    # Strip inline comments (# ...) so ast.literal_eval can parse it
    list_source = re.sub(r"#[^\n]*", "", list_source)
    return ast.literal_eval(list_source)


def main():
    print("🔄 Migrating curated scores from generate.py → data/players.json\n")

    # Parse hardcoded list
    hardcoded = parse_hardcoded_players()
    print(f"   Hardcoded players in generate.py: {len(hardcoded)}")

    # Load current players.json
    if not PLAYERS_JSON.exists():
        print(f"   ❌ {PLAYERS_JSON} does not exist. Run refresh_players.py first.")
        return

    with open(PLAYERS_JSON) as f:
        players = json.load(f)
    print(f"   Players in data/players.json:     {len(players)}")

    # Build lookup: normalized name → index in players list
    lookup = {}
    for idx, p in enumerate(players):
        key = p["n"].strip().lower()
        lookup[key] = idx

    updated = 0
    added = 0

    for hp in hardcoded:
        key = hp["n"].strip().lower()
        if key in lookup:
            # Overwrite curated fields
            idx = lookup[key]
            players[idx]["sR"] = hp["sR"]
            players[idx]["sL"] = hp["sL"]
            players[idx]["h"] = hp["h"]
            players[idx]["xhr"] = hp["xhr"]
            updated += 1
        else:
            # Player not in players.json — add them
            players.append(dict(hp))
            added += 1

    # Write back
    with open(PLAYERS_JSON, "w") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

    print(f"\n   ✅ Updated: {updated} players (sR, sL, h, xhr overwritten)")
    print(f"   ➕ Added:   {added} players (not found in players.json)")
    print(f"   📦 Total:   {len(players)} players in data/players.json")


if __name__ == "__main__":
    main()
