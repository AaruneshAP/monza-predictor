# Monza GP Predictor

A Monte Carlo simulation model predicting the Italian Grand Prix winner,
built on real FastF1 data, served as a static site.

**Live demo:** _add your Vercel URL here after deploying_

## How it works
- `model/` — Python. Pulls FastF1 qualifying, practice, and historical
  Monza data; runs a 100,000-iteration Monte Carlo simulation weighted for
  Monza's low-downforce, high-top-speed, slipstream-heavy characteristics.
- `frontend/` — Next.js + Tailwind + Recharts. Statically renders the
  simulation output — no backend, no server, no cold starts.

## Stack
Python (FastF1, pandas, numpy) · Next.js · TypeScript · Tailwind CSS ·
Recharts · deployed on Vercel

## Running locally
```
cd model && pip install -r requirements.txt && python generate_predictions.py
cd ../frontend && npm install && npm run dev
```

See `CLAUDE.md` for the full project brief and `DEPLOYMENT.md` for deploy
steps.
