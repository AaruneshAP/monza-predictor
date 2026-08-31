"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { RaceFile } from "../lib/data";

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
const formatUtcDate = (iso: string) =>
  new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeZone: "UTC" }).format(new Date(iso));

function levelLabel(score: number): string {
  if (score < 0.35) return "Low";
  if (score < 0.65) return "Medium";
  return "High";
}

export default function RaceDetail({ race }: { race: RaceFile }) {
  const top10 = race.predicted.slice(0, 10);
  const profile = race.circuit_profile;
  const actualByDriver: Record<string, number> = {};
  if (race.actual) {
    for (const row of race.actual.classification) actualByDriver[row.driver] = row.position;
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      {/* Hero */}
      <section className="mb-14">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <p className="text-accent text-sm font-medium tracking-wide uppercase">
            {race.race_name}
          </p>
          {race.backtest && (
            <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border border-neutral-700 text-neutral-400">
              Backtest
            </span>
          )}
          {race.status === "completed" && (
            <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border border-accent/40 text-accent">
              Graded
            </span>
          )}
        </div>
        <h1 className="text-4xl font-bold mb-4">Race Winner Prediction</h1>
        <p className="text-neutral-400 max-w-2xl">
          A Monte Carlo simulation model ({formatNumber(race.n_simulations)}{" "}
          runs) built on real qualifying pace, historical results at this circuit, and
          top-speed data — re-weighted per-circuit for overtaking difficulty,
          downforce level, and tire severity.
        </p>
        <p className="text-neutral-600 text-xs mt-3">
          Race date {formatUtcDate(race.race_date)} · generated{" "}
          {formatUtcTimestamp(race.generated_at)} · rain scenario weighted at{" "}
          {race.rain_probability_pct}%
        </p>
      </section>

      {/* Actual vs predicted, only once the race has actually happened */}
      {race.status === "completed" && race.actual && race.accuracy && (
        <section className="mb-14 rounded-lg border border-accent/30 bg-accent/5 p-5">
          <h2 className="text-lg font-semibold mb-3">Predicted vs. Actual</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm mb-4">
            <div>
              <p className="text-neutral-500 text-xs mb-1">Predicted winner</p>
              <p className="font-medium">
                {race.accuracy.predicted_winner} ({race.accuracy.predicted_winner_prob_pct}%)
              </p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Actual winner</p>
              <p className="font-medium">
                {race.accuracy.actual_winner}{" "}
                <span className={race.accuracy.winner_correct ? "text-accent" : "text-neutral-500"}>
                  ({race.accuracy.winner_correct ? "correct" : "missed"})
                </span>
              </p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Podium hits</p>
              <p className="font-medium">{race.accuracy.podium_hits} / 3</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Brier score (win)</p>
              <p className="font-medium">{race.accuracy.brier_score_win}</p>
            </div>
          </div>
          <p className="text-neutral-500 text-xs">
            The model gave the actual winner ({race.accuracy.actual_winner}) a{" "}
            {race.accuracy.actual_winner_predicted_prob_pct}% chance beforehand.{" "}
            {race.backtest
              ? "This was a blind backtest — generated using only data available before the race, never this race's own results."
              : "Predicted live, before the race."}{" "}
            See the <a href="/track-record" className="underline hover:text-accent">track record</a> page for the model's accuracy across every graded race.
          </p>
        </section>
      )}

      {/* Chart */}
      <section className="mb-14">
        <h2 className="text-lg font-semibold mb-4">Win Probability — Top 10</h2>
        <div className="h-[420px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top10} layout="vertical" margin={{ left: 40 }}>
              <XAxis type="number" unit="%" stroke="#666" />
              <YAxis type="category" dataKey="driver" stroke="#666" width={80} interval={0} />
              <Tooltip contentStyle={{ background: "#111", border: "1px solid #333" }} />
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
                {race.status === "completed" && <th className="px-4 py-3">Actual</th>}
              </tr>
            </thead>
            <tbody>
              {race.predicted.map((row) => (
                <tr key={row.driver} className="border-t border-neutral-800">
                  <td className="px-4 py-3">{row.position}</td>
                  <td className="px-4 py-3 font-medium">{row.driver}</td>
                  <td className="px-4 py-3 text-neutral-400">{row.team}</td>
                  <td className="px-4 py-3">{row.win_pct}%</td>
                  <td className="px-4 py-3">{row.podium_pct}%</td>
                  <td className="px-4 py-3">{row.points_pct}%</td>
                  <td className="px-4 py-3">{row.expected_position}</td>
                  {race.status === "completed" && (
                    <td className="px-4 py-3 text-neutral-400">
                      {actualByDriver[row.driver] ?? "—"}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Methodology */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Methodology</h2>
        <p className="text-neutral-400 text-sm leading-relaxed mb-3">
          Each driver&apos;s simulated race pace is sampled from a distribution
          weighted by qualifying pace percentile, top-speed ranking, season
          championship standings, historical finishing position at this
          circuit, tire degradation, and pit-stop delta. The simulation runs{" "}
          {formatNumber(race.n_simulations)} times, with{" "}
          {race.rain_probability_pct}% of runs treated as a wet-race scenario
          (estimated from this circuit&apos;s own rainfall history).
        </p>
        <p className="text-neutral-400 text-sm leading-relaxed">
          This circuit&apos;s weighting — {race.race_name}: overtaking difficulty{" "}
          <strong>{levelLabel(profile.overtaking_difficulty)}</strong>, downforce
          dependency <strong>{levelLabel(profile.downforce_level)}</strong>, tire
          severity <strong>{levelLabel(profile.tire_severity)}</strong>. Higher
          overtaking difficulty shifts weight toward grid position; lower
          downforce dependency shifts weight toward straight-line top speed;
          higher tire severity shifts weight toward tire-degradation
          management. See{" "}
          <a
            href="https://github.com/AaruneshAP/monza-predictor/blob/master/model/circuit_profiles.py"
            className="underline hover:text-accent"
          >
            circuit_profiles.py
          </a>{" "}
          for every circuit&apos;s numbers and how they translate into weights.
        </p>
      </section>

      <footer className="text-neutral-600 text-xs pt-8 border-t border-neutral-800">
        Built with FastF1 data · source on{" "}
        <a
          href="https://github.com/AaruneshAP/monza-predictor"
          className="underline hover:text-accent"
        >
          GitHub
        </a>
      </footer>
    </main>
  );
}
