import fs from "fs";
import path from "path";

const PREDICTIONS_DIR = path.join(process.cwd(), "public", "predictions");

export type PredictionRow = {
  position: number;
  driver: string;
  team: string;
  win_pct: number;
  podium_pct: number;
  points_pct: number;
  expected_position: number;
};

export type ActualRow = { driver: string; team: string; position: number };

export type Accuracy = {
  predicted_winner: string;
  predicted_winner_prob_pct: number;
  actual_winner: string;
  winner_correct: boolean;
  actual_winner_predicted_prob_pct: number;
  podium_hits: number;
  brier_score_win: number;
  mean_abs_position_error: number | null;
};

export type CircuitProfile = {
  overtaking_difficulty: number;
  downforce_level: number;
  tire_severity: number;
};

export type RaceStatus = "not_predicted" | "predicted" | "completed";

export type RaceFile = {
  year: number;
  round: number;
  race_name: string;
  slug: string;
  race_date: string;
  generated_at: string;
  backtest: boolean;
  status: RaceStatus;
  n_simulations: number;
  rain_probability_pct: number;
  grid_source: string;
  tire_deg_source: string;
  circuit_profile: CircuitProfile;
  predicted: PredictionRow[];
  actual: { classification: ActualRow[]; graded_at: string } | null;
  accuracy: Accuracy | null;
};

export type IndexRaceEntry = {
  round: number;
  slug: string;
  race_name: string;
  race_date: string;
  status: RaceStatus;
};

export type TrackRecord = {
  races_scored: number;
  winner_hit_rate_pct: number | null;
  avg_brier_score_win: number | null;
  avg_mean_abs_position_error: number | null;
  avg_podium_hits: number | null;
};

export type IndexFile = {
  season: number;
  updated_at: string;
  races: IndexRaceEntry[];
  next_race_slug: string | null;
  track_record: TrackRecord;
};

export function getIndex(): IndexFile {
  const p = path.join(PREDICTIONS_DIR, "index.json");
  return JSON.parse(fs.readFileSync(p, "utf-8"));
}

export function getRace(slug: string): RaceFile {
  const p = path.join(PREDICTIONS_DIR, `${slug}.json`);
  return JSON.parse(fs.readFileSync(p, "utf-8"));
}

/** Slugs of every race that's actually been predicted (has a file on
 * disk) — used by generateStaticParams so we don't try to prerender a
 * page for a round that hasn't been run yet. */
export function getAllPredictedSlugs(): string[] {
  return getIndex()
    .races.filter((r) => r.status !== "not_predicted")
    .map((r) => r.slug);
}

/** The race the homepage should show: the next upcoming one, or — if
 * every known round is somehow already completed — the most recent one. */
export function getFeaturedRace(): RaceFile {
  const index = getIndex();
  const predicted = index.races.filter((r) => r.status !== "not_predicted");
  const slug = index.next_race_slug ?? predicted[predicted.length - 1]?.slug;
  if (!slug) {
    throw new Error("No predicted races in the archive yet — run model/generate_predictions.py.");
  }
  return getRace(slug);
}
