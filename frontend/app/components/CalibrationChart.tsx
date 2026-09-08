"use client";

import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { CalibrationBin } from "../lib/data";

// Endpoints for the dashed "perfect calibration" reference — a model that
// said "30%" and was right 30% of the time sits exactly on this line;
// above it means underconfident, below means overconfident.
const PERFECT_CALIBRATION = [
  { x: 0, y: 0 },
  { x: 100, y: 100 },
];

function CalibrationTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload.find((p) => p.dataKey === "y" && p.payload?.n !== undefined)?.payload as
    | { x: number; y: number; n: number; label: string }
    | undefined;
  if (!point) return null;
  return (
    <div className="bg-neutral-950 border border-neutral-700 rounded px-3 py-2 text-xs">
      <p className="text-neutral-300 font-medium mb-1">Predicted {point.label}</p>
      <p className="text-neutral-400">
        Predicted ~{point.x.toFixed(1)}% · actual {point.y.toFixed(1)}%
      </p>
      <p className="text-neutral-600 mt-1">n = {point.n} prediction{point.n === 1 ? "" : "s"}</p>
    </div>
  );
}

export default function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const points = bins.map((b) => ({
    x: b.avg_predicted_win_pct,
    y: b.actual_win_rate_pct,
    n: b.n,
    label: `${b.bin_start}–${b.bin_end}%`,
  }));

  return (
    <div className="h-96">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
          <CartesianGrid stroke="#222" />
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, 100]}
            unit="%"
            stroke="#666"
            label={{ value: "Predicted win %", position: "insideBottom", offset: -12, fill: "#666" }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, 100]}
            unit="%"
            stroke="#666"
            label={{ value: "Actual win rate", angle: -90, position: "insideLeft", fill: "#666" }}
          />
          {/* Bubble size = sample size, so a bin resting on 2 predictions
              doesn't visually read as confidently as one resting on 200. */}
          <ZAxis type="number" dataKey="n" range={[60, 500]} name="predictions" />
          <Tooltip content={<CalibrationTooltip />} cursor={{ strokeDasharray: "3 3", stroke: "#444" }} />
          <Line
            data={PERFECT_CALIBRATION}
            dataKey="y"
            stroke="#555"
            strokeDasharray="5 5"
            dot={false}
            activeDot={false}
            isAnimationActive={false}
            legendType="none"
          />
          <Scatter data={points} dataKey="y" fill="#00D2BE" fillOpacity={0.75} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
