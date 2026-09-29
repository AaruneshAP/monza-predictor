"""One-off diagnostic: prints the real FastF1 event schedule for
SEASON_YEAR alongside what circuit_profiles.py assumes for each round, so a
mismatch (calendar swap, replaced race, reshuffled round order) can be
spotted directly instead of silently feeding the wrong historical_key into
the model. Not wired into the regular pipeline — run manually via
workflow_dispatch when the real calendar might have changed.
"""

import fastf1

from race_model import SEASON_YEAR
from circuit_profiles import CIRCUIT_PROFILES

schedule = fastf1.get_event_schedule(SEASON_YEAR)
schedule = schedule[schedule["RoundNumber"] > 0].set_index("RoundNumber")

print(f"{'Rnd':<4} {'Real EventName (FastF1)':<32} {'Real Date':<12} {'Location':<18} {'Country':<14} {'Profile event_name':<32} {'Match?'}")
for round_number in sorted(schedule.index):
    row = schedule.loc[round_number]
    real_name = row["EventName"]
    real_date = row["EventDate"].strftime("%Y-%m-%d")
    location = row.get("Location", "?")
    country = row.get("Country", "?")
    profile = CIRCUIT_PROFILES.get(round_number)
    profile_name = profile["event_name"] if profile else "(no profile)"
    match = "OK" if profile and profile_name == real_name else "MISMATCH"
    print(f"{round_number:<4} {real_name:<32} {real_date:<12} {location:<18} {country:<14} {profile_name:<32} {match}")
