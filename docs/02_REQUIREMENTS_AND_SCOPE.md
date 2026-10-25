# 02. Requirements and scope

## Problem statement

The project explores how an environmental dashboard could organize land-surface temperature and vegetation observations into zone-level summaries. Repeated, quality-controlled observations and verified geographic boundaries are prerequisites for reliable spatial or temporal conclusions; the bundled demonstration file does not satisfy real-world provenance requirements.

## Intended use and users

The implemented application is for local demonstration, classroom explanation, and software development. It is not intended for emergency response, health advice, municipal enforcement, or investment decisions. Users should treat all synthetic outputs as illustrations of application behavior.

## Functional requirements

| ID | Requirement | Current implementation |
|---|---|---|
| F1 | Display the latest environmental zone summary from MySQL | Implemented against `greenpulse_pune.zone_environment_summary`; shows an error/empty state when unavailable. |
| F2 | Present heat rankings, map layers, filters, and zone details | Implemented; coordinates are joined from the bundled CSV and are approximate. |
| F3 | Refresh dashboard data and show separate observation, processing, and dashboard times | Implemented; refresh does not start the pipeline or make the source data newer. |
| F4 | Display air quality when provider data are available | Implemented as a single-point Open-Meteo provider/model estimate; unavailable responses are not fabricated. |
| F5 | Provide electricity hotspot view | Implemented as a clearly labelled illustrative/simulated index, not utility consumption. |
| F6 | Replay CSV events through Kafka and aggregate with Spark | Implemented in producer and Spark consumer code; the default CSV is synthetic. |
| F7 | Retain optional zone/date history for ML | Implemented as a separate sink using an additive migration and separate checkpoint. |
| F8 | Train/evaluate/predict using source-screened non-demo observations | Implemented; current history is empty, so real training is not currently data-ready. |
| F9 | Offer an isolated synthetic ML demonstration | Implemented with `--demo`, distinct artifacts, labels, charts, and outputs. |
| F10 | Generate heuristic suggestions with traceable evidence | Implemented; suggestions are not official alerts and do not establish causality. |

## Non-functional requirements and characteristics

- **Security:** database credentials are read from environment variables or local Streamlit secrets; do not commit or share secrets.
- **Reliability:** database/API errors and empty datasets are surfaced; missing readings are not replaced with invented values.
- **Maintainability:** data validation, features, model evaluation, inference, and recommendations live in the `ml/` package.
- **Traceability:** ML outputs retain source status, dates, model version, thresholds, and supporting evidence.
- **Usability:** dashboard is designed for desktop-first exploration and uses readable labels, status messages, and filterable data.
- **Privacy:** this local prototype does not implement user accounts or a privacy/security deployment model.
- **Performance/scalability:** no load or production-scale benchmark was verified.

## Scope boundaries

**Included:** local dashboard, current MySQL summary reading, optional local Kafka/Spark replay, additive history/ML SQL migration, exploratory regression and classification, Open-Meteo API requests, and labelled simulated module outputs.

**Excluded or not verified:** verified municipal ward polygons, official satellite processing, a live sensor feed, citywide/station-level air-quality coverage, actual utility electricity data, production deployment, user authentication, service monitoring, model serving infrastructure, and intervention-impact evaluation.

## Assumptions and dependencies

The optional streaming path assumes a reachable Kafka broker, compatible Spark/Kafka connector, existing MySQL database and base summary schema, and MySQL credentials. The ML real-data path assumes that historical observations have trustworthy source provenance and adequate zone/date coverage. The optional API panels assume network access to Open-Meteo.

## Expected outputs

The system outputs dashboard metrics and charts; a latest-batch MySQL summary; optional historical zone/date rows; ML training reports and model artifacts; next-observation predictions; and heuristic recommendation records. Synthetic outputs remain labelled and segregated. See [architecture](03_SYSTEM_ARCHITECTURE.md) and [ML methodology](07_MACHINE_LEARNING.md).
