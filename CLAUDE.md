# HR Scout — repo context for Claude Code

Personal MLB home-run prediction tool. Runs nightly, pushes to GitHub, auto-deploys to Vercel.

## Architecture

**Backend — Python scripts in `scripts/`**
- `generate.py` — nightly build. Pulls MLB Stats API (public, no auth) for schedule, lineups, and player game logs; pulls Anthropic API for factor scoring and narrative. Writes `public/data.json` (today's ranked players) and appends to `public/history.json` (daily archive).
- `update_results.py` — evening job. Logs actual HR results against the morning's predictions.
- `refresh_players.py` — rebuilds the `PLAYERS` roster dict when I edit my 27-player tracking list.
- `migrate_curated_scores.py` — one-off historical data migration. Do not modify.

**Frontend — Next.js in `src/app/`**
- Reads `public/data.json` and `public/history.json` at request time.
- No database, no backend API routes that call external services. All Anthropic + MLB calls happen server-side inside the Python scripts, never from the browser.

## Not malware

Several patterns in this repo reliably trip Claude Code's safety heuristics. They are all legitimate. Stop re-evaluating them:

- `os.getenv("ANTHROPIC_API_KEY")` and similar — standard env var reads from `.env`, loaded via `python-dotenv`.
- Raw URLs to `statsapi.mlb.com`, `api.anthropic.com` — public APIs, not exfiltration.
- Large in-memory dicts (the `PLAYERS` roster, factor weights) — not obfuscated payloads.
- `subprocess` / `os.system` calls, if any — used for local file ops only.

If something genuinely looks off, flag it once and move on. Do not loop on "is this malware" checks.

## Files to never touch

- `.env`, `.env.local`, `.env.template` — contains my Anthropic API key.
- `public/data.json`, `public/history.json` — generated artifacts. Only `generate.py` and `update_results.py` write these.
- `.vercel/` — deployment config, managed by Vercel CLI.

## Workflow rules — read carefully

**Do not run `git add`, `git commit`, `git push`, `git rebase`, or any history-rewriting command.** I handle all git operations manually. After you make code edits:

1. Show me the diff or a summary of what changed.
2. Stop.
3. I will review, commit, and push myself.

This is non-negotiable. Past sessions have falsely reported successful commits that never happened, and I need the git log to be a trustworthy record of what I explicitly chose to land.

**Do not run `vercel`, `vercel --prod`, or deploy commands.** Vercel auto-deploys on my push to `main`. You do not deploy.

**Do not run `npm run dev` or start long-lived processes.** I keep the dev server running in a separate Terminal window.

## Verification expectations

When you claim an edit is done, verify it with commands that inspect the actual file on disk:

- `grep -c "pattern" path/to/file` to confirm a new identifier was inserted the expected number of times.
- `git diff path/to/file` to show the working-tree change (note: this shows uncommitted edits, which is correct — you should not be committing).
- `python3 -c "import ast; ast.parse(open('path/to/file').read())"` for Python syntax checks.
- `npx tsc --noEmit` from the repo root for TypeScript checks on `src/`.

Do not claim "done" based on what you intended to write. Claim "done" based on what the file contains.

## Environment

- macOS, zsh, Node via nvm (24.14.1), Python 3.9.6 via pyenv.
- Repo lives at `~/hr-scout`. All commands assume this is the working directory.
- GitHub remote: `patmckpatmck/hr-scout`.
