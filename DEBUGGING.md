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

### 11. A race can relocate venue while keeping its calendar title

Round 16 kept its official name, "Bahrain Grand Prix," for 2026 while
actually being held at Sepang International Circuit, Malaysia — Bahrain
itself unusable as a venue after the earlier Middle East war. Nothing in
`_season_rounds()` or `load_race_context()` would have caught this on its
own: `event_name` is used for live-session lookups
(`fastf1.get_session(2026, "Bahrain Grand Prix", ...)`), which correctly
finds the real session regardless of physical location, so the round would
have gone on predicting Q/FP2/results just fine — while silently pulling
`historical_key: "Bahrain Grand Prix"` (the *real* Bahrain circuit's
2019–2025 results) and using Bahrain's hand-tuned
overtaking_difficulty/downforce_level/tire_severity, none of which describe
Sepang at all. A relocation like this has no structural signal in FastF1's
schedule that this project checks for — round number, date, and EventName
all stayed exactly as expected. The one thing that did shift:
`get_event_schedule()`'s `Location` field, which read "Kuala Lumpur" for
round 16 while its `Country` field still said "Bahrain" (stale, not
updated) — an inconsistency worth spot-checking with a one-off script
comparing FastF1's live schedule fields against `circuit_profiles.py` if a
real-world calendar/venue change is ever suspected. Fixed by keeping
`event_name` as "Bahrain Grand Prix" (still correct for session lookups)
but setting `historical_key: None` and re-estimating the three
circuit-characteristic scores for Sepang instead of Bahrain — same
"no usable pre-2026 history" treatment as Madrid (round 14), since Sepang's
last F1 race (2017) predates `HISTORICAL_YEARS` anyway.

### 12. Cumulative season points ignored a team's recent trajectory entirely

`season_points_pctile` (the single largest-weighted term — `points_weight`
is 0.26 hand-tuned × 3.0 fitted calibration, well above any other term's
max contribution) came only from `_load_season_points()`'s cumulative
championship standings since round 1. That's deliberately robust against
single-race noise (see #2), but it has no concept of "recent" at all — a
team's points from March count exactly the same as points from last
weekend. Surfaced directly: ahead of round 17 (Singapore), the model had
Mercedes drivers (strong early-season points) as win favorites over
Red Bull despite Red Bull visibly improving over the last several rounds
and Ferrari locking out the front row in that weekend's actual qualifying
— cumulative standings couldn't see any of that, because nothing about
them is recency-weighted.

Fixed by blending in a second points signal computed only from the same
recent-rounds window (`RECENT_ROUNDS_FOR_FORM`, currently 8 rounds) that
quali pace, top speed, tire degradation, and pit loss already use —
`race_recent` (the per-round finish positions from `_load_season_form()`)
was already being fetched for those other features and sitting unused for
this one. Each driver's finish positions in that window are converted to
points via the standard scoring table (fastest-lap's extra point omitted)
and percentiled the same way as the full-season figure, then blended
40% full-season / 60% recent-window into `season_points_pctile`. Weighted
toward recent on purpose, per the actual feedback that prompted this —
a pure recent-only signal would reintroduce the small-sample noise problem
cumulative points were added to solve in the first place, but 8 races is a
large enough window that leaning on it more heavily is defensible. Verified
with a synthetic two-driver fixture (one dominant in cumulative points but
scoring zero in the recent window, one the reverse) confirming the recent
window can now flip the ranking, plus a second fixture with the recent
window entirely empty (matching the live FastF1 outage active at the time
of this fix — see the "has not been loaded yet" issue affecting every
round's season-form fetch) confirming it degrades to the neutral 0.5
default already used elsewhere rather than crashing or silently zeroing
someone out.

### 13. FastF1's car-telemetry feed outage, worked around with a second data source

The "has not been loaded yet" issue from #12 turned out to be bigger than
season-form data — once `model/generate_telemetry.py` existed and was
actually run against real FastF1 data for the first time, every one of 8
rounds failed the same way: `quali.load(laps=True, telemetry=True, ...)`
succeeds (lap results, sector times, compound all load fine) but the
underlying `car_data`/`position_data` endpoints don't ("Car telemetry
data is unavailable!", "Car position data is unavailable!" in FastF1's
own logs), so `lap.get_telemetry()` raises for every driver. This isn't
new-code-on-first-run flakiness — it's the same live-timing-feed gap
that's been intermittently breaking season-form quali/race data for
weeks, just hitting a different FastF1 data category this time.

Nothing in this project's control fixes an upstream outage, but the
*category* of data (raw car telemetry) turns out to have a second,
independent source: OpenF1 (api.openf1.org), a separately hosted F1 data
API with its own pipeline. When FastF1's `get_telemetry()` fails for a
driver's lap, `generate_telemetry.py` now falls back to OpenF1 instead of
just giving up on that driver — matching the session by date proximity to
the round's known race date (OpenF1's circuit/location naming doesn't
reliably line up with FastF1's event names, so date is the robust match),
resolving the driver's car number from its driver list, picking their
fastest non-pit timed lap, and pulling that lap's car_data. One real gap:
OpenF1 doesn't expose a distance-along-lap channel the way FastF1's
`add_distance()` does, so distance is reconstructed by integrating speed
over time (trapezoidal rule) from the lap's start — the same approach
FastF1 uses internally, just done by hand here.

Verified against OpenF1's documented response schema with a mocked
`requests.get` (session date-matching, pit-out-lap exclusion, fastest-lap
selection, tyre compound via the stints endpoint, and the distance
reconstruction's output range) before ever trying it against the real
API — this sandbox's own network policy blocks api.openf1.org outright
(a 403 at the egress proxy), so the only way to confirm it actually works
is the next real GitHub Actions `telemetry` dispatch, which does have
unrestricted internet access.

### 14. #13's premise was wrong: FastF1 lost `quali.laps` itself, not just car telemetry

The actual dispatch after #13's fallback shipped still failed every
round, with the OpenF1 fallback never once triggering. Chased it down
with a real traceback (added for exactly this — `str(exc)` alone kept
giving the same generic message regardless of which line raised it) and
found the failure one level earlier than assumed:

```
driver_laps = quali.laps.pick_driver(driver)
  File ".../fastf1/core.py", line 1276, in laps
    return self._get_property_warn_not_loaded("_laps")
fastf1.exceptions.DataNotLoadedError: ...has not been loaded yet
```

`quali.laps` itself raises — `quali.load(laps=True, telemetry=True, ...)`
never actually populated lap data for this session at all. #13's "lap
results, sector times, compound all load fine, only car_data doesn't"
was never verified, just assumed from how a *different* FastF1 call
elsewhere in this project (check_results.py's race-session loads) had
been behaving — a different session type, not evidence about qualifying
sessions during this same live-timing outage. Lap construction itself
depends on the same `_extended_timing_data` feed that was already
logging "Failed to load timing data!" warnings right above the
traceback, so of course `.laps` came back empty too.

Fixed by widening the try/except in `generate_telemetry.py`'s per-driver
loop to cover the whole FastF1 attempt — `quali.laps.pick_driver()`
through `fastest.get_telemetry()` — instead of just the telemetry call,
so ANY failure anywhere in that chain now falls through to the OpenF1
fallback (which independently sources lap selection, sector times, and
compound too, not just car telemetry — see #13). The lesson generalizing
past this one bug: when a live upstream feed is known to be
intermittently down, don't assume which *specific* calls against it will
fail based on a different call's behavior — wrap the whole dependent
chain, not just the piece that failed last time.

### 15. OpenF1 itself: a query-string `+` and no rate-limit pacing

With #14's fix shipped, the fallback finally triggered correctly for
every driver across all 8 rounds — real confirmation that session
matching, driver resolution, and fastest-lap selection all work exactly
as designed (genuine OpenF1 session keys, correct driver numbers, correct
lap picked). But every single `car_data` call still failed, 100% of the
time, with a `500 Internal Server Error` — while the `sessions`, `drivers`,
and `laps` calls on the same session all succeeded. The one thing that
request does differently: it filters by date range (`date>=`, `date<`),
built from a Python `datetime.isoformat()`, which renders the UTC offset
as `+00:00`. A consistent 500 specific to the one endpoint using that
format — not an intermittent data gap, not a 404 — is the signature of a
query-string parser mishandling the `+` rather than a real absence of
data. Switched to the `Z`-suffixed format OpenF1's own documentation
examples use instead of guessing twice.

Separately, hammering 8 rounds × up to 6 drivers with zero pacing between
requests drew real `429`s partway through every run — unsurprising for a
free public API with no API key. Added a minimum spacing between OpenF1
requests and a single retry with backoff on a 429, in `_openf1_get()`
rather than duplicated per call site.

Neither fix has been confirmed against the live API yet as of writing
this entry — both are reasoned from the exact, consistent failure pattern
in the previous real dispatch, not verified success. The next real
`telemetry` dispatch is what actually confirms or refutes them.
