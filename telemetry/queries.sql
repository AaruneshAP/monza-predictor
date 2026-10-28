-- Telemetry comparison queries
-- ============================================================
-- Real SQL, actually executed — model/generate_telemetry.py reads this
-- file, splits it on the `-- name: x` headers below, and runs each
-- query against an in-memory SQLite database it builds from one race's
-- FastF1 lap + telemetry data. This file is not documentation of what
-- the pipeline does; it IS what runs (see generate_telemetry.py's
-- _load_queries()).
--
-- Tables these queries read (built fresh per race, one row per driver
-- per their single fastest qualifying lap — see generate_telemetry.py
-- for exactly how; a flying lap, not the whole session, is what makes
-- these comparisons apples-to-apples):
--
--   laps(driver, team, lap_time_s, sector1_s, sector2_s, sector3_s, compound)
--     one row per driver.
--
--   samples(driver, distance_m, speed_kph, throttle_pct, brake, drs, time_s)
--     one row per raw car-telemetry sample along that lap, ordered by
--     distance_m. brake is 0/1. drs is FastF1's raw DRS channel code.
-- ============================================================

-- name: lap_summary
-- One row per driver: fastest qualifying lap time and sector splits,
-- fastest to slowest.
SELECT driver, team, lap_time_s, sector1_s, sector2_s, sector3_s, compound
FROM laps
ORDER BY lap_time_s ASC;

-- name: sector_speed
-- Average speed per driver within each of three equal-length distance
-- sectors. NOT the circuit's official timing sectors — FastF1 exposes
-- each sector's TIME but not the distance markers where sectors actually
-- start and end, so this divides each driver's own lap distance into
-- thirds as a reasonable proxy for "early/mid/late lap pace." The
-- correlated subquery re-reads each driver's own max distance per row,
-- which is fine at this table size (a few hundred samples per driver)
-- and keeps the sector cutoff self-contained in one query.
SELECT
  driver,
  CASE
    WHEN distance_m < (SELECT MAX(distance_m) FROM samples s2 WHERE s2.driver = s.driver) / 3.0 THEN 1
    WHEN distance_m < (SELECT MAX(distance_m) FROM samples s2 WHERE s2.driver = s.driver) * 2.0 / 3.0 THEN 2
    ELSE 3
  END AS sector,
  ROUND(AVG(speed_kph), 1) AS avg_speed_kph
FROM samples s
GROUP BY driver, sector
ORDER BY driver, sector;

-- name: drs_usage
-- Percent of a driver's lap distance spent with DRS actually open.
-- FastF1's DRS channel: 0/1 = off, 8 = eligible but not activated,
-- 10/12/14 = open. Only the open codes count here — "eligible" isn't
-- "used."
SELECT
  driver,
  ROUND(100.0 * SUM(CASE WHEN drs IN (10, 12, 14) THEN 1 ELSE 0 END) / COUNT(*), 1) AS drs_pct_of_lap
FROM samples
GROUP BY driver
ORDER BY drs_pct_of_lap DESC;

-- name: braking_points
-- Each driver's real braking zones: the distance where brake flips from
-- off to on (a 0 -> 1 transition), restricted to zones entered above
-- 80 km/h so a trivial lift-and-coast dab doesn't count as a "braking
-- point" alongside an actual heavy-braking corner entry.
WITH flagged AS (
  SELECT
    driver,
    distance_m,
    speed_kph,
    brake,
    LAG(brake) OVER (PARTITION BY driver ORDER BY distance_m) AS prev_brake
  FROM samples
)
SELECT driver, distance_m AS braking_point_m, speed_kph AS speed_at_braking_kph
FROM flagged
WHERE brake = 1 AND (prev_brake = 0 OR prev_brake IS NULL) AND speed_kph >= 80
ORDER BY driver, distance_m;

-- name: speed_trace
-- Speed/throttle/brake/DRS resampled onto 10m distance buckets per
-- driver, averaged within each bucket. The raw per-sample telemetry is
-- far denser than any chart needs and differs in sample count and exact
-- spacing across drivers (different car telemetry logging rates), so
-- this bucketed aggregate — not a raw dump of the samples table — is
-- what the frontend's speed-vs-distance comparison chart actually
-- plots, with every driver on the same distance grid.
SELECT
  driver,
  CAST(distance_m / 10 AS INT) * 10 AS distance_bucket_m,
  ROUND(AVG(speed_kph), 1) AS speed_kph,
  ROUND(AVG(throttle_pct), 1) AS throttle_pct,
  ROUND(AVG(brake), 2) AS brake_frac,
  MAX(CASE WHEN drs IN (10, 12, 14) THEN 1 ELSE 0 END) AS drs_open
FROM samples
GROUP BY driver, distance_bucket_m
ORDER BY driver, distance_bucket_m;
