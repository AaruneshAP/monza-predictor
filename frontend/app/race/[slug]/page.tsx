import type { Metadata } from "next";
import { getAllPredictedSlugs, getRace } from "../../lib/data";
import RaceDetail from "../../components/RaceDetail";

export function generateStaticParams() {
  return getAllPredictedSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const race = getRace(slug);
  return { title: race.race_name };
}

export default async function RacePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const race = getRace(slug);
  return <RaceDetail race={race} />;
}
