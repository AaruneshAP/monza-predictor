# Deployment (all free tier)

## Why no backend
Render's free tier sleeps after 15 min idle (30-50s cold start on wake) —
bad for a live demo. Railway and Fly.io no longer have real free tiers as
of 2026. This project sidesteps all of that: the model runs locally (or in
GitHub Actions, also free) and writes a static JSON file. The frontend is
100% static. No server to sleep, no cost, no cold start.

## Steps

1. **Run the model locally** to generate real data:
   ```
   cd model
   pip install -r requirements.txt
   python generate_predictions.py   # predicts the next upcoming race
   python check_results.py          # grades any races that have since finished
   ```
   This writes/updates `frontend/public/predictions/{slug}.json` and
   `frontend/public/predictions/index.json`.

2. **Push to GitHub** (a public repo also doubles as your portfolio piece —
   good README, clear commits).

3. **Deploy frontend to Vercel** (free):
   - Go to vercel.com → New Project → import your GitHub repo
   - Set the root directory to `frontend/`
   - Framework preset: Next.js (auto-detected)
   - Deploy — no environment variables needed

4. **(Optional) Auto-refresh predictions**: the included GitHub Action
   (`.github/workflows/refresh-predictions.yml`) predicts the next
   upcoming race and grades any race that's finished since the last run,
   daily, committing the updated archive. Vercel auto-redeploys on every
   push to main. Fully free, fully automated.

## Custom domain (optional, still free)
Vercel gives you a free `*.vercel.app` subdomain. If you want something
cleaner for a portfolio link, a `.me` or similar domain from a registrar
costs a small yearly fee — not required, just an option.
