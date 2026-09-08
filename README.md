# F1 Race Predictor

A Monte Carlo simulation model predicting the winner of every round of the
F1 season, built on real FastF1 data, with a running track record of how
its own predictions compared to what actually happened — served as a
static site.

**Live demo:** https://monza-predictor.vercel.app/

## How it works
- `model/` — Python. Pulls FastF1 qualifying data, historical results at
  each circuit, current-season form, and live championship standings for
  whichever round is next; runs a 100,000-iteration Monte Carlo
  simulation weighted per-circuit (overtaking difficulty, downforce
  level, tire severity — see `model/circuit_profiles.py`).
- `frontend/` — Next.js + Tailwind + Recharts. Statically renders every
  race in the archive as its own page, plus a `/track-record` page
  showing predicted-vs-actual accuracy across every graded race. No
  backend, no server, no cold starts.

## Stack
Python (FastF1, pandas, numpy) · Next.js · TypeScript · Tailwind CSS ·
Recharts · deployed on Vercel

## Running locally
```
cd model && pip install -r requirements.txt
python generate_predictions.py          # predicts the next upcoming race
python check_results.py                 # grades any races that have since finished
cd ../frontend && npm install && npm run dev
```

To backfill a race that already happened (for building up the track
record), generate a blind prediction for it first:
```
python generate_predictions.py --round 12 --backtest
python check_results.py
```

See `PROJECT_BRIEF.md` for the full project brief and `DEPLOYMENT.md` for
deploy steps.

## The prediction archive
Every round's prediction lives at `frontend/public/predictions/{slug}.json`,
listed in `frontend/public/predictions/index.json` alongside an aggregate
track record. A race file's `status` is one of:
- `predicted` — a prediction exists, the race hasn't happened yet (or
  hasn't been graded yet).
- `completed` — graded against the real result (`actual` + `accuracy`
  fields populated).

`generate_predictions.py` defaults to predicting "the next race that
needs it" — the earliest ungraded round whose date hasn't passed — so
re-running it during a race week naturally upgrades from season-form
projections to real qualifying/practice data as that becomes available,
and automatically advances to the next round once the previous one is
graded. A GitHub Action (`.github/workflows/refresh-predictions.yml`)
does this daily.

## Data-availability handling
For a race that hasn't happened yet, there's no live qualifying/FP2
session to read. FastF1 doesn't error on a session that hasn't happened —
it silently returns empty data — so `load_race_context()` detects that and
falls back to:
1. Historical results at that circuit, 2019–2025, per driver.
2. Current-season form (last 8 completed rounds): qualifying pace,
   speed-trap top speed, tire-degradation slope, pit-stop time loss.
3. Live championship standings through the most recent round.

The moment real qualifying/FP2 data exists for that round, re-running
`generate_predictions.py` picks it up automatically — no code changes
needed. Each run prints which source it used (`Grid source: ...`, `Tire
degradation source: ...`), and that's also in the race's JSON file.

## Track record
The `/track-record` page shows every graded prediction, including
backtested rounds — which are generated *blind*, using only data that
would have existed before that race, never its own result — so it's a
fair test of the model rather than hindsight dressed up as a prediction.
See `model/check_results.py` for exactly how winner-hit-rate, Brier score,
podium hits, and mean absolute position error are computed.

## Non-goals
- No user accounts, no live betting odds, no real-time race data during
  the actual GP (out of scope for v1).
- No paid infrastructure of any kind.

See DEBUGGING.md for the real bugs found and fixed while building this —
the more interesting read if you're technical.
