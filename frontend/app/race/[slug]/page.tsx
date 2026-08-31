import { getAllPredictedSlugs, getRace } from "../../lib/data";
import RaceDetail from "../../components/RaceDetail";

export function generateStaticParams() {
  return getAllPredictedSlugs().map((slug) => ({ slug }));
}

export default async function RacePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const race = getRace(slug);
  return <RaceDetail race={race} />;
}
