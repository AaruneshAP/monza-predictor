import type { PredictionRow } from "../lib/data";
import { teamColor } from "../lib/teamColors";

/** Converts a hex color like "#E8002D" to "r, g, b" for use inside an
 * rgba()/box-shadow — Tailwind's arbitrary values can't parametrize
 * opacity on a value computed at runtime, so this builds the glow color
 * as a plain inline style instead. */
function hexToRgb(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}

export default function StartingGridLadder({ predicted }: { predicted: PredictionRow[] }) {
  // Ordered by the real (or, pre-quali, projected) starting-grid slot —
  // NOT by predicted win probability. This is meant to look like an
  // actual F1 grid, so the order needs to actually BE the grid; showing
  // the top 10 by win% instead was a real bug (drivers up front here
  // didn't match the real announced grid once qualifying had happened).
  // Falls back to win_pct rank only for a race predicted before
  // grid_position existed, so an old prediction still renders something.
  const hasGridPositions = predicted.some((row) => row.grid_position != null);
  const ordered = hasGridPositions
    ? predicted
        .filter((row) => row.grid_position != null)
        .sort((a, b) => a.grid_position! - b.grid_position!)
    : predicted;
  const grid = ordered.slice(0, 10);
  if (grid.length === 0) return null;
  const maxWinPct = Math.max(...grid.map((row) => row.win_pct), 0.0001);

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
        // (confirmed live — the last row's right-column block covered
        // the caption text under it). Margin pushes the box down AND
        // grows the row (and so the container) to actually contain it.
        const isRightColumn = i % 2 === 1;
        const glowStrength = row.win_pct / maxWinPct; // 0-1, brightest for the model's pick
        return (
          <div
            key={row.driver}
            className={`rounded-md border p-3 ${isRightColumn ? "sm:mt-6" : ""}`}
            style={{
              borderColor: color,
              background: `linear-gradient(135deg, rgba(${rgb}, 0.22), rgba(${rgb}, 0.05))`,
              boxShadow: `0 0 ${8 + glowStrength * 22}px rgba(${rgb}, ${0.15 + glowStrength * 0.35})`,
            }}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[10px] text-neutral-500 font-mono">P{row.grid_position ?? row.position}</span>
              <span className="text-sm font-semibold text-neutral-100 font-mono">{row.win_pct}%</span>
            </div>
            <p className="text-xl font-bold text-neutral-50 leading-tight mt-1">{row.driver}</p>
            <p className="text-xs text-neutral-400 truncate">{row.team}</p>
          </div>
        );
      })}
    </div>
  );
}
