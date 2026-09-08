"use client";

import { Fragment, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { Contributions, RaceFile } from "../lib/data";

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

type SortKey =
  | "position"
  | "driver"
  | "team"
  | "win_pct"
  | "podium_pct"
  | "points_pct"
  | "expected_position"
  | "actual";

// Which direction makes sense to see FIRST when you click a column you
// weren't already sorting by — position/driver/team ascending (natural
// reading order), the rest descending except expected finish, where lower
// is better so ascending shows the best first.
const DEFAULT_SORT_DIR: Record<SortKey, "asc" | "desc"> = {
  position: "asc",
  driver: "asc",
  team: "asc",
  win_pct: "desc",
  podium_pct: "desc",
  points_pct: "desc",
  expected_position: "asc",
  actual: "asc",
};

function SortableHeader({
  label,
  sortKey: key,
  activeKey,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  dir: "asc" | "desc";
  onSort: (key: SortKey) => void;
}) {
  const isActive = activeKey === key;
  return (
    <th
      onClick={() => onSort(key)}
      className="px-4 py-3 cursor-pointer select-none hover:text-neutral-200 whitespace-nowrap"
      aria-sort={isActive ? (dir === "asc" ? "ascending" : "descending") : "none"}
    >
      {label}
      <span className="inline-block w-3 ml-1 text-neutral-600">{isActive ? (dir === "asc" ? "▲" : "▼") : ""}</span>
    </th>
  );
}

function ContributionBreakdown({ contributions }: { contributions: Contributions }) {
  const maxAbs = Math.max(...contributions.terms.map((t) => Math.abs(t.value)), 0.0001);
  return (
    <div className="py-4 px-4 sm:px-8">
      <p className="text-neutral-500 text-xs mb-3 max-w-xl">
        What drove this driver&apos;s race-pace score —{" "}
        <span className="text-neutral-300 font-medium">{contributions.base_score.toFixed(3)}</span>{" "}
        total, before the model&apos;s per-simulation randomness is added. This is not a breakdown of
        win% itself — win% comes out of 100,000 noisy simulations ranked against the whole field, not a
        straight sum of these terms — but it is the exact set of terms that sum to the score those
        simulations start from.
      </p>
      <div className="space-y-1.5 max-w-xl">
        {contributions.terms.map((term) => {
          const widthPct = (Math.abs(term.value) / maxAbs) * 100;
          const positive = term.value >= 0;
          return (
            <div key={term.key} className="flex items-center gap-3 text-xs">
              <span className="w-44 shrink-0 text-neutral-400">{term.label}</span>
              <div className="flex-1 h-3 bg-neutral-900 rounded-sm overflow-hidden">
                <div
                  className={`h-full rounded-sm ${positive ? "bg-accent" : "bg-red-500/70"}`}
                  style={{ width: `${widthPct}%` }}
                />
              </div>
              <span
                className={`w-16 shrink-0 text-right font-mono ${positive ? "text-neutral-300" : "text-red-400"}`}
              >
                {positive ? "+" : ""}
                {term.value.toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function RaceDetail({ race }: { race: RaceFile }) {
  const top10 = race.predicted.slice(0, 10);
  const profile = race.circuit_profile;
  const actualByDriver: Record<string, number> = {};
  if (race.actual) {
    for (const row of race.actual.classification) actualByDriver[row.driver] = row.position;
  }
  const [expandedDriver, setExpandedDriver] = useState<string | null>(null);
  const [showAllDrivers, setShowAllDrivers] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("position");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(DEFAULT_SORT_DIR[key]);
    }
  }

  const sortedPredicted = [...race.predicted].sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    const value = (row: typeof a) => (sortKey === "actual" ? actualByDriver[row.driver] ?? Infinity : row[sortKey]);
    const av = value(a);
    const bv = value(b);
    if (typeof av === "string" && typeof bv === "string") return av.localeCompare(bv) * dir;
    return ((av as number) - (bv as number)) * dir;
  });
  const chartData = showAllDrivers ? race.predicted : top10;
  // A fixed height dropped every-other Y-axis label once there were more
  // category ticks than it had room for (see DEBUGGING.md #7) — scale with
  // the driver count instead of hardcoding a height sized for 10.
  const chartHeight = Math.max(420, chartData.length * 34);

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
          {race.accuracy.baseline && (
            <p className="text-xs mt-2">
              <span className="text-neutral-400">
                Our model: <span className="font-medium text-neutral-200">{race.accuracy.brier_score_win}</span>
                {" · "}
                Grid-based baseline (always pick the polesitter): <span className="font-medium text-neutral-200">{race.accuracy.baseline.brier_score_win}</span>
              </span>{" "}
              <span
                className={
                  race.accuracy.brier_score_win < race.accuracy.baseline.brier_score_win
                    ? "text-accent"
                    : race.accuracy.brier_score_win > race.accuracy.baseline.brier_score_win
                    ? "text-neutral-500"
                    : "text-neutral-500"
                }
              >
                (
                {race.accuracy.brier_score_win < race.accuracy.baseline.brier_score_win
                  ? "model beats the baseline — lower is better"
                  : race.accuracy.brier_score_win > race.accuracy.baseline.brier_score_win
                  ? "baseline beats the model this time — lower is better"
                  : "tied with the baseline"}
                )
              </span>
            </p>
          )}
          {race.accuracy.result_notes && race.accuracy.result_notes.length > 0 && (
            <div className="mt-4 pt-4 border-t border-accent/20">
              <p className="text-neutral-500 text-xs mb-2">Where the podium call missed</p>
              <ul className="text-sm space-y-1.5">
                {race.accuracy.result_notes.map((note, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-neutral-600" aria-hidden="true">
                      •
                    </span>
                    <span className="text-neutral-300">{note}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Chart */}
      <section className="mb-14">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-lg font-semibold">
            Win Probability — {showAllDrivers ? `All ${chartData.length} Drivers` : "Top 10"}
          </h2>
          <button
            type="button"
            onClick={() => setShowAllDrivers((v) => !v)}
            className="text-xs px-2.5 py-1 rounded border border-neutral-700 text-neutral-400 hover:text-neutral-200 hover:border-neutral-500"
          >
            {showAllDrivers ? "Show top 10" : "Show all drivers"}
          </button>
        </div>
        <div style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 40 }}>
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
        <h2 className="text-lg font-semibold mb-1">Full Prediction Table</h2>
        <p className="text-neutral-600 text-xs mb-4">
          Click a column header to sort by it, click a row to see what drove that driver&apos;s
          score.
        </p>
        <div className="overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm text-left">
            <thead className="bg-neutral-900 text-neutral-400">
              <tr>
                <SortableHeader label="Pos" sortKey="position" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableHeader label="Driver" sortKey="driver" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableHeader label="Team" sortKey="team" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableHeader label="Win %" sortKey="win_pct" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableHeader label="Podium %" sortKey="podium_pct" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableHeader label="Points %" sortKey="points_pct" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableHeader
                  label="Exp. Pos"
                  sortKey="expected_position"
                  activeKey={sortKey}
                  dir={sortDir}
                  onSort={handleSort}
                />
                {race.status === "completed" && (
                  <SortableHeader label="Actual" sortKey="actual" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                )}
              </tr>
            </thead>
            <tbody>
              {sortedPredicted.map((row) => {
                const isExpandable = !!row.contributions;
                const isExpanded = expandedDriver === row.driver;
                const columnCount = race.status === "completed" ? 8 : 7;
                return (
                  <Fragment key={row.driver}>
                    <tr
                      onClick={() => isExpandable && setExpandedDriver(isExpanded ? null : row.driver)}
                      className={`border-t border-neutral-800 ${
                        isExpandable ? "cursor-pointer hover:bg-neutral-900/60" : ""
                      }`}
                    >
                      <td className="px-4 py-3">{row.position}</td>
                      <td className="px-4 py-3 font-medium">
                        {isExpandable && (
                          <span className="inline-block w-3 text-neutral-600">
                            {isExpanded ? "▾" : "▸"}
                          </span>
                        )}
                        {row.driver}
                      </td>
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
                    {isExpanded && row.contributions && (
                      <tr className="border-t border-neutral-800 bg-neutral-950">
                        <td colSpan={columnCount} className="p-0">
                          <ContributionBreakdown contributions={row.contributions} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
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
