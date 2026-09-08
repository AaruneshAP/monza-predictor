"use client";

import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ActualRow, PredictionRow } from "../lib/data";

const OVERRATED_COLOR = "#ef4444"; // red-500 — same red used for a negative contribution term
const UNDERRATED_COLOR = "#22c55e"; // green-500
const NEUTRAL_COLOR = "#737373"; // neutral-500 — within NEAR_ZERO_THRESHOLD of dead-on
const NEAR_ZERO_THRESHOLD = 0.5;

type MissRow = {
  driver: string;
  diff: number; // expected_position - actual_position: positive = finished BETTER than
  // predicted (model underrated them), negative = finished WORSE (model overrated them).
  expectedPosition: number;
  actualPosition: number;
  status?: string;
};

/** Mirrors check_results.py's _result_notes()/expected_position_by_driver
 * semantics deliberately — same two fields (a driver's predicted
 * expected_position vs their real classified position), so this chart
 * tells the same story as the "where the podium call missed" bullets
 * above it, not a second opinion computed a different way. Only drivers
 * present in both the predicted grid and the real classification are
 * plotted (drivers absent from either side, e.g. an unplanned late
 * substitution, are dropped rather than guessed at). */
function buildMissRows(predicted: PredictionRow[], actual: ActualRow[]): MissRow[] {
  const actualByDriver = new Map(actual.map((row) => [row.driver, row]));
  const rows: MissRow[] = [];
  for (const p of predicted) {
    const a = actualByDriver.get(p.driver);
    if (!a) continue;
    rows.push({
      driver: p.driver,
      diff: p.expected_position - a.position,
      expectedPosition: p.expected_position,
      actualPosition: a.position,
      status: a.status,
    });
  }
  return rows.sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff));
}

function barColor(diff: number): string {
  if (diff > NEAR_ZERO_THRESHOLD) return UNDERRATED_COLOR;
  if (diff < -NEAR_ZERO_THRESHOLD) return OVERRATED_COLOR;
  return NEUTRAL_COLOR;
}

function MissTooltip({ active, payload }: { active?: boolean; payload?: { payload: MissRow }[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0].payload;
  const verb = row.diff > 0 ? "beat" : row.diff < 0 ? "missed" : "matched";
  const isClassifiedFinish = row.status === "Finished" || row.status?.startsWith("+");
  return (
    <div className="bg-neutral-950 border border-neutral-700 rounded px-3 py-2 text-xs">
      <p className="text-neutral-300 font-medium mb-1">{row.driver}</p>
      <p className="text-neutral-400">
        Predicted ~P{row.expectedPosition.toFixed(1)} · actual P{row.actualPosition}
        {!isClassifiedFinish && row.status ? ` (${row.status})` : ""}
      </p>
      {Math.abs(row.diff) > NEAR_ZERO_THRESHOLD && (
        <p className="text-neutral-400 mt-1">
          {verb} the model&apos;s call by {Math.abs(row.diff).toFixed(1)} position{Math.abs(row.diff) >= 1.5 ? "s" : ""}
        </p>
      )}
    </div>
  );
}

export default function PredictedVsActualChart({
  predicted,
  actual,
}: {
  predicted: PredictionRow[];
  actual: ActualRow[];
}) {
  const rows = buildMissRows(predicted, actual);
  if (rows.length === 0) return null;

  return (
    <div className="mt-6 pt-6 border-t border-accent/20">
      <p className="text-neutral-400 text-sm mb-1">
        Predicted vs. actual finishing position, every driver
      </p>
      <p className="text-neutral-400 text-xs mb-4">
        <span className="text-green-500">Green</span>, right — finished better than the model
        expected (underrated). <span className="text-red-500">Red</span>, left — finished worse
        (overrated). Sorted by size of the miss.
      </p>
      <div style={{ height: Math.max(320, rows.length * 26) + 40 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ left: 40, right: 20, bottom: 24 }}>
            <XAxis
              type="number"
              stroke="#666"
              tickFormatter={(v: number) => (v > 0 ? `+${v}` : `${v}`)}
              label={{ value: "positions beaten (+) / missed by (−)", position: "insideBottom", offset: -14, fill: "#a3a3a3", fontSize: 11 }}
            />
            <YAxis type="category" dataKey="driver" stroke="#666" width={40} interval={0} />
            <ReferenceLine x={0} stroke="#525252" />
            <Tooltip content={<MissTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
            <Bar dataKey="diff" radius={2}>
              {rows.map((row) => (
                <Cell key={row.driver} fill={barColor(row.diff)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
