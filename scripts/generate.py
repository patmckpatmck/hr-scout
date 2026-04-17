#!/usr/bin/env python3
"""
HR Scout daily data generator.

Run once each morning to fetch MLB data, compute scores, and write public/data.json.
Usage: python3 scripts/generate.py
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

# ═══════════════════════════════════════════════════════════════════════════════
# STATIC DATA
# ═══════════════════════════════════════════════════════════════════════════════

PARK_FACTORS = {
    "LAD": {"L": 10, "R": 9,  "name": "Dodger Stadium"},
    "BAL": {"L": 9,  "R": 9,  "name": "Camden Yards"},
    "NYY": {"L": 10, "R": 6,  "name": "Yankee Stadium"},
    "LAA": {"L": 8,  "R": 8,  "name": "Angel Stadium"},
    "ATH": {"L": 8,  "R": 8,  "name": "Sutter Health Park"},
    "OAK": {"L": 8,  "R": 8,  "name": "Sutter Health Park"},
    "TOR": {"L": 7,  "R": 7,  "name": "Rogers Centre"},
    "DET": {"L": 7,  "R": 7,  "name": "Comerica Park"},
    "TB":  {"L": 7,  "R": 7,  "name": "Tropicana Field"},
    "COL": {"L": 9,  "R": 10, "name": "Coors Field"},
    "HOU": {"L": 6,  "R": 6,  "name": "Minute Maid Park"},
    "SEA": {"L": 6,  "R": 6,  "name": "T-Mobile Park"},
    "PHI": {"L": 7,  "R": 6,  "name": "Citizens Bank Park"},
    "AZ":  {"L": 6,  "R": 6,  "name": "Chase Field"},
    "CHC": {"L": 6,  "R": 6,  "name": "Wrigley Field"},
    "NYM": {"L": 5,  "R": 5,  "name": "Citi Field"},
    "ATL": {"L": 5,  "R": 5,  "name": "Truist Park"},
    "CWS": {"L": 5,  "R": 5,  "name": "Guaranteed Rate Field"},
    "CIN": {"L": 5,  "R": 5,  "name": "Great American Ball Park"},
    "MIL": {"L": 5,  "R": 5,  "name": "American Family Field"},
    "CLE": {"L": 4,  "R": 4,  "name": "Progressive Field"},
    "WSH": {"L": 4,  "R": 4,  "name": "Nationals Park"},
    "MIN": {"L": 4,  "R": 4,  "name": "Target Field"},
    "BOS": {"L": 6,  "R": 3,  "name": "Fenway Park"},
    "STL": {"L": 3,  "R": 3,  "name": "Busch Stadium"},
    "MIA": {"L": 3,  "R": 3,  "name": "loanDepot Park"},
    "TEX": {"L": 3,  "R": 3,  "name": "Globe Life Field"},
    "SD":  {"L": 2,  "R": 2,  "name": "Petco Park"},
    "KC":  {"L": 2,  "R": 2,  "name": "Kauffman Stadium"},
    "SF":  {"L": 3,  "R": 1,  "name": "Oracle Park"},
    "PIT": {"L": 1,  "R": 1,  "name": "PNC Park"},
}

BALLPARK_GEO = {
    "LAD": {"lat": 34.0739, "lon": -118.2400, "outBearing": 315},
    "BAL": {"lat": 39.2838, "lon": -76.6218,  "outBearing": 225},
    "NYY": {"lat": 40.8296, "lon": -73.9262,  "outBearing": 0},
    "LAA": {"lat": 33.8003, "lon": -117.8827, "outBearing": 270},
    "ATH": {"lat": 37.7516, "lon": -121.5665, "outBearing": 225},
    "TOR": {"lat": 43.6414, "lon": -79.3894,  "outBearing": 315},
    "DET": {"lat": 42.3390, "lon": -83.0485,  "outBearing": 315},
    "TB":  {"lat": 27.7683, "lon": -82.6534,  "outBearing": 0},
    "COL": {"lat": 39.7560, "lon": -104.9942, "outBearing": 315},
    "HOU": {"lat": 29.7573, "lon": -95.3555,  "outBearing": 180},
    "SEA": {"lat": 47.5913, "lon": -122.3320, "outBearing": 270},
    "PHI": {"lat": 39.9061, "lon": -75.1665,  "outBearing": 270},
    "AZ":  {"lat": 33.4453, "lon": -112.0667, "outBearing": 90},
    "CHC": {"lat": 41.9484, "lon": -87.6553,  "outBearing": 270},
    "NYM": {"lat": 40.7571, "lon": -73.8458,  "outBearing": 315},
    "ATL": {"lat": 33.8907, "lon": -84.4677,  "outBearing": 270},
    "CWS": {"lat": 41.8300, "lon": -87.6338,  "outBearing": 270},
    "CIN": {"lat": 39.0979, "lon": -84.5080,  "outBearing": 225},
    "MIL": {"lat": 43.0280, "lon": -87.9712,  "outBearing": 270},
    "CLE": {"lat": 41.4962, "lon": -81.6852,  "outBearing": 270},
    "WSH": {"lat": 38.8730, "lon": -77.0074,  "outBearing": 315},
    "MIN": {"lat": 44.9817, "lon": -93.2781,  "outBearing": 270},
    "BOS": {"lat": 42.3467, "lon": -71.0972,  "outBearing": 90},
    "STL": {"lat": 38.6226, "lon": -90.1928,  "outBearing": 270},
    "MIA": {"lat": 25.7781, "lon": -80.2197,  "outBearing": 270},
    "TEX": {"lat": 32.7512, "lon": -97.0832,  "outBearing": 315},
    "SD":  {"lat": 32.7076, "lon": -117.1570, "outBearing": 225},
    "KC":  {"lat": 39.0517, "lon": -94.4803,  "outBearing": 270},
    "SF":  {"lat": 37.7786, "lon": -122.3893, "outBearing": 270},
    "PIT": {"lat": 40.4468, "lon": -80.0057,  "outBearing": 315},
}

DOMES = {"TB", "TOR", "HOU", "SEA", "AZ", "MIL", "MIA", "TEX", "MIN"}

BULLPEN = {
    "COL": 10, "LAA": 9.47, "OAK": 9.47, "WSH": 8.40, "LAD": 8.30, "BAL": 8.09,
    "MIA": 8.09, "HOU": 7.98, "NYY": 7.87, "DET": 7.87, "TB": 7.87, "ATH": 7.77,
    "CIN": 7.77, "ATL": 7.66, "CWS": 7.55, "PHI": 7.34, "AZ": 7.02, "CHC": 7.02,
    "TOR": 6.91, "TEX": 6.70, "MIN": 6.49, "NYM": 6.38, "SEA": 6.28, "KC": 6.17,
    "MIL": 5.96, "PIT": 5.85, "SD": 5.43, "SF": 5.11, "CLE": 5.00, "STL": 4.79,
    "BOS": 4.79,
}

_players_path = Path(__file__).resolve().parent.parent / "data" / "players.json"
if _players_path.exists():
    with open(_players_path) as _f:
        PLAYERS = json.load(_f)
    print(f"  📦 Loaded {len(PLAYERS)} players from data/players.json")
else:
    print("  ⚠️  data/players.json not found, using empty player list")
    PLAYERS = []

_HARDCODED_PLAYERS = [
    # sR = HR rate score vs RHP (1-10), sL = HR rate score vs LHP (1-10), hr25 = 2025 full-season HR total
    {"n": "Aaron Judge",       "t": "NYY", "hand": "R", "xhr": 10, "sR": 7.08, "sL": 8.50, "h": 10, "hr25": 52},
    {"n": "Jo Adell",          "t": "LAA", "hand": "R", "xhr": 8,  "sR": 8.06, "sL": 7.00, "h": 9,  "hr25": 37},
    {"n": "Taylor Ward",       "t": "BAL", "hand": "R", "xhr": 6,  "sR": 8.06, "sL": 6.50, "h": 9,  "hr25": 36},
    {"n": "Nick Kurtz",        "t": "ATH", "hand": "L", "xhr": 7,  "sR": 7.81, "sL": 5.20, "h": 9,  "hr25": 35},
    {"n": "Eugenio Suárez",    "t": "CIN", "hand": "R", "xhr": 6,  "sR": 7.33, "sL": 8.00, "h": 10, "hr25": 48},
    {"n": "George Springer",   "t": "TOR", "hand": "R", "xhr": 8,  "sR": 7.24, "sL": 7.80, "h": 8,  "hr25": 31},
    {"n": "Cal Raleigh",       "t": "SEA", "hand": "L", "xhr": 8,  "sR": 6.25, "sL": 4.50, "h": 10, "hr25": 59},
    {"n": "Trent Grisham",     "t": "NYY", "hand": "L", "xhr": 6,  "sR": 8.06, "sL": 4.00, "h": 9,  "hr25": 34},
    {"n": "Giancarlo Stanton", "t": "NYY", "hand": "R", "xhr": 8,  "sR": 8.50, "sL": 9.00, "h": 6,  "hr25": 23},
    {"n": "Vinnie Pasquantino","t": "KC",  "hand": "L", "xhr": 6,  "sR": 8.33, "sL": 5.50, "h": 8,  "hr25": 31},
    {"n": "Mike Trout",        "t": "LAA", "hand": "R", "xhr": 5,  "sR": 9.05, "sL": 8.50, "h": 6,  "hr25": 25},
    {"n": "Kyle Schwarber",    "t": "PHI", "hand": "L", "xhr": 8,  "sR": 5.85, "sL": 7.50, "h": 10, "hr25": 56},
    {"n": "Christian Walker",  "t": "HOU", "hand": "R", "xhr": 6,  "sR": 8.26, "sL": 7.00, "h": 6,  "hr25": 24},
    {"n": "Daulton Varsho",    "t": "TOR", "hand": "L", "xhr": 7,  "sR": 10,   "sL": 4.50, "h": 5,  "hr25": 20},
    {"n": "Michael Busch",     "t": "CHC", "hand": "L", "xhr": 7,  "sR": 8.97, "sL": 5.00, "h": 8,  "hr25": 32},
    {"n": "Byron Buxton",      "t": "MIN", "hand": "R", "xhr": 8,  "sR": 7.10, "sL": 8.50, "h": 9,  "hr25": 34},
    {"n": "Colson Montgomery", "t": "CWS", "hand": "L", "xhr": 6,  "sR": 8.33, "sL": 4.50, "h": 5,  "hr25": 20},
    {"n": "Jazz Chisholm Jr.", "t": "NYY", "hand": "L", "xhr": 6,  "sR": 8.62, "sL": 5.50, "h": 8,  "hr25": 31},
    {"n": "Andy Pages",        "t": "LAD", "hand": "R", "xhr": 4,  "sR": 8.80, "sL": 7.50, "h": 7,  "hr25": 27},
    {"n": "Julio Rodríguez",   "t": "SEA", "hand": "R", "xhr": 5,  "sR": 6.67, "sL": 7.50, "h": 8,  "hr25": 32},
    {"n": "Junior Caminero",   "t": "TB",  "hand": "R", "xhr": 8,  "sR": 7.05, "sL": 8.00, "h": 10, "hr25": 45},
    {"n": "James Wood",        "t": "WSH", "hand": "L", "xhr": 6,  "sR": 6.30, "sL": 5.00, "h": 8,  "hr25": 30},
    {"n": "Josh Bell",         "t": "MIN", "hand": "B", "xhr": 6,  "sR": 8.00, "sL": 6.50, "h": 6,  "hr25": 22},
    {"n": "Ben Rice",          "t": "NYY", "hand": "L", "xhr": 7,  "sR": 7.39, "sL": 5.00, "h": 6,  "hr25": 23},
    {"n": "Brandon Lowe",      "t": "PIT", "hand": "L", "xhr": 6,  "sR": 8.62, "sL": 4.50, "h": 8,  "hr25": 31},
    {"n": "Shohei Ohtani",     "t": "LAD", "hand": "L", "xhr": 9,  "sR": 7.60, "sL": 8.50, "h": 10, "hr25": 54},
    {"n": "Tyler Soderstrom",  "t": "ATH", "hand": "L", "xhr": 5,  "sR": 8.33, "sL": 5.00, "h": 6,  "hr25": 25},
    {"n": "Seiya Suzuki",      "t": "CHC", "hand": "R", "xhr": 8,  "sR": 6.67, "sL": 8.00, "h": 8,  "hr25": 30},
    {"n": "Ronald Acuña Jr.",  "t": "ATL", "hand": "R", "xhr": 6,  "sR": 8.24, "sL": 7.00, "h": 5,  "hr25": 20},
    {"n": "Salvador Perez",    "t": "KC",  "hand": "R", "xhr": 8,  "sR": 9.29, "sL": 7.50, "h": 8,  "hr25": 30},
    {"n": "Kyle Manzardo",     "t": "CLE", "hand": "L", "xhr": 5,  "sR": 8.08, "sL": 4.50, "h": 7,  "hr25": 27},
    {"n": "Cody Bellinger",    "t": "NYY", "hand": "L", "xhr": 4,  "sR": 7.50, "sL": 5.50, "h": 7,  "hr25": 29},
    {"n": "Pete Crow-Armstrong","t": "CHC", "hand": "R", "xhr": 6,  "sR": 7.59, "sL": 6.50, "h": 8,  "hr25": 30},
    {"n": "Brent Rooker",      "t": "ATH", "hand": "R", "xhr": 7,  "sR": 8.28, "sL": 9.00, "h": 8,  "hr25": 30},
    {"n": "Bobby Witt Jr.",    "t": "KC",  "hand": "R", "xhr": 6,  "sR": 9.55, "sL": 7.00, "h": 6,  "hr25": 22},
    {"n": "Shea Langeliers",   "t": "ATH", "hand": "R", "xhr": 6,  "sR": 7.00, "sL": 7.50, "h": 8,  "hr25": 31},
    {"n": "Brett Baty",        "t": "NYM", "hand": "L", "xhr": 6,  "sR": 8.82, "sL": 4.00, "h": 5,  "hr25": 18},
    {"n": "Ryan Mountcastle",  "t": "BAL", "hand": "R", "xhr": 5,  "sR": 10,   "sL": 6.50, "h": 1,  "hr25": 5},
    {"n": "Matt Olson",        "t": "ATL", "hand": "L", "xhr": 6,  "sR": 7.78, "sL": 6.00, "h": 7,  "hr25": 29},
    {"n": "Juan Soto",         "t": "NYM", "hand": "L", "xhr": 8,  "sR": 7.50, "sL": 8.00, "h": 10, "hr25": 43},
    {"n": "Pete Alonso",       "t": "BAL", "hand": "R", "xhr": 9,  "sR": 7.43, "sL": 8.50, "h": 10, "hr25": 38},
    {"n": "Freddie Freeman",   "t": "LAD", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 6.50, "h": 6,  "hr25": 24},
    {"n": "Riley Greene",      "t": "DET", "hand": "L", "xhr": 8,  "sR": 0.88, "sL": 3.50, "h": 9,  "hr25": 36},
    {"n": "Marcell Ozuna",     "t": "PIT", "hand": "R", "xhr": 5,  "sR": 8.50, "sL": 7.50, "h": 5,  "hr25": 21},
    {"n": "CJ Abrams",        "t": "WSH", "hand": "L", "xhr": 4,  "sR": 7.65, "sL": 4.50, "h": 5,  "hr25": 18},
    {"n": "Rafael Devers",     "t": "SF",  "hand": "L", "xhr": 6,  "sR": 2.90, "sL": 5.50, "h": 8,  "hr25": 33},
    {"n": "Tyler O'Neill",     "t": "BAL", "hand": "R", "xhr": 8,  "sR": 5.00, "sL": 7.50, "h": 3,  "hr25": 10},
    {"n": "Francisco Lindor",  "t": "NYM", "hand": "B", "xhr": 4,  "sR": 7.78, "sL": 7.00, "h": 8,  "hr25": 31},
    {"n": "Michael Harris II", "t": "ATL", "hand": "L", "xhr": 4,  "sR": 8.82, "sL": 4.00, "h": 5,  "hr25": 20},
    {"n": "José Ramírez",      "t": "CLE", "hand": "B", "xhr": 4,  "sR": 7.86, "sL": 8.50, "h": 8,  "hr25": 30},
    {"n": "Oneil Cruz",        "t": "PIT", "hand": "L", "xhr": 7,  "sR": 9.47, "sL": 5.00, "h": 5,  "hr25": 19},
    {"n": "Ketel Marte",       "t": "AZ",  "hand": "B", "xhr": 7,  "sR": 6.80, "sL": 8.00, "h": 7,  "hr25": 27},
    {"n": "Corbin Carroll",    "t": "AZ",  "hand": "L", "xhr": 7,  "sR": 7.50, "sL": 4.50, "h": 8,  "hr25": 31},
    {"n": "Willy Adames",      "t": "SF",  "hand": "R", "xhr": 5,  "sR": 3.57, "sL": 6.50, "h": 7,  "hr25": 29},
    {"n": "Teoscar Hernández", "t": "LAD", "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 8.00, "h": 6,  "hr25": 25},
    {"n": "Jorge Polanco",     "t": "NYM", "hand": "B", "xhr": 5,  "sR": 8.33, "sL": 6.50, "h": 6,  "hr25": 25},
    {"n": "Dominic Canzone",   "t": "SEA", "hand": "L", "xhr": 7,  "sR": 9.00, "sL": 4.00, "h": 3,  "hr25": 12},
    {"n": "Dylan Crews",       "t": "WSH", "hand": "R", "xhr": 5,  "sR": 10,   "sL": 6.00, "h": 3,  "hr25": 10},
    {"n": "Colton Cowser",     "t": "BAL", "hand": "L", "xhr": 5,  "sR": 7.33, "sL": 5.00, "h": 4,  "hr25": 16},
    {"n": "Lenyn Sosa",        "t": "CWS", "hand": "R", "xhr": 5,  "sR": 7.50, "sL": 7.00, "h": 6,  "hr25": 22},
    {"n": "Wyatt Langford",    "t": "TEX", "hand": "R", "xhr": 5,  "sR": 7.62, "sL": 6.50, "h": 5,  "hr25": 21},
    {"n": "Jackson Holliday",  "t": "BAL", "hand": "L", "xhr": 5,  "sR": 7.65, "sL": 4.50, "h": 4,  "hr25": 17},
    {"n": "Roman Anthony",     "t": "BOS", "hand": "L", "xhr": 6,  "sR": 7.50, "sL": 5.00, "h": 2,  "hr25": 8},
    {"n": "Kristian Campbell", "t": "BOS", "hand": "R", "xhr": 5,  "sR": 7.17, "sL": 7.50, "h": 2,  "hr25": 6},
    {"n": "Cam Smith",         "t": "HOU", "hand": "R", "xhr": 6,  "sR": 5.56, "sL": 6.50, "h": 2,  "hr25": 9},
    {"n": "Jac Caglianone",    "t": "KC",  "hand": "L", "xhr": 7,  "sR": 5.00, "sL": 3.50, "h": 2,  "hr25": 6},
    {"n": "Jose Altuve",       "t": "HOU", "hand": "R", "xhr": 3,  "sR": 7.20, "sL": 7.50, "h": 7,  "hr25": 26},
    {"n": "Spencer Horwitz",   "t": "PIT", "hand": "L", "xhr": 4,  "sR": 8.89, "sL": 4.00, "h": 3,  "hr25": 11},
    {"n": "Josh Naylor",       "t": "SEA", "hand": "L", "xhr": 4,  "sR": 6.84, "sL": 5.50, "h": 5,  "hr25": 20},
    {"n": "Drake Baldwin",     "t": "ATL", "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 7.00, "h": 5,  "hr25": 19},
    # ── Additional players (expanded roster) ──
    # AZ
    {"n": "Geraldo Perdomo",   "t": "AZ",  "hand": "B", "xhr": 5,  "sR": 6.50, "sL": 5.50, "h": 6,  "hr25": 20},
    {"n": "Gabriel Moreno",    "t": "AZ",  "hand": "R", "xhr": 4,  "sR": 6.00, "sL": 7.00, "h": 5,  "hr25": 17},
    # ATL
    {"n": "Sean Murphy",       "t": "ATL", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 5,  "hr25": 17},
    # BAL
    {"n": "Adley Rutschman",   "t": "BAL", "hand": "B", "xhr": 5,  "sR": 6.50, "sL": 6.00, "h": 5,  "hr25": 18},
    # BOS
    {"n": "Wilyer Abreu",      "t": "BOS", "hand": "L", "xhr": 6,  "sR": 7.50, "sL": 4.50, "h": 6,  "hr25": 22},
    {"n": "Trevor Story",      "t": "BOS", "hand": "R", "xhr": 6,  "sR": 7.80, "sL": 8.00, "h": 7,  "hr25": 25},
    {"n": "Willson Contreras",  "t": "BOS", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 20},
    # CHC
    {"n": "Dansby Swanson",    "t": "CHC", "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 7.80, "h": 7,  "hr25": 24},
    {"n": "Ian Happ",          "t": "CHC", "hand": "B", "xhr": 6,  "sR": 7.00, "sL": 7.50, "h": 7,  "hr25": 23},
    {"n": "Kyle Tucker",       "t": "LAD", "hand": "L", "xhr": 6,  "sR": 7.50, "sL": 5.50, "h": 6,  "hr25": 22},
    # CIN
    {"n": "Elly De La Cruz",   "t": "CIN", "hand": "B", "xhr": 6,  "sR": 7.00, "sL": 6.50, "h": 6,  "hr25": 22},
    {"n": "Spencer Steer",     "t": "CIN", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 21},
    {"n": "Tyler Stephenson",  "t": "CIN", "hand": "R", "xhr": 4,  "sR": 6.50, "sL": 7.00, "h": 5,  "hr25": 15},
    # CLE
    {"n": "Bo Naylor",         "t": "CLE", "hand": "L", "xhr": 5,  "sR": 6.50, "sL": 4.00, "h": 5,  "hr25": 17},
    # COL
    {"n": "Hunter Goodman",    "t": "COL", "hand": "R", "xhr": 7,  "sR": 8.00, "sL": 8.50, "h": 8,  "hr25": 31},
    {"n": "Brenton Doyle",     "t": "COL", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 6.50, "h": 6,  "hr25": 18},
    {"n": "Ezequiel Tovar",    "t": "COL", "hand": "R", "xhr": 5,  "sR": 6.80, "sL": 7.00, "h": 6,  "hr25": 16},
    # CWS
    {"n": "Andrew Benintendi", "t": "CWS", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 4.50, "h": 6,  "hr25": 20},
    # DET
    {"n": "Spencer Torkelson", "t": "DET", "hand": "R", "xhr": 7,  "sR": 7.80, "sL": 8.50, "h": 8,  "hr25": 31},
    {"n": "Kerry Carpenter",   "t": "DET", "hand": "L", "xhr": 7,  "sR": 8.00, "sL": 5.00, "h": 7,  "hr25": 26},
    {"n": "Dillon Dingler",    "t": "DET", "hand": "R", "xhr": 4,  "sR": 6.50, "sL": 7.00, "h": 5,  "hr25": 16},
    # HOU
    {"n": "Yainer Diaz",       "t": "HOU", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.00, "h": 6,  "hr25": 20},
    {"n": "Isaac Paredes",     "t": "HOU", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 20},
    # KC
    {"n": "MJ Melendez",       "t": "KC",  "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 4.00, "h": 5,  "hr25": 16},
    # LAA
    {"n": "Zach Neto",         "t": "LAA", "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 8.00, "h": 7,  "hr25": 26},
    {"n": "Logan O'Hoppe",     "t": "LAA", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 19},
    # LAD
    {"n": "Mookie Betts",      "t": "LAD", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 20},
    {"n": "Max Muncy",         "t": "LAD", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 5.50, "h": 6,  "hr25": 19},
    # MIA
    {"n": "Kyle Stowers",      "t": "MIA", "hand": "L", "xhr": 6,  "sR": 7.50, "sL": 4.50, "h": 7,  "hr25": 25},
    {"n": "Agustín Ramírez",   "t": "MIA", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 21},
    {"n": "Connor Norby",      "t": "MIA", "hand": "R", "xhr": 4,  "sR": 6.50, "sL": 7.00, "h": 5,  "hr25": 14},
    # MIL
    {"n": "Christian Yelich",  "t": "MIL", "hand": "L", "xhr": 7,  "sR": 8.00, "sL": 5.50, "h": 8,  "hr25": 29},
    {"n": "William Contreras", "t": "MIL", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 5,  "hr25": 17},
    {"n": "Jackson Chourio",   "t": "MIL", "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 7.00, "h": 6,  "hr25": 21},
    {"n": "Garrett Mitchell",  "t": "MIL", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 4.50, "h": 5,  "hr25": 15},
    # MIN
    {"n": "Matt Wallner",      "t": "MIN", "hand": "L", "xhr": 6,  "sR": 7.50, "sL": 4.50, "h": 6,  "hr25": 22},
    {"n": "Kody Clemens",      "t": "MIN", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 4.50, "h": 6,  "hr25": 19},
    {"n": "Ryan Jeffers",      "t": "MIN", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.00, "h": 5,  "hr25": 18},
    # NYM
    {"n": "Brandon Nimmo",     "t": "TEX", "hand": "L", "xhr": 6,  "sR": 7.50, "sL": 5.00, "h": 7,  "hr25": 25},
    # NYY
    {"n": "Austin Wells",      "t": "NYY", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 4.50, "h": 6,  "hr25": 21},
    {"n": "Anthony Volpe",     "t": "NYY", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 19},
    {"n": "Ryan McMahon",      "t": "NYY", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 5.00, "h": 6,  "hr25": 20},
    # PHI
    {"n": "Bryce Harper",      "t": "PHI", "hand": "L", "xhr": 7,  "sR": 8.00, "sL": 6.50, "h": 8,  "hr25": 27},
    {"n": "Adolis García",     "t": "PHI", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 19},
    {"n": "J.T. Realmuto",     "t": "PHI", "hand": "R", "xhr": 4,  "sR": 6.50, "sL": 7.00, "h": 5,  "hr25": 15},
    # PIT
    {"n": "Ke'Bryan Hayes",    "t": "PIT", "hand": "R", "xhr": 4,  "sR": 6.00, "sL": 6.50, "h": 4,  "hr25": 13},
    # SD
    {"n": "Manny Machado",     "t": "SD",  "hand": "R", "xhr": 7,  "sR": 7.80, "sL": 8.50, "h": 7,  "hr25": 27},
    {"n": "Fernando Tatis Jr.","t": "SD",  "hand": "R", "xhr": 7,  "sR": 8.00, "sL": 8.50, "h": 7,  "hr25": 25},
    {"n": "Ramón Laureano",    "t": "SD",  "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 7.00, "h": 7,  "hr25": 24},
    {"n": "Gavin Sheets",      "t": "SD",  "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 4.50, "h": 6,  "hr25": 19},
    # SEA
    {"n": "Randy Arozarena",   "t": "SEA", "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 7.00, "h": 7,  "hr25": 27},
    # SF
    {"n": "Matt Chapman",      "t": "SF",  "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 21},
    {"n": "Heliot Ramos",      "t": "SF",  "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 21},
    {"n": "Patrick Bailey",    "t": "SF",  "hand": "B", "xhr": 4,  "sR": 6.00, "sL": 5.50, "h": 5,  "hr25": 17},
    # STL
    {"n": "Iván Herrera",      "t": "STL", "hand": "R", "xhr": 5,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 19},
    {"n": "Pedro Pagés",       "t": "STL", "hand": "R", "xhr": 4,  "sR": 6.50, "sL": 7.00, "h": 5,  "hr25": 17},
    {"n": "Masyn Winn",        "t": "STL", "hand": "R", "xhr": 4,  "sR": 6.50, "sL": 7.00, "h": 5,  "hr25": 15},
    {"n": "Nolan Arenado",     "t": "STL", "hand": "R", "xhr": 4,  "sR": 6.50, "sL": 7.50, "h": 5,  "hr25": 14},
    # TB
    {"n": "Yandy Díaz",        "t": "TB",  "hand": "R", "xhr": 6,  "sR": 7.50, "sL": 7.00, "h": 7,  "hr25": 25},
    {"n": "Christopher Morel", "t": "TB",  "hand": "R", "xhr": 6,  "sR": 7.00, "sL": 7.50, "h": 6,  "hr25": 18},
    # TEX
    {"n": "Corey Seager",      "t": "TEX", "hand": "L", "xhr": 6,  "sR": 7.50, "sL": 5.00, "h": 6,  "hr25": 21},
    # TOR
    {"n": "Vladimir Guerrero Jr.","t":"TOR","hand": "R", "xhr": 6,  "sR": 7.50, "sL": 8.00, "h": 7,  "hr25": 23},
    {"n": "Addison Barger",    "t": "TOR", "hand": "L", "xhr": 5,  "sR": 7.00, "sL": 4.50, "h": 6,  "hr25": 21},
    # WSH
    {"n": "Keibert Ruiz",      "t": "WSH", "hand": "B", "xhr": 4,  "sR": 6.00, "sL": 5.50, "h": 5,  "hr25": 16},
]

# Fall back to hardcoded list if data/players.json doesn't exist
if not PLAYERS:
    PLAYERS = _HARDCODED_PLAYERS
    print(f"  📦 Using hardcoded player list ({len(PLAYERS)} players)")

# ═══════════════════════════════════════════════════════════════════════════════
# SCORING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def hr9_to_score(v):
    if not v or v <= 0.9: return 5
    if v <= 1.1: return 6
    if v <= 1.3: return 7
    if v <= 1.5: return 8
    if v <= 1.7: return 9
    return 10

def recent5_sc(v):
    table = [1, 3, 5, 7, 9, 10]
    return table[min(v or 0, 5)]

def recent10_sc(v):
    if not v: return 2
    if v <= 1: return 4
    if v <= 2: return 5
    if v <= 3: return 6
    if v <= 5: return 7
    if v <= 7: return 9
    return 10

def gap_score(hr26, gp26, hr25):
    """Score the gap between 2026 pace and 2025 total.

    Players behind their 2025 pace score higher (regression upward expected).
    Players ahead of pace score lower (already producing).
    """
    if not gp26 or gp26 <= 0:
        return 5  # not enough data
    pace_162 = (hr26 / gp26) * 162
    gap = pace_162 - hr25  # positive = ahead, negative = behind
    if gap <= -20: return 10   # way behind — strong regression candidate
    if gap <= -10: return 8
    if gap <= -5:  return 7
    if gap < 0:    return 6
    if gap == 0:   return 5    # on pace
    if gap <= 5:   return 4
    if gap <= 10:  return 3
    return 2                   # way ahead — less upside

def wind_score(speed_mph, wind_deg, out_bearing, is_dome, batter_hand):
    if is_dome:
        return 5
    effective_bearing = out_bearing if batter_hand == "L" else (out_bearing + 180) % 360
    diff2 = abs(wind_deg - effective_bearing) % 360
    if diff2 > 180:
        diff2 = 360 - diff2
    alignment = 1 - (diff2 / 180)
    speed_factor = min(speed_mph / 20, 1)
    raw = alignment * speed_factor
    return round(3 + raw * 6)

def park_score(home_team, batter_hand):
    park = PARK_FACTORS.get(home_team)
    if not park:
        return 5
    return park["R"] if batter_hand == "R" else park["L"]

def compute_score(f):
    return (
        f["homeAway"] + f["ballpark"] + f["lhpVsRhp"] + f["pitcherHR9"] +
        f["bullpen"] + f["xhr"] + f["hr2025"] + f["wind"] +
        f["recent5"] + f["recent10"] + f["seasonGap"] + f["bvp"]
    ) / 9


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def extract_json(text):
    """Try to parse JSON from Claude's response text."""
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    # Find first [ or {
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
    # Strip trailing commas
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def call_claude(prompt, retries=4, max_searches=2):
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

            # Try each text block, then joined
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
                        "Use the team codes exactly as specified. Fill in 'TBD' for missing pitchers "
                        "and '?' for missing pitcher hands. Your entire response must start with "
                        "[ or {{ and be valid JSON. Nothing else."
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


def fetch_wind(geo):
    """Fetch wind data from Open-Meteo."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={geo['lat']}&longitude={geo['lon']}"
            f"&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=mph&forecast_days=1"
        )
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return {
                "speed": data.get("current", {}).get("wind_speed_10m", 0) or 0,
                "deg": data.get("current", {}).get("wind_direction_10m", 0) or 0,
            }
    except Exception:
        return {"speed": 0, "deg": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# LOOKUP HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _normalize(name):
    """Lowercase, strip accents/special chars for matching."""
    import unicodedata
    name = unicodedata.normalize("NFD", name.lower())
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    return name.strip().replace(".", "").replace("'", "")


def lookup_player(name, data_map):
    """Look up a player in a Claude-returned dict by fuzzy name matching."""
    if not data_map or not isinstance(data_map, dict):
        return None
    norm = _normalize(name)
    last = norm.split()[-1] if norm.split() else ""
    # Pass 1: exact normalized match
    for k, v in data_map.items():
        if _normalize(k) == norm:
            return v
    # Pass 2: last-name match (both directions)
    for k, v in data_map.items():
        k_norm = _normalize(k)
        k_last = k_norm.split()[-1] if k_norm.split() else ""
        if last == k_last or last == k_norm or k_last == norm:
            return v
    # Pass 3: substring containment
    for k, v in data_map.items():
        k_norm = _normalize(k)
        if last in k_norm or k_norm.split()[-1] in norm:
            return v
    return None


def lookup_pitcher(name, data_map):
    """Look up a pitcher in a Claude-returned dict."""
    if not name or not data_map or not isinstance(data_map, dict):
        return 1.1
    result = lookup_player(name, data_map)
    return result if result is not None else 1.1


def is_in_lineup(player_name, team, lineups):
    team_lineup = lineups.get(team, [])
    if not team_lineup:
        return True  # assume playing if no data
    name_lower = player_name.lower()
    last_name = player_name.split()[-1].lower() if player_name.split() else ""
    for ln in team_lineup:
        if ln.lower() in name_lower or last_name in ln.lower():
            return True
    return False


# Build a lookup index from the PLAYERS database keyed by lowercase last name
PLAYER_DB = {}
for _p in PLAYERS:
    _last = _p["n"].split()[-1].lower()
    PLAYER_DB[_last] = _p
    PLAYER_DB[_p["n"].lower()] = _p

# League-average defaults for players not in the database
DEFAULT_PLAYER = {"hand": "R", "xhr": 5, "sR": 5.0, "sL": 5.0, "h": 5, "hr25": 15}


def find_player_attrs(full_name, team):
    """Look up a player in the static DB. Returns (attrs_dict, is_new)."""
    name_lower = full_name.lower()
    last_name = full_name.split()[-1].lower() if full_name.split() else ""
    # Exact full-name match
    if name_lower in PLAYER_DB:
        return PLAYER_DB[name_lower], False
    # Last-name match on same team
    if last_name in PLAYER_DB and PLAYER_DB[last_name]["t"] == team:
        return PLAYER_DB[last_name], False
    # Last-name match (any team, for traded players)
    if last_name in PLAYER_DB:
        return PLAYER_DB[last_name], False
    # Not found — use defaults
    return {**DEFAULT_PLAYER, "n": full_name, "t": team}, True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    today = datetime.now().strftime("%B %d, %Y")
    print(f"═══ HR Scout — Generating data for {today} ═══\n")

    team_codes = "NYY,BOS,TB,BAL,TOR,CLE,DET,CWS,MIN,KC,HOU,TEX,SEA,LAA,ATH,LAD,SF,SD,COL,AZ,ATL,NYM,PHI,MIL,CIN,PIT,STL,MIA,WSH"

    # MLB team ID → abbreviation mapping (from MLB Stats API)
    MLB_TEAM_ABBR = {
        108:"LAA", 109:"AZ", 110:"BAL", 111:"BOS", 112:"CHC", 113:"CIN",
        114:"CLE", 115:"COL", 116:"DET", 117:"HOU", 118:"KC", 119:"LAD",
        120:"WSH", 121:"NYM", 133:"ATH", 134:"PIT", 135:"SD", 136:"SEA",
        137:"SF", 138:"STL", 139:"TB", 140:"TEX", 141:"TOR", 142:"MIN",
        143:"PHI", 144:"ATL", 145:"CWS", 146:"MIA", 147:"NYY", 158:"MIL",
    }

    # ── STAGE 1: Schedule from MLB Stats API ──
    print("⚾ Stage 1: Fetching schedule from MLB Stats API...")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    sched_url = (
        f"https://statsapi.mlb.com/api/v1/schedule?"
        f"date={today_iso}&sportId=1&hydrate=probablePitcher"
    )
    sched = []
    pitcher_ids = {}  # id → {"lastName": ..., "games": [(game_dict, role), ...]}
    try:
        req = urllib.request.Request(sched_url, headers={"User-Agent": "HRScout/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            api_data = json.loads(resp.read())

        for date_entry in api_data.get("dates", []):
            for game_data in date_entry.get("games", []):
                teams = game_data.get("teams", {})
                home_info = teams.get("home", {})
                away_info = teams.get("away", {})

                home_id = home_info.get("team", {}).get("id")
                away_id = away_info.get("team", {}).get("id")
                home_code = MLB_TEAM_ABBR.get(home_id, "")
                away_code = MLB_TEAM_ABBR.get(away_id, "")
                if not home_code or not away_code:
                    continue

                home_pp = home_info.get("probablePitcher") or {}
                away_pp = away_info.get("probablePitcher") or {}

                home_name = home_pp.get("fullName", "").split()[-1] if home_pp.get("fullName") else "TBD"
                away_name = away_pp.get("fullName", "").split()[-1] if away_pp.get("fullName") else "TBD"

                g = {
                    "homeTeam": home_code,
                    "awayTeam": away_code,
                    "homePitcher": home_name,
                    "awayPitcher": away_name,
                    "homePitcherHand": "?",
                    "awayPitcherHand": "?",
                    "_homePitcherId": home_pp.get("id") if home_pp else None,
                    "_awayPitcherId": away_pp.get("id") if away_pp else None,
                }
                sched.append(g)

                # Collect pitcher IDs for batch hand lookup
                for pp, role in [(home_pp, "home"), (away_pp, "away")]:
                    pid = pp.get("id") if pp else None
                    if pid:
                        if pid not in pitcher_ids:
                            pitcher_ids[pid] = []
                        pitcher_ids[pid].append((g, role))

        print(f"  ✅ {len(sched)} games from MLB API")
    except Exception as e:
        print(f"  ⚠️ MLB API failed: {e}")

    # Batch fetch pitcher handedness from MLB People API
    if pitcher_ids:
        try:
            id_str = ",".join(str(i) for i in pitcher_ids)
            people_url = f"https://statsapi.mlb.com/api/v1/people?personIds={id_str}"
            req = urllib.request.Request(people_url, headers={"User-Agent": "HRScout/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                people_data = json.loads(resp.read())

            hand_map = {}
            for person in people_data.get("people", []):
                hand_map[person["id"]] = person.get("pitchHand", {}).get("code", "?")

            for pid, game_roles in pitcher_ids.items():
                hand = hand_map.get(pid, "?")
                for g, role in game_roles:
                    g[f"{role}PitcherHand"] = hand

            filled = sum(1 for g in sched if g["homePitcherHand"] != "?" or g["awayPitcherHand"] != "?")
            print(f"  ✅ Pitcher hands resolved for {filled} games")
        except Exception as e:
            print(f"  ⚠️ People API failed: {e}")

    # Fallback: if API returned nothing, try Claude web search
    if not sched:
        print("  ⚠️ Falling back to Claude web search...")
        fallback = call_claude(
            f"Today is {today}. Go to https://www.mlb.com/schedule and find today's full MLB schedule. "
            f"Return ONLY a JSON array with every game: "
            f'[{{"homeTeam":"NYY","awayTeam":"BOS","homePitcher":"Cole","awayPitcher":"Sale",'
            f'"homePitcherHand":"R","awayPitcherHand":"L"}}]. '
            f"Use ONLY these team codes: {team_codes}. "
            f'Use "TBD" for unknown pitchers and "?" for unknown hands.',
            max_searches=5,
        )
        sched = fallback if isinstance(fallback, list) else []

    if not sched:
        print("❌ Failed to get schedule. Exiting.")
        return
    print(f"  ✅ {len(sched)} games loaded\n")

    # ── STAGE 2: Lineups ──
    teams_today = set()
    for g in sched:
        teams_today.add(g.get("homeTeam", ""))
        teams_today.add(g.get("awayTeam", ""))
    team_list = ",".join(sorted(teams_today))

    print("📋 Stage 2: Fetching confirmed lineups...")
    lineups_raw = call_claude(
        f"Today is {today}. Search for today's confirmed MLB starting lineups for: {team_list}. "
        f'Return ONLY a JSON object: {{"NYY":["Aaron Judge","Giancarlo Stanton","Juan Soto"],"BOS":["Rafael Devers"],...}}. '
        f"Use full first and last names for each batter. Include only confirmed starters. "
        f"If lineups not yet posted for a team, omit that team. If no lineups at all, return {{}}.",
        max_searches=5,
    )
    lineups = lineups_raw if isinstance(lineups_raw, dict) else {}
    lineup_count = sum(len(v) for v in lineups.values() if isinstance(v, list))
    print(f"  ✅ {lineup_count} batters across {len(lineups)} lineups\n")
    time.sleep(3)

    # ── STAGE 2b: IL check from MLB Stats API ──
    # Only flags players on the official 10-day or 60-day IL, not day-to-day
    # or minor-league reassignments. Source: team roster status codes.
    print("🏥 Stage 2b: Checking injured list via MLB API...")
    il_names = set()
    try:
        for tid in MLB_TEAM_ABBR:
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{tid}/roster?rosterType=fullSeason&season={datetime.now().year}"
            req = urllib.request.Request(roster_url, headers={"User-Agent": "HRScout/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                roster_data = json.loads(resp.read())
            for person in roster_data.get("roster", []):
                status_desc = person.get("status", {}).get("description", "")
                pos_code = person.get("position", {}).get("code", "")
                # Only official IL stints (10-day, 15-day, 60-day), not day-to-day
                if "Injured" in status_desc and pos_code != "1":
                    il_names.add(_normalize(person["person"]["fullName"]))
                    print(f"    {person['person']['fullName']}: {status_desc}")
        print(f"  ✅ {len(il_names)} position players on IL")
    except Exception as e:
        print(f"  ⚠️ IL check failed: {e}")
    print()

    def is_on_il(player_name):
        return _normalize(player_name) in il_names

    # ── STAGE 3: Pitcher HR/9 from MLB Stats API ──
    print("📊 Stage 3: Fetching pitcher HR/9 from MLB Stats API...")
    pitcher_hr9 = {}  # keyed by last name
    all_pitcher_ids = set()
    for g in sched:
        for role in ("_homePitcherId", "_awayPitcherId"):
            pid = g.get(role)
            if pid:
                all_pitcher_ids.add(pid)

    if all_pitcher_ids:
        try:
            season = datetime.now().year
            id_str = ",".join(str(i) for i in all_pitcher_ids)
            stats_url = (
                f"https://statsapi.mlb.com/api/v1/people?personIds={id_str}"
                f"&hydrate=stats(group=[pitching],type=[season],season={season})"
            )
            req = urllib.request.Request(stats_url, headers={"User-Agent": "HRScout/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                pdata = json.loads(resp.read())

            for person in pdata.get("people", []):
                last_name = person.get("lastName", "")
                stats_list = person.get("stats", [])
                hr9 = 1.1  # default
                for stat_group in stats_list:
                    splits = stat_group.get("splits", [])
                    if splits:
                        s = splits[0].get("stat", {})
                        ip = float(s.get("inningsPitched", "0") or "0")
                        hr_allowed = int(s.get("homeRuns", 0) or 0)
                        if ip >= 1:
                            hr9 = round((hr_allowed / ip) * 9, 2)
                if last_name:
                    pitcher_hr9[last_name] = hr9
                    print(f"    {last_name}: HR/9={pitcher_hr9[last_name]} → score {hr9_to_score(pitcher_hr9[last_name])}")

            print(f"  ✅ {len(pitcher_hr9)} pitchers from MLB API")
        except Exception as e:
            print(f"  ⚠️ MLB Stats API failed for pitchers: {e}")

    if not pitcher_hr9:
        print("  ⚠️ Falling back to Claude for pitcher HR/9...")
        pitcher_names = set()
        for g in sched:
            if g.get("homePitcher") and g["homePitcher"] != "TBD":
                pitcher_names.add(g["homePitcher"])
            if g.get("awayPitcher") and g["awayPitcher"] != "TBD":
                pitcher_names.add(g["awayPitcher"])
        pitcher_hr9_raw = call_claude(
            f"Search for the current {datetime.now().year} MLB season HR per 9 innings (HR/9) for: "
            f"{', '.join(sorted(pitcher_names))}. "
            f'Return ONLY JSON: {{"Sale":0.9,"Kirby":1.4,...}}. Use last names as keys. Default 1.1 for unknowns.',
        )
        pitcher_hr9 = pitcher_hr9_raw if isinstance(pitcher_hr9_raw, dict) else {}
    print()

    # ── Build active player list from lineups ──
    active = []
    new_players = set()  # names not in the static DB
    if lineup_count > 0:
        for team, names in lineups.items():
            if not isinstance(names, list):
                continue
            for full_name in names:
                if not isinstance(full_name, str):
                    continue
                attrs, is_new = find_player_attrs(full_name, team)
                active.append({
                    "n": full_name,
                    "t": team,
                    "hand": attrs.get("hand", "R"),
                    "xhr": attrs.get("xhr", 5),
                    "sR": attrs.get("sR", 5.0),
                    "sL": attrs.get("sL", 5.0),
                    "h": attrs.get("h", 5),
                    "hr25": attrs.get("hr25", 15),
                })
                if is_new:
                    new_players.add(full_name)
        print(f"  📋 {len(active)} batters from lineups ({len(new_players)} new)")
    else:
        # Fallback to static DB if no lineups available
        active = [p for p in PLAYERS if p["t"] in teams_today]
        print(f"  📋 {len(active)} batters from static DB (no lineups)")

    # ── STAGE 4: xHR + EV trends (batched) ──
    print("🎯 Stage 4: Fetching xHR rates & EV trends...")
    stats_map = {}
    all_active_names = [p["n"] for p in active]
    stats_batch_size = 15
    stats_prompt_tmpl = (
        "Today is {date}. Search Baseball Savant for current {year} expected home runs (xHR) "
        "and recent exit velocity trends for: {names}. "
        'Return ONLY JSON using the EXACT player names I gave you as keys: '
        '{{"Aaron Judge":{{"xhrPer600":8.2,"evTrend":1.5}},...}}. '
        "evTrend = change in avg exit velocity last 14 days vs prior 14 (e.g. +1.5 = trending harder). "
        "xhrPer600 = expected HRs per 600 PA. Default: xhrPer600:3, evTrend:0 if no data."
    )
    for i in range(0, len(all_active_names), stats_batch_size):
        batch = all_active_names[i:i + stats_batch_size]
        batch_label = f"({i // stats_batch_size + 1}/{(len(all_active_names) + stats_batch_size - 1) // stats_batch_size})"
        print(f"  🎯 Fetching xHR/EV batch {batch_label}...")
        batch_raw = call_claude(
            stats_prompt_tmpl.format(
                date=today, year=datetime.now().year, names=", ".join(batch)
            ),
            max_searches=5,
        )
        if isinstance(batch_raw, dict):
            stats_map.update(batch_raw)
        time.sleep(3)
    print(f"  ✅ {len(stats_map)} players\n")

    # ── STAGE 5: Wind ──
    print("🌬️ Stage 5: Fetching wind data...")
    unique_home = list({g.get("homeTeam", "") for g in sched})
    wind_data = {}
    for team in unique_home:
        geo = BALLPARK_GEO.get(team)
        if geo and team not in DOMES:
            wind_data[team] = fetch_wind(geo)
        else:
            wind_data[team] = {"speed": 0, "deg": 0}
    outdoor = sum(1 for t in unique_home if t not in DOMES)
    print(f"  ✅ Wind fetched for {outdoor} outdoor parks\n")

    # ── STAGE 6: Recent form from MLB Stats API ──
    print("🔥 Stage 6: Fetching recent HR form from MLB Stats API...")
    recent_map = {}
    season = datetime.now().year

    # Step 1: Build name→ID index from MLB active roster
    print("  🔍 Loading MLB player roster...")
    mlb_id_by_name = {}
    mlb_id_by_last_team = {}
    try:
        roster_url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}&gameType=R"
        req = urllib.request.Request(roster_url, headers={"User-Agent": "HRScout/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            roster_data = json.loads(resp.read())

        for person in roster_data.get("people", []):
            pos_code = person.get("primaryPosition", {}).get("code", "")
            if pos_code == "1":  # skip pitchers
                continue
            pid = person["id"]
            full_norm = _normalize(person.get("fullName", ""))
            last_norm = _normalize(person.get("lastName", ""))
            team_abbr = person.get("currentTeam", {}).get("abbreviation", "")
            mlb_id_by_name[full_norm] = pid
            mlb_id_by_last_team[(last_norm, team_abbr)] = pid

        print(f"  ✅ {len(mlb_id_by_name)} hitters indexed")
    except Exception as e:
        print(f"  ⚠️ Roster fetch failed: {e}")

    # Step 2: Resolve active player names to MLB IDs
    player_ids_to_fetch = {}  # pid → player_name
    unresolved = []
    for p in active:
        name_norm = _normalize(p["n"])
        last_norm = name_norm.split()[-1] if name_norm.split() else ""
        pid = mlb_id_by_name.get(name_norm)
        if not pid:
            pid = mlb_id_by_last_team.get((last_norm, p["t"]))
        if pid:
            player_ids_to_fetch[pid] = p["n"]
        else:
            unresolved.append(p["n"])

    if unresolved:
        print(f"  ⚠️ Could not resolve MLB IDs for {len(unresolved)} players: {', '.join(unresolved[:5])}...")

    # Step 3: Batch fetch game logs (groups of 50 to avoid URL length limits)
    batch_size = 50
    id_list = list(player_ids_to_fetch.keys())
    for i in range(0, len(id_list), batch_size):
        batch_ids = id_list[i:i + batch_size]
        try:
            id_str = ",".join(str(pid) for pid in batch_ids)
            stats_url = (
                f"https://statsapi.mlb.com/api/v1/people?personIds={id_str}"
                f"&hydrate=stats(group=[hitting],type=[gameLog],season={season})"
            )
            req = urllib.request.Request(stats_url, headers={"User-Agent": "HRScout/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                stats_data = json.loads(resp.read())

            for person in stats_data.get("people", []):
                pid = person["id"]
                player_name = player_ids_to_fetch.get(pid, "")
                for stat_group in person.get("stats", []):
                    splits = stat_group.get("splits", [])
                    last5 = splits[-5:]
                    last10 = splits[-10:]
                    hr5 = sum(s.get("stat", {}).get("homeRuns", 0) for s in last5)
                    hr10 = sum(s.get("stat", {}).get("homeRuns", 0) for s in last10)
                    gp = len(splits)
                    total_hr = sum(s.get("stat", {}).get("homeRuns", 0) for s in splits)
                    recent_map[player_name] = {
                        "r5": hr5, "r10": hr10,
                        "hr26": total_hr, "gp26": gp,
                    }
        except Exception as e:
            print(f"  ⚠️ Game log batch failed: {e}")

    matched = sum(1 for p in active if p["n"] in recent_map)
    print(f"  ✅ {matched}/{len(active)} players with game log data\n")

    # Build reverse map: player_name → batter MLB ID (for BvP lookups)
    batter_id_by_name = {v: k for k, v in player_ids_to_fetch.items()}

    # ── STAGE 6b: Batter vs Pitcher (BvP) ──
    print("⚔️ Stage 6b: Fetching Batter vs Pitcher history...")
    bvp_map = {}  # player_name → {"score": int, "ab": int}

    def bvp_score_from_rate(ab, hr):
        """Score BvP factor 0-10 based on HR/AB rate."""
        if ab < 10:
            return 5  # neutral for small sample
        rate = hr / ab if ab > 0 else 0
        if rate >= 0.15:
            return 10
        if rate >= 0.10:
            return 8
        if rate >= 0.05:
            return 6
        if rate >= 0.01:
            return 4
        return 2

    bvp_fetched = 0
    bvp_errors = 0
    for p in active:
        batter_mlb_id = batter_id_by_name.get(p["n"])
        if not batter_mlb_id:
            continue
        game = next((g for g in sched if g.get("homeTeam") == p["t"] or g.get("awayTeam") == p["t"]), None)
        if not game:
            continue
        is_home = game.get("homeTeam") == p["t"]
        pitcher_id = game.get("_awayPitcherId") if is_home else game.get("_homePitcherId")
        if not pitcher_id:
            continue
        try:
            bvp_url = (
                f"https://statsapi.mlb.com/api/v1/people/{batter_mlb_id}/stats"
                f"?stats=vsPlayer&opposingPlayerId={pitcher_id}&group=hitting"
            )
            req = urllib.request.Request(bvp_url, headers={"User-Agent": "HRScout/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                bvp_data = json.loads(resp.read())
            splits = bvp_data.get("stats", [{}])[0].get("splits", [])
            total_ab = sum(s.get("stat", {}).get("atBats", 0) for s in splits)
            total_hr = sum(s.get("stat", {}).get("homeRuns", 0) for s in splits)
            bvp_map[p["n"]] = {"score": bvp_score_from_rate(total_ab, total_hr), "ab": total_ab}
            bvp_fetched += 1
        except Exception:
            bvp_errors += 1

    print(f"  ✅ BvP fetched for {bvp_fetched} batters ({bvp_errors} errors)\n")

    # ── STAGE 7: Score & rank ──
    print("🏆 Stage 7: Computing scores...")

    # Diagnostic: show match rates
    _hr9_hits = sum(1 for g in sched for role in ("homePitcher", "awayPitcher")
                    if lookup_player(g.get(role, "TBD"), pitcher_hr9) is not None)
    _hr9_total = sum(1 for g in sched for role in ("homePitcher", "awayPitcher")
                     if g.get(role, "TBD") != "TBD")
    _xhr_hits = sum(1 for p in active if lookup_player(p["n"], stats_map) is not None)
    _rec_hits = sum(1 for p in active if lookup_player(p["n"], recent_map) is not None)
    print(f"  📊 Match rates: pitcherHR9={_hr9_hits}/{_hr9_total}, "
          f"xHR/EV={_xhr_hits}/{len(active)}, recent={_rec_hits}/{len(active)}")

    scored = []
    for p in active:
        game = next((g for g in sched if g.get("homeTeam") == p["t"] or g.get("awayTeam") == p["t"]), None)
        if not game:
            continue

        is_home = game.get("homeTeam") == p["t"]
        opp_team = game.get("awayTeam") if is_home else game.get("homeTeam")
        opp_pitcher = game.get("awayPitcher") if is_home else game.get("homePitcher")
        opp_pitcher_hand = game.get("awayPitcherHand") if is_home else game.get("homePitcherHand")

        hr9_val = lookup_pitcher(opp_pitcher, pitcher_hr9)
        lhp_vs_rhp = p["sL"] if opp_pitcher_hand == "L" else p["sR"]

        park = park_score(game.get("homeTeam", ""), p["hand"])
        wind = wind_data.get(game.get("homeTeam", ""), {"speed": 0, "deg": 0})
        geo = BALLPARK_GEO.get(game.get("homeTeam", ""))
        w_score = wind_score(
            wind["speed"], wind["deg"],
            geo["outBearing"] if geo else 0,
            game.get("homeTeam", "") in DOMES,
            p["hand"],
        ) if geo else 5

        stats = lookup_player(p["n"], stats_map)
        xhr_per_600 = stats.get("xhrPer600") if stats else None
        xhr_score = min(10, max(1, round(xhr_per_600 * 1.2))) if xhr_per_600 else p["xhr"]

        ev_trend = stats.get("evTrend") if stats else None
        ev_score = min(10, max(1, 5 + round(ev_trend * 1.5))) if ev_trend is not None else 5

        recent = lookup_player(p["n"], recent_map) or {"r5": 0, "r10": 0, "hr26": 0, "gp26": 0}
        r5 = recent.get("r5", 0) if isinstance(recent, dict) else 0
        r10 = recent.get("r10", 0) if isinstance(recent, dict) else 0
        hr26 = recent.get("hr26", 0) if isinstance(recent, dict) else 0
        gp26 = recent.get("gp26", 0) if isinstance(recent, dict) else 0

        bvp = bvp_map.get(p["n"], {"score": 5, "ab": 0})
        bvp_sc = bvp["score"]
        bvp_ab = bvp["ab"]

        factors = {
            "homeAway": 5 if is_home else 2,
            "ballpark": park,
            "lhpVsRhp": lhp_vs_rhp,
            "pitcherHR9": hr9_to_score(hr9_val),
            "bullpen": BULLPEN.get(opp_team, 6),
            "xhr": xhr_score,
            "hr2025": p["h"],
            "wind": w_score,
            "recent5": recent5_sc(r5),
            "recent10": recent10_sc(r10),
            "seasonGap": gap_score(hr26, gp26, p["hr25"]),
            "bvp": bvp_sc,
        }

        # Flags
        flags = []
        if is_on_il(p["n"]):
            flags.append("IL")
        if p["n"] in new_players:
            flags.append("NEW")

        scored.append({
            "name": p["n"],
            "team": p["t"],
            "hand": p["hand"],
            "score": round(compute_score(factors), 2),
            "factors": factors,
            "matchup": f"{'vs' if is_home else '@'} {opp_team}",
            "pitcher": opp_pitcher or "TBD",
            "pitcherHand": opp_pitcher_hand or "?",
            "parkName": PARK_FACTORS.get(game.get("homeTeam", ""), {}).get("name", game.get("homeTeam", "")),
            "windInfo": {
                "speed": wind["speed"],
                "deg": wind["deg"],
                "score": w_score,
                "isDome": game.get("homeTeam", "") in DOMES,
            },
            "xhrScore": xhr_score,
            "evScore": ev_score,
            "bvpScore": bvp_sc,
            "bvpAb": bvp_ab,
            "recent": {"r5": r5, "r10": r10},
            "flags": flags,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    # ── STAGE 8: Apply committed FD odds ──
    print("💰 Stage 8: Applying FanDuel odds from todays_odds.json...")

    def vegas_modifier(odds_val):
        if odds_val <= 200:
            return 0.5
        if odds_val <= 400:
            return 0
        if odds_val <= 600:
            return -0.3
        return -0.5

    odds_map = {}
    odds_path = Path(__file__).resolve().parent.parent / "data" / "todays_odds.json"
    today_iso = datetime.now().strftime("%Y-%m-%d")
    try:
        if odds_path.exists():
            odds_data = json.loads(odds_path.read_text())
            if odds_data.get("date") == today_iso:
                odds_map = odds_data.get("odds", {})
                print(f"  📋 Loaded {len(odds_map)} odds entries for {today_iso}")
            else:
                print(f"  ⚠️ Date mismatch: file has {odds_data.get('date')}, today is {today_iso} — skipping")
        else:
            print("  ⚠️ todays_odds.json not found — all players get base score as adjScore")
    except Exception as e:
        print(f"  ⚠️ Failed to read todays_odds.json: {e}")

    odds_matched = 0
    for player in scored:
        odds_str = odds_map.get(player["name"])
        if odds_str:
            try:
                parsed = int(odds_str.replace("+", "").strip())
                mod = vegas_modifier(parsed)
                player["adjScore"] = round(player["score"] + mod, 2)
                player["fdOdds"] = odds_str
                odds_matched += 1
            except (ValueError, TypeError):
                player["adjScore"] = player["score"]
                player["fdOdds"] = None
        else:
            player["adjScore"] = player["score"]
            player["fdOdds"] = None

    print(f"  ✅ Applied odds for {odds_matched}/{len(scored)} players\n")

    # Strip internal-only fields from schedule before output
    clean_sched = [
        {k: v for k, v in g.items() if not k.startswith("_")}
        for g in sched
    ]

    output = {
        "date": today,
        "generatedAt": datetime.now().isoformat(),
        "games": clean_sched,
        "players": scored,
        "windData": wind_data,
    }

    out_path = Path(__file__).parent.parent / "public" / "data.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n✅ Done! Wrote {len(scored)} players to {out_path}")

    # ── Append to history.json (preserving existing hitHR state) ──
    hist_path = Path(__file__).parent.parent / "public" / "history.json"
    try:
        history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    except (json.JSONDecodeError, OSError):
        history = []

    # If today already exists, preserve hitHR values from the existing entry
    existing_hr = {}
    for h in history:
        if h.get("date") == today:
            for p in h.get("players", []):
                if p.get("hitHR"):
                    existing_hr[p["name"]] = True
            break

    # Remove the old entry for today (scores/ranks may have changed on re-run)
    history = [h for h in history if h.get("date") != today]

    day_entry = {
        "date": today,
        "generatedAt": datetime.now().isoformat(),
        "players": [
            {
                "name": p["name"],
                "team": p["team"],
                "rank": i + 1,
                "score": p["score"],
                "hitHR": existing_hr.get(p["name"], False),
                "home_away_score": p["factors"]["homeAway"],
                "park_score": p["factors"]["ballpark"],
                "pitcher_hand_split_score": p["factors"]["lhpVsRhp"],
                "pitcher_hr9_score": p["factors"]["pitcherHR9"],
                "bullpen_hr9_score": p["factors"]["bullpen"],
                "xhr_score": p["factors"]["xhr"],
                "season_hr_score": p["factors"]["hr2025"],
                "wind_score": p["factors"]["wind"],
                "bvp_score": p["factors"]["bvp"],
                "recent_5_score": p["factors"]["recent5"],
                "recent_10_score": p["factors"]["recent10"],
                "season_gap_score": p["factors"]["seasonGap"],
            }
            for i, p in enumerate(scored)
        ],
    }
    history.append(day_entry)
    hist_path.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    preserved = sum(1 for p in day_entry["players"] if p["hitHR"])
    print(f"📜 History updated: {len(day_entry['players'])} players for {today}"
          f"{f' ({preserved} hitHR preserved)' if preserved else ''}")


if __name__ == "__main__":
    main()
