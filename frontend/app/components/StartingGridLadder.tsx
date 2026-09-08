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
  const grid = predicted.slice(0, 10);
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
        const isRightColumn = i % 2 === 1;
        const glowStrength = row.win_pct / maxWinPct; // 0-1, brightest for the model's pick
        return (
          <div
            key={row.driver}
            className={`rounded-md border p-3 ${isRightColumn ? "sm:translate-y-6" : ""}`}
            style={{
              borderColor: color,
              background: `linear-gradient(135deg, rgba(${rgb}, 0.22), rgba(${rgb}, 0.05))`,
              boxShadow: `0 0 ${8 + glowStrength * 22}px rgba(${rgb}, ${0.15 + glowStrength * 0.35})`,
            }}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[10px] text-neutral-500 font-mono">P{row.position}</span>
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
