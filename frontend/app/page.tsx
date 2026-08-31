"use client";

import predictions from "../public/predictions.json";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export type PredictionRow = {
  position: number;
  driver: string;
  team: string;
  win_pct: number;
  podium_pct: number;
  points_pct: number;
  expected_position: number;
};

type PredictionsFile = {
  generated_at: string;
  race: string;
  n_simulations: number;
  rain_probability_pct: number;
  drivers: PredictionRow[];
};

const data = predictions as PredictionsFile;

// Fixed locale + UTC timezone so the server-prerendered HTML and the
// client hydration pass render byte-identical text — a viewer-local
// toLocaleString() here would mismatch (different timezone/locale) and
// throw a React hydration error that silently kills the rest of the tree,
// including the chart below.
const formatNumber = (n: number) => new Intl.NumberFormat("en-US").format(n);
const formatUtcTimestamp = (iso: string) =>
  new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(iso)) + " UTC";

export default function Home() {
  const top10 = data.drivers.slice(0, 10);

  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      {/* Hero */}
      <section className="mb-14">
        <p className="text-accent text-sm font-medium tracking-wide uppercase mb-2">
          {data.race}
        </p>
        <h1 className="text-4xl font-bold mb-4">Race Winner Prediction</h1>
        <p className="text-neutral-400 max-w-2xl">
          A Monte Carlo simulation model ({formatNumber(data.n_simulations)}{" "}
          runs) built on real qualifying pace, historical Monza results, and
          top-speed data — re-weighted for Monza&apos;s low-downforce,
          slipstream-heavy character.
        </p>
        <p className="text-neutral-600 text-xs mt-3">
          Last updated {formatUtcTimestamp(data.generated_at)} · rain
          scenario weighted at {data.rain_probability_pct}%
        </p>
      </section>

      {/* Chart */}
      <section className="mb-14">
        <h2 className="text-lg font-semibold mb-4">Win Probability — Top 10</h2>
        <div className="h-[420px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top10} layout="vertical" margin={{ left: 40 }}>
              <XAxis type="number" unit="%" stroke="#666" />
              <YAxis
                type="category"
                dataKey="driver"
                stroke="#666"
                width={80}
                interval={0}
              />
              <Tooltip
                contentStyle={{ background: "#111", border: "1px solid #333" }}
              />
              <Bar dataKey="win_pct" fill="#00D2BE" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Table */}
      <section className="mb-14">
        <h2 className="text-lg font-semibold mb-4">Full Prediction Table</h2>
        <div className="overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm text-left">
            <thead className="bg-neutral-900 text-neutral-400">
              <tr>
                <th className="px-4 py-3">Pos</th>
                <th className="px-4 py-3">Driver</th>
                <th className="px-4 py-3">Team</th>
                <th className="px-4 py-3">Win %</th>
                <th className="px-4 py-3">Podium %</th>
                <th className="px-4 py-3">Points %</th>
                <th className="px-4 py-3">Exp. Pos</th>
              </tr>
            </thead>
            <tbody>
              {data.drivers.map((row) => (
                <tr key={row.driver} className="border-t border-neutral-800">
                  <td className="px-4 py-3">{row.position}</td>
                  <td className="px-4 py-3 font-medium">{row.driver}</td>
                  <td className="px-4 py-3 text-neutral-400">{row.team}</td>
                  <td className="px-4 py-3">{row.win_pct}%</td>
                  <td className="px-4 py-3">{row.podium_pct}%</td>
                  <td className="px-4 py-3">{row.points_pct}%</td>
                  <td className="px-4 py-3">{row.expected_position}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Methodology */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Methodology</h2>
        <p className="text-neutral-400 text-sm leading-relaxed">
          Each driver&apos;s simulated race pace is sampled from a distribution
          weighted by qualifying pace percentile, top-speed ranking, historical
          Monza finishing position, tire degradation, and pit-stop delta.
          Monza-specific adjustments: grid position is weighted down (overtaking
          is comparatively easy here), top speed is weighted up (low-drag,
          high-power tracks reward straight-line speed), and a slipstream
          variance factor accounts for the mid-pack shuffling Monza produces
          more than most circuits. The simulation runs{" "}
          {formatNumber(data.n_simulations)} times, with{" "}
          {data.rain_probability_pct}% of runs treated as a wet-race scenario.
        </p>
      </section>

      <footer className="text-neutral-600 text-xs pt-8 border-t border-neutral-800">
        Built with FastF1 data · source on{" "}
        <a href="#" className="underline hover:text-accent">
          GitHub
        </a>
      </footer>
    </main>
  );
}
