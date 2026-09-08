# Debugging Log

Real issues found while building the F1 Race Predictor, documented rather
than hidden — see the main README.md for the project overview.

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

### 10. Hand-tuned `base_score` weights, replaced with a real (if small) fit

The 7 weights in `base_score` — how much quali pace, season form, grid
position, top speed, tire management, historical form, and pit stops
each count toward a driver's score — were always hand-picked numbers
(`quali_weight: 0.25`, `points_weight: 0.26`, etc.), chosen because they
"felt about right," not derived from this project's own track record.
Replaced with a fit against the graded rounds actually in the archive.

**Method**: `model/fit_weights.py` rebuilds each graded round's exact
blind backtest (`load_race_context(round, backtest=True)` — the same
pre-race-only data the original prediction used, no hindsight), reads
off each driver's 7 `base_score` terms at the untouched hand-tuned
baseline, then runs a coordinate-wise grid search — for each term in
turn, try a candidate multiplier (0.25x to 3.0x) holding the rest fixed,
keep whichever minimizes a Brier-score proxy, repeat for 4 passes —
minimizing a softmax-of-`base_score` Brier proxy (the real Monte Carlo
model's win probability isn't cheap enough to evaluate per candidate
during a search; softmax is the same thing if the per-driver noise were
Gumbel instead of Gaussian, and the two look close enough to trust as a
search proxy). The output is 7 *calibration scalars* multiplied onto the
existing hand-tuned formula — including its circuit-conditional shape
(e.g. grid position mattering more at a high-overtaking-difficulty
circuit), which stays hand-set from `circuit_profiles.py` as before, since
there isn't remotely enough data yet to fit per-circuit slopes too. If a
fit can't beat the untouched baseline (all 1.0x) on its own training
data, it's discarded in favor of the baseline rather than reported as a
spurious improvement.

**Sample size — the real caveat**: only 4 rounds are graded at all
(10–13), and 2 of those (12, 13) couldn't even be rebuilt this run —
FastF1's public API caps at 500 calls/hour, and rebuilding several
rounds' worth of multi-year historical data hit that cap before reaching
them. **The fit is against 2 races** (round 10, Belgian GP; round 11,
Hungarian GP; 2026-07-19 to 2026-07-26) — realistically too few to trust
as a real signal rather than noise. Every fitted-weight number is stored
in `model/fitted_weights.json` alongside exactly how many races and
which rounds it came from, so that limitation travels with the numbers
instead of getting lost once they're sitting in a formula.

**What actually changed**: `points_weight` (season form) moved to 3.0x,
`grid_weight` and `historical_weight` moved down to 0.25x, the rest
stayed at 1.0x (no evidence to move them). Fit from 2 races found season
form mattering *much* more, and grid position / circuit history mattering
*much* less, than hand-tuned — plausible in isolation, but exactly the
kind of large swing a 2-race fit can produce from noise, not signal.

**Before/after, the real (not proxy) numbers** — re-running
`check_results.py` after regenerating rounds 10 and 11 with the fitted
weights (12 and 13 stayed on the hand-tuned weights this run, for the
same rate-limit reason as above): track-record average Brier **0.0426 →
0.042** across all 4 graded rounds. A real, if tiny, improvement — and
still well short of the always-pick-the-polesitter baseline's **0.0227**,
consistent with the project's other finding (see the baseline-comparison
feature) that this model doesn't yet beat that baseline. Two bugs
surfaced getting to this real number: `fit_weights.py`'s scoring function
initially indexed the calibration dict by each term's own key (e.g.
`quali_pace`) instead of the key that scales it (`quali_weight` — a
different namespace), crashing every real run with a `KeyError`; and
`--apply` originally re-fetched each round's full blind context from
FastF1 a second time to regenerate it, even though fitting had just
fetched the identical data moments earlier — needlessly doubling network
cost and crashing the whole script (losing an already-written
`fitted_weights.json`) when that pushed the run over the rate limit.
Fixed by reusing the already-fetched context instead of re-asking FastF1
for it.

Refit this once more graded rounds exist — 2 races isn't enough to trust,
and the FastF1 rate-limit ceiling on fully rebuilding the whole archive
in one CI run should ease as fewer rounds need touching per refit.
