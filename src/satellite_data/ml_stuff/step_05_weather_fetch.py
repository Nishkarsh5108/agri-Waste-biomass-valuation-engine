"""
Step 5: Fetch weather data from Open-Meteo for all sample points × 4 years.

Input:  data/sample_points.csv  (829 points with lat/lon)
Output: data/processed/weather_daily.csv

Per implementation plan §2.3 and §4.4:
  Variables: t_max, t_min, precipitation, ET0, solar radiation, wind speed

Uses Open-Meteo Historical Weather API (free, no key required).
Rate-limited to avoid hammering the server.
"""
import pandas as pd
import numpy as np
import requests
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DATA_DIR, PROCESSED_DIR, YEARS,
    SEASON_START_MMDD, SEASON_END_MMDD,
    WEATHER_VARIABLES,
)

# Open-Meteo API endpoint
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Column rename mapping (Open-Meteo names -> our internal names)
RENAME_MAP = {
    "temperature_2m_max": "t_max",
    "temperature_2m_min": "t_min",
    "precipitation_sum": "precip_mm",
    "et0_fao_evapotranspiration": "et0_mm",
    "shortwave_radiation_sum": "solar_rad",
    "wind_speed_10m_max": "wind_speed",
}


def fetch_weather_for_point(lat: float, lon: float, point_id: int,
                            start_date: str, end_date: str,
                            max_retries: int = 3) -> pd.DataFrame:
    """
    Fetch daily weather data for a single point from Open-Meteo Archive API.
    """
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(WEATHER_VARIABLES),
        "timezone": "Asia/Kolkata",
    }

    for attempt in range(max_retries):
        try:
            resp = requests.get(ARCHIVE_URL, params=params, timeout=30)
            if resp.status_code == 429:
                # Rate limited — wait and retry
                wait = 2 ** (attempt + 1)
                print(f"    Rate limited for point {point_id}, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()

            if "daily" not in data:
                print(f"    WARNING: No daily data for point {point_id}")
                return pd.DataFrame()

            daily = data["daily"]
            df = pd.DataFrame(daily)
            df["date"] = pd.to_datetime(df["time"])
            df.drop(columns=["time"], inplace=True)
            df["point_id"] = point_id
            df["lat"] = lat
            df["lon"] = lon

            # Rename columns
            df.rename(columns=RENAME_MAP, inplace=True)

            return df

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"    Error for point {point_id}: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"    FAILED: point {point_id} after {max_retries} attempts: {e}")
                return pd.DataFrame()

    return pd.DataFrame()


def run():
    """Main execution: fetch weather for all points across all years."""
    print("=" * 70)
    print("STEP 5: Fetch Open-Meteo Weather Data")
    print("=" * 70)

    # Check if already exists (resume support)
    out_path = PROCESSED_DIR / "weather_daily.csv"
    if out_path.exists():
        existing = pd.read_csv(out_path)
        print(f"Found existing weather data: {len(existing)} rows")
        print(f"  Points: {existing['point_id'].nunique()}")
        user_input = input("  Re-fetch? (y/N): ").strip().lower()
        if user_input != "y":
            print("  Skipping weather fetch (using existing data)")
            return existing

    # Load sample points
    points = pd.read_csv(DATA_DIR / "sample_points.csv")
    print(f"Sample points: {len(points)}")

    # Date range across all years
    start_date = f"{min(YEARS)}-{SEASON_START_MMDD}"
    end_date = f"{max(YEARS)}-{SEASON_END_MMDD}"
    print(f"Date range: {start_date} -> {end_date}")

    # Group points by approximate location to batch requests
    # Open-Meteo has generous limits, but we'll throttle to be safe
    all_weather = []
    n_points = len(points)

    for i, row in points.iterrows():
        pid = row["point_id"]
        lat = row["lat"]
        lon = row["lon"]

        df = fetch_weather_for_point(lat, lon, pid, start_date, end_date)
        if len(df) > 0:
            all_weather.append(df)

        if (i + 1) % 50 == 0 or (i + 1) == n_points:
            print(f"  Fetched {i + 1} / {n_points} points "
                  f"({len(all_weather)} successful)")

        # Throttle: 100ms between requests
        time.sleep(0.1)

    if not all_weather:
        print("ERROR: No weather data fetched!")
        return pd.DataFrame()

    combined = pd.concat(all_weather, ignore_index=True)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"WEATHER DATA SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total rows: {len(combined)}")
    print(f"Points:     {combined['point_id'].nunique()}")
    print(f"Date range: {combined['date'].min().date()} to {combined['date'].max().date()}")
    print(f"\nNaN summary:")
    for col in RENAME_MAP.values():
        if col in combined.columns:
            nan_pct = combined[col].isna().mean() * 100
            print(f"  {col:>15s}: {nan_pct:.1f}% NaN")

    combined.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path.name}")

    return combined


if __name__ == "__main__":
    run()
