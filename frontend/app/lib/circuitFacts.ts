/**
 * Static, publicly-known circuit facts (lap length, corner count) for
 * display only — never consumed by the model itself, which is why these
 * live here rather than in model/circuit_profiles.py (that file's numbers
 * are hand-estimated *weighting* inputs; these are plain facts about the
 * track). Keyed by round number to match circuit_profiles.py's rounds.
 *
 * Round 14 (Madrid) is new to the calendar for 2026 — its figures are as
 * publicly announced ahead of its debut, not yet raced, so treat them as
 * provisional until the circuit actually hosts a race.
 */
export type CircuitFacts = {
  length_km: number;
  corners: number;
};

export const CIRCUIT_FACTS: Record<number, CircuitFacts> = {
  1: { length_km: 5.278, corners: 14 }, // Albert Park
  2: { length_km: 5.451, corners: 16 }, // Shanghai
  3: { length_km: 5.807, corners: 18 }, // Suzuka
  4: { length_km: 5.412, corners: 19 }, // Miami
  5: { length_km: 4.361, corners: 14 }, // Gilles Villeneuve
  6: { length_km: 3.337, corners: 19 }, // Monaco
  7: { length_km: 4.657, corners: 14 }, // Barcelona-Catalunya
  8: { length_km: 4.318, corners: 10 }, // Red Bull Ring
  9: { length_km: 5.891, corners: 18 }, // Silverstone
  10: { length_km: 7.004, corners: 19 }, // Spa-Francorchamps
  11: { length_km: 4.381, corners: 14 }, // Hungaroring
  12: { length_km: 4.259, corners: 14 }, // Zandvoort
  13: { length_km: 5.793, corners: 11 }, // Monza
  14: { length_km: 5.474, corners: 20 }, // Madrid — as announced, pre-debut
  15: { length_km: 6.003, corners: 20 }, // Baku City Circuit
  16: { length_km: 5.412, corners: 15 }, // Bahrain International Circuit
  17: { length_km: 4.94, corners: 19 }, // Marina Bay
  18: { length_km: 5.513, corners: 20 }, // Circuit of the Americas
  19: { length_km: 4.304, corners: 17 }, // Autódromo Hermanos Rodríguez
  20: { length_km: 4.309, corners: 15 }, // Interlagos
  21: { length_km: 6.201, corners: 17 }, // Las Vegas Strip Circuit
  22: { length_km: 5.38, corners: 16 }, // Losail International Circuit
  23: { length_km: 5.281, corners: 16 }, // Yas Marina Circuit
};

export function getCircuitFacts(round: number): CircuitFacts | undefined {
  return CIRCUIT_FACTS[round];
}
