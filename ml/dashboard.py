import json
from pathlib import Path

import mysql.connector
import altair as alt
import pandas as pd
import streamlit as st

from ml.config import (
    ARTIFACT_DIR,
    ARTIFACT_METADATA_PATH,
    DEMO_PREDICTIONS_PATH,
    DEMO_TRAINING_REPORT_PATH,
    HEAT_THRESHOLDS,
    READINESS_REQUIREMENTS,
    TRAINING_REPORT_PATH,
    HeatThresholds,
)
from ml.database import collect_data_readiness, read_saved_ml_outputs
from ml.demo_mode import load_demo_observations
from ml.hotspot_detector import classify_lst
from ml.predict import run_inference


@st.cache_data(ttl=60, show_spinner=False)
def _load_readiness():
    return collect_data_readiness()


@st.cache_data(ttl=60, show_spinner=False)
def _load_saved_outputs():
    return read_saved_ml_outputs()


def _read_json(path):
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _format_display_date(value):
    if value in (None, ""):
        return "Not available"
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return parsed.strftime("%d %b %Y")


def _render_evidence_summary(evidence, demo=False):
    if not isinstance(evidence, dict):
        st.caption("Evidence details are unavailable.")
        return

    title = "Synthetic demo evidence" if demo else "Supporting evidence"
    st.markdown(f"**{title}**")
    source = evidence.get("data_source", "Not available")
    if demo:
        st.badge("SYNTHETIC DEMO ONLY · NOT REAL DATA", color="orange")
    else:
        st.caption(f"Data source: {source}")

    observation_date = _format_display_date(evidence.get("observation_date"))
    observation_columns = st.columns(3)
    observation_columns[0].metric(
        "Observation date",
        observation_date,
    )
    observed_lst = evidence.get("observed_lst_c")
    observation_columns[1].metric(
        "Observed LST",
        f"{float(observed_lst):.2f} °C" if observed_lst is not None else "N/A",
    )
    ndvi = evidence.get("mean_ndvi")
    observation_columns[2].metric(
        "Mean NDVI",
        f"{float(ndvi):.2f}" if ndvi is not None else "N/A",
    )

    predicted_lst = evidence.get("predicted_lst_c")
    if predicted_lst is not None:
        st.markdown("**Next-observation estimate**")
        forecast_columns = st.columns(3)
        forecast_columns[0].metric(
            "Predicted LST",
            f"{float(predicted_lst):.2f} °C",
        )
        lower = evidence.get("predicted_lst_lower_c")
        upper = evidence.get("predicted_lst_upper_c")
        forecast_columns[1].metric(
            "Illustrative error band",
            (
                f"{float(lower):.2f}–{float(upper):.2f} °C"
                if lower is not None and upper is not None
                else "Not available"
            ),
        )
        horizon = evidence.get("prediction_horizon_days")
        horizon_text = (
            f"{int(horizon)} days" if horizon is not None else "Not available"
        )
        forecast_columns[2].metric("Horizon", horizon_text)
        forecast_columns = st.columns(2)
        forecast_columns[0].caption(
            f"Target observation date: "
            f"{_format_display_date(evidence.get('predicted_for'))}"
        )
        if evidence.get("model_version"):
            forecast_columns[1].caption(
                f"Model version: {evidence['model_version']}"
            )

    thresholds = evidence.get("classification_thresholds_c")
    if thresholds:
        st.caption(
            "Exploratory temperature bands: "
            f"Low ≤ {thresholds.get('low_max', 'N/A')} °C · "
            f"Moderate ≤ {thresholds.get('moderate_max', 'N/A')} °C · "
            f"High ≤ {thresholds.get('high_max', 'N/A')} °C"
        )
    if evidence.get("low_ndvi_threshold") is not None:
        st.caption(
            f"Low-NDVI threshold: ≤ {evidence['low_ndvi_threshold']}"
        )
    if demo:
        st.caption(
            f"Data source: {source}. These illustrative values are synthetic "
            "and are not observed environmental measurements."
        )


def _render_data_readiness(report):
    st.subheader("Data readiness")
    summary = report["summary_table"]
    history = report["history_table"]
    if not summary.get("exists"):
        st.warning(
            "The existing zone_environment_summary table is unavailable.",
            title="Summary table unavailable",
        )
    elif summary.get("schema_error"):
        st.error(summary["schema_error"], title="Summary schema is incomplete")
    else:
        summary_metrics = st.columns(4)
        summary_metrics[0].metric(
            "Current summary rows", summary.get("row_count", 0)
        )
        summary_metrics[1].metric("Summary zones", summary.get("distinct_zones", 0))
        summary_metrics[2].metric(
            "Summary observation dates", summary.get("distinct_dates", 0)
        )
        summary_metrics[3].metric(
            "Summary batches", summary.get("distinct_batches", 0)
        )
        st.caption(
            "The existing zone_environment_summary remains a latest-summary table; "
            "it is not treated as a historical time series. Records received: "
            f"{summary.get('records_received') or 0} · latest summary processing time: "
            f"{summary.get('latest_processing_time') or 'unavailable'}"
        )

    if not history.get("exists"):
        st.warning(
            "Historical observation storage is not installed. Apply "
            "database/migrations/001_environmental_ml.sql, then start the Spark "
            "streaming job to record new source-tagged observations.",
            title="History table unavailable",
        )
    elif history.get("schema_error"):
        st.error(history["schema_error"], title="History schema is incomplete")
    else:
        validation = history.get("validation") or {}
        metrics = st.columns(4)
        metrics[0].metric("History rows", history.get("rows", 0))
        metrics[1].metric(
            "Eligible non-demo rows", validation.get("eligible_non_demo_rows", 0)
        )
        metrics[2].metric("Eligible dates", history.get("eligible_dates", 0))
        metrics[3].metric("Eligible zones", history.get("eligible_zones", 0))
        st.caption(
            "Observation window: "
            f"{history.get('earliest_eligible_observation') or 'unavailable'} to "
            f"{history.get('latest_observation') or 'unavailable'} · latest Spark "
            f"batch: {history.get('latest_batch_id') or 'unavailable'} · latest "
            f"processing time: {history.get('latest_processing_time') or 'unavailable'}"
        )
        sources = validation.get("sources", [])
        st.caption(
            "Recorded source identifiers: "
            + (", ".join(sources) if sources else "none")
        )
        st.caption(
            validation.get(
                "provenance_note",
                "Source identifiers are not independently verified; review "
                "provider documentation and quality flags.",
            )
        )
        excluded = validation.get("demonstration_rows_excluded", 0)
        conflicts = validation.get("conflicting_source_rows_excluded", 0)
        if excluded or conflicts:
            st.info(
                f"Excluded {excluded} demonstration/simulated rows and "
                f"{conflicts} rows with conflicting source values for the same "
                "zone and observation date."
            )

    local = report["local_demo_dataset"]
    if local.get("exists"):
        with st.expander("Bundled demonstration dataset (not used for training)"):
            st.write(
                f"Rows: {local.get('rows_received', local.get('rows', 0))} · "
                f"excluded synthetic/demo rows: "
                f"{local.get('demonstration_rows_excluded', 'not classified')}"
            )
            st.caption(
                "This dataset is excluded from the real-data model. Use the separate "
                "synthetic demo mode below if you need illustrative ML outputs."
            )


def _render_model_status(metadata, training_report, history):
    st.subheader("Model status and validation")
    if metadata:
        if not history.get("exists") or history.get("schema_error"):
            st.warning(
                "An accepted artifact exists, but current historical inputs are "
                "unavailable. Apply or repair the additive history-table migration "
                "before generating predictions.",
                title="Inference unavailable",
            )
            return False
        artifact = ARTIFACT_DIR / Path(metadata["artifact_file"]).name
        if not artifact.is_file():
            st.error(
                "Model metadata exists, but its artifact file is missing. "
                "Retrain only after the data readiness requirements are met.",
                title="Model artifact unavailable",
            )
            return False
        latest_date = history.get("latest_observation")
        trained_through = pd.to_datetime(
            metadata.get("training_data_end"), errors="coerce"
        )
        available_date = pd.to_datetime(latest_date, errors="coerce")
        stale = (
            pd.notna(available_date)
            and pd.notna(trained_through)
            and available_date > trained_through
        )
        st.badge(
            "Model needs retraining" if stale else "Accepted model available",
            color="orange" if stale else "green",
            icon=":material/model_training:",
        )
        values = st.columns(4)
        values[0].metric("Model version", metadata["model_version"])
        values[1].metric(
            "Trained through",
            str(metadata.get("training_data_end", "unknown"))[:10],
        )
        values[2].metric(
            "Training observations", metadata.get("training_observations", 0)
        )
        values[3].metric("Training zones", metadata.get("training_zones", 0))
        st.caption(metadata.get("forecast_horizon", ""))
        uncertainty = metadata.get("uncertainty", {})
        if uncertainty:
            st.caption(
                "Prediction error band: ±"
                f"{uncertainty['absolute_error_quantile_c']:.2f} °C from the "
                "chronological holdout. This empirical band is not a calibrated "
                "probability interval or a guarantee of future coverage."
            )
        st.caption(
            "Latest observation: "
            f"{latest_date or 'unavailable'} · latest history processing time: "
            f"{history.get('latest_processing_time') or 'unavailable'}"
        )
        metrics = metadata.get("validation_metrics", {})
        candidate = metrics.get("candidate_random_forest", {})
        baseline = metrics.get("baseline", {})
        if candidate:
            validation_columns = st.columns(3)
            validation_columns[0].metric(
                "Chronological holdout MAE",
                f"{candidate['mae_c']:.2f} °C",
                delta=f"{candidate['mae_c'] - baseline['mae_c']:+.2f} °C vs baseline",
                delta_color="inverse",
            )
            validation_columns[1].metric(
                "Chronological holdout RMSE",
                f"{candidate['rmse_c']:.2f} °C",
            )
            validation_columns[2].metric(
                "Chronological holdout R²",
                (
                    f"{candidate['r2']:.3f}"
                    if candidate.get("r2") is not None
                    else "not available"
                ),
            )
            st.caption(
                "Holdout MAE/RMSE are temperature errors in °C. The holdout "
                "contains later dates than the training period; random splits "
                "are not used."
            )
            holdout = metadata.get("holdout", [])
            if holdout:
                holdout_frame = pd.DataFrame(holdout)
                st.scatter_chart(
                    holdout_frame,
                    x="actual_lst_c",
                    y="predicted_lst_c",
                    color="zone_id",
                    alt="Chronological holdout actual versus predicted land-surface temperature",
                )
        else:
            st.info("Validation metrics are not available in the accepted artifact.")
        importance = metadata.get("top_feature_importances", [])
        if importance:
            st.caption("Top model feature importances are descriptive, not causal.")
            importance_frame = pd.DataFrame(importance).set_index("feature")
            st.bar_chart(
                importance_frame,
                y="importance",
                horizontal=True,
                alt="Accepted model feature importances",
            )
        if stale:
            st.warning(
                "Newer observations exist than those used to train this model. "
                "Run the explicit training command and deploy only if the new "
                "chronological holdout meets acceptance criteria."
            )
            st.code("python -m ml.train_model", language="powershell")
        return not stale

    if training_report:
        status = training_report.get("status", "unavailable")
        if status == "insufficient_data":
            st.warning(
                training_report.get(
                    "reason",
                    "Insufficient eligible historical observations for a model.",
                ),
                title="Insufficient data for a valid model",
            )
        elif status == "rejected":
            st.warning(
                training_report.get("reason", "Candidate model was rejected."),
                title="Candidate not accepted",
            )
            metrics = training_report.get("metrics", {})
            if metrics:
                st.json(metrics)
        elif status == "blocked":
            st.info(training_report.get("reason", "Training is currently blocked."))
    elif not history.get("exists"):
        st.warning(
            "No model is published. Add the history table and collect genuine "
            "source-tagged observations before training.",
            title="Insufficient data for a valid model",
        )
    else:
        validation = history.get("validation") or {}
        eligible = validation.get("eligible_non_demo_rows", 0)
        st.warning(
            f"No accepted model is published. There are {eligible} eligible "
            f"observations; requirements include at least "
            f"{READINESS_REQUIREMENTS.minimum_observations} observations, "
            f"{READINESS_REQUIREMENTS.minimum_dates} distinct dates, and "
            f"{READINESS_REQUIREMENTS.minimum_zones} zones, plus a sufficient "
            "chronological holdout.",
            title="Insufficient data for a valid model",
        )
    st.caption(
        "Training is explicit and never runs during dashboard refresh. Source "
        "identifiers must be reviewed for provenance. No "
        "synthetic values or unvalidated metrics are used as model evidence."
    )
    st.code("python -m ml.train_model", language="powershell")
    return False


def _render_predictions_and_recommendations(outputs, thresholds):
    st.subheader("Saved next-observation predictions")
    predictions = outputs.get("predictions", [])
    if not predictions:
        st.info("No saved predictions are available yet.")
    else:
        prediction_frame = pd.DataFrame(predictions)
        prediction_frame["hotspot_band"] = prediction_frame["predicted_lst_c"].map(
            lambda value: classify_lst(value, thresholds)
        )
        st.dataframe(
            prediction_frame[
                [
                    "zone_name",
                    "input_observation_date",
                    "target_observation_date",
                    "forecast_horizon_days",
                    "predicted_lst_c",
                    "predicted_lst_lower_c",
                    "predicted_lst_upper_c",
                    "hotspot_band",
                    "model_version",
                    "created_at",
                    "data_source_status",
                ]
            ],
            width="stretch",
            hide_index=True,
            alt="Saved next-observation land-surface temperature predictions",
        )
        verified = prediction_frame[
            prediction_frame["coordinates_verified"].eq(True)
            & prediction_frame["latitude"].notna()
            & prediction_frame["longitude"].notna()
        ]
        if not verified.empty:
            st.map(
                verified,
                latitude="latitude",
                longitude="longitude",
                color="#2bbf9f",
                alt="Predictions at source coordinates explicitly marked verified",
            )
            st.caption(
                "Only coordinates explicitly marked verified in the historical "
                "data are mapped. Unverified or missing coordinates are omitted."
            )
        else:
            st.info(
                "No predictions have verified coordinates. Zone-level mapping "
                "is withheld rather than using approximate locations."
            )

    st.subheader("Evidence-based review recommendations")
    recommendations = outputs.get("recommendations", [])
    if not recommendations:
        st.info(
            "No recommendations are currently supported by validated observations "
            "and the configured review bands."
        )
        return
    for item in recommendations:
        heading = (
            f"{item['priority']} · {item['zone_name']} · "
            f"{item['environmental_issue']}"
        )
        with st.expander(heading):
            st.write(item["reason"])
            st.markdown(f"**Suggested review:** {item['recommended_intervention']}")
            st.markdown(f"**Follow-up:** {item['follow_up_measurement']}")
            evidence = item.get("supporting_evidence")
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            _render_evidence_summary(evidence or {})
            st.caption(
                f"Created: {item['recommendation_timestamp']} · "
                f"Type: {item['issue_type']} · Source status: {item['source_status']} "
                "· Recommendations are heuristic planning prompts, not official "
                "warnings or causal claims."
            )


def _render_demo_outputs():
    st.divider()
    st.subheader("Synthetic demo model")
    st.warning(
        "DEMO ONLY — this model uses synthetic values. Its predictions, "
        "recommendations, map locations, and metrics are not real Pune "
        "measurements, warnings, or validated forecasting results.",
        title="Synthetic data demonstration",
    )
    try:
        training_report = _read_json(DEMO_TRAINING_REPORT_PATH)
        demo_output = _read_json(DEMO_PREDICTIONS_PATH)
    except (OSError, json.JSONDecodeError) as error:
        st.error(
            f"Demo model output could not be read: {error}",
            title="Demo output unavailable",
        )
        return
    if not training_report:
        st.caption(
            "To create the isolated demo model, run "
            "`python -m ml.train_model --demo` from the project folder."
        )
        return

    st.badge(
        "Synthetic demo model",
        color="orange",
        icon=":material/science:",
    )
    st.caption(
        f"Status: {training_report.get('status', 'unknown')} · Model: "
        f"{training_report.get('model_version', 'not created')}"
    )
    readiness = training_report.get("readiness", {})
    metrics = st.columns(3)
    metrics[0].metric(
        "Synthetic observations",
        readiness.get("eligible_observations", 0),
    )
    metrics[1].metric("Zones", readiness.get("distinct_zones", 0))
    metrics[2].metric("Observation dates", readiness.get("distinct_dates", 0))
    model_metrics = training_report.get("metrics", {})
    candidate = model_metrics.get("candidate_random_forest", {})
    baseline = model_metrics.get("baseline", {})
    if candidate and baseline:
        displayed_metrics = st.columns(3)
        displayed_metrics[0].metric(
            "Demo holdout MAE",
            f"{candidate['mae_c']:.2f} °C",
            delta=f"{candidate['mae_c'] - baseline['mae_c']:+.2f} °C vs baseline",
            delta_color="inverse",
        )
        displayed_metrics[1].metric(
            "Demo holdout RMSE", f"{candidate['rmse_c']:.2f} °C"
        )
        displayed_metrics[2].metric(
            "Demo holdout R²",
            f"{candidate['r2']:.3f}"
            if candidate.get("r2") is not None
            else "not available",
        )
    st.caption(training_report.get("metric_note", "Synthetic-only metrics."))
    if training_report.get("reason"):
        st.info(training_report["reason"])

    if not demo_output:
        st.caption(
            "After training, generate demo-only predictions with "
            "`python -m ml.predict --demo`."
        )
        return
    try:
        demo_observations, _ = load_demo_observations()
    except (OSError, ValueError) as error:
        st.error(
            f"Synthetic demo observations could not be loaded for charts: {error}",
            title="Demo charts unavailable",
        )
        return

    demo_predictions = demo_output.get("predictions", [])
    st.subheader("Demo charts")
    st.caption(
        "All charts below use synthetic demonstration values. They illustrate "
        "the dashboard only and do not show measured Pune conditions."
    )

    trend_column, heatmap_column = st.columns([1, 1.2])
    with trend_column:
        with st.container(border=True):
            st.markdown("**Land-surface temperature trend**")
            zone_names = sorted(demo_observations["zone_name"].dropna().unique())
            selected_zone = st.selectbox(
                "Select a demo zone",
                zone_names,
                key="demo_chart_zone",
            )
            zone_history = (
                demo_observations[
                    demo_observations["zone_name"] == selected_zone
                ]
                .sort_values("observation_date")
                .rename(
                    columns={
                        "observation_date": "Observation date",
                        "lst_celsius": "Land-surface temperature (°C)",
                    }
                )
            )
            st.line_chart(
                zone_history,
                x="Observation date",
                y="Land-surface temperature (°C)",
                alt=(
                    "Synthetic land-surface temperature over time for "
                    f"{selected_zone}"
                ),
            )

    with heatmap_column:
        with st.container(border=True):
            st.markdown("**Zone-by-date temperature heatmap**")
            heatmap_data = demo_observations[
                ["zone_name", "observation_date", "lst_celsius"]
            ].copy()
            heatmap = (
                alt.Chart(heatmap_data)
                .mark_rect()
                .encode(
                    x=alt.X(
                        "observation_date:T",
                        title="Observation date",
                        axis=alt.Axis(format="%d %b", labelAngle=-35),
                    ),
                    y=alt.Y(
                        "zone_name:N",
                        title="Demo zone",
                        sort=alt.EncodingSortField(
                            field="lst_celsius",
                            op="mean",
                            order="descending",
                        ),
                    ),
                    color=alt.Color(
                        "lst_celsius:Q",
                        title="LST (°C)",
                        scale=alt.Scale(scheme="redyellowgreen", reverse=True),
                    ),
                    tooltip=[
                        alt.Tooltip("zone_name:N", title="Zone"),
                        alt.Tooltip(
                            "observation_date:T",
                            title="Observation date",
                            format="%d %b %Y",
                        ),
                        alt.Tooltip(
                            "lst_celsius:Q",
                            title="LST (°C)",
                            format=".2f",
                        ),
                    ],
                )
                .properties(height=390)
            )
            st.altair_chart(
                heatmap,
                width="stretch",
                alt="Synthetic land-surface temperature by zone and observation date",
            )

    if demo_predictions:
        prediction_column, evaluation_column = st.columns(2)
        with prediction_column:
            with st.container(border=True):
                st.markdown("**Next-observation estimates by zone**")
                prediction_chart_data = (
                    pd.DataFrame(demo_predictions)
                    .sort_values("predicted_lst_c", ascending=False)
                    .rename(
                        columns={
                            "zone_name": "Zone",
                            "predicted_lst_c": "Predicted LST (°C)",
                        }
                    )
                )
                st.bar_chart(
                    prediction_chart_data,
                    x="Zone",
                    y="Predicted LST (°C)",
                    horizontal=True,
                    alt="Synthetic next-observation temperature estimates by zone",
                )
        holdout = training_report.get("holdout", [])
        if holdout:
            with evaluation_column:
                with st.container(border=True):
                    st.markdown("**Chronological demo holdout**")
                    st.scatter_chart(
                        pd.DataFrame(holdout),
                        x="actual_lst_c",
                        y="predicted_lst_c",
                        color="zone_id",
                        x_label="Observed LST (°C)",
                        y_label="Predicted LST (°C)",
                        alt=(
                            "Synthetic chronological holdout comparison of observed "
                            "and predicted temperature"
                        ),
                    )
                    st.caption(
                        "This is a synthetic holdout comparison, not evidence of "
                        "real-world prediction accuracy."
                    )

    if demo_predictions:
        st.subheader("Demo-only next-observation predictions")
        st.dataframe(
            pd.DataFrame(demo_predictions),
            width="stretch",
            hide_index=True,
            alt="Synthetic demonstration predictions, not real observations",
        )
    for item in demo_output.get("recommendations", []):
        with st.expander(
            f"DEMO ONLY · {item['priority']} · {item['zone_name']}"
        ):
            st.write(item["reason"])
            st.markdown(
                f"**Illustrative review suggestion:** "
                f"{item['recommended_intervention']}"
            )
            _render_evidence_summary(
                item.get("supporting_evidence", {}),
                demo=True,
            )
            st.caption(
                "Generated from synthetic demo values. Do not treat as a real "
                "planning recommendation."
            )
    st.caption(
        "No predictions or recommendations in this section are written to the "
        "real-data MySQL output tables."
    )


def render_ml_page():
    st.title("ML predictions & recommendations")
    st.write(
        "A transparent next-observation LST model and evidence-linked review "
        "suggestions. Predictions are not daily forecasts or official alerts."
    )
    try:
        report = _load_readiness()
        outputs = _load_saved_outputs()
    except (mysql.connector.Error, RuntimeError, ValueError) as error:
        st.error(
            f"ML data could not be loaded from MySQL: {error}",
            title="Database unavailable",
        )
        report = None
        outputs = {"predictions": [], "recommendations": []}

    low, moderate, high, ndvi_threshold = st.columns(4)
    with low:
        low_value = st.number_input(
            "Low band max (°C)",
            min_value=-50.0,
            max_value=80.0,
            value=float(HEAT_THRESHOLDS.low_max_c),
            step=0.5,
            key="ml_low_threshold",
        )
    with moderate:
        moderate_value = st.number_input(
            "Moderate band max (°C)",
            min_value=-50.0,
            max_value=80.0,
            value=float(HEAT_THRESHOLDS.moderate_max_c),
            step=0.5,
            key="ml_moderate_threshold",
        )
    with high:
        high_value = st.number_input(
            "High band max (°C)",
            min_value=-50.0,
            max_value=80.0,
            value=float(HEAT_THRESHOLDS.high_max_c),
            step=0.5,
            key="ml_high_threshold",
        )
    with ndvi_threshold:
        low_ndvi = st.number_input(
            "Low NDVI max",
            min_value=-1.0,
            max_value=1.0,
            value=float(HEAT_THRESHOLDS.low_ndvi_max),
            step=0.05,
            key="ml_low_ndvi",
        )
    try:
        thresholds = HeatThresholds(
            low_max_c=low_value,
            moderate_max_c=moderate_value,
            high_max_c=high_value,
            low_ndvi_max=low_ndvi,
        )
        thresholds.validate()
    except ValueError as error:
        st.error(str(error), title="Invalid heuristic thresholds")
        return

    if report:
        _render_data_readiness(report)
        try:
            training_report = _read_json(TRAINING_REPORT_PATH)
            metadata = _read_json(ARTIFACT_METADATA_PATH)
        except (OSError, json.JSONDecodeError) as error:
            st.error(
                f"Saved ML metadata could not be read: {error}",
                title="ML artifact metadata unavailable",
            )
            training_report = None
            metadata = None
        history = report["history_table"]
        model_available = _render_model_status(
            metadata, training_report, history
        )
        if model_available and st.button(
            "Generate predictions & recommendations",
            icon=":material/online_prediction:",
            type="primary",
        ):
            try:
                with st.spinner("Generating and saving model outputs..."):
                    result = run_inference(thresholds=thresholds)
            except (
                FileNotFoundError,
                mysql.connector.Error,
                RuntimeError,
                ValueError,
            ) as error:
                st.error(
                    f"Prediction generation failed: {error}",
                    title="Inference failed",
                )
            else:
                _load_readiness.clear()
                _load_saved_outputs.clear()
                st.success(
                    f"Saved {result['predictions_saved']} predictions and "
                    f"{result['recommendations_saved']} recommendations "
                    f"({result['verified_coordinate_predictions']} verified "
                    "coordinate points)."
                )
                st.rerun()
        _render_predictions_and_recommendations(outputs, thresholds)
    else:
        st.info(
            "Readiness and saved ML outputs will appear after the database "
            "connection succeeds."
        )
    _render_demo_outputs()
    st.caption(
        f"Heat bands: Low ≤ {thresholds.low_max_c:g} °C · Moderate ≤ "
        f"{thresholds.moderate_max_c:g} °C · High ≤ {thresholds.high_max_c:g} °C "
        f"· Low NDVI ≤ {thresholds.low_ndvi_max:g}. These are configurable "
        "exploratory thresholds, not government warning levels."
    )
