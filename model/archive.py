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


def compute_track_record() -> dict:
    """Aggregates accuracy across every completed, graded race in the
    archive. Returns None-valued fields if nothing's been graded yet."""
    if not PREDICTIONS_DIR.exists():
        races_scored = []
    else:
        races_scored = []
        for path in sorted(PREDICTIONS_DIR.glob("*.json")):
            if path.name == "index.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("status") == "completed" and data.get("accuracy"):
                races_scored.append(data)

    if not races_scored:
        return {
            "races_scored": 0,
            "winner_hit_rate_pct": None,
            "avg_brier_score_win": None,
            "avg_mean_abs_position_error": None,
            "avg_podium_hits": None,
        }

    n = len(races_scored)
    winner_hits = sum(1 for r in races_scored if r["accuracy"]["winner_correct"])
    avg_brier = sum(r["accuracy"]["brier_score_win"] for r in races_scored) / n
    avg_pos_err = sum(r["accuracy"]["mean_abs_position_error"] for r in races_scored) / n
    avg_podium_hits = sum(r["accuracy"]["podium_hits"] for r in races_scored) / n

    return {
        "races_scored": n,
        "winner_hit_rate_pct": round(winner_hits / n * 100, 1),
        "avg_brier_score_win": round(avg_brier, 4),
        "avg_mean_abs_position_error": round(avg_pos_err, 2),
        "avg_podium_hits": round(avg_podium_hits, 2),
    }
