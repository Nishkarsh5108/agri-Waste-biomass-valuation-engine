"""
Step 5: Fetch weather data from Open-Meteo for all sample points × years.

Input:  data/sample_points.csv  (829 points with lat/lon)
Output: data/processed/weather_daily.csv

Per implementation plan §2.3 and §4.4:
  Variables: t_max, t_min, precipitation, ET0, solar radiation, wind speed

Uses Open-Meteo Historical Weather API (free, no key required).
Rate-limited to avoid hammering the server.

THIS RUN: Fetches weather data for all years defined in config.py.
          If the output file already exists, skips the download to save time.
"""
import pandas as pd
import numpy as np
import requests
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DATA_DIR, PROCESSED_DIR,
    SEASON_START_MMDD, SEASON_END_MMDD, YEARS,
)

# ─────────────────────────────────────────────────────────────────
# CONFIGURATION FOR THIS RUN
# ─────────────────────────────────────────────────────────────────

# Years to fetch are defined in config.py (YEARS)

# ─────────────────────────────────────────────────────────────────
# API + COLUMN DEFINITIONS (fixed from original — §2.3)
# ─────────────────────────────────────────────────────────────────

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Only variables that actually exist in the Open-Meteo daily archive API.
# (The original WEATHER_VARIABLES from config may include names that the
#  API doesn't recognise, which caused 400 errors. This safe list is the fix.)
SAFE_WEATHER_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "et0_fao_evapotranspiration",
    "shortwave_radiation_sum",
    "wind_speed_10m_max",
]

# Open-Meteo names → internal column names
RENAME_MAP = {
    "temperature_2m_max":        "t_max",
    "temperature_2m_min":        "t_min",
    "precipitation_sum":         "precip_mm",
    "et0_fao_evapotranspiration":"et0_mm",
    "shortwave_radiation_sum":   "solar_rad",
    "wind_speed_10m_max":        "wind_speed",
}

# Full set of columns Step 6 expects. Variables the API doesn't provide
# are injected as NaN so downstream code never sees a missing column.
EXPECTED_COLS = [
    "t_max", "t_min", "precip_mm", "et0_mm",
    "humidity_pct", "solar_rad", "wind_speed",
    "soil_moist", "soil_temp",
]


# ─────────────────────────────────────────────────────────────────
# FETCH FUNCTION
# ─────────────────────────────────────────────────────────────────

def fetch_weather_for_point(
    lat: float, lon: float, point_id: int,
    start_date: str, end_date: str,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Fetch daily weather data for a single point from Open-Meteo Archive API.

    Uses SAFE_WEATHER_VARIABLES (not the config list) to avoid 400 errors.
    Injects NaN columns for any EXPECTED_COLS not returned by the API so
    the DataFrame shape stays consistent for Step 6.
    """
    params = {
        "latitude":   round(lat, 4),
        "longitude":  round(lon, 4),
        "start_date": start_date,
        "end_date":   end_date,
        "daily":      ",".join(SAFE_WEATHER_VARIABLES),
        "timezone":   "Asia/Kolkata",
    }

    for attempt in range(max_retries):
        try:
            resp = requests.get(ARCHIVE_URL, params=params, timeout=30)

            if resp.status_code == 429:
                # Rate limited — back off silently and retry
                wait = 2 ** (attempt + 1)
                print(f"    Rate limited for point {point_id}, waiting {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            if "daily" not in data:
                print(f"    WARNING: No daily data for point {point_id}")
                return pd.DataFrame()

            df = pd.DataFrame(data["daily"])
            df["date"] = pd.to_datetime(df["time"])
            df.drop(columns=["time"], inplace=True)
            df["point_id"] = point_id
            df["lat"]      = lat
            df["lon"]      = lon

            df.rename(columns=RENAME_MAP, inplace=True)

            # Inject missing columns as NaN so Step 6 never sees a KeyError
            for col in EXPECTED_COLS:
                if col not in df.columns:
                    df[col] = np.nan

            return df

        except Exception as e:
            # Catch-all: network errors, JSON decode errors, etc.
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"    Error for point {point_id}: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"    FAILED: point {point_id} after {max_retries} attempts: {e}")
                return pd.DataFrame()

    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def run():
    """
    Fetch weather for all sample points for all years.
    If weather_daily.csv already exists, it skips the download.
    """
    print("=" * 70)
    print("STEP 5: Fetch Open-Meteo Weather Data")
    print("=" * 70)

    out_path = PROCESSED_DIR / "weather_daily.csv"

    if out_path.exists():
        existing = pd.read_csv(out_path, parse_dates=["date"])
        print(f"Found existing weather data: {len(existing)} rows")
        print(f"  Points: {existing['point_id'].nunique()}")
        print("  Skipping weather fetch (using existing data)")
        return existing

    # Load sample points
    points = pd.read_csv(DATA_DIR / "sample_points.csv")
    print(f"Sample points: {len(points)}")

    # Date range for the new fetch
    start_date = f"{min(YEARS)}-{SEASON_START_MMDD}"
    end_date   = f"{max(YEARS)}-{SEASON_END_MMDD}"
    print(f"Fetching date range: {start_date} → {end_date}")
    print()

    # ── Fetch loop ────────────────────────────────────────────────
    all_weather = []
    n_points    = len(points)

    for i, row in points.iterrows():
        pid = row["point_id"]
        lat = row["lat"]
        lon = row["lon"]

        df = fetch_weather_for_point(lat, lon, pid, start_date, end_date)
        if not df.empty:
            all_weather.append(df)

        if (i + 1) % 50 == 0 or (i + 1) == n_points:
            print(f"  Fetched {i + 1} / {n_points} points "
                  f"({len(all_weather)} successful)")

        # Throttle: 100 ms between requests to avoid rate limits
        time.sleep(0.1)

    if not all_weather:
        print("ERROR: No weather data fetched!")
        return pd.DataFrame()

    new_df = pd.concat(all_weather, ignore_index=True)
    new_df["date"] = pd.to_datetime(new_df["date"])

    # ─────────────────────────────────────────────────────────────────
    # IDIOT-PROOF EMERGENCY SAVE (Because you leave Excel open)
    # ─────────────────────────────────────────────────────────────────
    emergency_path = PROCESSED_DIR / "weather_emergency_dump.csv"
    try:
        new_df.to_csv(emergency_path, index=False)
        print(f"\n[CRITICAL SUCCESS] Emergency backup safely written to -> {emergency_path.name}")
        print("Even if the script crashes after this line, YOUR DATA IS SAFE.")
    except Exception as e:
        print(f"\n[FATAL] Bro you even have the emergency file open?? Close it! Error: {e}")

    combined = new_df.sort_values(["point_id", "date"]).reset_index(drop=True)

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'=' * 50}")
    print(f"WEATHER DATA SUMMARY (combined)")
    print(f"{'=' * 50}")
    print(f"Total rows : {len(combined):,}")
    print(f"Points     : {combined['point_id'].nunique()}")
    print(f"Date range : {combined['date'].min().date()} → {combined['date'].max().date()}")
    print(f"\nNaN summary (new 2017-2021 rows only):")
    for col in EXPECTED_COLS:
        if col in new_df.columns:
            nan_pct = new_df[col].isna().mean() * 100
            print(f"  {col:>15s}: {nan_pct:.1f}% NaN")

    combined.to_csv(out_path, index=False)
    print(f"\nSaved → {out_path.name}  ({len(combined):,} rows total)")

    return combined


if __name__ == "__main__":
    run()