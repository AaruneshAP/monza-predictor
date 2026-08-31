import Link from "next/link";
import { getIndex, getRace } from "../lib/data";

export const metadata = {
  title: "Track Record — F1 Race Predictor",
};

export default function TrackRecordPage() {
  const index = getIndex();
  const completed = index.races.filter((r) => r.status === "completed").map((r) => getRace(r.slug));
  const tr = index.track_record;

  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      <section className="mb-12">
        <p className="text-accent text-sm font-medium tracking-wide uppercase mb-2">
          Model Evaluation
        </p>
        <h1 className="text-4xl font-bold mb-4">Track Record</h1>
        <p className="text-neutral-400 max-w-2xl">
          Every prediction below was graded against the real result — including
          backtested rounds, which were generated blind, using only data
          available before that race, never the race&apos;s own outcome. This
          is what separates a model from a claim about a model.
        </p>
      </section>

      {tr.races_scored === 0 ? (
        <p className="text-neutral-500 text-sm">
          No races graded yet — check back after the next one finishes.
        </p>
      ) : (
        <>
          <section className="mb-14 grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Stat label="Races scored" value={String(tr.races_scored)} />
            <Stat label="Winner hit rate" value={`${tr.winner_hit_rate_pct}%`} />
            <Stat label="Avg. Brier score (win)" value={String(tr.avg_brier_score_win)} sub="lower is better" />
            <Stat label="Avg. podium hits" value={`${tr.avg_podium_hits} / 3`} />
          </section>

          <section className="mb-14">
            <h2 className="text-lg font-semibold mb-4">Graded Races</h2>
            <div className="overflow-x-auto rounded-lg border border-neutral-800">
              <table className="w-full text-sm text-left">
                <thead className="bg-neutral-900 text-neutral-400">
                  <tr>
                    <th className="px-4 py-3">Race</th>
                    <th className="px-4 py-3">Predicted Winner</th>
                    <th className="px-4 py-3">Actual Winner</th>
                    <th className="px-4 py-3">Result</th>
                    <th className="px-4 py-3">Podium Hits</th>
                    <th className="px-4 py-3">Brier</th>
                    <th className="px-4 py-3">Mode</th>
                  </tr>
                </thead>
                <tbody>
                  {completed.map((race) => (
                    <tr key={race.slug} className="border-t border-neutral-800">
                      <td className="px-4 py-3 font-medium">
                        <Link href={`/race/${race.slug}`} className="hover:text-accent underline">
                          {race.race_name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-neutral-400">
                        {race.accuracy!.predicted_winner} ({race.accuracy!.predicted_winner_prob_pct}%)
                      </td>
                      <td className="px-4 py-3 text-neutral-400">{race.accuracy!.actual_winner}</td>
                      <td className="px-4 py-3">
                        <span className={race.accuracy!.winner_correct ? "text-accent" : "text-neutral-500"}>
                          {race.accuracy!.winner_correct ? "Correct" : "Missed"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-neutral-400">{race.accuracy!.podium_hits} / 3</td>
                      <td className="px-4 py-3 text-neutral-400">{race.accuracy!.brier_score_win}</td>
                      <td className="px-4 py-3 text-neutral-500">
                        {race.backtest ? "Backtest" : "Live"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">How this is scored</h2>
        <p className="text-neutral-400 text-sm leading-relaxed">
          <strong>Winner hit rate</strong> — how often the driver the model gave
          the highest win probability actually won. <strong>Brier score</strong>{" "}
          — mean squared error between each driver&apos;s predicted win
          probability and whether they actually won (0 = perfect, lower is
          better; a model that always predicts uniformly across ~20 drivers
          scores much worse than one that concentrates probability
          sensibly). <strong>Podium hits</strong> — how many of the model&apos;s
          predicted top 3 actually finished top 3. &quot;Backtest&quot; rounds were
          generated after the fact but deliberately blind — restricted to
          only the data that would have existed before that race — so they
          count as a fair test of the model, not hindsight.
        </p>
      </section>
    </main>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 p-4">
      <p className="text-neutral-500 text-xs mb-1">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
      {sub && <p className="text-neutral-600 text-[11px] mt-1">{sub}</p>}
    </div>
  );
}
