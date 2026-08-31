"""
Monza GP — Monte Carlo Win Probability Model
=============================================
Built on real FastF1 data, re-weighted for Monza's low-downforce,
high-top-speed, slipstream-heavy characteristics.

Data-availability note (see PROJECT_BRIEF.md): as of the date this is run, Monza
race weekend hasn't happened yet, so there's no live qualifying/FP2 session
for Monza itself. The model falls back to two real-data sources instead:
  1. Historical Monza results (2019-2025) per driver, as a track-specific
     baseline.
  2. Current-season form (quali pace, top speed, tire degradation, pit
     performance) from the most recent completed races, as a proxy for
     "how fast is this car right now."

This fallback is not hardcoded as the only path: load_monza_context()
*first* tries to pull this weekend's actual Monza 'Q' and 'FP2' sessions
from FastF1. FastF1 doesn't error on a session that hasn't run yet — it
just returns empty data — so we detect that and fall back automatically.
Once qualifying/FP2 actually go green later in race week, simply re-running
`python generate_predictions.py` picks up the real grid, real top speed,
and real tire-degradation data with no code changes. Check the printed
"Grid source" / "Tire degradation source" lines to see which path a given
run used.
"""

import warnings
from datetime import datetime, timezone

import fastf1
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

SEASON_YEAR = 2026
MONZA_EVENT = "Italian Grand Prix"

# Manual grid correction for known lineup changes FastF1 can't reflect yet —
# a session that hasn't happened has no session data to read a roster from,
# so `_load_current_grid()`'s "most recent completed race" heuristic breaks
# for a one-off substitution that reverts before the next round.
#
# Confirmed by user, 2026-08-31: Lawson's Red Bull seat at round 12 (Dutch
# GP) was a one-race substitution for Hadjar (round 12 data: Red Bull =
# VER+LAW, Racing Bulls = TSU+LIN; rounds 9-11: Red Bull = VER+HAD, Racing
# Bulls = LAW+LIN — confirms the swap). For Monza, Hadjar returns to Red
# Bull and Lawson moves back to Racing Bulls, bumping Tsunoda off the grid.
# Update or clear this dict once it's stale (e.g. after Monza actually runs
# and `live_quali`/`live_tire_deg` start driving the grid instead).
MONZA_GRID_TEAM_OVERRIDE = {
    "HAD": "Red Bull Racing",
    "LAW": "Racing Bulls",
}
MONZA_GRID_DROP = {"TSU"}
HISTORICAL_YEARS = range(2019, 2026)  # 2019-2025 inclusive
RECENT_ROUNDS_FOR_FORM = 8  # how many of the season's completed rounds to use for "current form"

# ---------------------------------------------------------------
# 1. DATA LOADING
# ---------------------------------------------------------------


def _completed_rounds(season: int) -> list[int]:
    """Round numbers for `season` whose race date has already passed,
    excluding pre-season testing (round 0)."""
    schedule = fastf1.get_event_schedule(season)
    now = pd.Timestamp.now(tz="UTC")
    completed = schedule[
        (schedule["RoundNumber"] > 0) & (schedule["EventDate"] < now.tz_localize(None))
    ]
    return sorted(completed["RoundNumber"].tolist())


def _load_historical_monza() -> pd.DataFrame:
    """Finishing position at Monza per driver for each year in
    HISTORICAL_YEARS. DNFs/non-classified drivers are scored as
    finishing one place behind the last classified driver that race."""
    rows = []
    for year in HISTORICAL_YEARS:
        try:
            session = fastf1.get_session(year, "Monza", "R")
            session.load(laps=False, telemetry=False, weather=False, messages=False)
        except Exception as exc:  # a given year's data can be flaky/unavailable
            print(f"  [historical] skipping {year} Monza: {exc}")
            continue

        results = session.results.copy()
        max_classified = results["Position"].max()
        fallback_pos = (max_classified if pd.notna(max_classified) else len(results)) + 1
        results["Position"] = results["Position"].fillna(fallback_pos)

        for _, r in results.iterrows():
            rows.append(
                {
                    "year": year,
                    "driver": r["Abbreviation"],
                    "team": r["TeamName"],
                    "finish_pos": float(r["Position"]),
                }
            )
    return pd.DataFrame(rows)


def _load_season_form(rounds: list[int]) -> dict:
    """Pulls qualifying + race data for the given 2026 rounds and returns
    per-driver aggregates: quali position, top speed, tire degradation
    slope, and pit-stop time loss."""
    quali_rows, race_rows = [], []
    tire_deg_rows, pit_delta_rows = [], []

    for rnd in rounds:
        # --- Qualifying: grid-pace proxy + top speed ---
        try:
            q = fastf1.get_session(SEASON_YEAR, rnd, "Q")
            q.load(laps=True, telemetry=False, weather=False, messages=False)
            q_results = q.results[["Abbreviation", "TeamName", "Position"]].copy()
            top_speed = q.laps.groupby("Driver")["SpeedST"].max()

            for _, r in q_results.iterrows():
                quali_rows.append(
                    {
                        "round": rnd,
                        "driver": r["Abbreviation"],
                        "team": r["TeamName"],
                        "quali_pos": r["Position"],
                        "top_speed": top_speed.get(r["Abbreviation"], np.nan),
                    }
                )
        except Exception as exc:
            print(f"  [season form] skipping round {rnd} quali: {exc}")

        # --- Race: finishing form + tire degradation + pit loss ---
        try:
            race = fastf1.get_session(SEASON_YEAR, rnd, "R")
            race.load(laps=True, telemetry=False, weather=False, messages=False)
            r_results = race.results[["Abbreviation", "TeamName", "Position"]].copy()
            for _, r in r_results.iterrows():
                race_rows.append(
                    {
                        "round": rnd,
                        "driver": r["Abbreviation"],
                        "team": r["TeamName"],
                        "finish_pos": r["Position"],
                    }
                )

            laps = race.laps.copy()
            laps["LapSeconds"] = laps["LapTime"].dt.total_seconds()
            clean = laps[
                laps["PitInTime"].isna()
                & laps["PitOutTime"].isna()
                & (laps["TrackStatus"] == "1")
                & laps["LapSeconds"].notna()
            ]

            # Tire degradation: slope of lap time vs tyre life within each stint.
            # Needs >=3 distinct tyre-life values or the least-squares fit is
            # singular (constant/near-constant x) and numpy just warns and
            # returns garbage — skip those stints instead.
            for (driver, stint), stint_laps in clean.groupby(["Driver", "Stint"]):
                if len(stint_laps) < 4 or stint_laps["TyreLife"].nunique() < 3:
                    continue
                try:
                    slope = np.polyfit(stint_laps["TyreLife"], stint_laps["LapSeconds"], 1)[0]
                except np.linalg.LinAlgError:
                    continue
                tire_deg_rows.append({"driver": driver, "slope": slope})

            # Pit loss: (in-lap + out-lap time) minus that stint's best clean lap.
            for driver, driver_laps in laps.groupby("Driver"):
                best_clean = clean[clean["Driver"] == driver]["LapSeconds"].min()
                if pd.isna(best_clean):
                    continue
                pit_laps = driver_laps[
                    driver_laps["PitInTime"].notna() | driver_laps["PitOutTime"].notna()
                ]
                for _, lap in pit_laps.iterrows():
                    if pd.notna(lap["LapSeconds"]):
                        pit_delta_rows.append(
                            {"driver": driver, "loss": lap["LapSeconds"] - best_clean}
                        )
        except Exception as exc:
            print(f"  [season form] skipping round {rnd} race: {exc}")

    return {
        "quali": pd.DataFrame(quali_rows),
        "race": pd.DataFrame(race_rows),
        "tire_deg": pd.DataFrame(tire_deg_rows),
        "pit_delta": pd.DataFrame(pit_delta_rows),
    }


def _load_season_points(latest_round: int) -> pd.DataFrame:
    """Cumulative championship points through the most recent completed
    round. This is a much more robust "how competitive is this car right
    now" signal than small-sample per-round proxies like an 8-round
    tire-degradation slope — it's the season's own full aggregate, and it's
    what actually separates a struggling-but-still-solid 6th-in-standings
    car from a genuine backmarker, which single-race proxies can miss."""
    standings = fastf1.ergast.Ergast().get_driver_standings(
        season=SEASON_YEAR, round=latest_round
    )
    df = standings.content[0][["driverCode", "points"]]
    return df.rename(columns={"driverCode": "driver"})


def _find_driver_full_name(driver: str, before_round: int, lookback: int = 6) -> str:
    """Scans backward from `before_round` for a race this driver actually
    appears in, to get their name when they're missing from the latest
    round's roster entirely (e.g. bumped by a substitute)."""
    for rnd in range(before_round - 1, max(before_round - 1 - lookback, 0), -1):
        try:
            session = fastf1.get_session(SEASON_YEAR, rnd, "R")
            session.load(laps=False, telemetry=False, weather=False, messages=False)
            match = session.results[session.results["Abbreviation"] == driver]
            if len(match):
                return match.iloc[0]["FullName"]
        except Exception:
            continue
    return driver


def _load_current_grid(latest_round: int) -> pd.DataFrame:
    """Driver/team lineup from the most recent completed race — this is
    "who's actually racing" for mid-season driver swaps and rookies.

    This heuristic breaks for a substitution that's already reverting by
    the *next* round (see MONZA_GRID_TEAM_OVERRIDE) — a session that hasn't
    happened yet has no roster to read, so that has to be corrected
    manually rather than inferred from data.
    """
    session = fastf1.get_session(SEASON_YEAR, latest_round, "R")
    session.load(laps=False, telemetry=False, weather=False, messages=False)
    grid = session.results[["Abbreviation", "FullName", "TeamName"]].drop_duplicates(
        "Abbreviation"
    )
    grid = grid.rename(
        columns={"Abbreviation": "driver", "FullName": "full_name", "TeamName": "team"}
    )

    grid = grid[~grid["driver"].isin(MONZA_GRID_DROP)]
    for driver, team in MONZA_GRID_TEAM_OVERRIDE.items():
        if driver in grid["driver"].values:
            grid.loc[grid["driver"] == driver, "team"] = team
        else:
            full_name = _find_driver_full_name(driver, latest_round)
            grid = pd.concat(
                [grid, pd.DataFrame([{"driver": driver, "full_name": full_name, "team": team}])],
                ignore_index=True,
            )
    return grid.reset_index(drop=True)


def _load_live_monza_session(session_type: str):
    """Attempts to load this year's actual Monza session (e.g. 'Q', 'FP2').

    FastF1 does not raise when a session hasn't happened yet — it silently
    returns empty results/laps tables — so "not available" is detected by
    checking for empty data, not by catching an exception. Returns the
    loaded Session if real data exists, otherwise None. This is what lets a
    later re-run during race week upgrade to live data automatically.
    """
    try:
        session = fastf1.get_session(SEASON_YEAR, MONZA_EVENT, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        print(f"  [live weekend] {session_type} not available yet: {exc}")
        return None
    if session.results is None or len(session.results) == 0:
        print(f"  [live weekend] {session_type} not available yet.")
        return None
    return session


def _live_quali_features(session) -> pd.DataFrame:
    """Real Monza grid position + quali-lap top speed, once quali has run."""
    df = session.results[["Abbreviation", "Position"]].rename(
        columns={"Abbreviation": "driver", "Position": "grid_pos"}
    )
    try:
        top_speed = session.laps.groupby("Driver")["SpeedST"].max()
        df["top_speed"] = df["driver"].map(top_speed)
    except Exception:
        df["top_speed"] = np.nan
    return df


def _live_practice_tire_deg(session) -> pd.Series:
    """Lap-time-vs-tyre-life slope from actual Monza FP2 long runs, per
    driver — a much more relevant degradation signal than season-average
    once it's available, since it's this track's tarmac/temps."""
    laps = session.laps.copy()
    laps["LapSeconds"] = laps["LapTime"].dt.total_seconds()
    clean = laps[
        laps["PitInTime"].isna()
        & laps["PitOutTime"].isna()
        & (laps["TrackStatus"] == "1")
        & laps["LapSeconds"].notna()
    ]
    rows = []
    for (driver, stint), stint_laps in clean.groupby(["Driver", "Stint"]):
        if len(stint_laps) < 4 or stint_laps["TyreLife"].nunique() < 3:
            continue
        try:
            slope = np.polyfit(stint_laps["TyreLife"], stint_laps["LapSeconds"], 1)[0]
        except np.linalg.LinAlgError:
            continue
        rows.append({"driver": driver, "slope": slope})
    if not rows:
        return pd.Series(dtype=float)
    return pd.DataFrame(rows).groupby("driver")["slope"].mean()


def _historical_rain_probability() -> float:
    """Fraction of the historical Monza races run with any rainfall."""
    wet_count, total = 0, 0
    for year in HISTORICAL_YEARS:
        try:
            session = fastf1.get_session(year, "Monza", "R")
            session.load(laps=False, telemetry=False, weather=True, messages=False)
            total += 1
            if session.weather_data is not None and session.weather_data["Rainfall"].any():
                wet_count += 1
        except Exception:
            continue
    return round(wet_count / total, 2) if total else 0.10


def load_monza_context(cache_dir: str = "./fastf1_cache") -> dict:
    """Pulls historical Monza results + current-season form via FastF1.
    Returns a dict of raw DataFrames consumed by build_features()."""
    fastf1.Cache.enable_cache(cache_dir)

    print("Loading current-season schedule...")
    completed = _completed_rounds(SEASON_YEAR)
    if not completed:
        raise RuntimeError(f"No completed {SEASON_YEAR} rounds found before Monza.")
    form_rounds = completed[-RECENT_ROUNDS_FOR_FORM:]
    latest_round = completed[-1]
    print(f"  Using rounds {form_rounds} of {SEASON_YEAR} as current-form window.")

    print("Loading historical Monza results (2019-2025)...")
    historical = _load_historical_monza()

    print("Loading current grid lineup...")
    grid = _load_current_grid(latest_round)

    print("Loading championship standings (season-form signal)...")
    season_points = _load_season_points(latest_round)

    print(f"Loading season form for rounds {form_rounds}...")
    season = _load_season_form(form_rounds)

    print("Checking for live Monza-weekend session data (Q/FP2)...")
    live_quali_session = _load_live_monza_session("Q")
    live_quali = _live_quali_features(live_quali_session) if live_quali_session is not None else None

    live_practice_session = _load_live_monza_session("FP2")
    live_tire_deg = (
        _live_practice_tire_deg(live_practice_session)
        if live_practice_session is not None
        else None
    )
    if live_tire_deg is not None and live_tire_deg.empty:
        live_tire_deg = None

    grid_source = "live_monza_qualifying" if live_quali is not None else "season_form_projection"
    tire_deg_source = "live_monza_fp2" if live_tire_deg is not None else "season_form"
    print(f"  Grid source: {grid_source}")
    print(f"  Tire degradation source: {tire_deg_source}")

    print("Estimating rain probability from Monza weather history...")
    rain_probability = _historical_rain_probability()

    return {
        "historical": historical,
        "grid": grid,
        "season_points": season_points,
        "quali": season["quali"],
        "race": season["race"],
        "tire_deg": season["tire_deg"],
        "pit_delta": season["pit_delta"],
        "live_quali": live_quali,
        "live_tire_deg": live_tire_deg,
        "grid_source": grid_source,
        "tire_deg_source": tire_deg_source,
        "rain_probability": rain_probability,
    }


# ---------------------------------------------------------------
# 2. FEATURE ENGINEERING (Monza-specific weighting)
# ---------------------------------------------------------------


def _pctile(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Rank-based percentile in [0, 1], NaN-safe.

    ascending=True: a LARGER raw value produces a LARGER percentile. Use
    this to build a 0=best/1=worst *badness* scale out of a "bigger raw
    number = worse" metric (e.g. tire-degradation slope, pit-stop time
    loss in seconds) — that's the scale build_features()'s `(1 - x)` and
    `- x * weight` formulas expect.

    ascending=False: a LARGER raw value produces a SMALLER percentile. Use
    this to build a 0=worst/1=best *goodness* scale out of a "smaller raw
    number = better" metric (e.g. finishing/qualifying position, where P1
    should map close to 1.0) — the scale used directly (no inversion) by
    quali_pace_pctile.

    Getting this backwards silently rewards the worst performers instead
    of the best — always check which scale the caller's formula expects.
    """
    ranked = series.rank(pct=True, ascending=ascending)
    return ranked.fillna(ranked.mean() if ranked.notna().any() else 0.5)


def build_features(raw: dict) -> pd.DataFrame:
    """
    Builds one row per current-grid driver:
      driver, team, grid_pos, quali_pace_pctile, top_speed_rank,
      season_points_pctile, historical_monza_avg_finish, tire_deg_factor,
      pit_delta, slipstream_factor

    Monza-specific weighting choices (applied later in monte_carlo_simulate,
    documented here for context):
    - grid_pos: weighted DOWN — Monza overtaking is comparatively easy,
      especially into Turn 1 (Rettifilo) and Roggia/Ascari on lap 1, and
      down the two long straights all race. Uses the real Monza grid once
      qualifying has actually run (raw["live_quali"]); until then it's
      projected from season-average qualifying rank.
    - top_speed_rank: weighted UP — low-drag setups and strong straight-
      line speed (engine mode, DRS efficiency) matter disproportionately.
    - season_points_pctile: cumulative championship points through the
      most recent round. This exists because single-race proxies (an
      8-round tire-degradation slope, a handful of quali top-speed traps)
      are noisy enough to rank a car with a genuinely strong, consistent
      season below one that's merely had a couple of clean weekends —
      points are the season's own aggregate and correct for that.
    - tire_deg_factor: weighted DOWN (both because Monza is low-severity on
      tires, and because the underlying signal is genuinely noisy — the
      slope estimates are often ~0.01-0.05s/lap on a couple dozen stints,
      not corrected for the fuel-burn effect that dominates that range, so
      small real differences get inflated into large percentile swings).
      Derived from each driver's lap-time-vs-tyre-life slope across their
      recent stints.
    - slipstream_factor: Monza-unique — midpack cars running similar pace
      get bunched into slipstream trains and see more shuffling than at
      most circuits; front-runners and backmarkers see less. Approximated
      from how close a driver's season quali pace sits to the field median.
    """
    grid = raw["grid"]
    quali = raw["quali"]
    season_points = raw["season_points"]
    historical = raw["historical"]
    tire_deg = raw["tire_deg"]
    pit_delta = raw["pit_delta"]
    live_quali = raw.get("live_quali")
    live_tire_deg = raw.get("live_tire_deg")

    # --- season-average qualifying position -> pace percentile + projected grid ---
    quali_avg = quali.groupby("driver")["quali_pos"].mean().rename("avg_quali_pos")
    top_speed_avg = quali.groupby("driver")["top_speed"].mean().rename("avg_top_speed")

    feat = grid.merge(quali_avg, on="driver", how="left").merge(
        top_speed_avg, on="driver", how="left"
    )

    if live_quali is not None:
        # Real Monza quali has happened — use it for grid + top speed.
        feat = feat.merge(
            live_quali.rename(columns={"top_speed": "live_top_speed"}),
            on="driver",
            how="left",
        )
        max_grid = feat["grid_pos"].max()
        fallback_grid = (max_grid if pd.notna(max_grid) else len(feat)) + 1
        feat["grid_pos"] = feat["grid_pos"].fillna(fallback_grid)
        feat["quali_pace_pctile"] = _pctile(feat["grid_pos"], ascending=False)
        feat["top_speed_rank"] = _pctile(
            feat["live_top_speed"].fillna(feat["avg_top_speed"]), ascending=True
        )
    else:
        # No live Monza quali yet — project from season-average pace instead.
        feat["quali_pace_pctile"] = _pctile(feat["avg_quali_pos"], ascending=False)
        feat["top_speed_rank"] = _pctile(feat["avg_top_speed"], ascending=True)
        feat = feat.sort_values("avg_quali_pos", na_position="last").reset_index(drop=True)
        feat["grid_pos"] = feat.index + 1

    # --- season points percentile: robust full-season competitiveness signal ---
    points_by_driver = season_points.set_index("driver")["points"]
    feat["season_points_pctile"] = _pctile(feat["driver"].map(points_by_driver), ascending=True)
    feat["season_points_pctile"] = feat["season_points_pctile"].fillna(0.0)

    # --- historical Monza finish, per driver, imputed for drivers with no history ---
    hist_avg = historical.groupby("driver")["finish_pos"].mean()
    default_finish = hist_avg.mean() if len(hist_avg) else feat["grid_pos"].median()
    feat["historical_monza_avg_finish"] = (
        feat["driver"].map(hist_avg).fillna(default_finish)
    )

    # --- tire degradation factor (0 = best/least degradation, 1 = worst) ---
    # Prefer real Monza FP2 long-run data once it exists; season-average
    # degradation from other tracks is a weaker proxy but the only option
    # before that.
    deg_avg = live_tire_deg if live_tire_deg is not None else tire_deg.groupby("driver")["slope"].mean()
    feat["tire_deg_factor"] = _pctile(feat["driver"].map(deg_avg), ascending=True)
    feat["tire_deg_factor"] = feat["tire_deg_factor"].fillna(0.5)

    # --- pit delta (0 = fastest pit loss, 1 = slowest) ---
    pit_avg = pit_delta.groupby("driver")["loss"].mean()
    feat["pit_delta"] = _pctile(feat["driver"].map(pit_avg), ascending=True)
    feat["pit_delta"] = feat["pit_delta"].fillna(0.5)

    # --- slipstream / train exposure: peaks for midpack, low at front/back ---
    feat["slipstream_factor"] = (1 - (feat["quali_pace_pctile"] - 0.5).abs() * 2).clip(
        lower=0.1
    )

    return feat[
        [
            "driver",
            "team",
            "grid_pos",
            "quali_pace_pctile",
            "top_speed_rank",
            "season_points_pctile",
            "historical_monza_avg_finish",
            "tire_deg_factor",
            "pit_delta",
            "slipstream_factor",
        ]
    ]


# ---------------------------------------------------------------
# 3. MONTE CARLO SIMULATION
# ---------------------------------------------------------------


def monte_carlo_simulate(
    features: pd.DataFrame,
    n_sims: int = 100_000,
    rain_probability: float = 0.10,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    For each simulation:
      1. Sample a 'race pace' score per driver from a normal distribution
         centered on their weighted feature score, with variance boosted
         by slipstream_factor (more randomness for closely-matched cars).
      2. Sample whether this simulation is a rain scenario using
         rain_probability. If rain: down-weight top_speed_rank, up-weight
         randomness (proxy for reduced predictability in wet conditions).
      3. Rank drivers by simulated pace.
      4. Record finishing position for this simulation.

    Aggregates to win_pct, podium_pct (top 3), points_pct (top 10),
    expected_position (mean finish across sims).
    """
    rng = np.random.default_rng(random_seed)
    driver_team = dict(zip(features["driver"], features["team"]))
    results = {row.driver: [] for row in features.itertuples()}

    for _ in range(n_sims):
        is_rain = rng.random() < rain_probability
        sim_scores = {}

        for row in features.itertuples():
            base_score = (
                row.quali_pace_pctile * 0.25
                + row.season_points_pctile * 0.26  # robust full-season form, see build_features
                + (1 / max(row.grid_pos, 1)) * 0.10  # de-weighted vs other tracks
                + row.top_speed_rank * (0.05 if is_rain else 0.20)
                # Kept intentionally small: the underlying slope estimates are
                # tiny (often ~0.01-0.05s/lap on ~20 stints) and not corrected
                # for fuel-burn effect, so this percentile is noisier than its
                # 0-1 spread suggests — see build_features' tire_deg_factor note.
                + (1 - row.tire_deg_factor) * 0.04
                + (1 - row.historical_monza_avg_finish / 20) * 0.10
                - row.pit_delta * 0.05
            )
            # Race-day noise has to be large enough relative to the feature-
            # score spread or the sim degenerates into picking the same
            # "fastest car" nearly every time — unrealistic for a sport
            # where even a dominant car rarely wins 80%+ of starts. The base
            # 0.18 was tuned so a clear form leader lands in a believable
            # ~25-35% win range rather than 80%+.
            #
            # The slipstream term is intentionally small (0.03, not 0.10):
            # a larger coefficient let the *variance* boost for midpack cars
            # overpower actual skill differences — e.g. it was giving a
            # midpack car with a clearly worse mean score (fewer points,
            # worse quali pace) a higher win_pct than a genuinely stronger
            # driver, purely because a wider distribution occasionally
            # spikes to P1 more often. Keep this small enough that it can
            # nudge close calls without inverting the field's real order.
            noise_scale = 0.18 + row.slipstream_factor * 0.03
            if is_rain:
                noise_scale *= 1.8  # wet races are less predictable
            sim_scores[row.driver] = base_score + rng.normal(0, noise_scale)

        # Lower rank number = better finish
        ranked = sorted(sim_scores, key=sim_scores.get, reverse=True)
        for pos, driver in enumerate(ranked, start=1):
            results[driver].append(pos)

    summary = []
    for driver, positions in results.items():
        positions = np.array(positions)
        summary.append(
            {
                "driver": driver,
                "team": driver_team.get(driver, ""),
                "win_pct": round((positions == 1).mean() * 100, 1),
                "podium_pct": round((positions <= 3).mean() * 100, 1),
                "points_pct": round((positions <= 10).mean() * 100, 1),
                "expected_position": round(positions.mean(), 2),
            }
        )

    return pd.DataFrame(summary).sort_values("win_pct", ascending=False)


# ---------------------------------------------------------------
# 4. MAIN
# ---------------------------------------------------------------


def main():
    raw = load_monza_context()
    features = build_features(raw)
    predictions = monte_carlo_simulate(
        features, n_sims=100_000, rain_probability=raw["rain_probability"]
    )

    print(f"\nMONZA GP WEEKEND-AWARE PREDICTION — run at {datetime.now(timezone.utc).isoformat()}")
    print("Monte Carlo simulations: 100,000")
    print(f"Rain scenario probability: {raw['rain_probability'] * 100:.0f}% (historical Monza rate 2019-2025)")
    print(f"Grid source: {raw['grid_source']} | Tire degradation source: {raw['tire_deg_source']}\n")
    print(predictions.to_string(index=False))


if __name__ == "__main__":
    main()
