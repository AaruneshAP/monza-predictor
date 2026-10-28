"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RaceFile, TelemetryDriver, TelemetryFile } from "../lib/data";
import { formatLapTime } from "../lib/format";
import { teamColor } from "../lib/teamColors";

const MAX_SELECTED = 3;
// A dashed line for the second driver sharing a team color (teammates
// share a livery, so color alone can't tell them apart on this chart —
// see pickLineStyle below).
const DASH_PATTERNS = [undefined, "6 4", "2 3"];

/** Assigns each selected driver a (color, dash) pair. Color follows the
 * team — the same real-livery color every other chart/table on this site
 * already uses — so identity here matches identity everywhere else.
 * Dash only comes into play for the rare case of two selected
 * teammates, where color alone can't distinguish the two lines. */
function pickLineStyle(selected: TelemetryDriver[], index: number): { color: string; dash?: string } {
  const driver = selected[index];
  const color = teamColor(driver.team);
  const sameColorBefore = selected.slice(0, index).filter((d) => teamColor(d.team) === color).length;
  return { color, dash: DASH_PATTERNS[sameColorBefore] };
}

function compoundColor(compound: string | null): string {
  switch (compound) {
    case "SOFT":
      return "#ef4444"; // red-500 — matches real F1 tyre-compound coloring
    case "MEDIUM":
      return "#eab308"; // yellow-500
    case "HARD":
      return "#f5f5f5"; // neutral-100
    case "INTERMEDIATE":
      return "#22c55e"; // green-500
    case "WET":
      return "#3b82f6"; // blue-500
    default:
      return "#737373"; // neutral-500 — unknown/not recorded
  }
}

type TraceTooltipPayload = { color: string; name: string; value: number }[];

function TraceTooltip({ active, payload, label }: { active?: boolean; payload?: TraceTooltipPayload; label?: number }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-neutral-950 border border-neutral-700 rounded px-3 py-2 text-xs">
      <p className="text-neutral-400 mb-1">{label} m</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value.toFixed(0)} km/h
        </p>
      ))}
    </div>
  );
}

export default function TelemetryExplorer({ race, telemetry }: { race: RaceFile; telemetry: TelemetryFile }) {
  const drivers = telemetry.drivers;
  const [selected, setSelected] = useState<string[]>(drivers.slice(0, 2).map((d) => d.driver));

  function toggle(driver: string) {
    setSelected((prev) => {
      if (prev.includes(driver)) return prev.filter((d) => d !== driver);
      if (prev.length >= MAX_SELECTED) return prev;
      return [...prev, driver];
    });
  }

  const selectedDrivers = drivers.filter((d) => selected.includes(d.driver));

  // Recharts wants one row per x-value with each series as its own key —
  // reshape the per-driver speed_trace arrays (all on the same 10m
  // distance grid, see telemetry/queries.sql's speed_trace query) into
  // that shape, keyed by distance_m.
  const chartData: Record<number, Record<string, number>> = {};
  for (const d of selectedDrivers) {
    for (const point of d.speed_trace) {
      const row = chartData[point.distance_m] ?? (chartData[point.distance_m] = { distance_m: point.distance_m });
      row[d.driver] = point.speed_kph;
    }
  }
  const chartRows = Object.values(chartData).sort((a, b) => a.distance_m - b.distance_m);

  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      <section className="mb-10">
        <p className="text-accent text-sm font-medium tracking-wide uppercase">{race.race_name}</p>
        <h1 className="text-4xl font-bold mb-2">Telemetry</h1>
        <p className="text-neutral-400 max-w-2xl text-sm">
          Each driver&apos;s single fastest lap from {telemetry.session} — not a whole session&apos;s
          worth of laps, so fuel load, tyre age, and traffic don&apos;t muddy the comparison. Speed,
          throttle, brake, and DRS plotted against distance around the lap, the standard way
          telemetry traces are compared.
        </p>
      </section>

      <section className="mb-8">
        <p className="text-neutral-500 text-xs mb-2">
          Compare up to {MAX_SELECTED} drivers{selected.length >= MAX_SELECTED ? " (max reached — deselect one to swap)" : ""}
        </p>
        <div className="flex flex-wrap gap-2">
          {drivers.map((d) => {
            const isSelected = selected.includes(d.driver);
            const color = teamColor(d.team);
            return (
              <button
                key={d.driver}
                type="button"
                onClick={() => toggle(d.driver)}
                disabled={!isSelected && selected.length >= MAX_SELECTED}
                className={`px-3 py-1.5 rounded-md border text-sm flex items-center gap-1.5 transition-colors ${
                  isSelected
                    ? "border-neutral-500 bg-neutral-800 text-neutral-100"
                    : "border-neutral-800 text-neutral-500 hover:text-neutral-300 disabled:opacity-40 disabled:hover:text-neutral-500"
                }`}
              >
                <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: color }} aria-hidden="true" />
                {d.driver}
              </button>
            );
          })}
        </div>
      </section>

      {selectedDrivers.length === 0 ? (
        <p className="text-neutral-500 text-sm mb-14">Select at least one driver to see their trace.</p>
      ) : (
        <section className="mb-14">
          <h2 className="text-lg font-semibold mb-4">Speed vs. distance</h2>
          <div className="h-[380px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartRows} margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                <XAxis
                  dataKey="distance_m"
                  type="number"
                  stroke="#666"
                  unit="m"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(v: number) => `${Math.round(v)}`}
                />
                <YAxis stroke="#666" unit=" km/h" width={70} domain={["dataMin - 10", "dataMax + 10"]} />
                <Tooltip content={<TraceTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {selectedDrivers.map((d, i) => {
                  const { color, dash } = pickLineStyle(selectedDrivers, i);
                  return (
                    <Line
                      key={d.driver}
                      type="monotone"
                      dataKey={d.driver}
                      name={d.driver}
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray={dash}
                      dot={false}
                      connectNulls
                      isAnimationActive={false}
                    />
                  );
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section className="mb-14">
        <h2 className="text-lg font-semibold mb-4">Lap summary</h2>
        <div className="overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm text-left">
            <thead className="bg-neutral-900 text-neutral-400">
              <tr>
                <th className="px-4 py-3">Driver</th>
                <th className="px-4 py-3">Lap time</th>
                <th className="px-4 py-3">S1</th>
                <th className="px-4 py-3">S2</th>
                <th className="px-4 py-3">S3</th>
                <th className="px-4 py-3">Compound</th>
                <th className="px-4 py-3">DRS used</th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((d) => (
                <tr
                  key={d.driver}
                  className="border-t border-neutral-800 border-l-[3px]"
                  style={{ borderLeftColor: teamColor(d.team) }}
                >
                  <td className="px-4 py-3 font-medium">{d.driver}</td>
                  <td className="px-4 py-3 font-mono">{formatLapTime(d.lap_time_s)}</td>
                  <td className="px-4 py-3 font-mono text-neutral-400">{d.sector1_s?.toFixed(3) ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-neutral-400">{d.sector2_s?.toFixed(3) ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-neutral-400">{d.sector3_s?.toFixed(3) ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle"
                      style={{ backgroundColor: compoundColor(d.compound) }}
                      aria-hidden="true"
                    />
                    {d.compound ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-neutral-400">
                    {d.drs_pct_of_lap != null ? `${d.drs_pct_of_lap}% of lap` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-neutral-500 text-xs mt-3">
          Sector times are each driver&apos;s own fastest-lap splits, not an official-timing sector
          breakdown of a single theoretical lap. &quot;DRS used&quot; is the share of this lap&apos;s
          distance spent with DRS actually open, not just eligible.
        </p>
      </section>

      <footer className="text-neutral-400 text-xs pt-8 border-t border-neutral-800">
        Built with FastF1 data, queried with SQL (
        <a
          href="https://github.com/AaruneshAP/monza-predictor/blob/master/telemetry/queries.sql"
          className="underline hover:text-accent"
        >
          telemetry/queries.sql
        </a>
        ) · source on{" "}
        <a href="https://github.com/AaruneshAP/monza-predictor" className="underline hover:text-accent">
          GitHub
        </a>
      </footer>
    </main>
  );
}
