# F1 Race Predictor — Project Brief

## Goal
A portfolio piece for job search. A live, polished website that shows a
Monte Carlo win-probability model for every round of the F1 season, built
with real FastF1 data, and tracks how accurate its own past predictions
were. The audience is a hiring contact (non-F1-expert), so the site should
clearly communicate the *methodology* (Monte Carlo simulation, feature
engineering, per-circuit weighting) and its own accuracy — not just show a
table of numbers.

Originally scoped to Monza only; generalized to the full season (see
"History" below) once that was working end to end.

## Architecture (zero-cost, no live backend)
- `model/` — Python. Pulls FastF1 data per round, runs the Monte Carlo
  simulation, writes the result into an archive at
  `frontend/public/predictions/{slug}.json` plus an `index.json` that
  lists every round and an aggregate accuracy summary.
- `frontend/` — Next.js + Tailwind + Recharts. Statically reads the
  archive at build time (via `fs` in Server Components + `generateStaticParams`
  for one page per race). No API calls at runtime, no server, no cold starts.
- Deploy: `frontend/` → Vercel (free). A scheduled GitHub Action
  (`.github/workflows/refresh-predictions.yml`) predicts the next upcoming
  race and grades any race that's finished since the last run, once daily;
  Vercel auto-redeploys on every push.

## Why this architecture (for whoever reads this repo)
Explicitly avoiding Railway/Render/Fly.io for the backend: as of 2026 none
of them offer a real always-on free tier without cold-start delays or
credit-card-gated trials. A static JSON archive + static site sidesteps
hosting costs entirely and demos instantly — important since this will be
shown live to a recruiter/contact.

## The prediction archive
- `model/circuit_profiles.py` — per-circuit characteristics (overtaking
  difficulty, downforce level, tire severity) that drive the Monte Carlo
  weights for that round. See its docstring for what each score means.
- `model/race_model.py` — the model itself: FastF1 data loading, feature
  engineering, Monte Carlo simulation, all parameterized by round number
  and circuit profile instead of hardcoded to one track.
- `model/generate_predictions.py` — predicts a round (default: the next
  upcoming one) and writes/updates its archive file + `index.json`.
  Supports `--backtest` to generate a *blind* prediction for a round that
  already happened (only using data available before it — no peeking at
  that round's own result), which is how the archive got real graded
  history from day one instead of starting empty.
- `model/check_results.py` — grades any predicted-but-ungraded race whose
  date has passed against its real result: winner hit, Brier score,
  podium hits, mean absolute position error. Rebuilds the aggregate track
  record in `index.json`.

## Build order (original, Monza-only v1)
1. Get `model/monza_gp_model.py` producing real, sane output using actual
   FastF1 data (see stub functions with TODOs).
2. `model/generate_predictions.py` — runs the model, serializes to
   `frontend/public/predictions.json` in the exact shape the frontend
   expects.
3. Build the frontend UI against the JSON: landing/hero section,
   prediction table, a simple bar chart of win%, and a short
   "methodology" section explaining Monte Carlo + Monza-specific weighting.
4. Polish: loading states not needed (static data), but do handle empty/
   stale-data states gracefully (e.g. "predictions last updated: <date>").
5. Deploy `frontend/` to Vercel. Confirm it works with no env vars needed.

## History: Monza-only → full season
v1 hardcoded everything to Monza (weights, historical lookups, frontend
copy). Once that was validated — including a real debugging pass that
caught a percentile-direction bug, a missing championship-standings
signal, and Monte Carlo calibration issues (see `README.md`'s debugging
log) — it was generalized to predict any round:
1. Extracted per-circuit weighting into `circuit_profiles.py`, anchored so
   plugging in Monza's own profile reproduces the weights that were
   hand-tuned specifically for Monza (i.e. the generalization is checked
   against the one circuit already validated by hand, not an untested
   guess).
2. Turned the single `predictions.json` into an archive
   (`frontend/public/predictions/*.json` + `index.json`) so every round
   can have its own page and a running track record.
3. Added blind backtesting so the track record could start with real
   graded history instead of being empty until the next race.
4. Rebuilt the frontend as a race picker + per-race pages + a
   `/track-record` page, instead of one static homepage.

## Design direction
Motorsport-adjacent but not cheesy — dark background, one accent color
(not a generic red/checkered-flag cliché), clean data-forward typography.
This is a job-search portfolio piece: it should read as "software
engineer who understands ML and can ship a real product," not "F1 fan
site."

## Non-goals
- No user accounts, no live betting odds, no real-time race data during
  the actual GP (out of scope for v1).
- No paid infrastructure of any kind.
