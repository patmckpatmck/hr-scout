#!/usr/bin/env python3
"""
calibrate.py — turn HR Scout composite scores into calibrated HR probabilities.

Reads public/history.json (the resulted daily archive), fits a single-feature
logistic regression  P(HR) = sigmoid(b0 + b1 * score)  by Newton/IRLS (no
scipy/sklearn dependency), and emits:

  (a) a bucket table  : score band -> n, actual HR rate, mean model P(HR)
  (b) fitted coefficients (with standard errors)
  (c) public/calibration.json : intercept/slope + a score->P(HR) lookup table
      so generate.py can display a real probability next to each score.

Also reports the Brier score of the calibrated model vs. a base-rate-only
predictor (everyone gets P = league HR rate).

Run:  .venv/bin/python scripts/calibrate.py
"""

import json
import os
from datetime import datetime

import numpy as np

HISTORY_PATH = os.path.join("public", "history.json")
OUT_PATH = os.path.join("public", "calibration.json")

# Score bands for the diagnostic bucket table. v1 composite scores can exceed 10
# (legacy divisor of 9), so the top band is open-ended.
BANDS = [
    (float("-inf"), 5.0),
    (5.0, 6.0),
    (6.0, 7.0),
    (7.0, 8.0),
    (8.0, 9.0),
    (9.0, 10.0),
    (10.0, float("inf")),
]


def band_label(lo, hi):
    if lo == float("-inf"):
        return f"< {hi:g}"
    if hi == float("inf"):
        return f">= {lo:g}"
    return f"{lo:g}-{hi:g}"


def load_rows(history):
    """Flatten history.json -> list of dicts (date, name, team, rank, score, hitHR)."""
    rows = []
    for day in history:
        date_long = day.get("date")
        for p in day.get("players", []):
            score = p.get("score")
            if not isinstance(score, (int, float)):
                continue
            rows.append(
                {
                    "date": date_long,
                    "name": p.get("name", ""),
                    "team": p.get("team", ""),
                    "rank": p.get("rank"),
                    "score": float(score),
                    "hitHR": bool(p.get("hitHR")),
                }
            )
    return rows


def sigmoid(z):
    # Clip to keep exp() from overflowing on wild intermediate iterates.
    z = np.clip(z, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def _newton(X, y, iters=100, tol=1e-11):
    # numpy 2.x's vectorized matmul raises spurious FP status flags (divide/
    # overflow/invalid) even on benign inputs; sigmoid() is clipped so the math
    # is safe. Suppress the flags rather than let them masquerade as real issues.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        beta = np.zeros(X.shape[1])
        for _ in range(iters):
            p = sigmoid(X @ beta)
            W = p * (1.0 - p)
            XtWX = X.T @ (X * W[:, None]) + 1e-8 * np.eye(X.shape[1])
            step = np.linalg.solve(XtWX, X.T @ (y - p))
            beta = beta + step
            if np.max(np.abs(step)) < tol:
                break
        p = sigmoid(X @ beta)
        W = p * (1.0 - p)
        cov = np.linalg.inv(X.T @ (X * W[:, None]) + 1e-8 * np.eye(X.shape[1]))
    if not np.all(np.isfinite(beta)):
        raise RuntimeError(f"logistic fit diverged: beta={beta}")
    return beta, cov


def fit_logistic(x, y):
    """Fit P(y=1) = sigmoid(b0 + b1*x) in RAW score units.

    Fits on a standardized feature (numerically stable IRLS) then maps the
    coefficients and their covariance back to raw score units via the linear
    change of variables x_std = (x - mu)/sd.
    """
    mu, sd = float(x.mean()), float(x.std())
    if sd == 0:
        sd = 1.0
    xs = (x - mu) / sd
    Xs = np.column_stack([np.ones_like(xs), xs])
    beta_s, cov_s = _newton(Xs, y)

    # x_std = (x - mu)/sd  =>  a0 + a1*x_std = (a0 - a1*mu/sd) + (a1/sd)*x
    J = np.array([[1.0, -mu / sd], [0.0, 1.0 / sd]])  # raw = J @ std
    beta = J @ beta_s
    cov = J @ cov_s @ J.T
    return beta, cov


def brier(pred, y):
    pred = np.asarray(pred, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean((pred - y) ** 2))


def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    rows = load_rows(history)
    if not rows:
        raise SystemExit("No scored rows found in history.json")

    x = np.array([r["score"] for r in rows], dtype=float)
    y = np.array([1.0 if r["hitHR"] else 0.0 for r in rows], dtype=float)
    n = len(rows)
    base_rate = float(y.mean())

    beta, cov = fit_logistic(x, y)
    b0, b1 = float(beta[0]), float(beta[1])
    se = np.sqrt(np.diag(cov))
    se0, se1 = float(se[0]), float(se[1])

    p_model = sigmoid(b0 + b1 * x)
    brier_model = brier(p_model, y)
    brier_base = brier(np.full(n, base_rate), y)

    # --- (a) bucket table ---
    print("=" * 68)
    print(f"HR Scout calibration  |  n={n}  |  base HR rate={base_rate:.4f}")
    dates = sorted({r["date"] for r in rows},
                   key=lambda d: datetime.strptime(d, "%B %d, %Y"))
    print(f"date range: {dates[0]}  ->  {dates[-1]}  ({len(dates)} days)")
    print("=" * 68)
    print(f"{'score band':>10} | {'n':>5} | {'HR':>5} | {'actual':>7} | "
          f"{'model':>7} | {'lift':>5}")
    print("-" * 68)
    for lo, hi in BANDS:
        mask = (x >= lo) & (x < hi)
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        actual = float(y[mask].mean())
        modelp = float(p_model[mask].mean())
        lift = actual / base_rate if base_rate else float("nan")
        print(f"{band_label(lo, hi):>10} | {cnt:>5} | {int(y[mask].sum()):>5} | "
              f"{actual:>7.3f} | {modelp:>7.3f} | {lift:>5.2f}")
    print("-" * 68)

    # --- (b) coefficients ---
    print("\nFitted logistic:  P(HR) = sigmoid(b0 + b1 * score)")
    print(f"  b0 (intercept) = {b0:+.4f}   (SE {se0:.4f})")
    print(f"  b1 (score)     = {b1:+.4f}   (SE {se1:.4f})")
    print(f"  odds ratio per +1 score point = {np.exp(b1):.3f}x")

    # --- Brier scores ---
    print("\nBrier score (lower is better):")
    print(f"  calibrated model : {brier_model:.5f}")
    print(f"  base-rate only   : {brier_base:.5f}")
    skill = (brier_base - brier_model) / brier_base if brier_base else 0.0
    print(f"  skill vs base    : {skill:+.2%}  (Brier skill score)")

    # --- (c) lookup table + coefficients to public/calibration.json ---
    grid = [round(s, 1) for s in np.arange(0.0, 12.01, 0.1)]
    lookup = [{"score": s, "pHR": round(float(sigmoid(b0 + b1 * s)), 4)} for s in grid]
    out = {
        "model": "logistic",
        "feature": "score",
        "formula": "pHR = 1 / (1 + exp(-(intercept + coef*score)))",
        "intercept": round(b0, 6),
        "coef": round(b1, 6),
        "intercept_se": round(se0, 6),
        "coef_se": round(se1, 6),
        "n": n,
        "date_range": [dates[0], dates[-1]],
        "days": len(dates),
        "base_rate": round(base_rate, 6),
        "brier_model": round(brier_model, 6),
        "brier_base_rate": round(brier_base, 6),
        "brier_skill_score": round(skill, 6),
        "lookup": lookup,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {OUT_PATH}  ({len(lookup)} lookup rows, score 0.0-12.0 step 0.1)")


if __name__ == "__main__":
    main()
