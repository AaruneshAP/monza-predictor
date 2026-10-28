import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getAllPredictedSlugs, getRace, getStrategy } from "../../../lib/data";
import StrategySimulator from "../../../components/StrategySimulator";

// Only prerender a strategy page for a race that actually has one — races
// predicted before this feature existed won't.
export function generateStaticParams() {
  return getAllPredictedSlugs()
    .filter((slug) => getStrategy(slug) !== null)
    .map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const race = getRace(slug);
  return { title: `${race.race_name} — Undercut simulator` };
}

export default async function StrategyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const strategy = getStrategy(slug);
  if (!strategy) notFound();
  const race = getRace(slug);
  return <StrategySimulator race={race} strategy={strategy} />;
}
