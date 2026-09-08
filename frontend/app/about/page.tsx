import Link from "next/link";

export const metadata = {
  title: "About",
};

export default function AboutPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      <section className="mb-12">
        <p className="text-accent text-sm font-medium tracking-wide uppercase mb-2">Model Card</p>
        <h1 className="text-4xl font-bold mb-4">About This Model</h1>
        <p className="text-neutral-400 max-w-2xl">
          What the model actually does, what it assumes, and where it&apos;s weak — written to be
          checked against the code, not to sell it. See{" "}
          <a
            href="https://github.com/AaruneshAP/monza-predictor"
            className="underline hover:text-accent"
          >
            the source
          </a>
          , <Link href="/track-record" className="underline hover:text-accent">
            the track record
          </Link>{" "}
          for current accuracy against a naive baseline, and{" "}
          <a
            href="https://github.com/AaruneshAP/monza-predictor/blob/master/DEBUGGING.md"
            className="underline hover:text-accent"
          >
            the debugging log
          </a>{" "}
          for the real bugs this went through before publishing.
        </p>
      </section>

      <section className="mb-12">
        <h2 className="text-lg font-semibold mb-3">What data the model uses</h2>
        <p className="text-neutral-400 text-sm leading-relaxed mb-3">
          Everything comes from FastF1, which wraps the official F1 timing data and the Ergast
          historical database. Per driver, per round, that&apos;s:
        </p>
        <ul className="text-neutral-400 text-sm leading-relaxed list-disc pl-5 space-y-1.5">
          <li>
            <strong className="text-neutral-300">Qualifying pace</strong> — grid position (real,
            once qualifying has run; projected from season-average pace before that) and
            speed-trap top speed from the last 8 completed rounds.
          </li>
          <li>
            <strong className="text-neutral-300">Championship standings</strong> — live points
            total through the most recent round, pulled via{" "}
            <code className="text-neutral-300">fastf1.ergast</code>.
          </li>
          <li>
            <strong className="text-neutral-300">Historical results at this circuit</strong> —
            finishing position for 2019–2025 (fewer years, or none, for a circuit new to the
            calendar).
          </li>
          <li>
            <strong className="text-neutral-300">Tire degradation</strong> — lap-time-vs-tyre-life
            slope from FP2 long runs once they exist, else a season-average slope from the last 8
            rounds.
          </li>
          <li>
            <strong className="text-neutral-300">Pit-stop performance</strong> — in-lap +
            out-lap time minus that driver&apos;s best clean lap, averaged across the season.
          </li>
          <li>
            <strong className="text-neutral-300">Rain probability</strong> — the fraction of that
            circuit&apos;s races since 2019 that saw any rainfall (a historical base rate, not a
            live weather forecast — see Limitations).
          </li>
        </ul>
        <p className="text-neutral-400 text-sm leading-relaxed mt-3">
          Each of those becomes a 0–1 percentile among the current grid before it enters the
          model, so the underlying units (seconds, points, km/h) never mix directly — only their
          relative rank does.
        </p>
      </section>

      <section className="mb-12">
        <h2 className="text-lg font-semibold mb-3">Key assumptions</h2>
        <ul className="text-neutral-400 text-sm leading-relaxed list-disc pl-5 space-y-2.5">
          <li>
            <strong className="text-neutral-300">The per-feature weights are hand-tuned, not fit.</strong>{" "}
            Quali pace, points, grid position, top speed, tire management, historical form, and
            pit stops are combined into one race-pace score with fixed weights (e.g. quali pace
            0.25, championship points 0.26) chosen so a clear form leader wins a believable
            25–35% of simulations rather than 80%+. That tuning target was a judgment call about
            plausibility, not a fit against held-out results.
          </li>
          <li>
            <strong className="text-neutral-300">
              Circuit character (overtaking difficulty, downforce level, tire severity) is a
              hand-set 0–1 estimate per track,
            </strong>{" "}
            not derived from this project&apos;s own overtake or lap data — that would need years
            of telemetry this project doesn&apos;t have. If a track&apos;s number looks wrong,
            the fix is editing that row, not the formula consuming it.
          </li>
          <li>
            <strong className="text-neutral-300">Race-day variance is a single noise term</strong>{" "}
            added to each driver&apos;s score per simulation, scaled up for closely-matched
            midpack cars and for rain — not a simulation of specific race events (see
            Limitations).
          </li>
          <li>
            <strong className="text-neutral-300">
              A driver&apos;s current team is whoever raced for them last round,
            </strong>{" "}
            reconciled against the real qualifying entry list once that exists for the round
            being predicted. Before qualifying, a substitution that&apos;s already reverting has
            to be corrected by hand (see <code className="text-neutral-300">
              GRID_OVERRIDE_BY_ROUND
            </code> in <code className="text-neutral-300">race_model.py</code>) — there&apos;s no
            live roster feed.
          </li>
        </ul>
      </section>

      <section className="mb-12">
        <h2 className="text-lg font-semibold mb-3">Known limitations</h2>
        <ul className="text-neutral-400 text-sm leading-relaxed list-disc pl-5 space-y-2.5">
          <li>
            <strong className="text-neutral-300">No safety car, VSC, or red-flag modeling.</strong>{" "}
            These reshuffle real races constantly — closing gaps, changing strategy windows,
            occasionally ending a leader&apos;s race outright — and this model has no signal for
            any of it. It only knows a driver&apos;s pace, not what happens to everyone else
            around them mid-race.
          </li>
          <li>
            <strong className="text-neutral-300">
              Small sample size, especially per circuit.
            </strong>{" "}
            At most 7 years of historical results per track (fewer for a new circuit), and the
            model&apos;s own graded track record is still small — see{" "}
            <Link href="/track-record" className="underline hover:text-accent">
              the track record page
            </Link>{" "}
            for the current count and whether it&apos;s actually beating the naive
            always-bet-the-polesitter baseline. Early on, a handful of races is not enough signal
            to call that either way with confidence.
          </li>
          <li>
            <strong className="text-neutral-300">
              Tire degradation is a genuinely noisy signal
            </strong>{" "}
            — raw lap-time-vs-tyre-life slopes are tiny (~0.01–0.05s/lap over ~20 stints) and not
            corrected for the fuel-burn effect that dominates that range. It&apos;s kept at a
            small weight everywhere for exactly this reason, but a small weight on noise is still
            noise, not signal.
          </li>
          <li>
            <strong className="text-neutral-300">
              Rain probability is a historical base rate, not a forecast.
            </strong>{" "}
            It reflects how often that circuit has been wet since 2019, not this weekend&apos;s
            actual weather — a live forecast integration would clearly beat this close to race
            day.
          </li>
          <li>
            <strong className="text-neutral-300">
              No compound-specific tire modeling, no strategy simulation, no team orders.
            </strong>{" "}
            Degradation is one slope per driver regardless of compound; the model doesn&apos;t
            simulate pit windows, undercuts, or a team favoring one driver over another.
          </li>
          <li>
            <strong className="text-neutral-300">Depends on FastF1&apos;s own data quality.</strong>{" "}
            FastF1 fuzzy-matches session names and doesn&apos;t error on a circuit that wasn&apos;t
            on a given year&apos;s calendar — silently substituting the closest-named race instead
            (documented in the debugging log). That&apos;s guarded against for historical lookups,
            but it&apos;s a real fragility in the underlying data source, not something this
            project controls.
          </li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">What I&apos;d improve with more time or data</h2>
        <ul className="text-neutral-400 text-sm leading-relaxed list-disc pl-5 space-y-2.5">
          <li>
            Fit the feature weights against held-out historical races instead of hand-tuning them
            to a plausible-looking win-probability spread — the current tuning target
            (&quot;doesn&apos;t look absurd&quot;) is a much weaker bar than &quot;minimizes
            Brier score on data the fit never saw.&quot;
          </li>
          <li>
            Model safety car / VSC probability per circuit from historical race data — the same
            kind of per-circuit profile this project already builds for overtaking difficulty,
            just for incident rate instead.
          </li>
          <li>
            Use the actual qualifying gap to pole (continuous, in seconds) instead of just
            percentile rank — order alone throws away how much faster P1 was than P2.
          </li>
          <li>
            Swap the historical wet-race base rate for a real weather forecast once one&apos;s
            available close to race day.
          </li>
          <li>
            Automate the mid-season driver-lineup correction with a live entry-list feed instead
            of a manually maintained override table.
          </li>
          <li>
            Most of all: let the track record grow. Every point above is a hypothesis about what
            would help — the only way to know for sure is more graded races against the baseline
            this model is supposed to beat.
          </li>
        </ul>
      </section>
    </main>
  );
}
