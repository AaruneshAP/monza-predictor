import { getFeaturedRace } from "./lib/data";
import RaceDetail from "./components/RaceDetail";

export default function Home() {
  const race = getFeaturedRace();
  return <RaceDetail race={race} />;
}
