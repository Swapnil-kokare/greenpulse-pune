import os
import socket
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import mysql.connector
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="GreenPulse Pune",
    page_icon=":material/eco:",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent
COORDINATE_SOURCE = ROOT / "data" / "pune_demo_observations.csv"
PUNE_LAT, PUNE_LON = 18.5204, 73.8567
PUNE_TIMEZONE = ZoneInfo("Asia/Kolkata")
PAGES = [
    "Pune overview",
    "Heat hotspots",
    "Air quality",
    "Electricity hotspots",
    "ML predictions & recommendations",
    "Data & pipeline status",
]
HEAT_COLORS = ["#2bbf9f", "#e7bd62", "#e16a5b"]
HEAT_CLASS_COLORS = {
    "Below review band": HEAT_COLORS[0],
    "Within 3 °C of threshold": HEAT_COLORS[1],
    "Review candidate": HEAT_COLORS[2],
}
VEGETATION_COLORS = ["#b76e4f", "#d6bd67", "#34b28c"]
AQI_COLORS = {
    "Good (0–50)": "#2bbf9f",
    "Moderate (51–100)": "#e7bd62",
    "Unhealthy for sensitive groups (101–150)": "#e99557",
    "Unhealthy (151–200)": "#e16a5b",
    "Very unhealthy (201–300)": "#bb79bd",
    "Hazardous (301+)": "#8d3545",
}
ZONE_SUMMARY_COLUMNS = (
    "zone_id",
    "zone_name",
    "records_received",
    "mean_lst_c",
    "mean_ndvi",
    "latest_observation_date",
    "batch_id",
    "processed_at",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #09131f;
        color: #f2f6fb;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        color: #f2f6fb;
    }
    [data-testid="stSidebar"] {
        background: #0e1b29;
        border-right: 1px solid #203246;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] label {
        color: #e4edf6;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    small {
        color: #b4c5d5;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: #e4edf6;
    }
    h1, h2, h3, h4, h5, h6 { color: #f4f7fb; }
    .block-container { max-width: 1680px; padding-top: 1.2rem; }
    h1, h2, h3 { letter-spacing: -0.025em; }
    [data-testid="stMetric"] {
        background: #101e2c;
        border: 1px solid #24384b;
        border-radius: 12px;
        padding: 15px 17px;
    }
    [data-testid="stMetricLabel"] { color: #c2d0dd; }
    [data-testid="stMetricValue"] { color: #f5f8fc; }
    .gp-subtitle { color: #c2d0dd; margin-top: -0.6rem; }
    [data-testid="stDataFrame"],
    [data-testid="stTable"] { color: #eaf0f6; }
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] [data-baseweb="select"] *,
    [data-testid="stRadio"] label,
    [data-testid="stToggle"] label {
        color: #edf3f9;
    }
    [data-testid="stButton"] button {
        color: #f4f8fb;
        border-color: #426078;
    }
    @media (max-width: 800px) {
        .block-container { padding: 1rem 1rem 2rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60, show_spinner=False)
def load_spark_data():
    try:
        configured_secrets = st.secrets.get("mysql", {})
    except StreamlitSecretNotFoundError:
        configured_secrets = {}

    if not isinstance(configured_secrets, Mapping):
        raise RuntimeError(
            "The [mysql] section in .streamlit/secrets.toml must be a key-value table."
        )

    password = os.getenv("MYSQL_PASSWORD") or configured_secrets.get("password")
    if not password:
        raise RuntimeError(
            "MySQL password is not configured. Set MYSQL_PASSWORD in the same "
            "PowerShell terminal used to start Streamlit, or add a local "
            "[mysql] password to .streamlit/secrets.toml. See README.md."
        )

    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", configured_secrets.get("host", "127.0.0.1")),
        port=int(os.getenv("MYSQL_PORT", configured_secrets.get("port", "3306"))),
        user=os.getenv("MYSQL_USER", configured_secrets.get("user", "root")),
        password=password,
        database=os.getenv(
            "MYSQL_DATABASE",
            configured_secrets.get("database", "greenpulse_pune"),
        ),
        connection_timeout=5,
    )
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT zone_id, zone_name, records_received, mean_lst_c, mean_ndvi,
                   latest_observation_date, batch_id, processed_at
            FROM zone_environment_summary
            WHERE batch_id = (
                SELECT MAX(batch_id) FROM zone_environment_summary
            )
            ORDER BY mean_lst_c DESC
            """
        )
        zones = pd.DataFrame(cursor.fetchall(), columns=ZONE_SUMMARY_COLUMNS)
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()

    for column in ("mean_lst_c", "mean_ndvi", "records_received", "batch_id"):
        if column in zones:
            zones[column] = pd.to_numeric(zones[column], errors="coerce")
    for column in ("latest_observation_date", "processed_at"):
        if column in zones:
            zones[column] = pd.to_datetime(zones[column], errors="coerce")
    return zones


@st.cache_data(ttl=3600, show_spinner=False)
def load_coordinate_reference():
    if not COORDINATE_SOURCE.exists():
        return pd.DataFrame(
            columns=["zone_id", "map_lat", "map_lon", "map_source"]
        )

    reference = pd.read_csv(COORDINATE_SOURCE)
    required = {"zone_id", "latitude", "longitude"}
    if not required.issubset(reference.columns):
        return pd.DataFrame(
            columns=["zone_id", "map_lat", "map_lon", "map_source"]
        )

    reference["latitude"] = pd.to_numeric(reference["latitude"], errors="coerce")
    reference["longitude"] = pd.to_numeric(reference["longitude"], errors="coerce")
    reference = reference.dropna(
        subset=["zone_id", "latitude", "longitude"]
    ).copy()
    reference = reference[
        reference["latitude"].between(-90, 90)
        & reference["longitude"].between(-180, 180)
    ]
    if "data_source" in reference:
        reference["map_source"] = reference["data_source"].fillna(
            "Source not provided"
        )
    else:
        reference["map_source"] = "Source not provided"

    return (
        reference[
            ["zone_id", "latitude", "longitude", "map_source"]
        ]
        .drop_duplicates("zone_id")
        .rename(columns={"latitude": "map_lat", "longitude": "map_lon"})
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_current_weather():
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": PUNE_LAT,
            "longitude": PUNE_LON,
            "current": (
                "temperature_2m,relative_humidity_2m,"
                "apparent_temperature,wind_speed_10m"
            ),
            "timezone": "Asia/Kolkata",
        },
        timeout=8,
    )
    response.raise_for_status()
    return response.json().get("current", {})


@st.cache_data(ttl=300, show_spinner=False)
def load_current_air():
    response = requests.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={
            "latitude": PUNE_LAT,
            "longitude": PUNE_LON,
            "current": "us_aqi,pm2_5,pm10,nitrogen_dioxide,ozone",
            "timezone": "Asia/Kolkata",
        },
        timeout=8,
    )
    response.raise_for_status()
    return response.json().get("current", {})


def val(value, digits=1, suffix=""):
    try:
        if pd.isna(value):
            return "—"
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def format_date(value, date_format="%d %b %Y"):
    if value is None or pd.isna(value):
        return "Not recorded"
    return pd.Timestamp(value).strftime(date_format)


def classify_heat(value, threshold):
    if pd.isna(value):
        return "Missing LST"
    if value >= threshold:
        return "Review candidate"
    if value >= threshold - 3:
        return "Within 3 °C of threshold"
    return "Below review band"


def attach_map_coordinates(zones, reference):
    result = zones.copy()
    if reference.empty or "zone_id" not in result:
        result["map_lat"] = pd.NA
        result["map_lon"] = pd.NA
        result["map_source"] = "Not stored in MySQL"
        return result

    result = result.merge(reference, on="zone_id", how="left")
    result["map_source"] = result["map_source"].fillna("Not stored in MySQL")
    return result


def source_label(reference):
    if "map_source" not in reference or reference.empty:
        return "Historical dataset; source metadata unavailable"
    sources = reference["map_source"].dropna().astype(str).unique()
    if any("SYNTHETIC_DEMO_NOT_REAL" in source for source in sources):
        return "Historical dataset · synthetic demo values"
    if sources.size:
        return f"Historical dataset · {sources[0]}"
    return "Historical dataset; source metadata unavailable"


def style_chart(figure, height=390):
    figure.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dbe6f4"),
        margin=dict(l=8, r=8, t=48, b=10),
        title=dict(font=dict(size=16, color="#f0f6ff"), x=0.02),
        xaxis=dict(gridcolor="#233249"),
        yaxis=dict(gridcolor="#233249"),
    )
    return figure


def render_city_map(zones, layer, heat_threshold=None):
    mapped = zones.dropna(subset=["map_lat", "map_lon"]).copy()
    value_column = {
        "Heat": "mean_lst_c",
        "Vegetation": "mean_ndvi",
    }.get(layer)
    if value_column and value_column in mapped:
        mapped = mapped.dropna(subset=[value_column])
    elif value_column:
        mapped = mapped.iloc[0:0]

    if mapped.empty:
        st.info(
            "Zone-level mapping is unavailable because no matched, valid zone "
            "coordinates are available. A verified geographic dataset is needed; "
            "no city marker is substituted for zone locations."
        )
        return

    if layer == "Heat":
        temperatures = mapped["mean_lst_c"].dropna()
        if temperatures.empty:
            st.info("No valid LST values are available to map.")
            return
        if heat_threshold is None:
            heat_threshold = float(temperatures.quantile(0.75))
        mapped["Heat classification"] = mapped["mean_lst_c"].apply(
            lambda value: classify_heat(value, heat_threshold)
        )

    hover_columns = [
        column
        for column in (
            "zone_id",
            "mean_lst_c",
            "mean_ndvi",
            "Illustrative index",
            "Classification",
            "latest_observation_date",
            "map_source",
            "Heat classification",
        )
        if column in mapped.columns
    ]
    if layer == "Heat":
        figure = px.scatter_map(
            mapped,
            lat="map_lat",
            lon="map_lon",
            color="Heat classification",
            color_discrete_map=HEAT_CLASS_COLORS,
            hover_name="zone_name",
            hover_data=hover_columns,
            zoom=10,
            center={"lat": PUNE_LAT, "lon": PUNE_LON},
            height=540,
            map_style="open-street-map",
            labels={
                "mean_lst_c": "Mean LST (°C)",
                "mean_ndvi": "Mean NDVI",
                "latest_observation_date": "Observation date",
                "map_source": "Source",
                "Heat classification": "Configured review category",
            },
        )
    elif layer == "Vegetation":
        figure = px.scatter_map(
            mapped,
            lat="map_lat",
            lon="map_lon",
            color="mean_ndvi",
            color_continuous_scale=VEGETATION_COLORS,
            hover_name="zone_name",
            hover_data=hover_columns,
            zoom=10,
            center={"lat": PUNE_LAT, "lon": PUNE_LON},
            height=540,
            map_style="open-street-map",
            labels={
                "mean_lst_c": "Mean LST (°C)",
                "mean_ndvi": "Mean NDVI",
                "latest_observation_date": "Observation date",
                "map_source": "Source",
            },
        )
        figure.update_coloraxes(colorbar_title="Mean NDVI")
    elif layer == "Electricity" and "Classification" in mapped:
        figure = px.scatter_map(
            mapped,
            lat="map_lat",
            lon="map_lon",
            color="Classification",
            color_discrete_map={
                "Illustrative high index": HEAT_COLORS[2],
                "Below demo threshold": HEAT_COLORS[0],
            },
            hover_name="zone_name",
            hover_data=hover_columns,
            zoom=10,
            center={"lat": PUNE_LAT, "lon": PUNE_LON},
            height=540,
            map_style="open-street-map",
            labels={
                "Illustrative index": "Illustrative index (0–100)",
                "Classification": "Demo category",
                "mean_lst_c": "Mean LST (°C)",
                "mean_ndvi": "Mean NDVI",
                "latest_observation_date": "Observation date",
                "map_source": "Source",
            },
        )
    else:
        figure = px.scatter_map(
            mapped,
            lat="map_lat",
            lon="map_lon",
            hover_name="zone_name",
            hover_data=hover_columns,
            zoom=10,
            center={"lat": PUNE_LAT, "lon": PUNE_LON},
            height=540,
            map_style="open-street-map",
            color_discrete_sequence=["#54c8a1"],
            labels={
                "mean_lst_c": "Mean LST (°C)",
                "mean_ndvi": "Mean NDVI",
                "latest_observation_date": "Observation date",
                "map_source": "Source",
            },
        )

    figure.update_traces(marker={"size": 15, "opacity": 0.9})
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dbe6f4"),
        margin=dict(l=0, r=0, t=8, b=0),
        uirevision="greenpulse-pune-map",
        dragmode="pan",
    )
    st.plotly_chart(
        figure,
        width="stretch",
        config={"scrollZoom": True},
        key=f"pune_zone_map_{layer.lower()}",
        alt=f"Interactive Pune zone map showing the {layer.lower()} layer",
    )
    st.caption(
        "Hover a marker for its zone, LST, NDVI, observation date, and source. "
        "Markers use dataset-provided coordinates; the bundled CSV labels these "
        "locations synthetic and they are not verified ward boundaries."
    )


def render_pipeline_status(zones, db_error, source, dashboard_time):
    with st.container(border=True):
        st.subheader("Data freshness & pipeline")
        if db_error:
            database_status = "Unavailable"
            latest_observation = "Unavailable"
            processed_at = "Unavailable"
            records_processed = "Unavailable"
        elif zones.empty:
            database_status = "Connected · no rows"
            latest_observation = "No observations"
            processed_at = "Not recorded"
            records_processed = "0"
        else:
            database_status = "Connected"
            observation_dates = zones["latest_observation_date"].dropna()
            latest_observation = (
                format_date(observation_dates.max()) if not observation_dates.empty
                else "Not recorded"
            )
            process_dates = zones["processed_at"].dropna()
            processed_at = (
                format_date(process_dates.max(), "%d %b %Y %H:%M:%S")
                if not process_dates.empty
                else "Not recorded"
            )
            count = zones["records_received"].sum(min_count=1)
            records_processed = (
                f"{int(count):,}" if pd.notna(count) else "Not recorded"
            )

        status_columns = st.columns(4)
        status_columns[0].metric("MySQL", database_status)
        status_columns[1].metric("Latest observation", latest_observation)
        status_columns[2].metric("Spark batch processed", processed_at)
        status_columns[3].metric("Records in latest summary", records_processed)
        st.caption(
            f"Source: {source} · Dashboard refreshed: "
            f"{dashboard_time.strftime('%d %b %Y, %H:%M:%S IST')} · "
            "Kafka/Spark process runtime is not monitored by this dashboard."
        )


def render_overview(
    zones, db_error, source, dashboard_time, weather, weather_error, air, air_error
):
    st.title("Pune Environmental Overview")
    st.markdown(
        '<p class="gp-subtitle">Explore environmental conditions, identify '
        "potential hotspots, and understand where targeted interventions may help.</p>",
        unsafe_allow_html=True,
    )

    if db_error:
        st.error(f"MySQL data is unavailable: {db_error}")
        st.info(
            "Check that MySQL is running, local credentials are configured in "
            "environment variables or .streamlit/secrets.toml, and the "
            "greenpulse_pune.zone_environment_summary table exists."
        )
    elif zones.empty:
        st.warning(
            "MySQL is reachable, but the latest batch has no zone summaries yet. "
            "No KPI values are shown until valid records are available."
        )

    valid_zones = zones.dropna(
        subset=["mean_lst_c", "mean_ndvi"], how="all"
    ) if not zones.empty else zones
    mean_lst = zones["mean_lst_c"].mean() if not zones.empty else None
    mean_ndvi = zones["mean_ndvi"].mean() if not zones.empty else None
    hottest = (
        zones.dropna(subset=["mean_lst_c"]).sort_values(
            "mean_lst_c", ascending=False
        ).head(1)
        if not zones.empty else zones
    )

    with st.container(horizontal=True):
        st.metric(
            "Zones monitored",
            int(valid_zones["zone_id"].nunique())
            if not valid_zones.empty and "zone_id" in valid_zones
            else "—",
            border=True,
        )
        st.metric("Mean land-surface temperature", val(mean_lst, 1, " °C"), border=True)
        st.metric(
            "Hottest monitored zone",
            str(hottest.iloc[0]["zone_name"]) if not hottest.empty else "—",
            val(hottest.iloc[0]["mean_lst_c"], 1, " °C")
            if not hottest.empty else None,
            border=True,
        )
        st.metric("Mean NDVI", val(mean_ndvi, 3), border=True)

    if not zones.empty:
        observations = zones["latest_observation_date"].dropna()
        if not observations.empty:
            latest_observation = pd.Timestamp(observations.max())
            now_local = datetime.now(PUNE_TIMEZONE).date()
            age_days = max(0, (now_local - latest_observation.date()).days)
            st.caption(
                f"Latest source observation: {latest_observation:%d %b %Y} "
                f"({age_days:,} days before today) · Values reflect the latest "
                "available database batch, not necessarily current conditions."
            )

    map_column, summary_column = st.columns([1.7, 1], gap="large")
    threshold = None
    if not zones.empty and not zones["mean_lst_c"].dropna().empty:
        temperatures = zones["mean_lst_c"].dropna()
        default_threshold = min(
            55.0, max(20.0, float(temperatures.quantile(0.75)))
        )
        threshold = st.slider(
            "Heat review threshold (°C)",
            min_value=20.0,
            max_value=55.0,
            value=default_threshold,
            step=0.5,
            key="overview_heat_threshold",
        )

    with map_column:
        st.subheader("Pune zone map")
        map_layer = st.segmented_control(
            "Map layer",
            ["Heat", "Vegetation", "Zone overview"],
            default="Heat",
            key="overview_map_layer",
        )
        render_city_map(zones, map_layer or "Heat", heat_threshold=threshold)

    with summary_column:
        st.subheader("Hottest monitored zones")
        if zones.empty or zones["mean_lst_c"].dropna().empty:
            st.info("A ranked hotspot view will appear when valid LST records are available.")
        else:
            ranked = zones.dropna(subset=["mean_lst_c"]).sort_values(
                "mean_lst_c", ascending=False
            ).head(8).copy()
            ranked["Review status"] = ranked["mean_lst_c"].apply(
                lambda temperature: classify_heat(temperature, threshold)
            )
            st.dataframe(
                ranked[
                    [
                        "zone_name",
                        "mean_lst_c",
                        "mean_ndvi",
                        "latest_observation_date",
                        "Review status",
                    ]
                ],
                width="stretch",
                hide_index=True,
                column_config={
                    "zone_name": st.column_config.TextColumn("Zone"),
                    "mean_lst_c": st.column_config.NumberColumn(
                        "LST (°C)", format="%.1f"
                    ),
                    "mean_ndvi": st.column_config.NumberColumn(
                        "NDVI", format="%.3f"
                    ),
                    "latest_observation_date": st.column_config.DateColumn(
                        "Observation date", format="DD MMM YYYY"
                    ),
                },
            )
            st.caption(
                "Review threshold is configurable and is not an official warning "
                "or government alert."
            )

    render_zone_explorer(zones, db_error)

    st.subheader("Current provider estimates")
    if weather_error:
        st.info(f"Open-Meteo weather is unavailable: {weather_error}")
    elif weather:
        st.badge(
            "Open-Meteo · current provider estimate",
            icon=":material/cloud:",
            color="blue",
        )
        weather_metrics = st.columns(4)
        weather_metrics[0].metric(
            "Air temperature", val(weather.get("temperature_2m"), 1, " °C")
        )
        weather_metrics[1].metric(
            "Feels like", val(weather.get("apparent_temperature"), 1, " °C")
        )
        weather_metrics[2].metric(
            "Relative humidity", val(weather.get("relative_humidity_2m"), 0, "%")
        )
        weather_metrics[3].metric(
            "Wind speed", val(weather.get("wind_speed_10m"), 1, " km/h")
        )
        st.caption(
            f"Open-Meteo forecast estimate · provider time "
            f"{weather.get('time', 'not provided')} · one approximate Pune "
            "grid point, not zone-level measurements."
        )

    if air_error:
        st.info(f"Open-Meteo air-quality data is unavailable: {air_error}")
    elif air:
        st.badge(
            "Open-Meteo · modelled air-quality estimate",
            icon=":material/air:",
            color="blue",
        )
        air_metrics = st.columns(4)
        air_metrics[0].metric("US AQI", val(air.get("us_aqi"), 0))
        air_metrics[1].metric("PM2.5", val(air.get("pm2_5"), 1, " µg/m³"))
        air_metrics[2].metric("PM10", val(air.get("pm10"), 1, " µg/m³"))
        air_metrics[3].metric(
            "Nitrogen dioxide",
            val(air.get("nitrogen_dioxide"), 1, " µg/m³"),
        )
        st.caption(
            f"Open-Meteo modelled air-quality estimate · provider time "
            f"{air.get('time', 'not provided')} · one approximate Pune grid "
            "point, not a ward-level reading."
        )

    render_pipeline_status(zones, db_error, source, dashboard_time)


def render_zone_explorer(zones, db_error):
    st.subheader("Zone explorer")
    st.caption(
        "Search and filter zones in the latest MySQL batch. Table columns can "
        "also be sorted from the column headers."
    )
    if db_error:
        st.info("Zone records are unavailable until the MySQL summary can be read.")
        return
    if zones.empty:
        st.info("No zone summaries are available in the latest database batch.")
        return

    temperatures = zones["mean_lst_c"].dropna()
    if temperatures.empty:
        default_threshold = 55.0
    else:
        default_threshold = min(
            55.0, max(20.0, float(temperatures.quantile(0.75)))
        )
    threshold = st.session_state.get(
        "overview_heat_threshold", default_threshold
    )
    filtered = zones.copy()
    filtered["Review status"] = filtered["mean_lst_c"].apply(
        lambda value: classify_heat(value, threshold)
    )

    search_column, severity_column, indicator_column = st.columns(
        [1.4, 1, 1.4]
    )
    with search_column:
        search = st.text_input(
            "Search zones",
            placeholder="Zone name or ID",
            key="overview_zone_search",
        ).strip().casefold()
    with severity_column:
        severity_options = filtered["Review status"].unique().tolist()
        selected_severities = st.multiselect(
            "Review status",
            severity_options,
            default=severity_options,
            key="overview_zone_severity",
        )
    with indicator_column:
        indicator_options = [
            label
            for label, column in (
                ("Mean LST", "mean_lst_c"),
                ("Mean NDVI", "mean_ndvi"),
                ("Records received", "records_received"),
                ("Observation date", "latest_observation_date"),
            )
            if column in filtered.columns
        ]
        selected_indicators = st.multiselect(
            "Displayed indicators",
            indicator_options,
            default=indicator_options,
            key="overview_zone_indicators",
        )

    filtered = filtered[filtered["Review status"].isin(selected_severities)]
    if search:
        matching = (
            filtered["zone_name"].fillna("").astype(str).str.casefold().str.contains(search)
            | filtered["zone_id"].fillna("").astype(str).str.casefold().str.contains(search)
        )
        filtered = filtered[matching]

    display_columns = ["zone_name", "zone_id", *[
        column
        for label, column in (
            ("Mean LST", "mean_lst_c"),
            ("Mean NDVI", "mean_ndvi"),
            ("Records received", "records_received"),
            ("Observation date", "latest_observation_date"),
        )
        if label in selected_indicators and column in filtered.columns
    ], "Review status"]
    table_config = {
        "zone_name": st.column_config.TextColumn("Zone"),
        "zone_id": st.column_config.TextColumn("Zone ID"),
        "mean_lst_c": st.column_config.NumberColumn("Mean LST (°C)", format="%.1f"),
        "mean_ndvi": st.column_config.NumberColumn("Mean NDVI", format="%.3f"),
        "records_received": st.column_config.NumberColumn(
            "Records received", format="%d"
        ),
        "latest_observation_date": st.column_config.DateColumn(
            "Latest observation", format="DD MMM YYYY"
        ),
        "Review status": st.column_config.TextColumn("Configured review status"),
    }
    if filtered.empty:
        st.info("No zones match the selected search and filters.")
    else:
        st.dataframe(
            filtered[display_columns],
            width="stretch",
            hide_index=True,
            column_config={
                column: table_config[column] for column in display_columns
            },
            alt="Searchable and filterable latest zone summaries",
        )

    zone_names = zones["zone_name"].dropna().astype(str).tolist()
    if not zone_names:
        st.info("No named zones are available for a detail view.")
        return
    selected_zone = st.selectbox(
        "Inspect a zone",
        zone_names,
        key="overview_selected_zone",
    )
    row = zones[zones["zone_name"].astype(str) == selected_zone].iloc[0]
    detail_metrics = st.columns(4)
    detail_metrics[0].metric("Zone ID", str(row["zone_id"]))
    detail_metrics[1].metric("Mean LST", val(row["mean_lst_c"], 2, " °C"))
    detail_metrics[2].metric("Mean NDVI", val(row["mean_ndvi"], 3))
    detail_metrics[3].metric(
        "Records in summary batch", val(row["records_received"], 0)
    )
    st.caption(
        f"Latest observation: {format_date(row['latest_observation_date'])} · "
        f"Processed: {format_date(row['processed_at'], '%d %b %Y %H:%M:%S')}"
    )
    st.info(
        "Historical zone trends are not available: the current MySQL table stores "
        "the latest summary batch, not a time series. Missing measurements are "
        "shown as unavailable rather than filled with invented values."
    )


def render_heat_page(zones, db_error):
    st.title("Heat hotspots")
    st.caption(
        "Rankings use the latest Spark-processed summary. Land-surface temperature "
        "is not the same as near-surface air temperature."
    )
    if db_error:
        st.error(f"Heat summaries are unavailable because MySQL could not be read: {db_error}")
        return
    if zones.empty or zones["mean_lst_c"].dropna().empty:
        st.info("No valid land-surface temperature summaries are available yet.")
        return

    temperatures = zones["mean_lst_c"].dropna()
    threshold = st.slider(
        "Review threshold (mean LST °C)",
        min_value=20.0,
        max_value=55.0,
        value=min(55.0, max(20.0, float(temperatures.quantile(0.75)))),
        step=0.5,
        key="heat_page_threshold",
    )
    ranked = zones.copy()
    ranked["Classification"] = ranked["mean_lst_c"].apply(
        lambda value: classify_heat(value, threshold)
    )
    st.caption(
        "Configured map bands: green = below the review band; amber = within "
        "3 °C below the threshold; red = at/above the selected threshold. This "
        "heuristic is not an official government heat warning."
    )
    st.subheader("Geographic view")
    render_city_map(ranked, "Heat", heat_threshold=threshold)
    st.caption(
        f"Review threshold: {threshold:.1f} °C. Amber covers the 3 °C below "
        "threshold band. Categories are review heuristics, not official alerts."
    )
    zone_names = ranked["zone_name"].dropna().astype(str).tolist()
    if zone_names:
        selected_zone = st.selectbox(
            "Inspect a hotspot zone",
            zone_names,
            key="heat_selected_zone",
        )
        selected_row = ranked[
            ranked["zone_name"].astype(str) == selected_zone
        ].iloc[0]
        detail = st.columns(4)
        detail[0].metric("Zone ID", str(selected_row["zone_id"]))
        detail[1].metric(
            "Mean land-surface temperature",
            val(selected_row["mean_lst_c"], 2, " °C"),
        )
        detail[2].metric("Mean NDVI", val(selected_row["mean_ndvi"], 3))
        detail[3].metric(
            "Review category", str(selected_row["Classification"])
        )
        st.caption(
            f"Observation date: {format_date(selected_row['latest_observation_date'])} · "
            "The current summary table does not retain historic per-zone readings, "
            "so no trend is available."
        )
    figure = px.bar(
        ranked.dropna(subset=["mean_lst_c"]).sort_values("mean_lst_c"),
        x="mean_lst_c",
        y="zone_name",
        orientation="h",
        color="Classification",
        color_discrete_map={
            "Review candidate": "#e16a5b",
            "Within 3 °C of threshold": HEAT_COLORS[1],
            "Below review band": HEAT_COLORS[0],
        },
        title="Zone ranking by surface temperature",
        labels={"mean_lst_c": "Mean LST (°C)", "zone_name": "Pune zone"},
    )
    st.plotly_chart(
        style_chart(figure, max(360, len(ranked) * 28)),
        width="stretch",
    )
    st.dataframe(
        ranked.sort_values("mean_lst_c", ascending=False),
        width="stretch",
        hide_index=True,
    )


def render_air_page():
    st.title("Air quality")
    st.caption(
        "Open-Meteo provider estimates for one approximate Pune grid point. "
        "These are modelled estimates, not ward-level or official monitoring-station readings."
    )
    weather = {}
    weather_error = None
    try:
        weather = load_current_weather()
    except requests.RequestException as error:
        weather_error = str(error)

    air = {}
    air_error = None
    try:
        air = load_current_air()
    except requests.RequestException as error:
        air_error = str(error)

    if weather:
        st.subheader("Current weather estimate")
        weather_columns = st.columns(4)
        weather_columns[0].metric(
            "Air temperature", val(weather.get("temperature_2m"), 1, " °C")
        )
        weather_columns[1].metric(
            "Feels like", val(weather.get("apparent_temperature"), 1, " °C")
        )
        weather_columns[2].metric(
            "Relative humidity", val(weather.get("relative_humidity_2m"), 0, "%")
        )
        weather_columns[3].metric(
            "Wind speed", val(weather.get("wind_speed_10m"), 1, " km/h")
        )
        st.caption(
            f"Open-Meteo Forecast API · provider timestamp: "
            f"{weather.get('time', 'not provided')} · point: "
            f"{PUNE_LAT:.4f}, {PUNE_LON:.4f} (approximate city reference)."
        )
    elif weather_error:
        st.info(f"Open-Meteo weather is unavailable: {weather_error}")

    if air:
        st.subheader("Air-quality provider estimates")
        air_columns = st.columns(5)
        air_columns[0].metric("US AQI", val(air.get("us_aqi"), 0))
        air_columns[1].metric("PM2.5", val(air.get("pm2_5"), 1, " µg/m³"))
        air_columns[2].metric("PM10", val(air.get("pm10"), 1, " µg/m³"))
        air_columns[3].metric(
            "Nitrogen dioxide", val(air.get("nitrogen_dioxide"), 1, " µg/m³")
        )
        air_columns[4].metric("Ozone", val(air.get("ozone"), 1, " µg/m³"))

        air_value_columns = {
            "US AQI": ("us_aqi", "US AQI"),
            "PM2.5 (µg/m³)": ("pm2_5", "PM2.5 (µg/m³)"),
            "PM10 (µg/m³)": ("pm10", "PM10 (µg/m³)"),
        }
        available_values = [
            label
            for label, (key, _) in air_value_columns.items()
            if air.get(key) is not None and pd.notna(air.get(key))
        ]
        if available_values:
            selected_measure = st.selectbox(
                "Map measurement",
                available_values,
                key="air_map_measurement",
            )
            data_key, color_label = air_value_columns[selected_measure]
            point = pd.DataFrame(
                [
                    {
                        "place": "Open-Meteo Pune grid estimate",
                        "latitude": PUNE_LAT,
                        "longitude": PUNE_LON,
                        "US AQI": air.get("us_aqi"),
                        "PM2.5 (µg/m³)": air.get("pm2_5"),
                        "PM10 (µg/m³)": air.get("pm10"),
                        "Provider timestamp": air.get("time", "Not provided"),
                    }
                ]
            )
            if data_key == "us_aqi":
                aqi = float(air[data_key])
                if aqi <= 50:
                    category = "Good (0–50)"
                elif aqi <= 100:
                    category = "Moderate (51–100)"
                elif aqi <= 150:
                    category = "Unhealthy for sensitive groups (101–150)"
                elif aqi <= 200:
                    category = "Unhealthy (151–200)"
                elif aqi <= 300:
                    category = "Very unhealthy (201–300)"
                else:
                    category = "Hazardous (301+)"
                point["US AQI category"] = category
                figure = px.scatter_map(
                    point,
                    lat="latitude",
                    lon="longitude",
                    color="US AQI category",
                    color_discrete_map=AQI_COLORS,
                    hover_name="place",
                    hover_data=[
                        "US AQI",
                        "US AQI category",
                        "PM2.5 (µg/m³)",
                        "PM10 (µg/m³)",
                        "Provider timestamp",
                    ],
                    zoom=10,
                    center={"lat": PUNE_LAT, "lon": PUNE_LON},
                    height=440,
                    map_style="open-street-map",
                )
            else:
                figure = px.scatter_map(
                    point,
                    lat="latitude",
                    lon="longitude",
                    color=color_label,
                    color_continuous_scale=HEAT_COLORS,
                    hover_name="place",
                    hover_data=[
                        "US AQI",
                        "PM2.5 (µg/m³)",
                        "PM10 (µg/m³)",
                        "Provider timestamp",
                    ],
                    zoom=10,
                    center={"lat": PUNE_LAT, "lon": PUNE_LON},
                    height=440,
                    map_style="open-street-map",
                )
                figure.update_coloraxes(colorbar_title=color_label)
            figure.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#dbe6f4"),
                margin=dict(l=0, r=0, t=8, b=0),
            )
            figure.update_traces(marker={"size": 18, "opacity": 0.95})
            st.subheader("Geographic coverage")
            st.plotly_chart(
                figure,
                width="stretch",
                config={"scrollZoom": True},
                alt="Single Open-Meteo air-quality estimate near central Pune",
            )
            st.dataframe(
                point.drop(columns=["latitude", "longitude"]),
                width="stretch",
                hide_index=True,
                alt="Available air-quality readings for one Pune grid point",
            )
            if data_key == "us_aqi":
                st.caption(
                    "US AQI category legend: " + " · ".join(AQI_COLORS)
                )
        else:
            st.info(
                "The provider returned no mappable AQI, PM2.5, or PM10 value. "
                "No map marker or substitute reading is shown."
            )
        st.caption(
            f"Open-Meteo Air Quality API · provider timestamp: "
            f"{air.get('time', 'not provided')} · one modelled grid point near "
            "central Pune, not citywide coverage."
        )
    else:
        st.warning(
            f"Air-quality data is unavailable: {air_error}"
            if air_error
            else "The air-quality API returned no current reading."
        )
        st.info("No map is displayed without an available provider reading.")

    st.info(
        "Zone-level air-quality hotspots require geolocated readings from "
        "monitoring stations or a validated multi-point provider dataset."
    )


def render_electricity_page(zones, db_error):
    st.title("Electricity hotspots")
    st.badge(
        "Simulated demonstration index",
        icon=":material/science:",
        color="orange",
    )
    st.warning(
        "No electricity-meter or utility-load dataset is connected. The index below "
        "is an existing illustrative demo derived from environmental indicators; it "
        "is not electricity consumption, an outage indicator, or a grid alert."
    )
    if db_error:
        st.error(f"Environmental inputs are unavailable because MySQL could not be read: {db_error}")
        return
    if zones.empty or zones["mean_lst_c"].dropna().empty or zones["mean_ndvi"].dropna().empty:
        st.info(
            "No valid environmental values are available to calculate the labelled "
            "demo index. No electricity measurements are connected."
        )
        return

    electricity = zones.copy()
    base_temperature = electricity["mean_lst_c"].fillna(
        electricity["mean_lst_c"].median()
    )
    vegetation = electricity["mean_ndvi"].fillna(
        electricity["mean_ndvi"].median()
    )
    electricity["Illustrative index"] = (
        55
        + (base_temperature - base_temperature.mean()) * 2.2
        - (vegetation - vegetation.mean()) * 18
    ).clip(0, 100).round(1)
    threshold = st.slider(
        "Illustrative index threshold",
        min_value=0,
        max_value=100,
        value=70,
        step=5,
    )
    electricity["Classification"] = electricity["Illustrative index"].apply(
        lambda value: (
            "Illustrative high index"
            if pd.notna(value) and value >= threshold
            else "Below demo threshold"
            if pd.notna(value)
            else "Missing source data"
        )
    )
    metrics = st.columns(4)
    metrics[0].metric("Zones shown", len(electricity))
    metrics[1].metric(
        "Demo high-index zones",
        int((electricity["Illustrative index"] >= threshold).sum()),
    )
    metrics[2].metric("Selected threshold", threshold)
    metrics[3].metric(
        "Mean illustrative index",
        val(electricity["Illustrative index"].mean(), 1),
    )
    st.subheader("Illustrative geographic view")
    render_city_map(electricity, "Electricity")
    st.caption(
        "Map legend: teal = below demo threshold; red = illustrative high index. "
        "Marker locations come from the bundled demo CSV and are not verified "
        "ward boundaries. No actual electricity readings are represented."
    )
    zone_names = electricity["zone_name"].dropna().astype(str).tolist()
    if zone_names:
        selected_zone = st.selectbox(
            "Inspect a zone",
            zone_names,
            key="electricity_selected_zone",
        )
        row = electricity[electricity["zone_name"].astype(str) == selected_zone].iloc[0]
        details = st.columns(3)
        details[0].metric("Zone ID", str(row["zone_id"]))
        details[1].metric(
            "Illustrative index", val(row["Illustrative index"], 1, " / 100")
        )
        details[2].metric("Demo category", str(row["Classification"]))
        st.caption(
            f"Environmental source observation date: "
            f"{format_date(row['latest_observation_date'])}. This is not an "
            "electricity observation date."
        )
    st.dataframe(
        electricity[
            [
                "zone_id",
                "zone_name",
                "Illustrative index",
                "Classification",
                "latest_observation_date",
            ]
        ].sort_values("Illustrative index", ascending=False),
        width="stretch",
        hide_index=True,
        column_config={
            "Illustrative index": st.column_config.NumberColumn(
                "Illustrative index (0–100)", format="%.1f"
            ),
            "latest_observation_date": st.column_config.DateColumn(
                "Environmental source date", format="DD MMM YYYY"
            ),
        },
        alt="Ranked illustrative index by zone, not measured electricity demand",
    )
    st.info(
        "Historical electricity trends are unavailable. Connect authorized, "
        "geolocated utility measurements before making electricity-hotspot claims."
    )
def probe_kafka_broker():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    host, separator, port_text = bootstrap_servers.rpartition(":")
    if not separator or not host:
        return "Unrecognized bootstrap address"
    try:
        with socket.create_connection((host, int(port_text)), timeout=0.5):
            return "TCP reachable"
    except (OSError, ValueError):
        return "Not reachable"


def render_data_page(zones, db_error, source, dashboard_time, coordinate_reference):
    st.title("Data & pipeline status")
    if db_error:
        st.error(f"MySQL connection/read failed: {db_error}")
        st.info(
            "Check MySQL availability, your local database credentials, and that "
            "the expected summary table exists."
        )
    render_pipeline_status(zones, db_error, source, dashboard_time)

    pipeline = st.columns(3)
    pipeline[0].metric(
        "Kafka broker TCP check",
        probe_kafka_broker(),
        help=(
            "Checks only whether a TCP connection can be opened. It does not "
            "verify Kafka protocol health or message production."
        ),
    )
    if db_error or zones.empty:
        pipeline[1].metric("Latest stored Spark batch", "Unavailable")
    else:
        batch_ids = zones["batch_id"].dropna()
        pipeline[1].metric(
            "Latest stored Spark batch",
            val(batch_ids.max(), 0) if not batch_ids.empty else "Not recorded",
        )
    pipeline[2].metric(
        "Spark process health",
        "Not monitored",
        help="A saved MySQL batch does not prove the Spark process is currently running.",
    )

    if zones.empty:
        matched_coordinates = 0
    else:
        matched_coordinates = int(zones["map_lat"].notna().sum())
    unmatched_zones = max(0, len(zones) - matched_coordinates)
    database_zone_ids = (
        set(zones["zone_id"].dropna().astype(str))
        if "zone_id" in zones
        else set()
    )
    coordinate_zone_ids = (
        set(coordinate_reference["zone_id"].dropna().astype(str))
        if "zone_id" in coordinate_reference
        else set()
    )
    unmatched_coordinate_rows = len(coordinate_zone_ids - database_zone_ids)
    geographic = st.columns(4)
    geographic[0].metric("Zones in latest batch", len(zones))
    geographic[1].metric("Zones with joined coordinates", matched_coordinates)
    geographic[2].metric("Zones without coordinates", unmatched_zones)
    geographic[3].metric(
        "Coordinate IDs not in latest batch", unmatched_coordinate_rows
    )
    st.caption(
        "Coordinates are matched to zone IDs from the bundled demonstration CSV. "
        "They are labelled synthetic and do not represent verified ward boundaries."
    )

    st.subheader("Latest database summary")
    if not zones.empty:
        st.dataframe(
            zones,
            width="stretch",
            hide_index=True,
            alt="Latest zone environment summaries from MySQL",
        )
    elif not db_error:
        st.info("The summary table is connected but currently contains no latest-batch rows.")
    st.subheader("What the dashboard can verify")
    st.markdown(
        "- Environmental summaries are read from "
        "`greenpulse_pune.zone_environment_summary`.\n"
        "- The database summary schema does not store coordinates or source "
        "provenance; map points and source labels are joined from the bundled CSV "
        "when matching zone IDs are available.\n"
        "- The bundled CSV labels its values `SYNTHETIC_DEMO_NOT_REAL`.\n"
        "- Dashboard refresh time, observation date, and database processing time "
        "are distinct.\n"
        "- The optional ML history sink writes to a separate table and checkpoint; "
        "its page reports when real training history is insufficient.\n"
        "- Kafka is checked only for TCP reachability; Kafka protocol, topic "
        "production, and Spark process health are not monitored."
    )


with st.sidebar:
    st.markdown("## :material/eco: GreenPulse Pune")
    st.caption("ENVIRONMENTAL INTELLIGENCE · PUNE, INDIA")
    st.radio(
        "Workspace",
        PAGES,
        label_visibility="collapsed",
        key="selected_page",
    )
    st.markdown("---")
    auto_refresh = st.toggle("Refresh dashboard automatically", value=True)
    refresh_seconds = st.selectbox(
        "Dashboard refresh interval",
        [30, 60, 120, 300],
        index=1,
        format_func=lambda seconds: f"{seconds} seconds",
        disabled=not auto_refresh,
    )
    st.caption("Refresh updates the dashboard view; it does not start Kafka or Spark.")

if auto_refresh:
    st_autorefresh(
        interval=refresh_seconds * 1000,
        key="greenpulse_dashboard_refresh",
    )

page_header, time_header, refresh_header = st.columns([2.2, 1.2, 0.8])
with page_header:
    st.markdown(":material/eco: **GreenPulse Pune**")
    st.markdown(
        '<div class="gp-subtitle">Environmental Intelligence for a Cooler, '
        "Healthier, More Sustainable Pune.</div>",
        unsafe_allow_html=True,
    )
with time_header:
    st.caption("DASHBOARD TIME · ASIA/KOLKATA")
    dashboard_time = datetime.now(PUNE_TIMEZONE)
    st.markdown(f"**{dashboard_time.strftime('%d %b %Y · %H:%M:%S IST')}**")
with refresh_header:
    if st.button(
        "Refresh now",
        icon=":material/refresh:",
        width="stretch",
    ):
        load_spark_data.clear()
        load_coordinate_reference.clear()
        load_current_weather.clear()
        load_current_air.clear()
        st.rerun()

try:
    zones = load_spark_data()
    database_error = None
except (mysql.connector.Error, RuntimeError, ValueError) as error:
    zones = pd.DataFrame()
    database_error = str(error)

try:
    coordinate_reference = load_coordinate_reference()
    coordinate_error = None
except (OSError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
    coordinate_reference = pd.DataFrame(
        columns=["zone_id", "map_lat", "map_lon", "map_source"]
    )
    coordinate_error = str(error)

zones = attach_map_coordinates(zones, coordinate_reference)
source = source_label(coordinate_reference)
st.badge(
    source,
    icon=":material/history:",
    color="orange" if "synthetic" in source.lower() else "blue",
)
if coordinate_error:
    st.warning(f"Coordinate reference could not be loaded: {coordinate_error}")

page = st.session_state["selected_page"]
if page == "Pune overview":
    weather = {}
    weather_error = None
    air = {}
    air_error = None
    try:
        weather = load_current_weather()
    except requests.RequestException as error:
        weather_error = str(error)
    try:
        air = load_current_air()
    except requests.RequestException as error:
        air_error = str(error)
    render_overview(
        zones,
        database_error,
        source,
        dashboard_time,
        weather,
        weather_error,
        air,
        air_error,
    )
elif page == "Heat hotspots":
    render_heat_page(zones, database_error)
elif page == "Air quality":
    render_air_page()
elif page == "Electricity hotspots":
    render_electricity_page(zones, database_error)
elif page == "ML predictions & recommendations":
    from ml.dashboard import render_ml_page

    render_ml_page()
elif page == "Data & pipeline status":
    render_data_page(
        zones, database_error, source, dashboard_time, coordinate_reference
    )

st.caption(
    "GreenPulse Pune · Environmental intelligence prototype · Not an official "
    "municipal alert system."
)
