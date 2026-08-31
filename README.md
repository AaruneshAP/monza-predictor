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

## Debugging log — issues found and fixed while building this

This model went through several rounds of "does this number actually make
sense" scrutiny before publishing. Documenting the real issues here rather
than hiding a clean history, since the debugging is arguably the more
interesting part of a Monte Carlo portfolio piece than the final chart.

### 1. Percentile-direction inversion (`tire_deg_factor`, `pit_delta`)

The `_pctile()` helper builds a 0–1 percentile from a raw metric, controlled
by an `ascending` flag. For `pit_delta` and `tire_deg_factor` the flag was
set backwards: it produced a "goodness" scale (1.0 = best) while the
formulas consuming them — `(1 - tire_deg_factor)`, `- pit_delta * weight`
— expected a "badness" scale (1.0 = worst). Net effect: **the model was
rewarding the worst pit crews and worst tire management, and penalizing
the best.** Concretely, Verstappen's pit-stop loss (17.0s average — the
best in a same sample comparison) was being scored as the *worst*
percentile (0.91) instead of the best. Fixed by correcting which direction
each call site needs, and rewrote `_pctile()`'s docstring to spell out both
directions explicitly so this doesn't happen again.

### 2. No season-standings signal

The model originally leaned entirely on small-sample proxies (an 8-round
tire-degradation slope, a handful of qualifying top-speed traps) with no
use of the one robust, official aggregate signal: championship points.
That let single-race noise outrank a driver's actual season-long form.
Added `season_points_pctile`, pulled live via `fastf1.ergast`, as a real
feature (weight 0.26 — the largest single weight in the model).

### 3. Noisy tire-degradation slope over-weighted

While investigating (1), the raw lap-time-vs-tyre-life slopes turned out to
be tiny (~0.01–0.05s/lap over ~20 stints) and not corrected for the
fuel-burn effect that dominates that range — so two drivers with
essentially indistinguishable real degradation (e.g. -0.0002 vs -0.0405
s/lap) were getting pushed to opposite ends of the percentile scale.
Turning near-noise into a 0-to-1 spread and weighting it like a real signal
was actively misleading the model. Cut its weight from 0.10 → 0.04 and
documented why in `build_features()`.

### 4. Monte Carlo win probabilities implausibly deterministic

Before any of the above, the season-form leader was winning **81.7%** of
simulated races — not credible for a sport with real race-day variance.
The noise term standard deviation was too small relative to the
feature-score spread, so the sim degenerated into "pick the fastest car
almost every time." Retuned the noise constants so a clear form leader
lands in a believable ~25–35% win range.

### 5. Slipstream-variance term inverting the field order

A second, subtler version of #4: the slipstream/train variance boost
(larger for midpack cars) was initially strong enough that a midpack car
with a *clearly worse* mean feature score — fewer championship points,
worse qualifying pace — could still out-win a genuinely stronger driver,
purely because a wider distribution occasionally spikes to P1 more often.
This surfaced as Leclerc and Verstappen (both with much stronger season
form) ranking below Gasly and Lawson in simulated win%. Reduced the
coefficient enough to keep the "midpack shuffling" effect without letting
variance override actual skill differences.

### 6. Stale mid-season driver-lineup assumption

`_load_current_grid()` assumes "whoever raced the most recent completed
round is the current lineup" — which breaks for a substitution that's
already reverting before the next race. Round 12 (Dutch GP) had Lawson
filling in for Hadjar at Red Bull (confirmed by diffing rosters across
rounds 9–12: Red Bull was VER+HAD through round 11, VER+LAW at round 12,
with Tsunoda taking Lawson's Racing Bulls seat that one race). Since a
session that hasn't happened has no roster to read, this can't be inferred
from data — added an explicit, dated `GRID_OVERRIDE_BY_ROUND` entry in
`race_model.py` restoring Hadjar to Red Bull and Lawson to Racing Bulls
for round 13. Manually-maintained and will go stale — remove it once
`live_quali` starts driving that round's grid instead.

### 7. Frontend: SSR crash and a silent hydration failure

- `page.tsx` renders Recharts components without `"use client"`, so
  Next.js tried to server-render a browser-only charting library and
  failed the build outright (`Super expression must either be null or a
  function`). Fixed by marking the page a Client Component.
- Separately, `new Date(...).toLocaleString()` on the "last updated"
  timestamp rendered different text on the server (build-time, one
  timezone/locale) versus the client (browser's local timezone/locale),
  throwing a React hydration error that silently killed the rest of the
  tree — including the chart, which rendered as a blank box with no
  visible error. Replaced with a fixed UTC + `en-US` `Intl` formatter so
  server and client output are byte-identical.
- The win-probability chart's Y-axis was also dropping every other driver
  label (only 5 of 10 rendered) because the container was too short
  (`h-72`) for 10 category ticks — Recharts silently skips labels that
  would overlap. Increased the height and set `interval={0}`.

### 8. Generalizing to every race: a silent wrong-data bug during backfill

Generalizing from Monza-only to any circuit (`circuit_profiles.py` +
parameterizing `race_model.py`) surfaced a new one while backfilling
historical rounds for the track record: `fastf1.get_session(year,
"Dutch Grand Prix", "R")` does **not** error for a year Zandvoort wasn't
on the calendar — it silently fuzzy-matches to the closest-named race
instead. Requesting "Dutch Grand Prix" for 2019 and 2020 (before
Zandvoort's 2021 return) silently returned the **Chinese** and **Russian**
Grands Prix. Without a check, that would have quietly fed two completely
unrelated races into round 12's historical baseline as if they were past
Dutch GPs. Fixed by verifying `session.event["EventName"]` actually
matches the requested name before using a historical session
(`_get_verified_session()`), and skipping years where it doesn't — same
category of bug as #1: trusting that a value means what its label claims
without checking.

### 9. "Next race to predict" picked round 1 instead of the actual next race

The first version of `_next_round_to_predict()` picked the earliest round
number that wasn't marked `completed` — which meant every round that
happened *before* this archive existed (rounds 1–12, never predicted, so
technically "not completed") outranked the real next race, round 13.
Fixed by filtering to rounds whose date hasn't passed before picking the
earliest — a past race that was simply never predicted isn't "next," it
needs an explicit `--backtest` call if you want it backfilled.

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
