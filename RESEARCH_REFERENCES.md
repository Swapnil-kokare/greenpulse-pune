# Research and dataset references for Future Smart City

This project focuses on **environmental hotspot identification and decision support** in Pune: urban heat, air quality, and electricity-demand hotspots. Traffic monitoring is intentionally out of scope.

## Dataset candidates

1. **Pune UHI / land-surface temperature feature dataset (GitHub)**  
   Repository: https://github.com/arnavvnn/Predicting-UHI-Intensity  
   The repository describes a Pune dataset with 2,382 sample points and 36 columns, with Landsat, ERA5, Sentinel-5P, MODIS, OpenStreetMap-derived morphology and related features. It is a third-party research repository, not an official municipal dataset. Inspect its README, file-level licence, provenance, temporal coverage and schema before using it. Do not assume its values are current.

2. **Pune Air Quality Dataset (Zenodo)**  
   https://zenodo.org/records/18677141  
   Described as historical Pune AQI/pollutant time series for 2022-08-01 through 2026-02-18, assembled from Open-Meteo air-quality data and city metadata. Check the record for downloadable files, licence and exact fields.

3. **Daily Air Quality Index and Pollutant Concentrations for Pune (Mendeley Data)**  
   https://data.mendeley.com/datasets/y6p778djzj/1  
   Described as daily AQI/pollutant records for multiple monitoring locations, derived from hourly OpenAQ records. Review the data dictionary, station coverage and licence before reuse.

4. **Landsat 8 Collection 2 Level-2**  
   https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2

5. **Landsat 9 Collection 2 Level-2**  
   https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2

6. **NASA MODIS MOD11A1 land-surface temperature**  
   https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1

7. **Pune Municipal Corporation Environmental Status Report 2024–25**  
   https://opendata.pmc.gov.in/opendata/PMCReports/ESR_2024-25.pdf

## Research papers to cite

- More, P. & Dhaarna (2026). “Urban heat & cool island: Investigating Pune’s (India) thermal dynamics using MODIS and Landsat 8–9 data.” *Sustainable Cities and Society*, 138, 107174. DOI: https://doi.org/10.1016/j.scs.2026.107174  
  Relevant for LST, NDVI, NDMI, impervious surfaces and day/night/seasonal thermal patterns in Pune.

- Raj, A., Anjali, A., Singh, V. K. & Semwal, V. B. (2025). “Mapping urban heat islands in Pune, India: ecological impacts and environmental challenges.” *Remote Sensing Letters*, 16(6), 654–664. DOI: https://doi.org/10.1080/2150704X.2025.2486319  
  Relevant to land-cover change, urban heat and environmental planning.

- “Assessing the impact of land use land cover changes on land surface temperature over Pune city, India” (2021). *Quaternary International*, 575–576, 259–269. DOI: https://doi.org/10.1016/j.quaint.2020.04.052  
  Relevant to Landsat-derived LST and land-use/land-cover change from 1990–2019.

- “Assessing thermal environmental changes of a semi-arid city using multi-temporal LCZ approach: a case study of Pune, India.” PubMed record: https://pubmed.ncbi.nlm.nih.gov/40888962/  
  Relevant to local climate zones and the thermal effects of urban expansion.

## How to describe the methodology accurately

- **Heat hotspot candidates:** rank georeferenced land-surface temperature observations by zone. Examine NDVI/NDMI for vegetation/moisture context and built-up indices such as NDBI or impervious-surface measures where available.
- **Air-quality hotspots:** use pollutant readings with station coordinates and timestamps. A single modelled grid-point API value is not a city-wide or ward-level measurement.
- **Electricity hotspots:** use interval meter/feeder/transformer consumption data with zone mapping. Without actual utility data, show only labelled simulated values.
- **Likely reasons:** present them as indicators or hypotheses, not proven causes. Confirm with multiple observations, spatial context and field/official data.
- **Interventions:** recommend actions for investigation (shade/tree-canopy assessment, cool roofs, surface permeability, emissions inspection, demand-side efficiency) and validate feasibility with qualified local authorities.
- **Data provenance:** store source, timestamp, units, spatial resolution, licence and whether a record is real, modelled or simulated.

## Current prototype limitations

The bundled `data/pune_demo_observations.csv` is synthetic illustrative data. The app's zone-level air-quality and electricity series are simulated. Open-Meteo calls, when reachable, return provider-reported grid estimates, not official station readings. Do not report the demo zone rankings as actual Pune hotspots.
