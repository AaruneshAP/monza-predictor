"""
Runs the Monza model and writes frontend/public/predictions.json
in the exact shape the Next.js frontend expects.

Usage:
    python model/generate_predictions.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from monza_gp_model import load_monza_context, build_features, monte_carlo_simulate

OUTPUT_PATH = Path(__file__).parent.parent / "frontend" / "public" / "predictions.json"


def main():
    raw = load_monza_context()
    features = build_features(raw)
    rain_probability = raw["rain_probability"]
    predictions = monte_carlo_simulate(
        features, n_sims=100_000, rain_probability=rain_probability
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "race": "Italian Grand Prix — Monza",
        "n_simulations": 100_000,
        "rain_probability_pct": round(rain_probability * 100, 1),
        "grid_source": raw["grid_source"],
        "tire_deg_source": raw["tire_deg_source"],
        "drivers": [
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
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(payload['drivers'])} driver predictions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
