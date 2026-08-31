# Monza GP Predictor — Project Brief

## Goal
A portfolio piece for job search. A live, polished website that shows a
Monte Carlo win-probability model for the F1 Monza Grand Prix, built with
real FastF1 data. The audience is a hiring contact (non-F1-expert), so the
site should clearly communicate the *methodology* (Monte Carlo simulation,
feature engineering, why Monza is weighted differently from other tracks),
not just show a table of numbers.

## Architecture (zero-cost, no live backend)
- `model/` — Python. Pulls FastF1 data, runs the Monte Carlo simulation,
  writes the result to `frontend/public/predictions.json`.
- `frontend/` — Next.js + Tailwind. Statically reads `predictions.json`
  at build time. No API calls at runtime, no server, no cold starts.
- Deploy: `frontend/` → Vercel (free). Re-run the model + redeploy
  whenever you want fresh numbers (see `.github/workflows/` for an
  optional scheduled refresh via GitHub Actions, also free).

## Why this architecture (for whoever reads this repo)
Explicitly avoiding Railway/Render/Fly.io for the backend: as of 2026 none
of them offer a real always-on free tier without cold-start delays or
credit-card-gated trials. A static JSON + static site sidesteps hosting
costs entirely and demos instantly — important since this will be shown
live to a recruiter/contact.

## Build order
1. Get `model/monza_gp_model.py` producing real, sane output using actual
   FastF1 data (see stub functions with TODOs).
2. `model/generate_predictions.py` — runs the model, serializes to
   `frontend/public/predictions.json` in the exact shape the frontend
   expects (see `PredictionRow` type in `frontend/app/page.tsx`).
3. Build the frontend UI against the JSON: landing/hero section,
   prediction table, a simple bar chart of win%, and a short
   "methodology" section explaining Monte Carlo + Monza-specific weighting.
4. Polish: loading states not needed (static data), but do handle empty/
   stale-data states gracefully (e.g. "predictions last updated: <date>").
5. Deploy `frontend/` to Vercel. Confirm it works with no env vars needed.

## Design direction
Motorsport-adjacent but not cheesy — dark background, one accent color
(not a generic red/checkered-flag cliché), clean data-forward typography.
This is a job-search portfolio piece: it should read as "software
engineer who understands ML and can ship a real product," not "F1 fan
site."

## Non-goals
- No user accounts, no live betting odds, no real-time race data during
  the actual GP (out of scope for v1).
- No paid infrastructure of any kind.
