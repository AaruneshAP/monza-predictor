// Pure display-formatting helpers — deliberately no fs/path or other
// server-only imports here, unlike lib/data.ts, so this is safe to
// import as a runtime value from a "use client" component (RaceDetail.tsx)
// without dragging Node built-ins into the client bundle.

// check_results.py rounds every Brier score to 4 decimal places, but JSON
// (and JS) drops trailing zeros — a genuinely exact 0.0 (the baseline
// nailing a race, e.g. the polesitter winning) serializes as the bare
// number 0 and renders as "0" next to a model score like "0.0323",
// reading like a missing value rather than the real, perfect score it
// is. Always render a Brier score through this so 0 shows as "0.0000",
// not "0".
export function formatBrier(n: number): string {
  return n.toFixed(4);
}

// A qualifying lap time in seconds, as "M:SS.sss" — the standard F1 timing
// display (e.g. 83.456 -> "1:23.456"). Every real quali lap in this sport
// is well over a minute, so this always shows the minutes digit rather
// than switching format below 60s.
export function formatLapTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return `${minutes}:${rest.toFixed(3).padStart(6, "0")}`;
}
