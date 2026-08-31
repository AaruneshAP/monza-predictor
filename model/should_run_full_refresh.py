"""
Cheap gate for the scheduled GitHub Action: is today within a race
weekend's window? Prints `true`/`false` and writes it to $GITHUB_OUTPUT
(if set) so the workflow can poll every few hours year-round without
burning FastF1 calls (or piling up empty commits) outside race weeks —
the tight cadence only actually does anything when it matters, and no one
has to remember to edit cron dates before each race.

Usage:
    python should_run_full_refresh.py
"""

import os
from datetime import datetime, timedelta, timezone

import fastf1

SEASON_YEAR = 2026
WINDOW_BEFORE_DAYS = 3  # start polling tightly from the Thursday of race week (covers FP1/FP2)
WINDOW_AFTER_DAYS = 2   # keep polling through Tuesday, in case result grading lags


def should_run() -> bool:
    fastf1.Cache.enable_cache("./fastf1_cache")
    schedule = fastf1.get_event_schedule(SEASON_YEAR)
    schedule = schedule[schedule["RoundNumber"] > 0]
    today = datetime.now(timezone.utc).date()

    for _, row in schedule.iterrows():
        race_date = row["EventDate"].date()
        window_start = race_date - timedelta(days=WINDOW_BEFORE_DAYS)
        window_end = race_date + timedelta(days=WINDOW_AFTER_DAYS)
        if window_start <= today <= window_end:
            return True
    return False


def main():
    result = should_run()
    print("true" if result else "false")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"should_run={'true' if result else 'false'}\n")


if __name__ == "__main__":
    main()
