"""
Step 8: Assemble the final training DataFrame.

Input:  data/processed/features_all.csv
        data/processed/pseudo_labels.csv
        data/processed/variety_clusters.csv
        data/processed/static_features.csv
        data/INDIA_DISTRICTS.geojson
Output: data/processed/training_data.csv

Merges all features + static layers + pseudo-labels + variety clusters.
Assigns target variable (days_to_harvest).
Adds district_code via spatial join with district boundaries.
Performs final causality audit.
"""
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DATA_DIR, PROCESSED_DIR,
    TRAIN_YEARS, VAL_YEARS, TEST_YEARS,
)


def assign_district_codes(df: pd.DataFrame, geojson_path: Path) -> pd.DataFrame:
    """
    Assign district_code to each point via point-in-polygon lookup.
    Uses a simplified approach without geopandas dependency.
    """
    print("  Assigning district codes...")

    # Try to use geopandas if available
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        districts = gpd.read_file(str(geojson_path))
        # Create geodataframe from points
        unique_points = df[["point_id", "lat", "lon"]].drop_duplicates("point_id")
        geometry = [Point(lon, lat) for lat, lon in
                    zip(unique_points["lat"], unique_points["lon"])]
        points_gdf = gpd.GeoDataFrame(unique_points, geometry=geometry, crs="EPSG:4326")

        # Spatial join
        joined = gpd.sjoin(points_gdf, districts, how="left", predicate="within")

        # Use district name or ID column
        district_col = None
        for candidate in ["dtname", "DISTRICT", "NAME_2", "district", "name"]:
            if candidate in joined.columns:
                district_col = candidate
                break

        if district_col:
            point_district = joined[["point_id", district_col]].rename(
                columns={district_col: "district_code"})
            df = df.merge(point_district, on="point_id", how="left")
            n_assigned = df["district_code"].notna().sum()
            print(f"    Assigned district to {n_assigned}/{len(df)} rows (geopandas)")
        else:
            print(f"    WARNING: No district name column found in GeoJSON. "
                  f"Available: {list(districts.columns)}")
            df["district_code"] = "unknown"

    except ImportError:
        print("    geopandas not available — using lat-based approximate zoning")
        # Fallback: simple lat/lon based agro-zoning
        # Punjab: ~29.5–32.5°N, Haryana: ~27.5–30.5°N, UP: ~26–28°N
        conditions = [
            (df["lat"] > 31.5),                          # Northern Punjab
            (df["lat"] > 30.0) & (df["lat"] <= 31.5),   # Southern Punjab
            (df["lat"] > 28.5) & (df["lat"] <= 30.0),   # Haryana
            (df["lat"] <= 28.5),                          # UP / other
        ]
        choices = ["punjab_north", "punjab_south", "haryana", "up_west"]
        df["district_code"] = np.select(conditions, choices, default="other")

    return df


def assign_agro_zone(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign agro-ecological zone based on location and elevation.
    Simplified approach using lat/lon and elevation.
    """
    conditions = [
        (df["elevation_m"] > 500),                                    # Sub-montane
        (df["elevation_m"] <= 500) & (df["lat"] > 31.0),            # Trans-Gangetic Plains North
        (df["elevation_m"] <= 500) & (df["lat"] > 29.0) & (df["lat"] <= 31.0),  # Upper Gangetic
        (df["elevation_m"] <= 500) & (df["lat"] <= 29.0),           # Middle Gangetic
    ]
    choices = ["sub_montane", "trans_gangetic_north", "upper_gangetic", "middle_gangetic"]
    df["agro_zone"] = np.select(conditions, choices, default="other")
    return df


def run():
    """Main execution: assemble the final training DataFrame."""
    print("=" * 70)
    print("STEP 8: Assemble Final Training DataFrame")
    print("=" * 70)

    # Load all components
    features = pd.read_csv(PROCESSED_DIR / "features_all.csv")
    features["date"] = pd.to_datetime(features["date"])
    print(f"Features: {len(features)} rows, {len(features.columns)} columns")

    labels = pd.read_csv(PROCESSED_DIR / "pseudo_labels.csv")
    print(f"Labels: {len(labels)} point-years")

    clusters = pd.read_csv(PROCESSED_DIR / "variety_clusters.csv")
    print(f"Clusters: {len(clusters)} point-years")

    static = pd.read_csv(PROCESSED_DIR / "static_features.csv")
    print(f"Static: {len(static)} points")

    # -- Merge pseudo-labels --
    df = features.merge(
        labels[["point_id", "year", "harvest_doy", "harvest_date",
                "label_confidence", "ndvi_harvest_doy", "sar_harvest_doy"]],
        on=["point_id", "year"],
        how="left"
    )
    print(f"\nAfter label merge: {len(df)} rows")
    print(f"  Labeled:   {df['harvest_doy'].notna().sum()} rows "
          f"({df['harvest_doy'].notna().mean()*100:.1f}%)")

    # -- Merge variety clusters --
    df = df.merge(clusters, on=["point_id", "year"], how="left")
    df["variety_cluster"] = df["variety_cluster"].fillna(0).astype(np.int8)

    # -- Merge static features --
    static_merge_cols = ["point_id", "elevation_m", "slope_deg", "aspect_deg",
                         "worldcover_class", "is_cropland"]
    df = df.merge(static[static_merge_cols], on="point_id", how="left")

    # -- Assign district codes --
    geojson_path = DATA_DIR / "INDIA_DISTRICTS.geojson"
    if geojson_path.exists():
        df = assign_district_codes(df, geojson_path)
    else:
        print("  WARNING: District GeoJSON not found, using lat-based zoning")
        df["district_code"] = "unknown"

    # -- Assign agro zone --
    df = assign_agro_zone(df)

    # -- Compute target variable: days_to_harvest --
    # For each row, days_to_harvest = harvest_doy - current_doy
    df["days_to_harvest"] = df["harvest_doy"] - df["doy"]

    # -- Drop calendar columns to prevent the "lazy calendar" target leak --
    cols_to_drop = ["doy", "week", "month"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    # Only keep rows where we can compute a valid target
    # AND where days_to_harvest > 0 (before harvest only)
    valid_mask = (df["days_to_harvest"].notna()) & (df["days_to_harvest"] > 0)
    print(f"\nRows with valid target (days_to_harvest > 0): "
          f"{valid_mask.sum()} / {len(df)}")

    # -- Assign train/val/test splits --
    df["split"] = "unused"
    df.loc[df["year"].isin(TRAIN_YEARS), "split"] = "train"
    df.loc[df["year"].isin(VAL_YEARS), "split"] = "val"
    df.loc[df["year"].isin(TEST_YEARS), "split"] = "test"

    # -- Drop rows without labels (no harvest detected) --
    labeled = df[df["harvest_doy"].notna()].copy()
    print(f"\nFinal dataset (labeled only): {len(labeled)} rows")

    # -- Causality audit --
    print(f"\n{'=' * 50}")
    print(f"CAUSALITY AUDIT")
    print(f"{'=' * 50}")
    # Check that no feature column contains values that could only exist
    # with future knowledge. Verify key constraint:
    future_leak_cols = ["peak_ndvi", "days_since_peak", "amplitude",
                        "cumul_ndvi"]  # These should NOT exist
    for col in future_leak_cols:
        if col in labeled.columns:
            print(f"  [WARN] LEAK DETECTED: Column '{col}' should not exist!")
        else:
            print(f"  [OK] No '{col}' column (correctly absent)")

    causal_cols = ["rolling_max_ndvi_30d", "days_since_rolling_max_30d",
                   "cumul_ndvi_to_t", "rolling_amplitude_30d",
                   "ndvi_rate", "ndvi_accel"]
    for col in causal_cols:
        if col in labeled.columns:
            print(f"  [OK] Causal feature '{col}' present")
        else:
            print(f"  [WARN] Missing causal feature '{col}'")

    # -- Summary --
    print(f"\n{'=' * 50}")
    print(f"FINAL DATASET SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total rows:   {len(labeled)}")
    print(f"Total columns: {len(labeled.columns)}")
    print(f"\nSplit distribution:")
    print(labeled["split"].value_counts().to_string())
    print(f"\nLabel confidence distribution:")
    print(labeled["label_confidence"].value_counts().to_string())
    print(f"\nTarget (days_to_harvest) statistics:")
    valid_target = labeled[labeled["days_to_harvest"] > 0]["days_to_harvest"]
    if len(valid_target) > 0:
        print(f"  Mean:   {valid_target.mean():.1f} days")
        print(f"  Median: {valid_target.median():.0f} days")
        print(f"  Std:    {valid_target.std():.1f} days")
        print(f"  Min:    {valid_target.min():.0f}, Max: {valid_target.max():.0f}")

    # Save
    out_path = PROCESSED_DIR / "training_data.csv"
    labeled.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path.name}")

    # Also save a metadata summary
    meta = {
        "n_rows": len(labeled),
        "n_columns": len(labeled.columns),
        "columns": list(labeled.columns),
        "years": TRAIN_YEARS + VAL_YEARS + TEST_YEARS,
        "train_rows": len(labeled[labeled["split"] == "train"]),
        "val_rows": len(labeled[labeled["split"] == "val"]),
        "test_rows": len(labeled[labeled["split"] == "test"]),
        "n_points": int(labeled["point_id"].nunique()),
    }
    meta_path = PROCESSED_DIR / "dataset_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved metadata -> {meta_path.name}")

    return labeled


if __name__ == "__main__":
    run()
