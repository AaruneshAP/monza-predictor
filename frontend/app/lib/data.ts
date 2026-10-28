import fs from "fs";
import path from "path";

const PREDICTIONS_DIR = path.join(process.cwd(), "public", "predictions");
const TELEMETRY_DIR = path.join(process.cwd(), "public", "telemetry");
const STRATEGY_DIR = path.join(process.cwd(), "public", "strategy");

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
  // The real (once quali's run) or projected starting-grid slot — NOT the
  // same thing as `position` above, which ranks by predicted win
  // probability. Absent on a race predicted before this field existed,
  // and can be missing for an individual driver even on a race that has
  // it if that driver's real grid slot wasn't resolvable (e.g. a gap in
  // the live qualifying data this was generated from).
  grid_position?: number | null;
  // Qualifying lap time in seconds — the time that actually set
  // grid_position. Only exists once real qualifying has run (absent
  // before that, and absent on a race predicted before this field
  // existed), same as grid_position can be missing for a driver whose
  // slot wasn't resolvable.
  quali_time?: number | null;
  win_pct: number;
  // Standard deviation of win_pct across N_CONFIDENCE_BATCHES Monte Carlo
  // batches — this driver's own simulation-estimation noise at this
  // sample size, not a formal confidence interval. Absent (undefined) on
  // a race predicted before this field existed; null was never written
  // but treated the same as absent, matching every other optional field
  // here.
  win_pct_stdev?: number | null;
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

// --- Telemetry (model/generate_telemetry.py) ---
// One driver's single fastest qualifying lap, not a whole session — see
// that script's docstring for why a flying lap is what makes a
// speed-vs-distance comparison between drivers apples-to-apples.

export type TelemetrySpeedPoint = {
  distance_m: number;
  speed_kph: number;
  throttle_pct: number;
  brake_frac: number;
  drs_open: boolean;
};

export type TelemetrySectorSpeed = {
  // 1, 2, or 3 — thirds of this driver's OWN lap distance, not the
  // circuit's official timing sectors (FastF1 doesn't expose those as
  // distance markers, only as times) — see telemetry/queries.sql.
  sector: number;
  avg_speed_kph: number;
};

export type TelemetryBrakingPoint = {
  distance_m: number;
  speed_kph: number;
};

export type TelemetryDriver = {
  driver: string;
  team: string;
  lap_time_s: number;
  sector1_s: number | null;
  sector2_s: number | null;
  sector3_s: number | null;
  compound: string | null;
  sector_speed: TelemetrySectorSpeed[];
  drs_pct_of_lap: number | null;
  braking_points: TelemetryBrakingPoint[];
  speed_trace: TelemetrySpeedPoint[];
};

export type TelemetryFile = {
  year: number;
  round: number;
  race_name: string;
  slug: string;
  session: string;
  generated_at: string;
  drivers: TelemetryDriver[];
};

/** Null when this race has no telemetry file yet — telemetry is
 * backfilled separately from predictions (see refresh-predictions.yml's
 * manual `telemetry` dispatch input) and won't exist for every race. */
export function getTelemetry(slug: string): TelemetryFile | null {
  const p = path.join(TELEMETRY_DIR, `${slug}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf-8"));
}

// --- Strategy / undercut simulator (model/generate_strategy.py) ---
// Reuses the Monte Carlo approach from race_model.py's monte_carlo_simulate()
// to estimate undercut success for every ordered pair among the top
// predicted drivers — see simulate_undercut()'s docstring for the model.

export type StrategyDriver = {
  driver: string;
  team: string;
};

export type UndercutPair = {
  undercut_driver: string;
  rival_driver: string;
  window_laps: number;
  success_pct: number;
  safety_car_window_pct: number;
  pit_loss_s: number;
  tire_deg_slope_s_per_lap: number;
};

export type StrategyFile = {
  year: number;
  round: number;
  race_name: string;
  slug: string;
  race_date: string;
  generated_at: string;
  window_laps: number;
  safety_car_probability_pct: number;
  drivers: StrategyDriver[];
  pairs: UndercutPair[];
};

/** Null when this race has no strategy file yet (predates this feature). */
export function getStrategy(slug: string): StrategyFile | null {
  const p = path.join(STRATEGY_DIR, `${slug}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf-8"));
}
