import fs from "fs";
import path from "path";

const PREDICTIONS_DIR = path.join(process.cwd(), "public", "predictions");

export type ContributionTerm = {
  key: string;
  label: string;
  value: number;
};

export type Contributions = {
  base_score: number;
  terms: ContributionTerm[];
};

export type PredictionRow = {
  position: number;
  driver: string;
  team: string;
  win_pct: number;
  podium_pct: number;
  points_pct: number;
  expected_position: number;
  // Absent on a race predicted before this field existed.
  contributions?: Contributions | null;
};

export type ActualRow = {
  driver: string;
  team: string;
  position: number;
  status?: string;
  grid_position?: number | null;
};

export type BaselineScore = {
  polesitter: string;
  winner_correct: boolean;
  brier_score_win: number;
};

export type Accuracy = {
  predicted_winner: string;
  predicted_winner_prob_pct: number;
  actual_winner: string;
  winner_correct: boolean;
  actual_winner_predicted_prob_pct: number;
  podium_hits: number;
  brier_score_win: number;
  mean_abs_position_error: number | null;
  // Absent on races graded before this field existed — always guard with
  // `?.length` before rendering, never assume it's present.
  result_notes?: string[];
  // Null if the race had no real GridPosition data to identify a
  // polesitter from. Absent (undefined) on races graded before this
  // field existed.
  baseline?: BaselineScore | null;
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
  // Absent (null) if no graded race has real grid-position data.
  avg_baseline_brier_score_win: number | null;
};

export type CalibrationBin = {
  bin_start: number;
  bin_end: number;
  n: number;
  avg_predicted_win_pct: number;
  actual_win_rate_pct: number;
};

export type IndexFile = {
  season: number;
  updated_at: string;
  races: IndexRaceEntry[];
  next_race_slug: string | null;
  track_record: TrackRecord;
  // Absent on an index.json built before this field existed.
  calibration_bins?: CalibrationBin[];
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
