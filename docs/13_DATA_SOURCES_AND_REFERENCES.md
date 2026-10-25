# 13. Data sources and references

## Data provenance used by the current prototype

| Source | Use in project | Provenance/coverage available | Interpretation |
|---|---|---|---|
| `data/pune_demo_observations.csv` | Dashboard coordinate/source lookup, optional Kafka replay, demo training and inference | 144 rows, 18 zone names, eight dates (2025-03-15 to 2025-07-06), source label `SYNTHETIC_DEMO_NOT_REAL`. Coordinate values are illustrative. | Synthetic demo values, not satellite observations or measured Pune conditions. |
| `data/README_DATA.md` | Bundled file field notes | Local documentation; not independent provenance evidence. | Explains the demo data layout, not an external source. |
| MySQL `greenpulse_pune.zone_environment_summary` | Dashboard latest-batch KPI, map/ranking inputs | Inspected batch 4, 18 zones, observation date 2025-07-06, 288 received source records, process timestamp 2026-10-25 20:02:31. Summary schema has no source or coordinate fields. | Existing summary of the synthetic replay according to the bundled source mapping; not a verified independent dataset. |
| Open-Meteo Forecast API | Optional current weather estimates | App requests one approximate Pune grid point and provider time; outputs depend on network/API availability. | Provider/model estimate, not a local weather station measurement. |
| Open-Meteo Air Quality API | Optional AQI/pollutant estimates | App requests one approximate Pune grid point for US AQI, PM2.5, PM10, nitrogen dioxide, and ozone when the request succeeds. Values are not persisted in the environmental summary table. | Provider/model estimate, not citywide or official station-level measurement. |
| Electricity zone indicators | Illustrative dashboard module | No verified utility data source connected. | Simulated/derived index only; not actual consumption. |

No geographic boundary file is included. The bundled coordinate points are not verified ward centroids or polygons. The project currently has no independent license/provenance statement for the synthetic generation beyond its explicit synthetic source label; do not assign it a third-party data license.

## Potential data sources to investigate (not currently used as project observations)

The following are leads recorded in the repository's [research reference notes](../RESEARCH_REFERENCES.md). Before use, verify current metadata, download access, provenance, spatial/temporal coverage, field definitions, licensing, and citation requirements:

- [Pune UHI intensity research repository](https://github.com/arnavvnn/Predicting-UHI-Intensity) — third-party research repository; exact provenance and reuse permissions require review.
- [Pune air-quality dataset record on Zenodo](https://zenodo.org/records/18677141) — inspect record metadata, license, downloadable files, and source lineage before reuse.
- [Daily Pune air-quality data on Mendeley Data](https://data.mendeley.com/datasets/y6p778djzj/1) — inspect data dictionary, station coverage, and license.
- [Landsat 8 Collection 2 Level 2 catalog](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2).
- [Landsat 9 Collection 2 Level 2 catalog](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2).
- [NASA MODIS MOD11A1 catalog](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1).
- [Pune Municipal Corporation Environmental Status Report 2024–25](https://opendata.pmc.gov.in/opendata/PMCReports/ESR_2024-25.pdf).

These are candidate sources, not inputs used to produce the reported prototype statistics. Satellite products require product-specific scaling, quality/cloud screening, acquisition-time alignment, and a clear conversion to Celsius before analysis.

## Technical references

- [Python documentation](https://docs.python.org/3/).
- [Streamlit documentation](https://docs.streamlit.io/).
- [Apache Kafka documentation](https://kafka.apache.org/documentation/).
- [Apache Spark Structured Streaming guide](https://spark.apache.org/docs/latest/streaming/index.html).
- [PySpark documentation](https://spark.apache.org/docs/latest/api/python/).
- [MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/).
- [Pandas documentation](https://pandas.pydata.org/docs/).
- [NumPy documentation](https://numpy.org/doc/).
- [scikit-learn documentation](https://scikit-learn.org/stable/).
- [Open-Meteo Forecast API](https://open-meteo.com/en/docs).
- [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api).
- [Plotly Python documentation](https://plotly.com/python/).
- [Docker Compose documentation](https://docs.docker.com/compose/).

## Citation and licensing caveat

The project source tree does not include a verified external environmental dataset license or a citation record for the bundled synthetic data. The references above include software/API documentation and possible data leads; they should not be presented as citations for the synthetic values. Before a formal research submission, add the exact dataset/product version, provider/author, access date, license, geographic extent, temporal range, and processing steps for every real input.
