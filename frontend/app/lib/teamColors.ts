/**
 * Real team colors for the 2026 grid, keyed by a lowercase substring of the
 * team name — the archive's `team` field isn't consistent across rounds
 * (e.g. "Red Bull" vs "Red Bull Racing", "Alpine" vs "Alpine F1 Team", "RB
 * F1 Team" vs "Racing Bulls"), so matching is substring-based rather than
 * an exact lookup. Order matters: checked top to bottom, first match wins
 * (kept short so a more specific fragment doesn't get shadowed by a
 * shorter, unrelated one).
 *
 * Colors are the commonly-cited livery hex for each team. Audi and
 * Cadillac are new to the 2026 grid — their liveries are best-effort
 * approximations (Audi's traditional motorsport red, Cadillac's brand
 * navy) rather than a confirmed official color, since neither has raced
 * yet; update these once a livery is actually revealed.
 */
const TEAM_COLORS: [fragment: string, color: string][] = [
  ["ferrari", "#E8002D"],
  ["mclaren", "#FF8000"],
  ["mercedes", "#00D2BE"],
  ["red bull", "#3671C6"],
  ["aston martin", "#229971"],
  ["alpine", "#0090FF"],
  ["williams", "#64C4FF"],
  ["racing bulls", "#6692FF"],
  ["rb f1", "#6692FF"],
  ["haas", "#B6BABD"],
  ["audi", "#BB0A30"],
  ["cadillac", "#001489"],
];

const FALLBACK_COLOR = "#525252"; // neutral-600 — an unrecognized/future team name

export function teamColor(team: string): string {
  const lower = team.toLowerCase();
  for (const [fragment, color] of TEAM_COLORS) {
    if (lower.includes(fragment)) return color;
  }
  return FALLBACK_COLOR;
}
