import Link from "next/link";
import { getIndex, getRace } from "../lib/data";
import { formatBrier } from "../lib/format";
import CalibrationChart from "../components/CalibrationChart";

export const metadata = {
  title: "Track Record",
};

export default function TrackRecordPage() {
  const index = getIndex();
  const completed = index.races.filter((r) => r.status === "completed").map((r) => getRace(r.slug));
  const tr = index.track_record;
  const calibrationBins = index.calibration_bins ?? [];

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
          <section className="mb-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Stat label="Races scored" value={String(tr.races_scored)} />
            <Stat label="Winner hit rate" value={`${tr.winner_hit_rate_pct}%`} />
            <Stat
              label="Avg. Brier score (win)"
              value={tr.avg_brier_score_win !== null ? formatBrier(tr.avg_brier_score_win) : "—"}
              sub="lower is better"
            />
            <Stat label="Avg. podium hits" value={`${tr.avg_podium_hits} / 3`} />
          </section>

          {tr.avg_baseline_brier_score_win !== null && (
            <p className="text-neutral-500 text-xs mb-14">
              Grid-based baseline (always pick the polesitter to win) averages{" "}
              <span className="text-neutral-300 font-medium">{formatBrier(tr.avg_baseline_brier_score_win)}</span> Brier
              across the same graded races —{" "}
              {tr.avg_brier_score_win !== null && tr.avg_brier_score_win < tr.avg_baseline_brier_score_win ? (
                <span className="text-accent">the model is beating that naive heuristic on average.</span>
              ) : tr.avg_brier_score_win !== null && tr.avg_brier_score_win > tr.avg_baseline_brier_score_win ? (
                <span>the model is not yet beating that naive heuristic on average — worth watching as more races get graded.</span>
              ) : (
                <span>the model is currently tied with that naive heuristic.</span>
              )}
            </p>
          )}

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
                      <td className="px-4 py-3 text-neutral-400">{formatBrier(race.accuracy!.brier_score_win)}</td>
                      <td className="px-4 py-3 text-neutral-500">
                        {race.backtest ? "Backtest" : "Live"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {calibrationBins.length > 0 && (
            <section className="mb-14">
              <h2 className="text-lg font-semibold mb-2">Calibration</h2>
              <p className="text-neutral-400 text-sm max-w-2xl mb-4">
                Every driver-race win% prediction across every graded race, bucketed by
                predicted win% and plotted against how often drivers in that bucket
                actually won. The dashed line is perfect calibration — a point on it
                means when the model said &quot;X%,&quot; it was right about X% of the
                time. Points above the line mean the model was underconfident in that
                range; below means overconfident. Bubble size shows how many
                predictions fed that point — small bubbles are a handful of races and
                should be read as noisy, not as a verdict.
              </p>
              <CalibrationChart bins={calibrationBins} />
              <p className="text-neutral-400 text-xs mt-3">
                Calibration matters more than raw accuracy for a model that reports a
                probability rather than a single guess: a model can pick the wrong
                winner every time and still be well-calibrated (if the driver it gave
                20% to wins about 1 time in 5), and it can pick the right winner
                often while being badly calibrated (if everything it&apos;s confident
                about is systematically over- or under-stated). Accuracy asks &quot;did
                it guess right&quot; — calibration asks &quot;can you trust the number
                it gave you.&quot;
              </p>
            </section>
          )}
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
      {sub && <p className="text-neutral-400 text-xs mt-1">{sub}</p>}
    </div>
  );
}
