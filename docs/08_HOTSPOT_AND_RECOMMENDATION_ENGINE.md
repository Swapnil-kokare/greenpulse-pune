# 08. Hotspot and recommendation engine

## LST classification

`ml/hotspot_detector.py` classifies a numeric LST using configurable thresholds in `ml/config.py`:

| Label | Default rule |
|---|---|
| Low | LST ≤ 30°C |
| Moderate | 30°C < LST ≤ 35°C |
| High | 35°C < LST ≤ 40°C |
| Very high | LST > 40°C |
| Unavailable | Missing or invalid numeric value |

The dashboard's heat review may also use its own configurable threshold. These values are exploratory application defaults, not official government, health, or meteorological warning thresholds. Thresholds can be changed with `ML_HEAT_LOW_MAX_C`, `ML_HEAT_MODERATE_MAX_C`, `ML_HEAT_HIGH_MAX_C`, and `ML_LOW_NDVI_MAX`; invalid ordering is rejected.

## Recommendation rules

The rule engine accepts zone observations, optional predictions, and thresholds. By default, it rejects records marked synthetic, simulated, demo, or `not_real`; the demo call opts in explicitly and marks each output synthetic.

It can generate:

- **Observed elevated-LST review suggestion:** for observed High/Very high LST. It prompts a reviewer to examine land cover, shade, cool-roof feasibility, and surface materials, then verify source quality and collect a comparable follow-up.
- **Predicted heat plus low vegetation suggestion:** when predicted LST falls in High/Very high and the latest NDVI is at or below the configurable low-NDVI threshold (default 0.25). It prompts consideration of canopy/restoration/shade options and calls for another observation.

The rule prefers the predicted-heat/low-NDVI case when its conditions match; otherwise, observed high temperature may trigger the observed-evidence rule. The report stores thresholds, observation date, LST, NDVI, source status, and prediction context where available. It is a heuristic association, not proof that vegetation caused a temperature reading or that a suggested intervention will cool a place. Recommendations are not official alerts.

## Synthetic demo example

The saved demo inference artifact contains 18 next-observation estimates and 13 heuristic suggestions. In demo mode this is expected software output generated from synthetic records. It must not be interpreted as evidence of real zone conditions, actionable priorities, or intervention effectiveness.

## How to improve the evidence

Use quality-controlled LST/NDVI observations with verified source and timestamp, reliable ward or grid geometry, matched acquisition dates, and field/land-cover context. Calibrate thresholds to an explicitly selected study purpose and cite the validation method. For interventions, compare before/after observations and appropriate controls; a recommendation alone does not establish impact.
