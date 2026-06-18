"""
Step 1: Load raw satellite CSVs, validate, merge S1 + S2, and clean.

Input:  data/sattelite_raw/sentinel{1,2}_raw_{year}.csv + static_layers.csv
Output: data/processed/merged_raw_{year}.csv (one file per year)
        data/processed/static_features.csv
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Allow importing config from same directory
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    RAW_DIR, PROCESSED_DIR, DATA_DIR,
    YEARS, S2_BANDS, S1_BANDS,
)


def load_sentinel2(year: int) -> pd.DataFrame:
    """Load and clean a single year of Sentinel-2 data."""
    path = RAW_DIR / f"sentinel2_raw_{year}.csv"
    print(f"  Loading S2 {year} from {path.name}...")
    df = pd.read_csv(path)

    # Validate expected columns exist
    missing = [b for b in S2_BANDS if b not in df.columns]
    if missing:
        raise ValueError(f"S2 {year}: Missing bands {missing}. Columns: {list(df.columns)}")

    # Keep only needed columns
    keep_cols = ["point_id", "date"] + S2_BANDS + ["lat", "lon"]
    df = df[keep_cols].copy()

    # Parse date
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = year

    # Convert DN to reflectance (Sentinel-2 L2A scale factor = 10000)
    for band in S2_BANDS:
        df[band] = df[band].astype(np.float32) / 10000.0

    # Sanity check: reflectance should be [0, 1] with some tolerance
    for band in S2_BANDS:
        outlier_mask = (df[band] < 0) | (df[band] > 1.5)
        n_outliers = outlier_mask.sum()
        if n_outliers > 0:
            print(f"    WARNING: {n_outliers} outlier values in {band} (setting to NaN)")
            df.loc[outlier_mask, band] = np.nan

    print(f"    -> {len(df)} rows, {df['point_id'].nunique()} points, "
          f"date range: {df['date'].min().date()} to {df['date'].max().date()}")
    return df


def load_sentinel1(year: int) -> pd.DataFrame:
    """Load and clean a single year of Sentinel-1 data."""
    path = RAW_DIR / f"sentinel1_raw_{year}.csv"
    print(f"  Loading S1 {year} from {path.name}...")
    df = pd.read_csv(path)

    # Validate
    missing = [b for b in S1_BANDS if b not in df.columns]
    if missing:
        raise ValueError(f"S1 {year}: Missing bands {missing}. Columns: {list(df.columns)}")

    keep_cols = ["point_id", "date"] + S1_BANDS + ["lat", "lon"]
    df = df[keep_cols].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = year

    # VH and VV are in dB (typically -30 to 0 range)
    for band in S1_BANDS:
        df[band] = df[band].astype(np.float32)

    # Sanity check: SAR values typically in [-35, 5] dB range
    for band in S1_BANDS:
        outlier_mask = (df[band] < -40) | (df[band] > 10)
        n_outliers = outlier_mask.sum()
        if n_outliers > 0:
            print(f"    WARNING: {n_outliers} outlier values in {band} (setting to NaN)")
            df.loc[outlier_mask, band] = np.nan

    print(f"    -> {len(df)} rows, {df['point_id'].nunique()} points, "
          f"date range: {df['date'].min().date()} to {df['date'].max().date()}")
    return df


def load_static_layers() -> pd.DataFrame:
    """Load static geographic/terrain features."""
    path = RAW_DIR / "static_layers.csv"
    print(f"  Loading static layers from {path.name}...")
    df = pd.read_csv(path)

    keep_cols = ["point_id", "elevation_m", "slope_deg", "aspect_deg",
                 "worldcover_class", "lat", "lon"]
    df = df[keep_cols].copy()

    # Worldcover class 40 = cropland (ESA WorldCover)
    df["is_cropland"] = (df["worldcover_class"] == 40).astype(np.int8)

    print(f"    -> {len(df)} points, {df['is_cropland'].sum()} classified as cropland")
    return df


def load_sample_points() -> pd.DataFrame:
    """Load the sample points CSV."""
    path = DATA_DIR / "sample_points.csv"
    df = pd.read_csv(path)
    print(f"  Sample points: {len(df)} points")
    return df


def merge_s1_s2_for_year(s2_df: pd.DataFrame, s1_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge S1 and S2 data for a single year.

    Strategy: Create a unified timeline. S1 and S2 have different revisit
    schedules (5-day S2, 12-day S1), so we perform an outer merge on
    (point_id, date). This gives us NaN for S1 bands on S2-only dates and
    vice versa. The temporal interpolation step (step_03) will handle gap-filling.
    """
    # Ensure no duplicate (point_id, date) in either dataset
    # S2 can have duplicates if overlapping tiles — take mean
    s2_agg = s2_df.groupby(["point_id", "date", "year"]).agg(
        {**{b: "mean" for b in S2_BANDS}, "lat": "first", "lon": "first"}
    ).reset_index()

    s1_agg = s1_df.groupby(["point_id", "date", "year"]).agg(
        {**{b: "mean" for b in S1_BANDS}, "lat": "first", "lon": "first"}
    ).reset_index()

    # Outer merge
    merged = pd.merge(
        s2_agg, s1_agg,
        on=["point_id", "date", "year"],
        how="outer",
        suffixes=("", "_s1"),
    )

    # Consolidate lat/lon (prefer S2, fall back to S1)
    merged["lat"] = merged["lat"].fillna(merged.get("lat_s1"))
    merged["lon"] = merged["lon"].fillna(merged.get("lon_s1"))
    merged.drop(columns=["lat_s1", "lon_s1"], errors="ignore", inplace=True)

    merged.sort_values(["point_id", "date"], inplace=True)
    merged.reset_index(drop=True, inplace=True)

    return merged


def run():
    """Main execution: load, validate, merge, and save."""
    print("=" * 70)
    print("STEP 1: Load & Clean Raw Satellite Data")
    print("=" * 70)

    # Load static layers (one-time)
    static = load_static_layers()
    static_path = PROCESSED_DIR / "static_features.csv"
    static.to_csv(static_path, index=False)
    print(f"  Saved static features -> {static_path.name}")

    # Load and merge per year
    all_merged = []
    for year in YEARS:
        print(f"\n--- Year {year} ---")
        s2 = load_sentinel2(year)
        s1 = load_sentinel1(year)
        merged = merge_s1_s2_for_year(s2, s1)
        print(f"  Merged: {len(merged)} rows, {merged['point_id'].nunique()} points")

        # Save per-year parquet
        out_path = PROCESSED_DIR / f"merged_raw_{year}.csv"
        merged.to_csv(out_path, index=False)
        print(f"  Saved -> {out_path.name}")
        all_merged.append(merged)

    # Also save a combined file for convenience
    combined = pd.concat(all_merged, ignore_index=True)
    combined_path = PROCESSED_DIR / "merged_raw_all_years.csv"
    combined.to_csv(combined_path, index=False)
    print(f"\n{'=' * 70}")
    print(f"Combined all years: {len(combined)} rows, {combined['point_id'].nunique()} unique points")
    print(f"Saved -> {combined_path.name}")

    # Summary statistics
    print(f"\nNaN summary (combined):")
    nan_pct = combined[S2_BANDS + S1_BANDS].isnull().mean() * 100
    for col, pct in nan_pct.items():
        print(f"  {col}: {pct:.1f}% NaN")

    return combined


if __name__ == "__main__":
    run()
