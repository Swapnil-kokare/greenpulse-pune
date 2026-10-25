# 06. Database design

## Database and evidence

The configured database is `greenpulse_pune`. The dashboard queries the latest batch from `zone_environment_summary`. Its schema and constraints below were inspected directly in the MySQL instance. The ML migration at `database/migrations/001_environmental_ml.sql` is additive and does not change this established summary table.

## Existing summary table

| Column | MySQL type | Null/default | Key | Meaning |
|---|---|---|---|---|
| `id` | `BIGINT` | Not null, auto-increment | Primary | Row identifier |
| `batch_id` | `BIGINT` | Not null | Unique-key part | Spark micro-batch identifier |
| `zone_id` | `VARCHAR(20)` | Not null | Unique-key part | Zone identifier |
| `zone_name` | `VARCHAR(100)` | Not null | — | Display name |
| `records_received` | `INT` | Not null | — | Count aggregated by Spark |
| `mean_lst_c` | `DOUBLE` | Nullable | — | Mean LST in Celsius |
| `mean_ndvi` | `DOUBLE` | Nullable | — | Mean NDVI |
| `latest_observation_date` | `DATE` | Nullable | — | Latest date in the batch aggregate |
| `processed_at` | `TIMESTAMP` | Nullable; default current timestamp | — | Database processing/write time |

The table uses InnoDB and `utf8mb4`. It has a primary key on `id` and unique key `unique_batch_zone(batch_id, zone_id)`. There is no foreign key, coordinate, explicit data-source, or quality-flag column in this table. The dashboard's coordinate reference and source labels are therefore joined from the bundled CSV by zone ID; those bundled values are synthetic.

The dashboard query selects rows where `batch_id` equals the maximum batch ID and orders by `mean_lst_c` descending. It does not query a historical series from this table.

## Additive ML migration

The migration defines the following tables. The readiness report observed `environment_observations` present; the migration file alone is the source of column definitions and constraints below. Do not treat this file as proof that every ML table is populated.

### `environment_observations`

Columns: `observation_id BIGINT UNSIGNED` primary key auto-increment; `zone_id VARCHAR(128)` and `zone_name VARCHAR(255)` not null; `observation_date DATE` not null; `lst_celsius DOUBLE` and `ndvi DOUBLE` not null; nullable `ndbi`, `latitude`, `longitude` as `DOUBLE`; `coordinates_verified BOOLEAN NOT NULL DEFAULT FALSE`; `data_source VARCHAR(255) NOT NULL`; `records_received BIGINT UNSIGNED NOT NULL DEFAULT 0`; nullable `last_batch_id BIGINT`; and `processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`.

Unique key: `(zone_id, observation_date, data_source)`. Indexes: `observation_date` and `(zone_id, observation_date)`. This is a zone/date/source history table rather than a foreign-key child of the summary table.

### `ml_predictions`

Columns: `prediction_id CHAR(36)` primary key; `zone_id VARCHAR(128)`, `zone_name VARCHAR(255)`, input and target dates (`DATE`), forecast horizon (`SMALLINT UNSIGNED`), prediction and optional lower/upper LST (`DOUBLE`), model version and data-source status (`VARCHAR(128)` / `VARCHAR(255)`), optional coordinates (`DOUBLE`) and verification flag (`BOOLEAN NOT NULL DEFAULT FALSE`), and `created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`.

Unique key: `(zone_id, input_observation_date, target_observation_date, model_version)`. Indexes: `created_at` and `target_observation_date`. The table does not declare a foreign key to `environment_observations`.

### `environmental_recommendations`

Columns: `recommendation_id CHAR(36)` primary key; zone ID/name, environmental issue, issue type, JSON supporting evidence, intervention text, reason, priority, optional confidence, recommendation timestamp, follow-up measurement, optional related prediction ID, deduplication key, and source status. Types and lengths are defined in the migration: `VARCHAR(128/255/32/64)`, `JSON`, `TEXT`, nullable `DOUBLE`, and timestamp types.

Unique key: `deduplication_key`; indexes on recommendation timestamp and zone ID. `related_prediction_id` references `ml_predictions(prediction_id)` with `ON DELETE SET NULL`. There is no zone dimension/ward-boundary table.

## Relationships

The only declared foreign key is from an optional recommendation to a prediction. Zone IDs are repeated values, not enforced by a zone dimension. The ER diagram represents the migration design, not a claim that result tables contain data.

**Figure 6.1.** Entity relationship view of the verified summary-table definition and the additive ML migration; the only declared foreign key is from recommendations to predictions. Zone IDs are not foreign-key relationships. See the [editable ER diagram source](diagrams/05_database_er.mmd) and [diagram index](diagrams/README.md).

## Insert/update and retention behavior

- Summary records are written through `ON DUPLICATE KEY UPDATE` for the `(batch_id, zone_id)` key.
- History records are upserted by `(zone_id, observation_date, data_source)`; repeated batches update weighted averages and counts.
- Predictions are assigned deterministic IDs and upserted using their unique zone/date/model identity.
- Recommendations use a deterministic deduplication identity; the unique key prevents duplicate recommendations for the same evidence identity.
- No scheduled retention, archive, or purge policy was verified. Do not assume automatic historical cleanup.

## Inspected database snapshot

At inspection, the latest batch was 4, with 18 zones, one observation date (2025-07-06), 288 received records, and `processed_at=2026-10-25 20:02:31`. The history table existed but contained zero rows in the saved readiness report. The latest summary is an old observation replay with a later processing timestamp, not a current field measurement.
