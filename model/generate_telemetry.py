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
from datetime import datetime, timezone
from pathlib import Path

import fastf1
import pandas as pd

import archive
from generate_predictions import _season_rounds
from race_model import SEASON_YEAR

TOP_N_DRIVERS = 6  # how many of the race's classified finishers get telemetry pulled
QUERIES_PATH = Path(__file__).parent.parent / "telemetry" / "queries.sql"
TELEMETRY_DIR = Path(__file__).parent.parent / "frontend" / "public" / "telemetry"


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
        try:
            tel = fastest.get_telemetry().add_distance()
        except Exception as exc:
            print(f"  [telemetry] {driver}: couldn't load lap telemetry ({exc}), skipping")
            continue
        if tel.empty:
            print(f"  [telemetry] {driver}: empty telemetry for fastest lap, skipping")
            continue

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
