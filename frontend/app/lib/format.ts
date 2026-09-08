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
