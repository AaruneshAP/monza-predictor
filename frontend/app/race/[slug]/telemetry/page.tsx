import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getAllPredictedSlugs, getRace, getTelemetry } from "../../../lib/data";
import TelemetryExplorer from "../../../components/TelemetryExplorer";

// Only prerender a telemetry page for a race that actually has one — not
// every predicted race does, since telemetry is backfilled separately
// (see refresh-predictions.yml's manual `telemetry` dispatch input).
export function generateStaticParams() {
  return getAllPredictedSlugs()
    .filter((slug) => getTelemetry(slug) !== null)
    .map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const race = getRace(slug);
  return { title: `${race.race_name} — Telemetry` };
}

export default async function TelemetryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const telemetry = getTelemetry(slug);
  if (!telemetry) notFound();
  const race = getRace(slug);
  return <TelemetryExplorer race={race} telemetry={telemetry} />;
}
