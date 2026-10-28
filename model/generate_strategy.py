"""
Generates undercut/pit-window risk-reward estimates for a race and writes
frontend/public/strategy/{slug}.json, the same static-JSON pattern used
for predictions and telemetry.

Folded directly into generate_predictions.py's flow (called from
generate() there) rather than its own script/workflow step: it reuses
the `raw` context and `predictions` DataFrame that run already fetched
and computed, so this adds zero extra FastF1 calls.
"""

import json
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

import pandas as pd

from race_model import SEASON_YEAR, UNDERCUT_WINDOW_LAPS, simulate_undercut

STRATEGY_DIR = Path(__file__).parent.parent / "frontend" / "public" / "strategy"

# Precompute undercut pairs among only the top-N predicted drivers — an
# undercut matters for track position among drivers actually fighting
# each other, and every additional driver adds N-1 more simulated pairs.
TOP_N_DRIVERS = 8


def write_strategy(slug: str, meta: dict, raw: dict, predictions: pd.DataFrame) -> Path:
    """`meta`: the same {round, event_name, race_date, slug} dict
    generate_predictions.py already has for this race. `predictions`:
    the monte_carlo_simulate() output, already sorted by win_pct — only
    used here to pick which drivers are worth simulating undercuts
    between."""
    top = predictions.head(TOP_N_DRIVERS)
    top_drivers = top["driver"].tolist()
    driver_team = dict(zip(top["driver"], top.get("team", pd.Series(dtype=str))))

    pairs = []
    for undercut_driver, rival_driver in permutations(top_drivers, 2):
        pairs.append(
            simulate_undercut(
                undercut_driver,
                rival_driver,
                raw["pit_delta"],
                raw["tire_deg"],
                safety_car_probability=raw["safety_car_probability"],
            )
        )

    payload = {
        "year": SEASON_YEAR,
        "round": meta["round"],
        "race_name": meta["event_name"],
        "slug": meta["slug"],
        "race_date": meta["race_date"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_laps": UNDERCUT_WINDOW_LAPS,
        "safety_car_probability_pct": round(raw["safety_car_probability"] * 100, 1),
        "drivers": [{"driver": d, "team": driver_team.get(d, "")} for d in top_drivers],
        "pairs": pairs,
    }

    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STRATEGY_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(pairs)} undercut pairs to {out_path}")
    return out_path
