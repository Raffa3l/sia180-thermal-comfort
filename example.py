"""
Example: SIA 180 Thermal Comfort – Klassenzimmer 2.OG

Loads the sample data, computes the 48-hour rolling outdoor temperature mean,
and generates an interactive HTML chart saved as example.html.
"""

from pathlib import Path
from sia180_thermal_comfort import (
    parse_room_temp_csv,
    parse_outdoor_temp_csv,
    compute_comfort_data,
    plot_sia180,
)

DATA_DIR = Path(__file__).parent / "data"

# ── Load data ──────────────────────────────────────────────────────────────────
df_room    = parse_room_temp_csv(DATA_DIR / "Klassenzimmer-2.OG.csv")
df_outdoor = parse_outdoor_temp_csv(DATA_DIR / "METEO-Aussentemperaturen.csv")

print(f"Room temperature:    {len(df_room):,} rows  "
      f"({df_room['time'].min().date()} – {df_room['time'].max().date()})")
print(f"Outdoor temperature: {len(df_outdoor):,} rows  "
      f"({df_outdoor['time'].min().date()} – {df_outdoor['time'].max().date()})")

# ── Process ────────────────────────────────────────────────────────────────────
data = compute_comfort_data(df_room, df_outdoor)
print(f"Merged data points:  {len(data):,}")
print(f"Seasons present:     {sorted(data['season'].unique())}")

# ── Plot ───────────────────────────────────────────────────────────────────────
fig = plot_sia180(
    data,
    title="Thermischer Komfort – Klassenzimmer 2.OG (SIA 180:2014)",
)

out_path = Path(__file__).parent / "example.html"
fig.write_html(str(out_path), include_plotlyjs="cdn")
print(f"\nSaved → {out_path}")

fig.show()
