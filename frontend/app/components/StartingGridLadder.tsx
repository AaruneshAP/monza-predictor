import type { PredictionRow } from "../lib/data";
import { teamColor } from "../lib/teamColors";

/** Converts a hex color like "#E8002D" to "r, g, b" for use inside an
 * rgba() background — Tailwind's arbitrary values can't parametrize
 * opacity on a value computed at runtime, so this builds it as a plain
 * inline style instead. */
function hexToRgb(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}

/** A plain, factual rendering of the starting grid — the real slot once
 * qualifying has run, or the pre-quali projection before it. Deliberately
 * carries no win probability, glow, or any other prediction signal: this
 * is meant to answer "who's starting where," not "who's likely to win,"
 * which is what the Bars view (the other half of this section's toggle)
 * is for. Blending the two here once made the grid itself look wrong
 * (ordered by win% rank instead of by grid slot) and confused what this
 * view was even showing. */
export default function StartingGridLadder({ predicted }: { predicted: PredictionRow[] }) {
  // Ordered by the real (or, pre-quali, projected) starting-grid slot —
  // NOT by predicted win probability. Falls back to win_pct rank only for
  // a race predicted before grid_position existed, so an old prediction
  // still renders something instead of nothing.
  const hasGridPositions = predicted.some((row) => row.grid_position != null);
  const grid = hasGridPositions
    ? predicted
        .filter((row) => row.grid_position != null)
        .sort((a, b) => a.grid_position! - b.grid_position!)
    : predicted;
  if (grid.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-x-4 sm:gap-y-3 max-w-xl">
      {grid.map((row, i) => {
        const color = teamColor(row.team);
        const rgb = hexToRgb(color);
        // Real F1 grid boxes stagger the left (odd-position) car slightly
        // ahead of the right (even-position) car in every row, down the
        // whole grid — not alternated row to row. Only applied at the
        // sm: breakpoint and up, where the two-column layout exists.
        //
        // Uses margin-top, not a transform: a transform shifts the box
        // visually without adding to its layout size, so the grid
        // container's own height came out too short and the last
        // staggered block overlapped whatever content followed it below
        // (confirmed live). Margin pushes the box down AND grows the row
        // (and so the container) to actually contain it.
        const isRightColumn = i % 2 === 1;
        return (
          <div
            key={row.driver}
            className={`rounded-md border p-3 ${isRightColumn ? "sm:mt-6" : ""}`}
            style={{
              borderColor: color,
              background: `linear-gradient(135deg, rgba(${rgb}, 0.22), rgba(${rgb}, 0.05))`,
            }}
          >
            <span className="text-[10px] text-neutral-500 font-mono">P{row.grid_position ?? row.position}</span>
            <p className="text-xl font-bold text-neutral-50 leading-tight mt-1">{row.driver}</p>
            <p className="text-xs text-neutral-400 truncate">{row.team}</p>
          </div>
        );
      })}
    </div>
  );
}
