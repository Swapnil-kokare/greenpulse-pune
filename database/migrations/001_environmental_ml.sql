-- Additive ML storage. Existing zone_environment_summary is not modified.
CREATE TABLE IF NOT EXISTS environment_observations (
    observation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    zone_id VARCHAR(128) NOT NULL,
    zone_name VARCHAR(255) NOT NULL,
    observation_date DATE NOT NULL,
    lst_celsius DOUBLE NOT NULL,
    ndvi DOUBLE NOT NULL,
    ndbi DOUBLE NULL,
    latitude DOUBLE NULL,
    longitude DOUBLE NULL,
    coordinates_verified BOOLEAN NOT NULL DEFAULT FALSE,
    data_source VARCHAR(255) NOT NULL,
    records_received BIGINT UNSIGNED NOT NULL DEFAULT 0,
    last_batch_id BIGINT NULL,
    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (observation_id),
    UNIQUE KEY uq_environment_observation (zone_id, observation_date, data_source),
    KEY idx_environment_observation_date (observation_date),
    KEY idx_environment_observation_zone_date (zone_id, observation_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ml_predictions (
    prediction_id CHAR(36) NOT NULL,
    zone_id VARCHAR(128) NOT NULL,
    zone_name VARCHAR(255) NOT NULL,
    input_observation_date DATE NOT NULL,
    target_observation_date DATE NOT NULL,
    forecast_horizon_days SMALLINT UNSIGNED NOT NULL,
    predicted_lst_c DOUBLE NOT NULL,
    predicted_lst_lower_c DOUBLE NULL,
    predicted_lst_upper_c DOUBLE NULL,
    model_version VARCHAR(128) NOT NULL,
    data_source_status VARCHAR(255) NOT NULL,
    latitude DOUBLE NULL,
    longitude DOUBLE NULL,
    coordinates_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (prediction_id),
    UNIQUE KEY uq_ml_prediction (
        zone_id, input_observation_date, target_observation_date, model_version
    ),
    KEY idx_ml_prediction_created (created_at),
    KEY idx_ml_prediction_target (target_observation_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS environmental_recommendations (
    recommendation_id CHAR(36) NOT NULL,
    zone_id VARCHAR(128) NOT NULL,
    zone_name VARCHAR(255) NOT NULL,
    environmental_issue VARCHAR(255) NOT NULL,
    issue_type VARCHAR(32) NOT NULL,
    supporting_evidence JSON NOT NULL,
    recommended_intervention TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority VARCHAR(32) NOT NULL,
    confidence DOUBLE NULL,
    recommendation_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    follow_up_measurement TEXT NOT NULL,
    related_prediction_id CHAR(36) NULL,
    deduplication_key CHAR(64) NOT NULL,
    source_status VARCHAR(255) NOT NULL,
    PRIMARY KEY (recommendation_id),
    UNIQUE KEY uq_recommendation_deduplication (deduplication_key),
    KEY idx_recommendation_timestamp (recommendation_timestamp),
    KEY idx_recommendation_zone (zone_id),
    CONSTRAINT fk_recommendation_prediction
        FOREIGN KEY (related_prediction_id)
        REFERENCES ml_predictions (prediction_id)
        ON DELETE SET NULL
) ENGINE=InnoDB;
