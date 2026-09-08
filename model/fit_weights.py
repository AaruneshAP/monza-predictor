"""
Fits the 7 base_score-term calibration scalars (see race_model.py's
HAND_TUNED_WEIGHTS/DEFAULT_CALIBRATION) against every graded round
currently in the track record, instead of leaving them hand-picked.

Usage:
    python fit_weights.py            # fit and write fitted_weights.json
    python fit_weights.py --apply    # also regenerate every graded round's
                                      # backtest with the new weights and
                                      # re-grade it, for a real (not proxy)
                                      # before/after Brier comparison

Writes model/fitted_weights.json (calibration + metadata: how many races,
which rounds, what date range, the method). race_model.py's
weight_profile_for() picks this up automatically on every subsequent
run — nothing else needs to change once this has run for the *next*
prediction. --apply additionally rewrites the `predicted` half of every
round already used to fit (never `actual` — the real result doesn't
change) so the track record itself reflects the new weights immediately,
rather than only new predictions from here on.

METHOD
------
For each graded round, this re-runs the exact same blind backtest
load_race_context(round, backtest=True) + build_features() originally
used to predict it (never the round's own live data — see
race_model.py's module docstring), then reads off each driver's
7 base_score terms at the pure hand-tuned baseline (calibration all
1.0) via compute_contributions().

Fitting itself is a coordinate-wise grid search minimizing a Brier-score
proxy — the real metric this project already reports everywhere else,
not a generic loss picked for its own sake. The real Monte Carlo model
turns a driver's score into a win probability by adding Gaussian noise
and ranking 100,000 times per race; that isn't cheap enough to evaluate
per candidate weight vector during a search. This script substitutes a
softmax over each driver's base_score as a fast stand-in for "probability
this driver has the highest simulated score" — the two coincide exactly
if the per-driver noise were i.i.d. Gumbel rather than Gaussian (the
standard random-utility/discrete-choice result), and are a reasonable
approximation given how close a Gaussian and a Gumbel actually look. This
proxy is ONLY used to pick the calibration scalars efficiently — the
authoritative before/after comparison is the real thing: regenerate each
graded round's backtest with the fitted weights via
`generate_predictions.py --round N --backtest --force`, then re-grade
with `check_results.py --regrade` and compare real Brier scores, exactly
as documented in DEBUGGING.md's entry for this change.

Both calibration and the sample it was fit from are stored explicitly
in fitted_weights.json rather than left implicit, because the sample is
genuinely small (however many rounds are graded when this ran — check
the file) and that limitation should travel with the numbers, not get
lost once they're sitting in a formula.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import archive
from race_model import (
    DEFAULT_CALIBRATION,
    build_features,
    compute_contributions,
    load_race_context,
)

FITTED_WEIGHTS_PATH = Path(__file__).parent / "fitted_weights.json"

# Human labels for calibration.items()'s keys, purely for the summary
# printout — distinct from SCORE_TERM_LABELS (race_model.py), which
# labels the terms *those* keys scale, not the scaling keys themselves.
CALIBRATION_LABELS = {
    "quali_weight": "Quali pace",
    "points_weight": "Season form (championship points)",
    "grid_weight": "Grid position",
    "top_speed_weight": "Top speed",
    "tire_deg_weight": "Tire management",
    "historical_weight": "Historical form at this circuit",
    "pit_weight": "Pit stops",
}

# Candidates tried for each term in turn, holding the others at their
# current-best value — deliberately centered on 1.0 (the hand-tuned
# formula, unchanged) so "no evidence to move this weight" is a real,
# reachable outcome, not just the search's starting point.
CANDIDATES = [0.25, 0.4, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
COORDINATE_DESCENT_PASSES = 4


def _training_races() -> list[dict]:
    """Every graded round, with each driver's base_score terms (at the
    hand-tuned baseline) and the real winner — the pooled dataset the fit
    runs against. Skips a round if the real winner isn't even in its
    rebuilt driver set (a last-minute substitution the backtest's grid
    projection didn't have — same "can't train on it" call check_results.py
    makes for a grid mismatch elsewhere) or if FastF1 has nothing for it.
    """
    races = []
    for race in archive._scored_races():
        round_number = race["round"]
        actual_winner = race["accuracy"]["actual_winner"]
        try:
            raw = load_race_context(round_number, backtest=True)
        except Exception as exc:
            print(f"  round {round_number}: skipping (couldn't rebuild features: {exc})")
            continue
        features = build_features(raw)
        contributions = compute_contributions(
            features, raw["profile"], rain_probability=raw["rain_probability"], calibration=DEFAULT_CALIBRATION
        )
        if actual_winner not in contributions:
            print(f"  round {round_number}: skipping ({actual_winner} not in the rebuilt driver set)")
            continue
        races.append(
            {
                "round": round_number,
                "event_name": raw["event_name"],
                "race_date": race["race_date"],
                "actual_winner": actual_winner,
                "terms_by_driver": {driver: c["terms"] for driver, c in contributions.items()},
            }
        )
    return races


def _scores_by_driver(race: dict, calibration: dict) -> dict[str, float]:
    scores = {}
    for driver, terms in race["terms_by_driver"].items():
        scores[driver] = sum(calibration[t["key"]] * t["value"] for t in terms)
    return scores


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    max_score = max(scores.values())
    exp_scores = {driver: pow(2.718281828459045, s - max_score) for driver, s in scores.items()}
    total = sum(exp_scores.values())
    return {driver: v / total for driver, v in exp_scores.items()}


def _pooled_brier(calibration: dict, races: list[dict]) -> float:
    """Average, across races, of the per-race mean squared error between
    each driver's softmax-proxy win probability and whether they actually
    won — the same Brier-score shape check_results.py's _score() computes
    for the real model, applied to the fast proxy instead of a full
    Monte Carlo run."""
    race_briers = []
    for race in races:
        probs = _softmax(_scores_by_driver(race, calibration))
        terms = [(probs[d], 1.0 if d == race["actual_winner"] else 0.0) for d in probs]
        race_briers.append(sum((p - y) ** 2 for p, y in terms) / len(terms))
    return sum(race_briers) / len(race_briers)


def _fit_calibration(races: list[dict]) -> tuple[dict, float, float]:
    """Coordinate-wise grid search: for each term in turn, try every
    candidate scalar holding the rest fixed, keep whichever minimizes
    pooled proxy Brier, repeat for COORDINATE_DESCENT_PASSES passes."""
    calibration = dict(DEFAULT_CALIBRATION)
    baseline_brier = _pooled_brier(calibration, races)

    for _ in range(COORDINATE_DESCENT_PASSES):
        for key in calibration:
            best_value = calibration[key]
            best_brier = _pooled_brier(calibration, races)
            for candidate in CANDIDATES:
                trial = dict(calibration)
                trial[key] = candidate
                brier = _pooled_brier(trial, races)
                if brier < best_brier:
                    best_brier, best_value = brier, candidate
            calibration[key] = best_value

    fitted_brier = _pooled_brier(calibration, races)
    if fitted_brier >= baseline_brier:
        # Small-sample overfitting risk is real here — if the search
        # can't even beat the untouched hand-tuned baseline on its own
        # training data, trust the baseline instead of a "fit" that
        # isn't actually fitting anything.
        return dict(DEFAULT_CALIBRATION), baseline_brier, baseline_brier
    return calibration, baseline_brier, fitted_brier


def _apply(races: list[dict]) -> None:
    """Regenerates every trained-on round's backtest with the just-fitted
    weights (now on disk, so generate_predictions.py picks them up
    automatically) and re-grades them — the real before/after comparison,
    not the proxy one. Still backtest=True throughout: this changes which
    weights score the same pre-race-only data, not what data is used, so
    it's not hindsight."""
    import subprocess
    import sys

    import generate_predictions

    before = archive.compute_track_record()

    print("\nRegenerating each graded round's backtest with the fitted weights...")
    for race in races:
        generate_predictions.generate(race["round"], backtest=True, force=True)
        print(f"  round {race['round']} ({race['event_name']}): regenerated")

    print("\nRe-grading against the real results...")
    subprocess.run([sys.executable, "check_results.py", "--regrade"], check=True, cwd=Path(__file__).parent)

    after = archive.compute_track_record()
    print(f"\nReal Brier score — before: {before['avg_brier_score_win']}  →  after: {after['avg_brier_score_win']}")
    print(f"Baseline (always-pick-polesitter) Brier for comparison: {after['avg_baseline_brier_score_win']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Also regenerate and re-grade every trained-on round's backtest with the fitted weights, for a real before/after Brier comparison (not just the fitting proxy's).",
    )
    args = parser.parse_args()

    print("Rebuilding features for every graded round (blind backtest — no hindsight)...")
    races = _training_races()
    if len(races) < 2:
        print(
            f"Only {len(races)} usable graded race(s) — too few to fit anything meaningful. "
            "Leaving fitted_weights.json untouched."
        )
        return

    print(f"Fitting against {len(races)} races: " + ", ".join(f"round {r['round']} ({r['event_name']})" for r in races))
    calibration, baseline_brier, fitted_brier = _fit_calibration(races)

    dates = sorted(r["race_date"] for r in races)
    payload = {
        "calibration": calibration,
        "meta": {
            "fit_at": datetime.now(timezone.utc).isoformat(),
            "method": "coordinate-wise grid search minimizing a softmax-proxy Brier score (see fit_weights.py docstring)",
            "n_races": len(races),
            "rounds": [r["round"] for r in races],
            "date_range": [dates[0], dates[-1]],
            "proxy_brier_baseline": round(baseline_brier, 4),
            "proxy_brier_fitted": round(fitted_brier, 4),
        },
    }
    FITTED_WEIGHTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nFit from {len(races)} races ({dates[0]} to {dates[-1]}):")
    for key, value in calibration.items():
        print(f"  {CALIBRATION_LABELS[key]:35s} {value:.2f}x hand-tuned")
    print(f"\nProxy Brier — baseline (all 1.0x): {baseline_brier:.4f}  →  fitted: {fitted_brier:.4f}")
    print(f"Wrote {FITTED_WEIGHTS_PATH}")

    if args.apply:
        _apply(races)
    else:
        print(
            "\nThis is the fast proxy used only to pick the weights — for the real, authoritative "
            "before/after comparison, re-run with --apply (regenerates and re-grades every "
            "trained-on round's backtest with the fitted weights)."
        )


if __name__ == "__main__":
    main()
