import type { Metadata } from "next";
import { getFeaturedRace } from "./lib/data";
import RaceDetail from "./components/RaceDetail";

export function generateMetadata(): Metadata {
  const race = getFeaturedRace();
  // The root layout's title.template does NOT apply here — Next only
  // applies a layout's template to a *child* route segment's title, and
  // "/" is the same segment as the root layout that defines the
  // template, not a child of it. Writing the full string directly (as
  // every other route's title ultimately resolves to) sidesteps that
  // rather than ending up with a bare, unsuffixed tab title.
  return { title: `${race.race_name} — F1 Race Predictor` };
}

export default function Home() {
  const race = getFeaturedRace();
  return <RaceDetail race={race} />;
}
