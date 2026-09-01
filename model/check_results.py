"""
Grades every predicted-but-not-yet-graded race in the archive against its
real result, once that race has actually happened. This is what makes the
"predicted vs actual" track record real rather than aspirational — it
only ever compares a prediction against a result that came after it was
generated (backtested predictions are blind by construction — see
race_model.load_race_context's backtest mode).

Usage:
    python check_results.py

Run this after generate_predictions.py in the scheduled workflow (see
.github/workflows/refresh-predictions.yml) — each run grades whatever
races have finished since the last run and leaves everything else alone.
"""

import os
from datetime import datetime, timezone

import fastf1
import pandas as pd

import archive
from generate_predictions import _season_rounds, rebuild_index
from race_model import SEASON_YEAR


def _load_actual_result(round_number: int) -> list[dict] | None:
    """Full classification for a round, DNFs given a fallback position one
    behind the last classified driver (same convention as the historical
    baseline in race_model.py, for consistency). Returns None if the
    session has no real result yet (race hasn't actually happened, even if
    its scheduled date has passed)."""
    try:
        session = fastf1.get_session(SEASON_YEAR, round_number, "R")
        session.load(laps=False, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        print(f"  round {round_number}: couldn't load session ({exc})")
        return None
    if session.results is None or len(session.results) == 0:
        return None

    results = session.results.copy()
    max_classified = results["Position"].max()
    fallback_pos = (max_classified if pd.notna(max_classified) else len(results)) + 1
    results["Position"] = results["Position"].fillna(fallback_pos)

    return [
        {"driver": r["Abbreviation"], "team": r["TeamName"], "position": int(r["Position"])}
        for _, r in results.iterrows()
    ]


def _score(predicted: list[dict], actual: list[dict]) -> dict:
    predicted_by_driver = {row["driver"]: row for row in predicted}
    actual_position_by_driver = {row["driver"]: row["position"] for row in actual}

    predicted_winner = predicted[0]["driver"]  # predicted list is sorted by win_pct desc
    actual_winner = next(r["driver"] for r in actual if r["position"] == 1)

    # Brier score needs a proper probability distribution over the actual
    # winner. If the real winner wasn't even on the grid the model
    # predicted (grid mismatch — a very-last-minute substitution, say),
    # add them at 0% so the score still penalizes correctly instead of
    # silently looking better than it is.
    win_probs = {row["driver"]: row["win_pct"] / 100 for row in predicted}
    if actual_winner not in win_probs:
        win_probs[actual_winner] = 0.0
    brier_terms = [
        (prob - (1.0 if driver == actual_winner else 0.0)) ** 2
        for driver, prob in win_probs.items()
    ]
    brier_score_win = sum(brier_terms) / len(brier_terms)

    predicted_podium = {row["driver"] for row in predicted[:3]}
    actual_podium = {driver for driver, pos in actual_position_by_driver.items() if pos <= 3}
    podium_hits = len(predicted_podium & actual_podium)

    position_errors = [
        abs(row["expected_position"] - actual_position_by_driver[row["driver"]])
        for row in predicted
        if row["driver"] in actual_position_by_driver
    ]
    mean_abs_position_error = round(sum(position_errors) / len(position_errors), 2) if position_errors else None

    return {
        "predicted_winner": predicted_winner,
        "predicted_winner_prob_pct": predicted_by_driver[predicted_winner]["win_pct"],
        "actual_winner": actual_winner,
        "winner_correct": predicted_winner == actual_winner,
        "actual_winner_predicted_prob_pct": predicted_by_driver.get(actual_winner, {}).get("win_pct", 0.0),
        "podium_hits": podium_hits,
        "brier_score_win": round(brier_score_win, 4),
        "mean_abs_position_error": mean_abs_position_error,
    }


def main():
    os.makedirs("./fastf1_cache", exist_ok=True)
    fastf1.Cache.enable_cache("./fastf1_cache")
    graded_any = False

    for r in _season_rounds():
        existing = archive.read_race(r["slug"])
        if existing is None:
            continue  # never predicted — nothing to grade
        if existing.get("status") == "completed":
            continue  # already graded
        if existing.get("race_date") > datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            continue  # hasn't happened yet

        print(f"Checking round {r['round']} ({r['event_name']})...")
        actual = _load_actual_result(r["round"])
        if actual is None:
            print("  no result yet, skipping")
            continue

        existing["status"] = "completed"
        existing["actual"] = {
            "classification": actual,
            "graded_at": datetime.now(timezone.utc).isoformat(),
        }
        existing["accuracy"] = _score(existing["predicted"], actual)
        archive.write_race(r["slug"], existing)
        print(f"  graded: predicted {existing['accuracy']['predicted_winner']} to win, actual winner {existing['accuracy']['actual_winner']} ({'correct' if existing['accuracy']['winner_correct'] else 'incorrect'})")
        graded_any = True

    rebuild_index()
    if not graded_any:
        print("Nothing new to grade.")


if __name__ == "__main__":
    main()
