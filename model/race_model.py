"""
F1 Race Predictor — Monte Carlo Win Probability Model
======================================================
Generalized from a Monza-only model into one that can predict any round of
the season, re-weighted per circuit via circuit_profiles.py (downforce
level, overtaking difficulty, tire severity) instead of hardcoding one
track's numbers everywhere.

Data-availability handling: for a race that hasn't happened yet, there's
no live qualifying/FP2 session for it. FastF1 doesn't error on a session
that hasn't run — it silently returns empty data — so load_race_context()
detects that and falls back to two real-data sources instead:
  1. Historical results at this circuit, 2019-2025 (or fewer years, or
     none, for a new circuit — see circuit_profiles.py's `historical_key`).
  2. Current-season form (quali pace, top speed, tire degradation, pit
     performance, championship standings) from the most recent completed
     rounds, as a proxy for "how fast is this car right now."

Once qualifying/FP2 actually run for that round, simply re-running
`python generate_predictions.py` picks up the real grid, real top speed,
and real tire-degradation data with no code changes — check the printed
"Grid source" / "Tire degradation source" lines to see which path a given
run used.

Backtesting: pass backtest=True to load_race_context() to generate a
*blind* pre-race prediction for a round that's already happened, using
only data available before it (no live quali/FP2 for that round, no
season-form rounds at or after it). This is what makes the "predicted vs
actual" track record honest — it's not hindsight-informed.
"""

import warnings
from datetime import datetime, timezone

import fastf1
import numpy as np
import pandas as pd

from circuit_profiles import get_profile

warnings.filterwarnings("ignore", category=FutureWarning)

SEASON_YEAR = 2026
HISTORICAL_YEARS = range(2019, 2026)  # 2019-2025 inclusive
RECENT_ROUNDS_FOR_FORM = 8  # how many of the season's completed rounds to use for "current form"

# Manual grid corrections for known lineup changes FastF1 can't reflect yet
# — a session that hasn't happened has no roster to read, so a substitution
# that's already reverting before the *next* round has to be corrected by
# hand rather than inferred from data. Keyed by round number; add an entry
# only when you know of a specific correction needed for that race.
#
# Round 13 (Italian GP) confirmed by user, 2026-08-31: Lawson's Red Bull
# seat at round 12 (Dutch GP) was a one-race substitution for Hadjar
# (round 12 data: Red Bull = VER+LAW, Racing Bulls = TSU+LIN; rounds 9-11:
# Red Bull = VER+HAD, Racing Bulls = LAW+LIN — confirms the swap). For
# Monza, Hadjar returns to Red Bull and Lawson moves back to Racing Bulls,
# bumping Tsunoda off the grid. Stale once live_quali starts driving the
# grid for that round instead — safe to delete after round 13 runs.
GRID_OVERRIDE_BY_ROUND = {
    13: {
        "team_overrides": {"HAD": "Red Bull Racing", "LAW": "Racing Bulls"},
        "drop": {"TSU"},
    },
}

# ---------------------------------------------------------------
# 1. DATA LOADING
# ---------------------------------------------------------------


def _completed_rounds(season: int, strictly_before_round: int | None = None) -> list[int]:
    """Round numbers for `season` that count as "already happened".

    Live mode (strictly_before_round=None): rounds whose date has passed,
    per the real calendar.

    Backtest mode (strictly_before_round=N): every round number < N,
    regardless of today's date — this is what makes a backtest a fair
    blind prediction using only what would have been known before round N.
    """
    schedule = fastf1.get_event_schedule(season)
    rounds = schedule[schedule["RoundNumber"] > 0]
    if strictly_before_round is not None:
        rounds = rounds[rounds["RoundNumber"] < strictly_before_round]
    else:
        now = pd.Timestamp.now(tz="UTC")
        rounds = rounds[rounds["EventDate"] < now.tz_localize(None)]
    return sorted(rounds["RoundNumber"].tolist())


def _get_verified_session(year: int, historical_key: str, session_type: str):
    """fastf1.get_session() fuzzy-matches its event-name argument and does
    NOT error when a circuit wasn't on that year's calendar — it silently
    substitutes the closest-scoring name instead (confirmed: requesting
    "Dutch Grand Prix" for 2019/2020, before Zandvoort returned to the
    calendar, silently resolved to the Chinese and Russian Grands Prix).
    Ingesting that as "historical Dutch GP data" would silently corrupt
    the feature. Loads the session and verifies session.event['EventName']
    actually matches before returning it; returns None otherwise.
    """
    try:
        session = fastf1.get_session(year, historical_key, session_type)
        session.load(laps=False, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        print(f"  [historical] skipping {year} {historical_key}: {exc}")
        return None
    resolved_name = session.event["EventName"]
    if resolved_name != historical_key:
        print(
            f"  [historical] skipping {year}: '{historical_key}' doesn't match "
            f"this calendar (fastf1 resolved it to '{resolved_name}' instead — "
            f"the circuit likely wasn't racing that year)"
        )
        return None
    return session


def _load_historical_circuit(historical_key: str | None) -> pd.DataFrame:
    """Finishing position per driver for each year in HISTORICAL_YEARS at
    this circuit. historical_key=None (brand-new circuit) short-circuits
    to an empty frame — build_features() imputes a sensible default for
    that case rather than treating it as an error.

    DNFs/non-classified drivers are scored as finishing one place behind
    the last classified driver that race.
    """
    if historical_key is None:
        return pd.DataFrame(columns=["year", "driver", "team", "finish_pos"])

    rows = []
    for year in HISTORICAL_YEARS:
        session = _get_verified_session(year, historical_key, "R")
        if session is None:
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
    """Pulls qualifying + race data for the given rounds and returns
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
    what actually separates a struggling-but-still-solid mid-table car
    from a genuine backmarker, which single-race proxies can miss."""
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


def _load_current_grid(latest_round: int, round_number: int) -> pd.DataFrame:
    """Driver/team lineup from the most recent completed race — this is
    "who's actually racing" for mid-season driver swaps and rookies.

    This heuristic breaks for a substitution that's already reverting by
    the *next* round (see GRID_OVERRIDE_BY_ROUND) — a session that hasn't
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

    override = GRID_OVERRIDE_BY_ROUND.get(round_number, {})
    drop = override.get("drop", set())
    team_overrides = override.get("team_overrides", {})

    grid = grid[~grid["driver"].isin(drop)]
    for driver, team in team_overrides.items():
        if driver in grid["driver"].values:
            grid.loc[grid["driver"] == driver, "team"] = team
        else:
            full_name = _find_driver_full_name(driver, latest_round)
            grid = pd.concat(
                [grid, pd.DataFrame([{"driver": driver, "full_name": full_name, "team": team}])],
                ignore_index=True,
            )
    return grid.reset_index(drop=True)


def _load_live_session(event_name: str, session_type: str):
    """Attempts to load this year's actual session (e.g. 'Q', 'FP2') for
    the given event.

    FastF1 does not raise when a session hasn't happened yet — it silently
    returns empty results/laps tables — so "not available" is detected by
    checking for empty data, not by catching an exception. Returns the
    loaded Session if real data exists, otherwise None. This is what lets a
    later re-run during race week upgrade to live data automatically.
    """
    try:
        session = fastf1.get_session(SEASON_YEAR, event_name, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        print(f"  [live weekend] {session_type} not available yet: {exc}")
        return None
    if session.results is None or len(session.results) == 0:
        print(f"  [live weekend] {session_type} not available yet.")
        return None
    return session


def _live_quali_features(session) -> pd.DataFrame:
    """Real grid position + quali-lap top speed, once quali has run."""
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
    """Lap-time-vs-tyre-life slope from actual FP2 long runs, per driver —
    a much more relevant degradation signal than season-average once it's
    available, since it's this track's own tarmac/temps."""
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


def _historical_rain_probability(historical_key: str | None) -> float:
    """Fraction of the historical races at this circuit run with any
    rainfall. Falls back to a generic 10% for a circuit with no history."""
    if historical_key is None:
        return 0.10
    wet_count, total = 0, 0
    for year in HISTORICAL_YEARS:
        try:
            session = fastf1.get_session(year, historical_key, "R")
            if session.event["EventName"] != historical_key:
                continue  # fastf1 fuzzy-matched to a different race — see _get_verified_session
            session.load(laps=False, telemetry=False, weather=True, messages=False)
            total += 1
            if session.weather_data is not None and session.weather_data["Rainfall"].any():
                wet_count += 1
        except Exception:
            continue
    return round(wet_count / total, 2) if total else 0.10


def load_race_context(round_number: int, cache_dir: str = "./fastf1_cache", backtest: bool = False) -> dict:
    """Pulls historical + current-season context for `round_number` via
    FastF1. Returns a dict of raw DataFrames consumed by build_features().

    backtest=True generates a *blind* prediction as if run before that
    round happened: season-form/points/grid are computed using only
    rounds strictly before it, and live quali/FP2 for that round are
    never consulted (even if they exist, since the round already
    happened) — this is what keeps a "predicted vs actual" comparison
    honest rather than hindsight-informed.
    """
    fastf1.Cache.enable_cache(cache_dir)
    profile = get_profile(round_number)
    event_name = profile["event_name"]

    print(f"Loading current-season schedule (round {round_number}: {event_name})...")
    cutoff = round_number if backtest else None
    completed = _completed_rounds(SEASON_YEAR, strictly_before_round=cutoff)
    if not completed:
        raise RuntimeError(
            f"No completed {SEASON_YEAR} rounds found before round {round_number} — "
            f"can't build season-form features for a season opener this way."
        )
    form_rounds = completed[-RECENT_ROUNDS_FOR_FORM:]
    latest_round = completed[-1]
    print(f"  Using rounds {form_rounds} of {SEASON_YEAR} as current-form window.")

    print(f"Loading historical {event_name} results (2019-2025)...")
    historical = _load_historical_circuit(profile["historical_key"])

    print("Loading current grid lineup...")
    grid = _load_current_grid(latest_round, round_number)

    print("Loading championship standings (season-form signal)...")
    season_points = _load_season_points(latest_round)

    print(f"Loading season form for rounds {form_rounds}...")
    season = _load_season_form(form_rounds)

    if backtest:
        print("  Backtest mode: skipping live quali/FP2 (blind pre-race prediction).")
        live_quali, live_tire_deg = None, None
    else:
        print(f"Checking for live {event_name} session data (Q/FP2)...")
        live_quali_session = _load_live_session(event_name, "Q")
        live_quali = _live_quali_features(live_quali_session) if live_quali_session is not None else None

        live_practice_session = _load_live_session(event_name, "FP2")
        live_tire_deg = (
            _live_practice_tire_deg(live_practice_session)
            if live_practice_session is not None
            else None
        )
        if live_tire_deg is not None and live_tire_deg.empty:
            live_tire_deg = None

    grid_source = "live_qualifying" if live_quali is not None else "season_form_projection"
    tire_deg_source = "live_fp2" if live_tire_deg is not None else "season_form"
    print(f"  Grid source: {grid_source}")
    print(f"  Tire degradation source: {tire_deg_source}")

    print(f"Estimating rain probability from {event_name} weather history...")
    rain_probability = _historical_rain_probability(profile["historical_key"])

    return {
        "round_number": round_number,
        "event_name": event_name,
        "profile": profile,
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
# 2. FEATURE ENGINEERING
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
      season_points_pctile, historical_avg_finish, tire_deg_factor,
      pit_delta, slipstream_factor

    The per-circuit weighting these feed into (grid_pos down/up, top_speed
    up/down, tire_deg up/down, slipstream variance) is applied in
    monte_carlo_simulate() based on raw["profile"] — see
    circuit_profiles.py and weight_profile_for() below for how.

    - grid_pos: uses the real grid once qualifying has actually run
      (raw["live_quali"]); until then it's projected from season-average
      qualifying rank.
    - top_speed_rank: from quali-lap speed-trap data (live if available,
      else season-average).
    - season_points_pctile: cumulative championship points through the
      most recent round. This exists because single-race proxies (an
      8-round tire-degradation slope, a handful of quali top-speed traps)
      are noisy enough to rank a car with a genuinely strong, consistent
      season below one that's merely had a couple of clean weekends —
      points are the season's own aggregate and correct for that.
    - tire_deg_factor: kept a small weight everywhere the underlying
      signal is noisy — the slope estimates are often ~0.01-0.05s/lap on a
      couple dozen stints, not corrected for the fuel-burn effect that
      dominates that range, so small real differences get inflated into
      large percentile swings. Derived from each driver's
      lap-time-vs-tyre-life slope across their recent stints.
    - slipstream_factor: midpack cars running similar pace get bunched
      into slipstream trains and see more shuffling than at circuits where
      cars run more spread out; front-runners and backmarkers see less.
      Approximated from how close a driver's season quali pace sits to the
      field median.
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
        # Real quali has happened — use it for grid + top speed.
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
        # No live quali yet — project from season-average pace instead.
        feat["quali_pace_pctile"] = _pctile(feat["avg_quali_pos"], ascending=False)
        feat["top_speed_rank"] = _pctile(feat["avg_top_speed"], ascending=True)
        feat = feat.sort_values("avg_quali_pos", na_position="last").reset_index(drop=True)
        feat["grid_pos"] = feat.index + 1

    # --- season points percentile: robust full-season competitiveness signal ---
    points_by_driver = season_points.set_index("driver")["points"]
    feat["season_points_pctile"] = _pctile(feat["driver"].map(points_by_driver), ascending=True)
    feat["season_points_pctile"] = feat["season_points_pctile"].fillna(0.0)

    # --- historical finish at this circuit, per driver, imputed for drivers with no history ---
    hist_avg = historical.groupby("driver")["finish_pos"].mean()
    default_finish = hist_avg.mean() if len(hist_avg) else feat["grid_pos"].median()
    feat["historical_avg_finish"] = feat["driver"].map(hist_avg).fillna(default_finish)

    # --- tire degradation factor (0 = best/least degradation, 1 = worst) ---
    # Prefer real FP2 long-run data once it exists; season-average
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
            "historical_avg_finish",
            "tire_deg_factor",
            "pit_delta",
            "slipstream_factor",
        ]
    ]


# ---------------------------------------------------------------
# 3. MONTE CARLO SIMULATION
# ---------------------------------------------------------------


def weight_profile_for(profile: dict) -> dict:
    """Translates a circuit's 0-1 profile scores into concrete Monte Carlo
    weights. Anchored so that plugging in Monza's own profile
    (overtaking=0.15, downforce=0.05, tire=0.15) reproduces close to the
    weights that were hand-tuned specifically for Monza in the original
    single-track version of this model — i.e. this generalization isn't
    an untested guess, it's checked to collapse back to known-reasonable
    numbers at the one circuit this project already validated by hand.
    """
    overtaking = profile["overtaking_difficulty"]
    downforce = profile["downforce_level"]
    tire = profile["tire_severity"]

    grid_weight = 0.05 + overtaking * 0.25  # 0.0875 at Monza, up to 0.30 at Monaco
    top_speed_weight_dry = 0.05 + (1 - downforce) * 0.20  # 0.24 at Monza, down to 0.06 at Monaco
    tire_deg_weight = 0.02 + tire * 0.12  # 0.038 at Monza, up to ~0.12 at Qatar
    slipstream_coefficient = 0.01 + (1 - downforce) * 0.03  # 0.0385 at Monza

    return {
        "quali_weight": 0.25,
        "points_weight": 0.26,
        "grid_weight": grid_weight,
        "top_speed_weight_dry": top_speed_weight_dry,
        "top_speed_weight_wet": top_speed_weight_dry * 0.25,
        "tire_deg_weight": tire_deg_weight,
        "historical_weight": 0.10,
        "pit_weight": 0.05,
        "slipstream_coefficient": slipstream_coefficient,
    }


def monte_carlo_simulate(
    features: pd.DataFrame,
    profile: dict,
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
         rain_probability. If rain: down-weight top_speed, up-weight
         randomness (proxy for reduced predictability in wet conditions).
      3. Rank drivers by simulated pace.
      4. Record finishing position for this simulation.

    Aggregates to win_pct, podium_pct (top 3), points_pct (top 10),
    expected_position (mean finish across sims).

    Weight constants (see weight_profile_for) were tuned so a clear form
    leader lands in a believable ~25-35% win range rather than 80%+ — an
    earlier version of this model, weighted more naively, had a season
    leader winning 82% of simulations, which isn't credible for a sport
    with real race-day variance. The slipstream/variance term is
    deliberately kept small relative to the skill-based terms — a larger
    version of it let a midpack car's higher variance let it out-win a
    genuinely stronger driver in simulated win%, purely from having fatter
    tails, which inverted the field's real order.
    """
    w = weight_profile_for(profile)
    rng = np.random.default_rng(random_seed)
    driver_team = dict(zip(features["driver"], features["team"]))
    results = {row.driver: [] for row in features.itertuples()}

    for _ in range(n_sims):
        is_rain = rng.random() < rain_probability
        top_speed_weight = w["top_speed_weight_wet"] if is_rain else w["top_speed_weight_dry"]
        sim_scores = {}

        for row in features.itertuples():
            base_score = (
                row.quali_pace_pctile * w["quali_weight"]
                + row.season_points_pctile * w["points_weight"]
                + (1 / max(row.grid_pos, 1)) * w["grid_weight"]
                + row.top_speed_rank * top_speed_weight
                + (1 - row.tire_deg_factor) * w["tire_deg_weight"]
                + (1 - row.historical_avg_finish / 20) * w["historical_weight"]
                - row.pit_delta * w["pit_weight"]
            )
            noise_scale = 0.18 + row.slipstream_factor * w["slipstream_coefficient"]
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
# 4. MAIN (ad-hoc single-round run — see generate_predictions.py for the
#    archive-aware version used by the site)
# ---------------------------------------------------------------


def main(round_number: int = 13, backtest: bool = False):
    raw = load_race_context(round_number, backtest=backtest)
    features = build_features(raw)
    predictions = monte_carlo_simulate(
        features, raw["profile"], n_sims=100_000, rain_probability=raw["rain_probability"]
    )

    print(f"\n{raw['event_name'].upper()} PREDICTION — run at {datetime.now(timezone.utc).isoformat()}")
    print("Monte Carlo simulations: 100,000")
    print(f"Rain scenario probability: {raw['rain_probability'] * 100:.0f}%")
    print(f"Grid source: {raw['grid_source']} | Tire degradation source: {raw['tire_deg_source']}\n")
    print(predictions.to_string(index=False))


if __name__ == "__main__":
    import sys

    round_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 13
    backtest_arg = "--backtest" in sys.argv
    main(round_arg, backtest=backtest_arg)
