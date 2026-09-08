"""
Shared helpers for the prediction archive: slugs, file paths, and
index.json / per-race JSON read-write. Both generate_predictions.py
(writes predictions) and check_results.py (writes actual results and
grades them) import this so the two scripts can't disagree about the
file layout or how the track record is computed.
"""

import json
import re
from pathlib import Path

PREDICTIONS_DIR = Path(__file__).parent.parent / "frontend" / "public" / "predictions"
INDEX_PATH = PREDICTIONS_DIR / "index.json"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def race_slug(year: int, round_number: int, event_name: str) -> str:
    return f"{year}-r{round_number:02d}-{slugify(event_name)}"


def race_path(slug: str) -> Path:
    return PREDICTIONS_DIR / f"{slug}.json"


def read_race(slug: str) -> dict | None:
    path = race_path(slug)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_race(slug: str, data: dict) -> None:
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    race_path(slug).write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_index() -> dict:
    if not INDEX_PATH.exists():
        return {"season": None, "races": [], "next_race_slug": None, "track_record": None}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def write_index(data: dict) -> None:
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _scored_races() -> list[dict]:
    """Every completed, graded race in the archive — the shared source
    both compute_track_record() and compute_calibration_bins() walk, so
    the two can't disagree about which races count as "graded"."""
    if not PREDICTIONS_DIR.exists():
        return []
    races_scored = []
    for path in sorted(PREDICTIONS_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "completed" and data.get("accuracy"):
            races_scored.append(data)
    return races_scored


def compute_track_record() -> dict:
    """Aggregates accuracy across every completed, graded race in the
    archive. Returns None-valued fields if nothing's been graded yet."""
    races_scored = _scored_races()

    if not races_scored:
        return {
            "races_scored": 0,
            "winner_hit_rate_pct": None,
            "avg_brier_score_win": None,
            "avg_mean_abs_position_error": None,
            "avg_podium_hits": None,
            "avg_baseline_brier_score_win": None,
        }

    n = len(races_scored)
    winner_hits = sum(1 for r in races_scored if r["accuracy"]["winner_correct"])
    avg_brier = sum(r["accuracy"]["brier_score_win"] for r in races_scored) / n
    avg_pos_err = sum(r["accuracy"]["mean_abs_position_error"] for r in races_scored) / n
    avg_podium_hits = sum(r["accuracy"]["podium_hits"] for r in races_scored) / n

    # Grid-based baseline (always predict the polesitter to win) — absent
    # per-race if that race had no GridPosition data, so average only over
    # the races that actually have it rather than assuming every race does.
    baseline_briers = [
        r["accuracy"]["baseline"]["brier_score_win"]
        for r in races_scored
        if r["accuracy"].get("baseline")
    ]
    avg_baseline_brier = round(sum(baseline_briers) / len(baseline_briers), 4) if baseline_briers else None

    return {
        "races_scored": n,
        "winner_hit_rate_pct": round(winner_hits / n * 100, 1),
        "avg_brier_score_win": round(avg_brier, 4),
        "avg_mean_abs_position_error": round(avg_pos_err, 2),
        "avg_podium_hits": round(avg_podium_hits, 2),
        "avg_baseline_brier_score_win": avg_baseline_brier,
    }


def compute_calibration_bins(bin_size: int = 10) -> list[dict]:
    """Buckets every driver-race win% prediction across every graded race
    by predicted win%, and for each bucket computes the actual win rate
    among predictions that fell in it.

    This is what a calibration plot needs and a Brier score alone
    doesn't show: not "did we pick the right winner" but "when the model
    said 30%, did drivers it said that about actually win about 30% of
    the time." A model can post a fine Brier score while still being
    systematically over- or under-confident — calibration is the check
    for that, and it matters more than raw hit-rate for anything that
    reports a probability rather than a single guess.

    Small-sample size is exposed per bin (`n`) rather than hidden — with
    only a handful of graded races most bins have very few points, and a
    rate computed from 2 predictions is not the same claim as one from
    200. The frontend should show `n` alongside each point rather than
    let a thin bin look as authoritative as a thick one.
    """
    bins: dict[int, dict] = {}

    for race in _scored_races():
        actual_winner = race["accuracy"]["actual_winner"]
        for row in race["predicted"]:
            win_pct = row["win_pct"]
            bin_start = min(int(win_pct // bin_size) * bin_size, 100 - bin_size)
            b = bins.setdefault(bin_start, {"predicted_sum": 0.0, "wins": 0, "n": 0})
            b["predicted_sum"] += win_pct
            b["n"] += 1
            if row["driver"] == actual_winner:
                b["wins"] += 1

    return [
        {
            "bin_start": bin_start,
            "bin_end": bin_start + bin_size,
            "n": b["n"],
            "avg_predicted_win_pct": round(b["predicted_sum"] / b["n"], 1),
            "actual_win_rate_pct": round(b["wins"] / b["n"] * 100, 1),
        }
        for bin_start, b in sorted(bins.items())
    ]
