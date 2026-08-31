"""
Per-circuit characteristics used to re-weight the Monte Carlo model for
each track, instead of hardcoding one track's numbers everywhere.

These three scores are the same kind of domain knowledge the original
Monza-only model asserted in prose ("Monza is low-downforce, overtaking is
easy, tire deg is low") — just made explicit and reusable per circuit:

- overtaking_difficulty (0-1): how hard it is to pass on track. Higher =
  grid position should matter MORE (Monaco, Hungaroring).
- downforce_level (0-1): how downforce/cornering-grip dependent the track
  is, as opposed to straight-line-speed dependent. Higher = top speed
  should matter LESS (Monaco, Singapore); lower = top speed matters MORE
  (Monza, Spa, Vegas).
- tire_severity (0-1): how much tire degradation typically shapes the
  race. Higher = tire-management skill should matter MORE (Qatar,
  Bahrain, Silverstone); lower = it matters less (Monaco, Monza).

These are characterized from publicly known circuit characteristics, not
derived from this project's own lap data — deriving them robustly would
need years of overtake-count telemetry we don't have. Treat them as an
editable estimate, not a measured constant; if a track's characteristics
don't seem right, the fix is to adjust its row here, not the formulas that
consume it (see race_model.py's weight_profile_for()).

`historical_key` is the name used to look up that circuit's *past* races
via FastF1 (fastf1.get_session(year, historical_key, "R")), which can
differ from this year's official EventName when a circuit's race changed
its title (see round 7 below). None means the circuit is new for this
season and has no pre-2026 history to pull — build_features() already
handles an empty historical baseline gracefully (imputes the field
average).
"""

CIRCUIT_PROFILES = {
    1: {
        "event_name": "Australian Grand Prix",
        "historical_key": "Australian Grand Prix",
        "overtaking_difficulty": 0.45,
        "downforce_level": 0.50,
        "tire_severity": 0.45,
    },
    2: {
        "event_name": "Chinese Grand Prix",
        "historical_key": "Chinese Grand Prix",
        "overtaking_difficulty": 0.40,
        "downforce_level": 0.50,
        "tire_severity": 0.55,
    },
    3: {
        "event_name": "Japanese Grand Prix",
        "historical_key": "Japanese Grand Prix",
        "overtaking_difficulty": 0.75,
        "downforce_level": 0.75,
        "tire_severity": 0.55,
    },
    4: {
        "event_name": "Miami Grand Prix",
        "historical_key": "Miami Grand Prix",
        "overtaking_difficulty": 0.55,
        "downforce_level": 0.55,
        "tire_severity": 0.55,
    },
    5: {
        "event_name": "Canadian Grand Prix",
        "historical_key": "Canadian Grand Prix",
        "overtaking_difficulty": 0.35,
        "downforce_level": 0.35,
        "tire_severity": 0.45,
    },
    6: {
        "event_name": "Monaco Grand Prix",
        "historical_key": "Monaco Grand Prix",
        "overtaking_difficulty": 0.95,
        "downforce_level": 0.95,
        "tire_severity": 0.15,
    },
    7: {
        "event_name": "Barcelona Grand Prix",
        # Pre-2026, this circuit's race was titled "Spanish Grand Prix" —
        # Madrid takes that title for 2026 (round 14, brand new, no
        # history). Use the pre-rename name to find Catalunya's own past.
        "historical_key": "Spanish Grand Prix",
        "overtaking_difficulty": 0.70,
        "downforce_level": 0.70,
        "tire_severity": 0.70,
    },
    8: {
        "event_name": "Austrian Grand Prix",
        "historical_key": "Austrian Grand Prix",
        "overtaking_difficulty": 0.25,
        "downforce_level": 0.30,
        "tire_severity": 0.40,
    },
    9: {
        "event_name": "British Grand Prix",
        "historical_key": "British Grand Prix",
        "overtaking_difficulty": 0.45,
        "downforce_level": 0.55,
        "tire_severity": 0.75,
    },
    10: {
        "event_name": "Belgian Grand Prix",
        "historical_key": "Belgian Grand Prix",
        "overtaking_difficulty": 0.20,
        "downforce_level": 0.25,
        "tire_severity": 0.45,
    },
    11: {
        "event_name": "Hungarian Grand Prix",
        "historical_key": "Hungarian Grand Prix",
        "overtaking_difficulty": 0.85,
        "downforce_level": 0.85,
        "tire_severity": 0.50,
    },
    12: {
        "event_name": "Dutch Grand Prix",
        "historical_key": "Dutch Grand Prix",
        "overtaking_difficulty": 0.75,
        "downforce_level": 0.75,
        "tire_severity": 0.50,
    },
    13: {
        "event_name": "Italian Grand Prix",
        "historical_key": "Italian Grand Prix",
        "overtaking_difficulty": 0.15,
        "downforce_level": 0.05,
        "tire_severity": 0.15,
    },
    14: {
        "event_name": "Spanish Grand Prix",
        # Madrid — new to the calendar in 2026, no pre-2026 history.
        "historical_key": None,
        "overtaking_difficulty": 0.60,
        "downforce_level": 0.55,
        "tire_severity": 0.50,
    },
    15: {
        "event_name": "Azerbaijan Grand Prix",
        "historical_key": "Azerbaijan Grand Prix",
        "overtaking_difficulty": 0.35,
        "downforce_level": 0.30,
        "tire_severity": 0.40,
    },
    16: {
        "event_name": "Bahrain Grand Prix",
        "historical_key": "Bahrain Grand Prix",
        "overtaking_difficulty": 0.30,
        "downforce_level": 0.45,
        "tire_severity": 0.80,
    },
    17: {
        "event_name": "Singapore Grand Prix",
        "historical_key": "Singapore Grand Prix",
        "overtaking_difficulty": 0.85,
        "downforce_level": 0.85,
        "tire_severity": 0.55,
    },
    18: {
        "event_name": "United States Grand Prix",
        "historical_key": "United States Grand Prix",
        "overtaking_difficulty": 0.45,
        "downforce_level": 0.60,
        "tire_severity": 0.70,
    },
    19: {
        "event_name": "Mexico City Grand Prix",
        "historical_key": "Mexico City Grand Prix",
        "overtaking_difficulty": 0.40,
        "downforce_level": 0.65,
        "tire_severity": 0.35,
    },
    20: {
        "event_name": "São Paulo Grand Prix",
        "historical_key": "São Paulo Grand Prix",
        "overtaking_difficulty": 0.35,
        "downforce_level": 0.50,
        "tire_severity": 0.60,
    },
    21: {
        "event_name": "Las Vegas Grand Prix",
        "historical_key": "Las Vegas Grand Prix",
        "overtaking_difficulty": 0.30,
        "downforce_level": 0.25,
        "tire_severity": 0.35,
    },
    22: {
        "event_name": "Qatar Grand Prix",
        "historical_key": "Qatar Grand Prix",
        "overtaking_difficulty": 0.50,
        "downforce_level": 0.70,
        "tire_severity": 0.85,
    },
    23: {
        "event_name": "Abu Dhabi Grand Prix",
        "historical_key": "Abu Dhabi Grand Prix",
        "overtaking_difficulty": 0.60,
        "downforce_level": 0.60,
        "tire_severity": 0.40,
    },
}


def get_profile(round_number: int) -> dict:
    if round_number not in CIRCUIT_PROFILES:
        raise KeyError(
            f"No circuit profile for round {round_number}. Add one to "
            f"CIRCUIT_PROFILES in circuit_profiles.py — see the module "
            f"docstring for what each field means and how to estimate it."
        )
    return CIRCUIT_PROFILES[round_number]
