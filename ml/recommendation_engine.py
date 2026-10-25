import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from ml.config import HEAT_THRESHOLDS, HeatThresholds
from ml.hotspot_detector import classify_lst


def generate_recommendations(
    observed_zones,
    predictions,
    thresholds=HEAT_THRESHOLDS,
    generated_at=None,
    allow_demo=False,
):
    """Create traceable, non-causal suggestions only from non-demo evidence."""
    thresholds.validate()
    generated_at = generated_at or datetime.now(timezone.utc)
    prediction_by_zone = {}
    if predictions is not None and not predictions.empty:
        prediction_by_zone = {
            str(row["zone_id"]): row
            for row in predictions.to_dict(orient="records")
        }

    recommendations = []
    for row in observed_zones.to_dict(orient="records"):
        source = row.get("data_source")
        if not source or (not allow_demo and any(
            marker in str(source).casefold()
            for marker in ("synthetic", "simulated", "demo", "not_real")
        )):
            continue

        zone_id = str(row["zone_id"])
        zone_name = str(row.get("zone_name") or zone_id)
        observed_lst = row.get("lst_celsius")
        ndvi = row.get("ndvi")
        observation_date = row.get("observation_date")
        prediction = prediction_by_zone.get(zone_id)

        observed_risk = classify_lst(observed_lst, thresholds)
        predicted_lst = (
            prediction.get("predicted_lst_c") if prediction else None
        )
        predicted_risk = classify_lst(predicted_lst, thresholds)
        issue = None
        issue_type = None
        evidence = {
            "data_source": str(source),
            "observation_date": str(observation_date),
            "observed_lst_c": (
                float(observed_lst) if pd.notna(observed_lst) else None
            ),
            "mean_ndvi": float(ndvi) if pd.notna(ndvi) else None,
            "classification_thresholds_c": {
                "low_max": thresholds.low_max_c,
                "moderate_max": thresholds.moderate_max_c,
                "high_max": thresholds.high_max_c,
            },
            "low_ndvi_threshold": thresholds.low_ndvi_max,
        }
        if prediction:
            evidence.update(
                {
                    "predicted_lst_c": float(predicted_lst),
                    "predicted_lst_lower_c": (
                        float(prediction["predicted_lst_lower_c"])
                        if pd.notna(prediction.get("predicted_lst_lower_c"))
                        else None
                    ),
                    "predicted_lst_upper_c": (
                        float(prediction["predicted_lst_upper_c"])
                        if pd.notna(prediction.get("predicted_lst_upper_c"))
                        else None
                    ),
                    "predicted_for": str(
                        prediction["target_observation_date"]
                    ),
                    "prediction_horizon_days": int(
                        prediction["forecast_horizon_days"]
                    ),
                    "model_version": prediction["model_version"],
                }
            )

        if (
            predicted_lst is not None
            and predicted_risk in {"High", "Very high"}
            and pd.notna(ndvi)
            and float(ndvi) <= thresholds.low_ndvi_max
        ):
            issue = "Predicted elevated land-surface temperature with low NDVI"
            issue_type = "predicted"
            intervention = (
                "Evaluate tree-canopy restoration, suitable native vegetation, "
                "and shade options after reviewing local land use and feasibility."
            )
            reason = (
                "The model prediction is in the configured elevated-LST band and "
                "the latest observed NDVI is below the configured low-vegetation "
                "threshold. This association does not establish causation."
            )
            priority = "High" if predicted_risk == "Very high" else "Moderate"
            follow_up = (
                "Collect the next quality-controlled LST and NDVI observation "
                "for this zone and document land-cover context."
            )
        elif observed_risk in {"High", "Very high"}:
            issue = "Observed elevated land-surface temperature"
            issue_type = "observed"
            intervention = (
                "Review land cover, shade, cool-roof feasibility, and surface "
                "materials before prioritizing an intervention."
            )
            reason = (
                "A recorded LST falls in the configured exploratory review band. "
                "The recommendation is a planning prompt, not a causal conclusion "
                "or an official heat alert."
            )
            priority = "High" if observed_risk == "Very high" else "Moderate"
            follow_up = (
                "Verify the observation against its source quality flags and "
                "collect a comparable follow-up LST measurement."
            )
        else:
            continue

        identity = {
            "zone_id": zone_id,
            "issue_type": issue_type,
            "issue": issue,
            "observation_date": str(observation_date),
            "model_version": evidence.get("model_version"),
            "classification_thresholds_c": evidence[
                "classification_thresholds_c"
            ],
            "low_ndvi_threshold": thresholds.low_ndvi_max,
        }
        deduplication_key = hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode("utf-8")
        ).hexdigest()
        recommendations.append(
            {
                "zone_id": zone_id,
                "zone_name": zone_name,
                "environmental_issue": issue,
                "issue_type": issue_type,
                "supporting_evidence": evidence,
                "recommended_intervention": intervention,
                "reason": reason,
                "priority": priority,
                "confidence": None,
                "recommendation_timestamp": generated_at,
                "follow_up_measurement": follow_up,
                "related_prediction_id": (
                    prediction.get("prediction_id") if prediction else None
                ),
                "deduplication_key": deduplication_key,
                "source_status": (
                    "SYNTHETIC DEMO ONLY - NOT REAL DATA"
                    if allow_demo
                    else (
                        "source-tagged non-demonstration input; provenance requires "
                        "independent review"
                    )
                ),
            }
        )
    return recommendations
