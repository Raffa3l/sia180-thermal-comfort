"""
SIA 180:2014 Thermal Comfort Visualization

Plots room temperature against 48-hour rolling mean outdoor temperature
and overlays the comfort zone boundaries defined in the Swiss standard SIA 180:2014.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path


# ── Season helper ─────────────────────────────────────────────────────────────

def get_season(month: int) -> str:
    if month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    elif month in (9, 10, 11):
        return "Fall"
    return "Winter"


# ── CSV parsers ───────────────────────────────────────────────────────────────

def parse_room_temp_csv(filepath) -> pd.DataFrame:
    """Parse Logger CSV (semicolon-separated with *DATA section header).

    Expected column order after *DATA: TIME ; RH ; T
    Returns DataFrame with columns [time, temp_room].
    """
    filepath = Path(filepath)
    with open(filepath, "r", encoding="latin-1") as f:
        lines = f.readlines()

    data_start = None
    for i, line in enumerate(lines):
        if line.strip() == "*DATA":
            data_start = i + 1
            break
    if data_start is None:
        raise ValueError(f"No *DATA section found in {filepath}")

    df = pd.read_csv(
        filepath,
        skiprows=data_start,
        sep=";",
        header=None,
        names=["time", "RH", "temp_room"],
        encoding="latin-1",
    )
    df["time"] = pd.to_datetime(df["time"])
    df["temp_room"] = pd.to_numeric(df["temp_room"], errors="coerce")
    return df[["time", "temp_room"]]


def _parse_meteo_date(date_str: str) -> pd.Timestamp:
    """Parse METEO date format 'DD.DDMM.YY HH:MM' (e.g. '23.2301.26 00:00')."""
    s = str(date_str).strip('"').strip()
    date_part, time_part = s.split(" ")
    day   = date_part[0:2]
    month = date_part[5:7]
    year  = "20" + date_part[8:10]
    return pd.Timestamp(f"{year}-{month}-{day} {time_part}")


def parse_outdoor_temp_csv(filepath) -> pd.DataFrame:
    """Parse METEO export (semicolon-separated, 3-row header, quoted dates).

    Returns DataFrame with columns [time, temp_outdoor].
    """
    filepath = Path(filepath)
    df = pd.read_csv(
        filepath,
        skiprows=3,
        sep=";",
        header=None,
        names=["time", "temp_outdoor"],
        encoding="latin-1",
    )
    df["time"] = df["time"].apply(_parse_meteo_date)
    df["temp_outdoor"] = pd.to_numeric(df["temp_outdoor"], errors="coerce")
    return df[["time", "temp_outdoor"]]


# ── Data processing ───────────────────────────────────────────────────────────

def compute_comfort_data(df_room: pd.DataFrame, df_outdoor: pd.DataFrame) -> pd.DataFrame:
    """Aggregate both series to hourly means, apply 48-hour rolling average to
    outdoor temperature, merge, assign seasons.

    Parameters
    ----------
    df_room : DataFrame with columns [time, temp_room]
    df_outdoor : DataFrame with columns [time, temp_outdoor]

    Returns
    -------
    DataFrame with columns [time, temp_room, temp_oa_48h, season]
    """
    # ── room temperature: hourly mean ──────────────────────────────────────────
    df_room = df_room.copy()
    df_room["hour"] = df_room["time"].dt.floor("h")
    room_h = (
        df_room.groupby("hour")["temp_room"]
        .mean()
        .reset_index()
        .rename(columns={"hour": "time"})
    )

    # ── outdoor temperature: hourly mean + 48-hour rolling average ─────────────
    df_outdoor = df_outdoor.copy()
    df_outdoor["hour"] = df_outdoor["time"].dt.floor("h")
    oa_h = (
        df_outdoor.groupby("hour")["temp_outdoor"]
        .mean()
        .reset_index()
        .rename(columns={"hour": "time"})
    )

    # Fill gaps so rolling window is applied over a continuous time grid
    full_range = pd.date_range(oa_h["time"].min(), oa_h["time"].max(), freq="h")
    oa_h = pd.merge(pd.DataFrame({"time": full_range}), oa_h, on="time", how="left")
    oa_h["temp_oa_48h"] = oa_h["temp_outdoor"].rolling(48, min_periods=1).mean()
    oa_h = oa_h[["time", "temp_oa_48h"]].dropna()

    # ── merge and season assignment ────────────────────────────────────────────
    data = pd.merge(room_h, oa_h, on="time", how="inner").dropna()
    data["season"] = data["time"].dt.month.apply(get_season)
    data = data.sort_values("time").reset_index(drop=True)
    return data


# ── SIA 180 comfort boundaries ────────────────────────────────────────────────

def _comfort_lines(minx: float, maxx: float):
    """Return the three SIA 180:2014 boundary line DataFrames."""
    # Lower limit – heating setpoint
    df_heat = pd.DataFrame(
        {"tempOa": [minx, 19, 23.5, maxx], "tempR": [20.5, 20.5, 22.0, 22.0]}
    )
    # Upper limit – active cooling (SIA 180:2014 Fig. 4)
    df_cool_active = pd.DataFrame(
        {"tempOa": [minx, 12, 17.5, maxx], "tempR": [24.5, 24.5, 26.5, 26.5]}
    )
    # Upper limit – passive cooling (SIA 180:2014 Fig. 3)
    df_cool_passive = pd.DataFrame(
        {"tempOa": [minx, 10, maxx], "tempR": [25.0, 25.0, 0.33 * maxx + 21.8]}
    )
    return df_heat, df_cool_active, df_cool_passive


# ── Plotly chart ──────────────────────────────────────────────────────────────

SEASON_COLORS = {
    "Spring": "#2db27d",
    "Summer": "#febc2b",
    "Fall":   "#440154",
    "Winter": "#365c8d",
}


def plot_sia180(
    data: pd.DataFrame,
    title: str = "Thermal Comfort according to SIA 180:2014",
) -> go.Figure:
    """Create an interactive Plotly SIA 180:2014 comfort diagram.

    Parameters
    ----------
    data : output of compute_comfort_data()
    title : chart title

    Returns
    -------
    plotly.graph_objects.Figure
    """
    minx = int(np.floor(min(0.0,  data["temp_oa_48h"].min())))
    maxx = int(np.ceil( max(28.0, data["temp_oa_48h"].max())))
    miny = int(np.floor(min(21.0, data["temp_room"].min()))) - 1
    maxy = int(np.ceil( max(32.0, data["temp_room"].max()))) + 1

    df_heat, df_cool_active, df_cool_passive = _comfort_lines(minx, maxx)

    fig = go.Figure()

    # ── boundary lines ─────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df_cool_passive["tempOa"], y=df_cool_passive["tempR"],
        mode="lines", name="Upper limit SIA 180 passive cooling",
        line=dict(color="#FDE725", width=2), opacity=0.8,
        hovertemplate=(
            "Upper limit SIA 180 passive cooling<br>"
            "T_room: %{y:.1f} °C<br>T_outdoor: %{x:.1f} °C<extra></extra>"
        ),
    ))
    fig.add_trace(go.Scatter(
        x=df_cool_active["tempOa"], y=df_cool_active["tempR"],
        mode="lines", name="Upper limit SIA 180 active cooling",
        line=dict(color="#1E9B8A", width=2), opacity=0.8,
        hovertemplate=(
            "Upper limit SIA 180 active cooling<br>"
            "T_room: %{y:.1f} °C<br>T_outdoor: %{x:.1f} °C<extra></extra>"
        ),
    ))
    fig.add_trace(go.Scatter(
        x=df_heat["tempOa"], y=df_heat["tempR"],
        mode="lines", name="Lower limit SIA 180",
        line=dict(color="#440154", width=2), opacity=0.8,
        hovertemplate=(
            "Lower limit SIA 180<br>"
            "T_room: %{y:.1f} °C<br>T_outdoor: %{x:.1f} °C<extra></extra>"
        ),
    ))

    # ── seasonal scatter points ────────────────────────────────────────────────
    for season, color in SEASON_COLORS.items():
        subset = data[data["season"] == season]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset["temp_oa_48h"],
            y=subset["temp_room"],
            mode="markers",
            name=season,
            marker=dict(color=color, opacity=0.3, size=6),
            customdata=np.stack(
                [subset["time"].dt.strftime("%Y-%m-%d %H:%M"), subset["season"]], axis=1
            ),
            hovertemplate=(
                "T_room: %{y:.1f} °C<br>"
                "T_outdoor (48h avg): %{x:.1f} °C<br>"
                "Date: %{customdata[0]}<br>"
                "Season: %{customdata[1]}<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis=dict(
            title=dict(
                text="Moving average outdoor temperature over last 48 hours (°C)",
                font=dict(size=13, color="darkgrey"),
            ),
            range=[minx, maxx],
            zeroline=False,
            tick0=minx,
            dtick=2,
        ),
        yaxis=dict(
            title=dict(
                text="Room Temperature (°C)",
                font=dict(size=13, color="darkgrey"),
            ),
            range=[miny, maxy],
            dtick=1,
        ),
        hoverlabel=dict(align="left"),
        margin=dict(l=80, t=60, r=50, b=120),
        legend=dict(orientation="h", x=0.0, y=-0.25),
    )
    return fig
