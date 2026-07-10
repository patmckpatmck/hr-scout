#!/usr/bin/env python3
"""
validate_market.py — does HR Scout's calibrated model beat the betting market?

Joins the calibrated model's per-player P(HR) (from public/history.json scores +
public/calibration.json) against hr_favorites_odds_picks.csv on (date, normalized
name), then compares model vs. market consensus on the overlap set:

  (a) Brier score of model vs. Brier score of market on the overlap picks
  (b) model's top-3 daily scores: actual hit rate vs. their market implied prob
  (c) biggest model-vs-market disagreements and who was right

Run:  .venv/bin/python scripts/validate_market.py
"""

import csv
import json
import os
import re
import unicodedata
from datetime import datetime

import numpy as np

HISTORY_PATH = os.path.join("public", "history.json")
CALIB_PATH = os.path.join("public", "calibration.json")
PICKS_PATH = os.path.join("analysis", "hr_favorites_odds_picks.csv")


def normalize(name):
    """Same normalization as update_results.py: lower, strip accents+punct."""
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def to_iso(date_long):
    return datetime.strptime(date_long, "%B %d, %Y").strftime("%Y-%m-%d")


def brier(pred, y):
    pred = np.asarray(pred, float)
    y = np.asarray(y, float)
    return float(np.mean((pred - y) ** 2))


def main():
    with open(CALIB_PATH) as f:
        calib = json.load(f)
    b0, b1 = calib["intercept"], calib["coef"]

    with open(HISTORY_PATH) as f:
        history = json.load(f)

    # Model table: (iso_date, norm_name) -> row
    model = {}
    per_day = {}  # iso_date -> list of (score, norm_name, hitHR)
    for day in history:
        iso = to_iso(day["date"])
        for p in day.get("players", []):
            score = p.get("score")
            if not isinstance(score, (int, float)):
                continue
            nn = normalize(p.get("name", ""))
            p_hr = float(sigmoid(b0 + b1 * float(score)))
            rec = {
                "date": iso,
                "name": p.get("name", ""),
                "team": p.get("team", ""),
                "score": float(score),
                "pHR": p_hr,
                "hitHR": bool(p.get("hitHR")),
            }
            model[(iso, nn)] = rec
            per_day.setdefault(iso, []).append(rec)

    model_dates = set(per_day)

    # Picks
    picks = []
    with open(PICKS_PATH) as f:
        for r in csv.DictReader(f):
            picks.append(
                {
                    "date": r["date"],
                    "name": r["player"],
                    "norm": normalize(r["player"]),
                    "implied": float(r["consensus_implied"]),
                    "homered": r["homered"].strip().lower() == "true",
                }
            )
    pick_dates = {p["date"] for p in picks}

    # --- Join on (date, normalized name) ---
    overlap = []
    picks_in_model_days = 0
    for pk in picks:
        if pk["date"] not in model_dates:
            continue
        picks_in_model_days += 1
        rec = model.get((pk["date"], pk["norm"]))
        if rec is None:
            continue
        # sanity: outcome should agree between sources
        outcome = 1.0 if rec["hitHR"] else 0.0
        overlap.append(
            {
                **pk,
                "model_p": rec["pHR"],
                "score": rec["score"],
                "team": rec["team"],
                "outcome": outcome,
                "market_outcome": 1.0 if pk["homered"] else 0.0,
            }
        )

    print("=" * 72)
    print("MARKET VALIDATION — HR Scout model vs. betting-market consensus")
    print("=" * 72)
    md = sorted(model_dates)
    pd_ = sorted(pick_dates)
    print(f"model history days : {len(md)}  ({md[0]} -> {md[-1]})")
    print(f"picks CSV days     : {len(pd_)}  ({pd_[0]} -> {pd_[-1]})")
    date_overlap = sorted(model_dates & pick_dates)
    print(f"overlapping days   : {len(date_overlap)}  "
          f"({date_overlap[0]} -> {date_overlap[-1]})" if date_overlap else
          "overlapping days   : 0")
    print(f"picks on model days: {picks_in_model_days}")
    print(f"picks joined to a scored player (overlap set): {len(overlap)}")

    if not overlap:
        print("\nNo overlap — cannot compare. Stop.")
        return

    # Outcome-source agreement check
    disagree = [o for o in overlap if o["outcome"] != o["market_outcome"]]
    print(f"outcome-source disagreements (history vs picks): {len(disagree)} "
          f"of {len(overlap)}")

    y = np.array([o["outcome"] for o in overlap])
    mp = np.array([o["model_p"] for o in overlap])
    mk = np.array([o["implied"] for o in overlap])
    n = len(overlap)
    base = float(y.mean())

    # --- (a) Brier ---
    print("\n" + "-" * 72)
    print(f"(a) Brier score on overlap set (n={n}, actual HR rate={base:.3f})")
    print("-" * 72)
    bm = brier(mp, y)
    bk = brier(mk, y)
    bb = brier(np.full(n, base), y)
    print(f"  model  Brier : {bm:.4f}")
    print(f"  market Brier : {bk:.4f}")
    print(f"  base-rate    : {bb:.4f}")
    winner = "MODEL" if bm < bk else "MARKET" if bk < bm else "TIE"
    print(f"  lower (better): {winner}   (delta = {bm - bk:+.4f}, model - market)")
    print(f"  mean model P  : {mp.mean():.3f}   mean market implied : {mk.mean():.3f}")

    # Paired bootstrap on Brier difference (model - market)
    rng = np.random.default_rng(1)
    diffs = []
    idx = np.arange(n)
    for _ in range(10000):
        s = rng.choice(idx, size=n, replace=True)
        diffs.append(brier(mp[s], y[s]) - brier(mk[s], y[s]))
    diffs = np.array(diffs)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"  bootstrap 95% CI of (model-market) Brier diff: [{lo:+.4f}, {hi:+.4f}]")
    p_model_better = float((diffs < 0).mean())
    print(f"  bootstrap P(model Brier < market Brier): {p_model_better:.2%}")

    # --- (b) model top-3 daily ---
    print("\n" + "-" * 72)
    print("(b) Model top-3 daily scores: actual hit rate vs. market implied")
    print("-" * 72)
    top_hits, top_n, top_implied = 0, 0, []
    for iso in date_overlap:
        day_recs = sorted(per_day[iso], key=lambda r: r["score"], reverse=True)
        top3 = day_recs[:3]
        for rec in top3:
            nn = normalize(rec["name"])
            pk = next((p for p in picks if p["date"] == iso and p["norm"] == nn), None)
            if pk is None:
                continue  # no market price for this model-top-3 player that day
            top_n += 1
            top_hits += 1 if rec["hitHR"] else 0
            top_implied.append(pk["implied"])
    if top_n:
        rate = top_hits / top_n
        imp = float(np.mean(top_implied))
        print(f"  model top-3 players that also had a market price: n={top_n}")
        print(f"  actual HR hit rate : {rate:.3f} ({top_hits}/{top_n})")
        print(f"  mean market implied: {imp:.3f}")
        print(f"  model top-3 {'BEAT' if rate > imp else 'DID NOT beat'} "
              f"market implied (delta {rate - imp:+.3f})")
    else:
        print("  No model top-3 players overlapped with market picks.")

    # --- (c) biggest disagreements ---
    print("\n" + "-" * 72)
    print("(c) Biggest model-vs-market disagreements (|model_p - implied|)")
    print("-" * 72)
    for o in overlap:
        o["gap"] = o["model_p"] - o["implied"]
    ranked = sorted(overlap, key=lambda o: abs(o["gap"]), reverse=True)[:15]
    print(f"{'date':>10} {'player':>20} {'mkt':>5} {'model':>6} {'gap':>6} "
          f"{'HR?':>4} {'closer':>7}")
    for o in ranked:
        hr = "YES" if o["outcome"] else "no"
        closer = "model" if abs(o["model_p"] - o["outcome"]) < abs(o["implied"] - o["outcome"]) else "market"
        print(f"{o['date']:>10} {o['name'][:20]:>20} {o['implied']:>5.2f} "
              f"{o['model_p']:>6.2f} {o['gap']:>+6.2f} {hr:>4} {closer:>7}")

    # who's right when they disagree materially (gap >= 0.05)
    material = [o for o in overlap if abs(o["gap"]) >= 0.05]
    if material:
        mc = sum(1 for o in material
                 if abs(o["model_p"] - o["outcome"]) < abs(o["implied"] - o["outcome"]))
        print(f"\n  On {len(material)} material disagreements (|gap|>=0.05): "
              f"model closer {mc}, market closer {len(material)-mc}")

    # --- significance note ---
    print("\n" + "-" * 72)
    print("Significance")
    print("-" * 72)
    print(f"  overlap n = {n}; HR events = {int(y.sum())}")
    se = (base * (1 - base) / n) ** 0.5 if n else float("nan")
    print(f"  approx SE of the overlap hit rate: {se:.3f} "
          f"(~+/-{1.96*se:.3f} at 95%)")
    print("  Interpret Brier deltas against that noise floor before concluding.")


if __name__ == "__main__":
    main()
