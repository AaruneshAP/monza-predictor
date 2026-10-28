"""
Generates a lap-telemetry comparison for an already-completed race: each
of that race's top classified finishers' single fastest qualifying lap —
speed, throttle, brake, and DRS versus distance — loaded into a local
SQLite database and queried with the real SQL in telemetry/queries.sql
(every query there is read from that file and executed here; it's not
documentation, it's what actually runs — see _load_queries()).

Writes frontend/public/telemetry/{slug}.json, the same static-JSON
pattern as the rest of the prediction archive (see archive.py and
DEPLOYMENT.md's "why no backend" for why: this needs no server, Vercel
just serves it as a static file alongside predictions/).

Needs a race that's already happened — status == "completed" in the
prediction archive, i.e. check_results.py has graded it — since
telemetry only exists for a session that's actually run. A single
driver's fastest lap (not the whole session) is deliberate: it's what
makes a speed-vs-distance comparison between drivers apples-to-apples —
comparing arbitrary race laps would mix in fuel load, tire age, and
traffic differences that have nothing to do with driving or car pace.

FastF1's own car-telemetry feed has a real, recurring outage (see
DEBUGGING.md) where lap results load fine but the underlying car_data/
position_data don't. When that happens for a given driver's lap, this
falls back to OpenF1 (api.openf1.org) — an independently hosted F1 data
API with its own pipeline, not FastF1's, so the two don't share a single
point of failure — see _openf1_fastest_lap_telemetry().

Usage:
    python generate_telemetry.py                # every completed round without telemetry yet
    python generate_telemetry.py --round 14      # just round 14
    python generate_telemetry.py --round 14 --force   # regenerate an existing one
"""

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fastf1
import pandas as pd
import requests

import archive
from generate_predictions import _season_rounds
from race_model import SEASON_YEAR

TOP_N_DRIVERS = 6  # how many of the race's classified finishers get telemetry pulled
QUERIES_PATH = Path(__file__).parent.parent / "telemetry" / "queries.sql"
TELEMETRY_DIR = Path(__file__).parent.parent / "frontend" / "public" / "telemetry"

OPENF1_BASE = "https://api.openf1.org/v1"
OPENF1_TIMEOUT = 15  # seconds per request — a public free API, fail fast rather than hang the whole run


def _load_queries() -> dict[str, str]:
    """Parses telemetry/queries.sql into {name: sql} by its `-- name: x`
    header comments — this is the single source of truth for every query
    this script runs, so the .sql file on disk can never drift from the
    SQL that's actually executed."""
    text = QUERIES_PATH.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    # re.split with one capturing group returns
    # [preamble, name1, sql1, name2, sql2, ...] — pair them up.
    queries = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}
    if not queries:
        raise RuntimeError(f"No '-- name: x' queries found in {QUERIES_PATH}")
    return queries


def _openf1_find_session(race_date: str) -> int | None:
    """Finds this round's Qualifying session_key on OpenF1 by matching
    session date to the round's known race date — qualifying always runs
    within a couple days of the race, and this avoids needing OpenF1's
    circuit/location naming to line up with FastF1's event names, which
    it often doesn't. Returns None if OpenF1 has nothing in range (a
    session it doesn't carry, or OpenF1 itself unreachable)."""
    try:
        resp = requests.get(
            f"{OPENF1_BASE}/sessions",
            params={"year": SEASON_YEAR, "session_name": "Qualifying"},
            timeout=OPENF1_TIMEOUT,
        )
        resp.raise_for_status()
        sessions = resp.json()
    except Exception as exc:
        print(f"  [openf1] couldn't list qualifying sessions: {exc}")
        return None

    race_dt = datetime.strptime(race_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    best, best_delta = None, None
    for s in sessions:
        try:
            start = datetime.fromisoformat(s["date_start"].replace("Z", "+00:00"))
        except Exception:
            continue
        delta = abs((race_dt - start).total_seconds())
        if delta > 3 * 86400:  # quali is always within a few days of its race
            continue
        if best_delta is None or delta < best_delta:
            best, best_delta = s, delta
    return best["session_key"] if best else None


def _openf1_fastest_lap_telemetry(session_key: int, driver_code: str) -> dict | None:
    """Fallback telemetry source for one driver's fastest qualifying lap,
    used when FastF1's own car-telemetry feed has nothing (a real,
    recurring outage — see DEBUGGING.md). OpenF1 (api.openf1.org) is an
    independently hosted F1 data API serving the same category of car
    telemetry from its own pipeline, not FastF1's, so the two don't share
    a single point of failure. Returns the same shape the FastF1 path in
    generate() produces (lap fields + a list of raw samples), or None if
    OpenF1 doesn't have this driver's data either.

    OpenF1's car_data has no distance-along-lap channel of its own
    (FastF1 computes its via Session.add_distance()) — reconstructed here
    the same way, by integrating speed over time from the lap's start.
    """
    try:
        resp = requests.get(
            f"{OPENF1_BASE}/drivers",
            params={"session_key": session_key, "name_acronym": driver_code},
            timeout=OPENF1_TIMEOUT,
        )
        resp.raise_for_status()
        drivers = resp.json()
    except Exception as exc:
        print(f"    [openf1] {driver_code}: couldn't resolve driver number ({exc})")
        return None
    if not drivers:
        print(f"    [openf1] {driver_code}: not in this session's entry list")
        return None
    driver_number = drivers[0]["driver_number"]

    try:
        resp = requests.get(
            f"{OPENF1_BASE}/laps",
            params={"session_key": session_key, "driver_number": driver_number},
            timeout=OPENF1_TIMEOUT,
        )
        resp.raise_for_status()
        laps = resp.json()
    except Exception as exc:
        print(f"    [openf1] {driver_code}: couldn't load laps ({exc})")
        return None

    # A valid timed lap: has a duration, and wasn't a pit in/out lap
    # (not representative pace — using one would produce a false
    # "fastest lap").
    valid = [lap for lap in laps if lap.get("lap_duration") and not lap.get("is_pit_out_lap") and lap.get("date_start")]
    if not valid:
        print(f"    [openf1] {driver_code}: no valid timed laps")
        return None
    fastest = min(valid, key=lambda lap: lap["lap_duration"])

    try:
        lap_start = datetime.fromisoformat(fastest["date_start"].replace("Z", "+00:00"))
    except Exception as exc:
        print(f"    [openf1] {driver_code}: couldn't parse lap start time ({exc})")
        return None
    lap_end = lap_start + timedelta(seconds=fastest["lap_duration"])

    try:
        resp = requests.get(
            f"{OPENF1_BASE}/car_data",
            params={
                "session_key": session_key,
                "driver_number": driver_number,
                "date>=": lap_start.isoformat(),
                "date<": lap_end.isoformat(),
            },
            timeout=OPENF1_TIMEOUT,
        )
        resp.raise_for_status()
        samples = resp.json()
    except Exception as exc:
        print(f"    [openf1] {driver_code}: couldn't load car telemetry ({exc})")
        return None
    if not samples:
        print(f"    [openf1] {driver_code}: no car telemetry samples for this lap")
        return None

    rows = []
    for s in samples:
        try:
            t = datetime.fromisoformat(s["date"].replace("Z", "+00:00"))
        except Exception:
            continue
        rows.append(
            {
                "time_s": (t - lap_start).total_seconds(),
                "speed_kph": s.get("speed"),
                "throttle_pct": s.get("throttle"),
                "brake": 1 if (s.get("brake") or 0) > 0 else 0,
                "drs": s.get("drs") or 0,
            }
        )
    rows.sort(key=lambda r: r["time_s"])
    if len(rows) < 2:
        print(f"    [openf1] {driver_code}: not enough telemetry samples to build a trace")
        return None

    # Reconstruct cumulative distance by integrating speed over time
    # (trapezoidal rule, speed km/h -> m/s) — the same approach FastF1's
    # own add_distance() uses, since OpenF1's car_data carries no
    # distance channel of its own.
    distance = 0.0
    rows[0]["distance_m"] = 0.0
    for prev, cur in zip(rows, rows[1:]):
        dt = cur["time_s"] - prev["time_s"]
        v_avg_ms = ((prev["speed_kph"] or 0) + (cur["speed_kph"] or 0)) / 2 / 3.6
        distance += max(v_avg_ms * dt, 0.0)
        cur["distance_m"] = distance

    # Tyre compound isn't on the laps endpoint — a lightweight extra call
    # to stints, matched by lap number. Not worth failing the driver over
    # if this one part doesn't resolve.
    compound = None
    try:
        resp = requests.get(
            f"{OPENF1_BASE}/stints",
            params={"session_key": session_key, "driver_number": driver_number},
            timeout=OPENF1_TIMEOUT,
        )
        resp.raise_for_status()
        lap_number = fastest.get("lap_number")
        for stint in resp.json():
            if stint.get("lap_start") is not None and stint.get("lap_end") is not None:
                if stint["lap_start"] <= lap_number <= stint["lap_end"]:
                    compound = stint.get("compound")
                    break
    except Exception:
        pass

    return {
        "lap_time_s": fastest["lap_duration"],
        "sector1_s": fastest.get("duration_sector_1"),
        "sector2_s": fastest.get("duration_sector_2"),
        "sector3_s": fastest.get("duration_sector_3"),
        "compound": compound,
        "samples": rows,
    }


def _next_round_without_telemetry(rounds: list[dict]) -> list[dict]:
    """Every completed round in the archive that doesn't have a
    telemetry file yet, in round order."""
    targets = []
    for r in rounds:
        existing = archive.read_race(r["slug"])
        if existing is None or existing.get("status") != "completed":
            continue
        if not (TELEMETRY_DIR / f"{r['slug']}.json").exists():
            targets.append(r)
    return targets


def generate(round_number: int, force: bool = False) -> str:
    rounds_by_number = {r["round"]: r for r in _season_rounds()}
    if round_number not in rounds_by_number:
        raise ValueError(f"Round {round_number} has no schedule/profile entry.")
    meta = rounds_by_number[round_number]

    race = archive.read_race(meta["slug"])
    if race is None or race.get("status") != "completed" or not race.get("actual"):
        raise RuntimeError(
            f"{meta['slug']} isn't graded yet (status != 'completed') — telemetry needs "
            f"a session that's actually happened. Run check_results.py first."
        )

    out_path = TELEMETRY_DIR / f"{meta['slug']}.json"
    if out_path.exists() and not force:
        raise RuntimeError(
            f"{out_path} already exists — pass force=True (--force on the CLI) to regenerate it."
        )

    classification = sorted(race["actual"]["classification"], key=lambda r: r["position"])
    drivers = [row["driver"] for row in classification[:TOP_N_DRIVERS]]
    team_by_driver = {row["driver"]: row["team"] for row in classification}

    print(f"Loading {meta['event_name']} qualifying for telemetry (drivers: {drivers})...")
    quali = fastf1.get_session(SEASON_YEAR, round_number, "Q")
    quali.load(laps=True, telemetry=True, weather=False, messages=False)

    # Resolved lazily, at most once per round — only if FastF1's own
    # telemetry turns out to have nothing and a fallback is actually
    # needed. False (not None) once a lookup has been tried and found
    # nothing, so a round-wide outage doesn't re-query OpenF1's sessions
    # endpoint once per driver.
    openf1_session_key: int | None | bool = None

    lap_rows = []
    sample_rows = []
    for driver in drivers:
        driver_laps = quali.laps.pick_driver(driver)
        if driver_laps.empty:
            print(f"  [telemetry] {driver}: no quali laps found, skipping")
            continue
        fastest = driver_laps.pick_fastest()
        if fastest is None or pd.isna(fastest.get("LapTime")):
            print(f"  [telemetry] {driver}: no valid fastest lap, skipping")
            continue

        tel = None
        try:
            tel = fastest.get_telemetry().add_distance()
            if tel.empty:
                tel = None
        except Exception as exc:
            print(f"  [telemetry] {driver}: FastF1 has no car telemetry for this lap ({exc}) — trying OpenF1...")

        if tel is not None:
            lap_rows.append(
                {
                    "driver": driver,
                    "team": team_by_driver.get(driver, ""),
                    "lap_time_s": fastest["LapTime"].total_seconds(),
                    "sector1_s": fastest["Sector1Time"].total_seconds() if pd.notna(fastest.get("Sector1Time")) else None,
                    "sector2_s": fastest["Sector2Time"].total_seconds() if pd.notna(fastest.get("Sector2Time")) else None,
                    "sector3_s": fastest["Sector3Time"].total_seconds() if pd.notna(fastest.get("Sector3Time")) else None,
                    "compound": fastest.get("Compound"),
                }
            )
            for _, row in tel.iterrows():
                sample_rows.append(
                    {
                        "driver": driver,
                        "distance_m": float(row["Distance"]),
                        "speed_kph": float(row["Speed"]),
                        "throttle_pct": float(row["Throttle"]),
                        "brake": 1 if row["Brake"] else 0,
                        "drs": int(row["DRS"]) if pd.notna(row["DRS"]) else 0,
                        "time_s": row["Time"].total_seconds(),
                    }
                )
            continue

        # FastF1 has no car telemetry for this lap — fall back to OpenF1,
        # an independently hosted data source with its own pipeline, not
        # FastF1's, so the two don't share a single point of failure
        # (see DEBUGGING.md for the FastF1-side outage this works around).
        if openf1_session_key is None:
            openf1_session_key = _openf1_find_session(race["race_date"]) or False
        if not openf1_session_key:
            print(f"  [telemetry] {driver}: OpenF1 has no matching qualifying session either, skipping")
            continue

        fallback = _openf1_fastest_lap_telemetry(openf1_session_key, driver)
        if fallback is None:
            print(f"  [telemetry] {driver}: OpenF1 fallback also has nothing, skipping")
            continue

        lap_rows.append(
            {
                "driver": driver,
                "team": team_by_driver.get(driver, ""),
                "lap_time_s": fallback["lap_time_s"],
                "sector1_s": fallback["sector1_s"],
                "sector2_s": fallback["sector2_s"],
                "sector3_s": fallback["sector3_s"],
                "compound": fallback["compound"],
            }
        )
        for s in fallback["samples"]:
            sample_rows.append({"driver": driver, **s})
        print(f"  [telemetry] {driver}: used OpenF1 fallback ({len(fallback['samples'])} samples)")

    if not lap_rows:
        raise RuntimeError(f"No usable qualifying telemetry found for any of {drivers} — nothing to write.")

    laps_df = pd.DataFrame(lap_rows)
    # Explicit columns even if every driver's telemetry somehow failed to
    # load (lap_rows non-empty but sample_rows empty) — otherwise an
    # empty pd.DataFrame([]) has no columns at all and to_sql() below
    # crashes instead of just producing empty query results (same
    # landmine documented in race_model.py's _load_season_form()).
    samples_df = pd.DataFrame(
        sample_rows, columns=["driver", "distance_m", "speed_kph", "throttle_pct", "brake", "drs", "time_s"]
    )

    print(f"Loaded {len(laps_df)} laps, {len(samples_df)} telemetry samples into SQLite — running queries.sql...")
    conn = sqlite3.connect(":memory:")
    laps_df.to_sql("laps", conn, index=False)
    samples_df.to_sql("samples", conn, index=False)

    queries = _load_queries()
    lap_summary = pd.read_sql_query(queries["lap_summary"], conn).to_dict(orient="records")
    sector_speed_rows = pd.read_sql_query(queries["sector_speed"], conn).to_dict(orient="records")
    drs_usage_rows = pd.read_sql_query(queries["drs_usage"], conn).to_dict(orient="records")
    braking_points_rows = pd.read_sql_query(queries["braking_points"], conn).to_dict(orient="records")
    speed_trace_rows = pd.read_sql_query(queries["speed_trace"], conn).to_dict(orient="records")
    conn.close()

    # Reshape each query's flat rows into per-driver groups — the
    # frontend consumes one driver's data at a time (whichever it's
    # currently comparing), not a flat table it would have to re-group
    # client-side.
    sector_speed_by_driver: dict[str, list] = {}
    for row in sector_speed_rows:
        sector_speed_by_driver.setdefault(row["driver"], []).append(
            {"sector": row["sector"], "avg_speed_kph": row["avg_speed_kph"]}
        )

    braking_points_by_driver: dict[str, list] = {}
    for row in braking_points_rows:
        braking_points_by_driver.setdefault(row["driver"], []).append(
            {"distance_m": round(row["braking_point_m"], 1), "speed_kph": row["speed_at_braking_kph"]}
        )

    trace_by_driver: dict[str, list] = {}
    for row in speed_trace_rows:
        trace_by_driver.setdefault(row["driver"], []).append(
            {
                "distance_m": row["distance_bucket_m"],
                "speed_kph": row["speed_kph"],
                "throttle_pct": row["throttle_pct"],
                "brake_frac": row["brake_frac"],
                "drs_open": bool(row["drs_open"]),
            }
        )

    drs_pct_by_driver = {row["driver"]: row["drs_pct_of_lap"] for row in drs_usage_rows}

    payload = {
        "year": SEASON_YEAR,
        "round": round_number,
        "race_name": meta["event_name"],
        "slug": meta["slug"],
        "session": "Qualifying",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "drivers": [
            {
                "driver": row["driver"],
                "team": row["team"],
                "lap_time_s": round(row["lap_time_s"], 3),
                "sector1_s": round(row["sector1_s"], 3) if row["sector1_s"] is not None else None,
                "sector2_s": round(row["sector2_s"], 3) if row["sector2_s"] is not None else None,
                "sector3_s": round(row["sector3_s"], 3) if row["sector3_s"] is not None else None,
                "compound": row["compound"],
                "sector_speed": sector_speed_by_driver.get(row["driver"], []),
                "drs_pct_of_lap": drs_pct_by_driver.get(row["driver"]),
                "braking_points": braking_points_by_driver.get(row["driver"], []),
                "speed_trace": trace_by_driver.get(row["driver"], []),
            }
            for row in lap_summary
        ],
    }

    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote telemetry for {len(payload['drivers'])} drivers to {out_path}")
    return meta["slug"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--round", type=int, default=None, help="Round number to pull telemetry for (default: every completed round that doesn't have telemetry yet)")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing telemetry file for the given --round")
    args = parser.parse_args()

    os.makedirs("./fastf1_cache", exist_ok=True)
    fastf1.Cache.enable_cache("./fastf1_cache")

    rounds = _season_rounds()

    if args.round is not None:
        generate(args.round, force=args.force)
        return

    targets = _next_round_without_telemetry(rounds)
    if not targets:
        print("Every completed round already has telemetry. Nothing to do.")
        return
    for r in targets:
        try:
            generate(r["round"], force=args.force)
        except Exception as exc:
            print(f"  [telemetry] round {r['round']} failed: {exc}")


if __name__ == "__main__":
    main()
