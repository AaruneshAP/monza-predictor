"use client";

import { useEffect, useState } from "react";

/**
 * Days until `raceDate` ("YYYY-MM-DD"), computed against the *viewer's*
 * current date — not the server's. Static pages here can sit unrebuilt
 * for days (predictions only regenerate near a race weekend — see
 * should_run_full_refresh.py), so a day-count baked in at build time
 * would go stale and, worse, would very likely disagree with a value
 * recomputed from the viewer's own clock at hydration time, throwing the
 * same class of SSR/hydration mismatch already hit and fixed once in
 * this file's sibling (see DEBUGGING.md #7). Rendering null until this
 * effect runs means the server and the first client render agree (both
 * render nothing), then the real number fills in right after — no
 * mismatch possible.
 */
function useDaysUntil(raceDate: string): number | null {
  const [daysLeft, setDaysLeft] = useState<number | null>(null);

  useEffect(() => {
    const now = new Date();
    const todayUtcMidnight = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
    const [year, month, day] = raceDate.split("-").map(Number);
    const raceUtcMidnight = Date.UTC(year, month - 1, day);
    setDaysLeft(Math.round((raceUtcMidnight - todayUtcMidnight) / 86_400_000));
  }, [raceDate]);

  return daysLeft;
}

export default function RaceCountdown({ raceDate, raceName }: { raceDate: string; raceName: string }) {
  const daysLeft = useDaysUntil(raceDate);

  if (daysLeft === null) return null;

  let text: string;
  if (daysLeft > 1) text = `Next prediction in ${daysLeft} days — ${raceName}`;
  else if (daysLeft === 1) text = `Next prediction tomorrow — ${raceName}`;
  else if (daysLeft === 0) text = `Race day — ${raceName}`;
  else text = `${raceName} weekend is underway — results pending`;

  return (
    <p className="text-xs text-neutral-500 mt-3 flex items-center gap-1.5">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent" aria-hidden="true" />
      {text}
    </p>
  );
}
