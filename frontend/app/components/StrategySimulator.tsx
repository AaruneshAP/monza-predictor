"use client";

import { useMemo, useState } from "react";
import type { RaceFile, StrategyFile, UndercutPair } from "../lib/data";
import { teamColor } from "../lib/teamColors";

/** Color the success probability itself like a risk meter: green when the
 * undercut is favored, red when it isn't, consistent with this site's
 * existing red/green win-probability coloring elsewhere. */
function successColor(pct: number): string {
  if (pct >= 60) return "#22c55e"; // green-500
  if (pct >= 40) return "#eab308"; // yellow-500
  return "#ef4444"; // red-500
}

function DriverPicker({
  label,
  drivers,
  selected,
  disabled,
  onSelect,
}: {
  label: string;
  drivers: { driver: string; team: string }[];
  selected: string;
  disabled: string | null;
  onSelect: (driver: string) => void;
}) {
  return (
    <div>
      <p className="text-neutral-500 text-xs mb-2">{label}</p>
      <div className="flex flex-wrap gap-2">
        {drivers.map((d) => {
          const isSelected = d.driver === selected;
          const isDisabled = d.driver === disabled;
          const color = teamColor(d.team);
          return (
            <button
              key={d.driver}
              type="button"
              disabled={isDisabled}
              onClick={() => onSelect(d.driver)}
              className={`px-3 py-1.5 rounded-md border text-sm flex items-center gap-1.5 transition-colors ${
                isSelected
                  ? "border-neutral-500 bg-neutral-800 text-neutral-100"
                  : "border-neutral-800 text-neutral-500 hover:text-neutral-300 disabled:opacity-30 disabled:hover:text-neutral-500"
              }`}
            >
              <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: color }} aria-hidden="true" />
              {d.driver}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function explanation(pair: UndercutPair): string {
  const parts: string[] = [];
  parts.push(
    `${pair.undercut_driver} pits ${pair.window_laps} lap${pair.window_laps === 1 ? "" : "s"} before ${pair.rival_driver}.`
  );
  parts.push(
    `A Safety Car falling in that window (${pair.safety_car_window_pct}% chance here) would make ${pair.rival_driver}'s eventual stop effectively free, so it forces the undercut to fail outright.`
  );
  parts.push(
    `Otherwise, it comes down to ${pair.undercut_driver}'s own pit-stop cost (~${pair.pit_loss_s}s) against the pace ${pair.rival_driver} loses to tire wear while staying out (~${pair.tire_deg_slope_s_per_lap}s/lap).`
  );
  return parts.join(" ");
}

export default function StrategySimulator({ race, strategy }: { race: RaceFile; strategy: StrategyFile }) {
  const drivers = strategy.drivers;
  const [undercutDriver, setUndercutDriver] = useState(drivers[0]?.driver ?? "");
  const [rivalDriver, setRivalDriver] = useState(drivers[1]?.driver ?? "");

  const pairsByKey = useMemo(() => {
    const map = new Map<string, UndercutPair>();
    for (const pair of strategy.pairs) map.set(`${pair.undercut_driver}:${pair.rival_driver}`, pair);
    return map;
  }, [strategy.pairs]);

  const pair = pairsByKey.get(`${undercutDriver}:${rivalDriver}`);

  function pickUndercutDriver(driver: string) {
    setUndercutDriver(driver);
    if (driver === rivalDriver) setRivalDriver(drivers.find((d) => d.driver !== driver)?.driver ?? "");
  }

  function pickRivalDriver(driver: string) {
    setRivalDriver(driver);
    if (driver === undercutDriver) setUndercutDriver(drivers.find((d) => d.driver !== driver)?.driver ?? "");
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      <section className="mb-10">
        <p className="text-accent text-sm font-medium tracking-wide uppercase">{race.race_name}</p>
        <h1 className="text-4xl font-bold mb-2">Undercut simulator</h1>
        <p className="text-neutral-400 max-w-2xl text-sm">
          Pick a driver to undercut a rival by pitting {strategy.window_laps} laps earlier, and see the
          modeled probability it pays off — a Monte Carlo simulation over each driver&apos;s own measured
          pit-stop cost and tire degradation, plus this circuit&apos;s historical safety car rate
          ({strategy.safety_car_probability_pct}% of races here have had one).
        </p>
      </section>

      <section className="mb-10 grid grid-cols-1 md:grid-cols-2 gap-6">
        <DriverPicker
          label="Undercutting driver (pits early)"
          drivers={drivers}
          selected={undercutDriver}
          disabled={rivalDriver}
          onSelect={pickUndercutDriver}
        />
        <DriverPicker
          label="Rival (stays out)"
          drivers={drivers}
          selected={rivalDriver}
          disabled={undercutDriver}
          onSelect={pickRivalDriver}
        />
      </section>

      {pair ? (
        <section className="mb-14 rounded-lg border border-neutral-800 p-8 text-center">
          <p className="text-neutral-500 text-xs uppercase tracking-wide mb-2">Undercut success probability</p>
          <p className="text-6xl font-bold mb-4" style={{ color: successColor(pair.success_pct) }}>
            {pair.success_pct}%
          </p>
          <p className="text-neutral-400 text-sm max-w-xl mx-auto">{explanation(pair)}</p>
        </section>
      ) : (
        <p className="text-neutral-500 text-sm mb-14">Pick two different drivers to see the result.</p>
      )}

      <footer className="text-neutral-400 text-xs pt-8 border-t border-neutral-800">
        Simulated with the same Monte Carlo approach used for the race prediction · source on{" "}
        <a href="https://github.com/AaruneshAP/monza-predictor" className="underline hover:text-accent">
          GitHub
        </a>
      </footer>
    </main>
  );
}
