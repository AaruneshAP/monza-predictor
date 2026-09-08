"""
Regenerates one or more already-graded rounds' predictions (bypassing the
"already completed" guard) with whatever weights are current, then
re-grades them against the real results — for backfilling a schema
change (a new predicted-row field, e.g. contributions or win_pct_stdev)
onto rounds that were graded before that field existed, without
re-fitting or touching any other round. A one-off, not for regular use;
see `predict`/`regrade`/`fit_weights` in refresh-predictions.yml for the
other one-off workflow_dispatch inputs this mirrors.

Usage:
    python backfill_round.py 12 13
"""

import subprocess
import sys
from pathlib import Path

import generate_predictions


def main():
    if len(sys.argv) < 2:
        print("Usage: python backfill_round.py ROUND [ROUND ...]")
        sys.exit(1)
    rounds = [int(r) for r in sys.argv[1:]]

    for round_number in rounds:
        slug = generate_predictions.generate(round_number, backtest=True, force=True)
        print(f"Regenerated round {round_number} ({slug})")

    print("\nRe-grading against the real results...")
    subprocess.run([sys.executable, "check_results.py", "--regrade"], check=True, cwd=Path(__file__).parent)


if __name__ == "__main__":
    main()
