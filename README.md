# HR Scout

Personal MLB home-run prediction tool. Daily pipeline scores every confirmed starting batter across 12 factors (ballpark, pitcher HR/9, bullpen, wind, xHR, BvP history, recent form, Vegas odds, etc.) and ranks them by likelihood to hit a home run.

Powers [homerunscout.com](https://homerunscout.com) (web app) and [@hrmagicball](https://tiktok.com/@hrmagicball) (TikTok/Instagram Reels).

## How it runs

Three-step daily pipeline:

1. **10:30 AM ET (automated)** — GitHub Action runs `scripts/generate.py`, pulls lineups/pitchers/stats from MLB Stats API and Anthropic API, writes `public/data.json` and appends to `public/history.json`, commits as `hr-scout-bot`. Vercel auto-deploys within 60 seconds.
2. **Morning, manual (~30 sec)** — I edit `data/todays_odds.json` with today's date and FanDuel HR odds for the top ~30 players, then run `./run.sh --odds-only` to apply the Vegas odds modifier and produce `adjScore` values. Commit and push.
3. **3:00 AM ET next day (automated)** — GitHub Action runs `scripts/update_results.py`, matches actual HR results against yesterday's predictions, commits the updated `history.json`.

## Daily workflow (local, step 2 above)

```bash
cd ~/hr-scout
git pull --rebase                         # bot has pushed since last session
# edit data/todays_odds.json: update date, enter FanDuel odds for top 30
./run.sh --odds-only                      # applies Vegas modifier, ~1 sec
git add public/data.json
git commit -m "daily odds update"
git push
```

`data/todays_odds.json` is gitignored — only `data.json` gets committed.

## Architecture

**Backend.** Python scripts in `scripts/`:
- `generate.py` — daily build. Default mode hits APIs; `--odds-only` flag skips all API calls and only re-applies the Vegas modifier.
- `update_results.py` — logs actual HR results against predictions. Pure stdlib, uses MLB Stats API only.
- `refresh_players.py` — rebuilds `data/players.json` from the season's top HR hitters. Run weekly.

**Frontend.** Next.js in `src/app/`. Reads `public/data.json` and `public/history.json` at request time. No database, no API routes — all external calls happen server-side in the Python scripts.

**Automation.** Two GitHub Actions workflows in `.github/workflows/` handle the scheduled generate and update-results jobs. Both commit back to `main` using the auto-provisioned `GITHUB_TOKEN` with `contents: write` permission. The `ANTHROPIC_API_KEY` repo secret is required for the morning generate job.

## Setup

Requires Python 3.11+, Node 20+, and an Anthropic API key.

```bash
# clone
git clone https://github.com/patmckpatmck/hr-scout.git
cd hr-scout

# python deps
pip install -r requirements.txt

# env
cp .env.template .env
# edit .env, add ANTHROPIC_API_KEY

# refresh player roster (one-time)
python3 scripts/refresh_players.py

# run the frontend
npm install
npm run dev
# open http://localhost:3000
```

For the automated pipeline, also set the `ANTHROPIC_API_KEY` repo secret at `Settings → Secrets and variables → Actions`.

## Scoring model

Two passes run in parallel — same input factor scores, different aggregation. Both score every player every day and both are archived.

**v1 (legacy).** 12 factors, each scored 1–10, summed and divided by 9 (legacy divisor that inflates scores into the observed 3.0–8.0+ range). Vegas odds modifier applied on top:

| Odds range | Adjustment |
|------------|------------|
| +200 or shorter | +0.5 |
| +201 to +400 | 0.0 |
| +401 to +600 | −0.3 |
| +601 or longer | −0.5 |

**v2 (experimental, deployed May 2026).** Curated 8-factor weighted average. Drops `season_gap`, `bullpen`, `wind`, and `BvP` (each showed lift ≤ 1.0 across 56 days of May 2026 data). Keeps LHP/RHP split, Season HR, and Recent 10 at weight 1.5; xHR at 1.3; and Pitcher HR/9, Recent 5, Ballpark, and Home/Away at 1.0. Divisor = 9.8 (sum of weights), so v2 scores are bounded ≤ 10.

The frontend has separate "Today's Top 20" (v1, by `adjScore`) and "🚀 Top 20 v2" (by `v2Rank`) tabs, plus an in-tab v1 vs v2 hit-rate comparison block keyed to the v2 experiment window.

**What's working so far (56-day May 2026 eval):**
- Tier sorting is real: rank 1-5 hits 20.4%, 6-10 hits 18.9%, 11-20 hits 15.5% (baseline 11.6%).
- Strongest factor signals: LHP/RHP split (1.50× lift), Season HR (1.47×), Recent 10 (1.44×), xHR (1.34×).
- Position-level discrimination at the very top isn't statistically reliable yet — rank 1 = 16.7% (CI ±9.9pp) vs rank 4-5 = 24.1%, intervals overlap.

Full scoring factor list and formula details are in `HR-Scout-Project-Document.docx`.

## Costs

~$0.10–0.20 per day in Anthropic API credits (one generate run). ~$20–30 per MLB season.

## License

Personal project. No license — not intended for redistribution.