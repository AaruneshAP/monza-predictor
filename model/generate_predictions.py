"""
Generates a race prediction and writes/updates it in the archive at
frontend/public/predictions/. Also rebuilds index.json (the season race
list + aggregate track record the frontend reads for navigation).

Usage:
    python generate_predictions.py                 # predict the next race
    python generate_predictions.py --round 14       # predict a specific round
    python generate_predictions.py --round 12 --backtest
        # generate a BLIND prediction for a round that already happened,
        # using only data available before it — for backfilling the
        # archive so the track record has real graded history from day
        # one. Never uses that round's own live quali/FP2/results.

"Next race to predict" = the earliest round (by round number) that isn't
already marked "completed" in the archive. That naturally re-predicts the
same upcoming race every time this runs (picking up live quali/FP2 as the
week progresses) and automatically advances once check_results.py grades
it after the race actually happens.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import fastf1

import archive
from race_model import SEASON_YEAR, build_features, load_race_context, monte_carlo_simulate
from circuit_profiles import CIRCUIT_PROFILES


def _season_rounds() -> list[dict]:
    """All rounds in circuit_profiles.py, in order, with their schedule
    date — the profile table is the source of truth for "which rounds
    exist" since every round needs a profile to be predictable anyway."""
    schedule = fastf1.get_event_schedule(SEASON_YEAR)
    schedule = schedule[schedule["RoundNumber"] > 0].set_index("RoundNumber")
    rounds = []
    for round_number in sorted(CIRCUIT_PROFILES):
        if round_number not in schedule.index:
            continue
        row = schedule.loc[round_number]
        event_name = CIRCUIT_PROFILES[round_number]["event_name"]
        rounds.append(
            {
                "round": round_number,
                "event_name": event_name,
                "race_date": row["EventDate"].strftime("%Y-%m-%d"),
                "slug": archive.race_slug(SEASON_YEAR, round_number, event_name),
            }
        )
    return rounds


def _next_round_to_predict(rounds: list[dict]) -> dict:
    """The next race that actually needs a live prediction: the earliest
    round whose date hasn't passed and isn't already graded. Rounds that
    already happened but were never predicted (e.g. before this archive
    existed) are NOT "next" — those need an explicit --round N --backtest
    call if you want them backfilled, not a live (non-blind) prediction."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    upcoming = [r for r in rounds if r["race_date"] >= today]
    for r in upcoming:
        existing = archive.read_race(r["slug"])
        if existing is None or existing.get("status") != "completed":
            return r
    raise RuntimeError("Every upcoming round in circuit_profiles.py is already marked completed.")


def generate(round_number: int, backtest: bool = False, force: bool = False) -> str:
    rounds_by_number = {r["round"]: r for r in _season_rounds()}
    if round_number not in rounds_by_number:
        raise ValueError(f"Round {round_number} has no schedule/profile entry.")
    meta = rounds_by_number[round_number]

    existing = archive.read_race(meta["slug"])
    if existing is not None and existing.get("status") == "completed" and not force:
        raise RuntimeError(
            f"{meta['slug']} is already graded (status=completed) — regenerating would "
            f"silently wipe its actual/accuracy data. Pass force=True (--force on the CLI) "
            f"if you really mean to redo it; you'll need to re-run check_results.py "
            f"afterward to re-grade it."
        )

    raw = load_race_context(round_number, backtest=backtest)
    features = build_features(raw)
    predictions = monte_carlo_simulate(
        features, raw["profile"], n_sims=100_000, rain_probability=raw["rain_probability"]
    )

    payload = {
        "year": SEASON_YEAR,
        "round": round_number,
        "race_name": meta["event_name"],
        "slug": meta["slug"],
        "race_date": meta["race_date"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backtest": backtest,
        "status": "predicted",
        "n_simulations": 100_000,
        "rain_probability_pct": round(raw["rain_probability"] * 100, 1),
        "grid_source": raw["grid_source"],
        "tire_deg_source": raw["tire_deg_source"],
        "circuit_profile": {
            "overtaking_difficulty": raw["profile"]["overtaking_difficulty"],
            "downforce_level": raw["profile"]["downforce_level"],
            "tire_severity": raw["profile"]["tire_severity"],
        },
        "predicted": [
            {
                "position": i + 1,
                "driver": row["driver"],
                "team": row.get("team", ""),
                "win_pct": row["win_pct"],
                "podium_pct": row["podium_pct"],
                "points_pct": row["points_pct"],
                "expected_position": row["expected_position"],
            }
            for i, row in enumerate(predictions.to_dict(orient="records"))
        ],
        "actual": None,
        "accuracy": None,
    }

    archive.write_race(meta["slug"], payload)
    print(f"Wrote {len(payload['predicted'])} driver predictions to {archive.race_path(meta['slug'])}")
    return meta["slug"]


def rebuild_index() -> None:
    rounds = _season_rounds()
    races = []
    for r in rounds:
        existing = archive.read_race(r["slug"])
        status = existing.get("status", "not_predicted") if existing else "not_predicted"
        races.append(
            {
                "round": r["round"],
                "slug": r["slug"],
                "race_name": r["event_name"],
                "race_date": r["race_date"],
                "status": status,
            }
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    upcoming = [r for r in races if r["race_date"] >= today and r["status"] != "completed"]
    next_race_slug = upcoming[0]["slug"] if upcoming else None

    index = {
        "season": SEASON_YEAR,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "races": races,
        "next_race_slug": next_race_slug,
        "track_record": archive.compute_track_record(),
    }
    archive.write_index(index)
    print(f"Rebuilt index.json — {len(races)} rounds, next: {next_race_slug}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--round", type=int, default=None, help="Round number to predict (default: next unpredicted/incomplete round)")
    parser.add_argument("--backtest", action="store_true", help="Blind pre-race prediction for a round that already happened")
    parser.add_argument("--force", action="store_true", help="Overwrite an already-graded (completed) race — you'll need to re-run check_results.py after")
    args = parser.parse_args()

    if args.round is not None:
        round_number = args.round
    else:
        rounds = _season_rounds()
        round_number = _next_round_to_predict(rounds)["round"]

    generate(round_number, backtest=args.backtest, force=args.force)
    rebuild_index()


if __name__ == "__main__":
    main()
