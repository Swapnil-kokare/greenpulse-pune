# 01. Project overview

## Purpose

GreenPulse Pune is a student-built environmental intelligence prototype. It demonstrates how tabular environmental observations can be replayed through Kafka, aggregated with Spark Structured Streaming, persisted to MySQL, and explored through a Streamlit dashboard. Optional ML modules demonstrate temporal LST regression, exploratory hotspot classification, and evidence-linked recommendations.

The application is a visualization and decision-support prototype. It does not measure all of Pune, issue official public-health warnings, prove why a zone is hot, or demonstrate that any intervention has reduced heat or pollution.

## Environmental problem

Urban surfaces can retain heat and vegetation coverage can vary across neighborhoods. Comparing georeferenced, repeated observations can help identify areas for further study and inform where better measurements or interventions may be evaluated. Air quality and electricity demand are also relevant planning dimensions, but this prototype does not contain validated ward-level data for those domains.

## Motivation and intended users

The project is intended for B.Tech students, project evaluators, and developers learning about environmental data systems, streaming architectures, dashboard design, and cautious ML evaluation. Municipal planners or researchers could use a future validated version as a preliminary exploration tool, but the current synthetic data are not suitable for operational decisions.

## Objectives

1. Present environmental indicators and their data provenance in a readable dashboard.
2. Demonstrate an optional CSV replay → Kafka → Spark → MySQL workflow.
3. Preserve a latest-batch summary while providing a separate additive zone/date history sink.
4. Keep real-data model training separate from synthetic demo training.
5. Show exploratory classifications and recommendations with their threshold and evidence limitations.
6. Make data availability, freshness, and missing-source limitations visible.

## Current outputs

The prototype can show latest LST and NDVI summaries, approximate map markers, rankings, tables and charts, optional Open-Meteo provider estimates, simulated electricity indicators, and ML demo predictions/recommendations. The bundle contains synthetic LST/NDVI records. See [Results and Findings](14_RESULTS_AND_FINDINGS.md) for measured counts from the local files/database and clear qualifications.

## Project materials

- [README](../README.md) — installation and quick start.
- [Architecture](03_SYSTEM_ARCHITECTURE.md) — implemented component relationships.
- [Requirements and scope](02_REQUIREMENTS_AND_SCOPE.md) — included/excluded behavior.
- [Data sources](13_DATA_SOURCES_AND_REFERENCES.md) — provenance and references.
- [Results](14_RESULTS_AND_FINDINGS.md) — inspected outputs and evidence.

## Contributors

Contributor identities are not verifiable from the inspected source tree. Project owners should add their confirmed team names for a college submission.
