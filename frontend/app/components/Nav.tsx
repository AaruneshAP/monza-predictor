import Link from "next/link";
import { getIndex } from "../lib/data";

function statusDot(status: string) {
  if (status === "completed") return "bg-accent";
  if (status === "predicted") return "bg-neutral-500";
  return "bg-neutral-800";
}

export default function Nav() {
  const index = getIndex();
  const predicted = index.races.filter((r) => r.status !== "not_predicted");

  return (
    <nav className="border-b border-neutral-800 bg-neutral-950/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-4xl mx-auto px-6 py-3 flex items-center gap-4 overflow-x-auto text-sm">
        <Link href="/" className="font-semibold text-neutral-200 shrink-0 hover:text-accent">
          F1 Predictor
        </Link>
        <div className="flex items-center gap-2 shrink-0">
          {predicted.map((r) => (
            <Link
              key={r.slug}
              href={`/race/${r.slug}`}
              title={`${r.race_name} — ${r.status}`}
              className="flex items-center gap-1.5 px-2 py-1 rounded border border-neutral-800 text-neutral-400 hover:text-neutral-200 hover:border-neutral-600 whitespace-nowrap"
            >
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${statusDot(r.status)}`} />
              R{r.round}
            </Link>
          ))}
        </div>
        <Link
          href="/track-record"
          className="ml-auto shrink-0 text-neutral-400 hover:text-accent whitespace-nowrap"
        >
          Track Record
        </Link>
      </div>
    </nav>
  );
}
