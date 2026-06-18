"""
Step 7: Variety Duration Clustering.

Input:  data/processed/interpolated_5day.csv
Output: data/processed/variety_clusters.csv

Per implementation plan §3.5:
  Separate fields into short-duration (~120d, PR-126) vs medium vs
  long-duration (~160d, Pusa-44) categories using unsupervised clustering
  on the July-August vegetative NDVI trajectory.

Method:
  1. Extract NDVI from July 1 – August 31 per (point_id, year)
  2. Compute features: max NDVI, rate of rise, DOY of first NDVI > 0.5
  3. K-means clustering (k=3)
  4. Output: variety_cluster label (categorical) per point-year
"""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR,
    VARIETY_CLUSTER_K, CLUSTER_START_MMDD, CLUSTER_END_MMDD,
)


def extract_cluster_features(group: pd.DataFrame) -> dict:
    """
    Extract clustering features from the July-August vegetative NDVI.
    """
    point_id = group["point_id"].iloc[0]
    year = group["year"].iloc[0]

    # Filter to July 1 – August 31
    start = pd.Timestamp(f"{year}-{CLUSTER_START_MMDD}")
    end   = pd.Timestamp(f"{year}-{CLUSTER_END_MMDD}")
    veg_phase = group[(group["date"] >= start) & (group["date"] <= end)]

    result = {"point_id": point_id, "year": year}

    ndvi = veg_phase["ndvi"].dropna()

    if len(ndvi) < 3:
        result["max_ndvi_jul_aug"] = np.nan
        result["ndvi_rise_rate"] = np.nan
        result["doy_first_ndvi_05"] = np.nan
        return result

    # Feature 1: Max NDVI reached in Jul-Aug
    result["max_ndvi_jul_aug"] = ndvi.max()

    # Feature 2: Rate of NDVI rise (slope of linear fit)
    x = np.arange(len(ndvi))
    if len(x) >= 2:
        coeffs = np.polyfit(x, ndvi.values, 1)
        result["ndvi_rise_rate"] = coeffs[0]  # Slope
    else:
        result["ndvi_rise_rate"] = 0.0

    # Feature 3: DOY of first NDVI > 0.5
    dates = veg_phase["date"].values
    above_05 = veg_phase[veg_phase["ndvi"] > 0.5]
    if len(above_05) > 0:
        first_date = pd.Timestamp(above_05["date"].iloc[0])
        result["doy_first_ndvi_05"] = first_date.day_of_year
    else:
        result["doy_first_ndvi_05"] = 999  # Never reached 0.5

    return result


def run():
    """Main execution: variety clustering."""
    print("=" * 70)
    print("STEP 7: Variety Duration Clustering")
    print("=" * 70)

    in_path = PROCESSED_DIR / "interpolated_5day.csv"
    df = pd.read_csv(in_path)
    df["date"] = pd.to_datetime(df["date"])
    print(f"Loaded: {len(df)} rows from {in_path.name}")

    # Extract features for each point-year
    features = []
    total_groups = df.groupby(["point_id", "year"]).ngroups
    print(f"Extracting clustering features for {total_groups} groups...")

    for idx, ((pid, yr), group) in enumerate(df.groupby(["point_id", "year"])):
        feat = extract_cluster_features(group.sort_values("date"))
        features.append(feat)

    feat_df = pd.DataFrame(features)

    # Drop rows with NaN features (not enough data in Jul-Aug)
    feat_cols = ["max_ndvi_jul_aug", "ndvi_rise_rate", "doy_first_ndvi_05"]
    valid = feat_df.dropna(subset=feat_cols)
    print(f"  Valid point-years for clustering: {len(valid)} / {len(feat_df)}")

    if len(valid) < VARIETY_CLUSTER_K:
        print("  ERROR: Not enough valid points for clustering!")
        feat_df["variety_cluster"] = 0
    else:
        # Standardize features
        scaler = StandardScaler()
        X = scaler.fit_transform(valid[feat_cols].values)

        # K-means
        kmeans = KMeans(n_clusters=VARIETY_CLUSTER_K, random_state=42, n_init=10)
        valid_clusters = kmeans.fit_predict(X)

        # Map clusters back — order by centroid max_ndvi_jul_aug
        # So cluster 0 = shortest duration, cluster K-1 = longest
        centroids = scaler.inverse_transform(kmeans.cluster_centers_)
        order = np.argsort(centroids[:, 0])  # Sort by max_ndvi (proxy for vigor/duration)
        cluster_map = {old: new for new, old in enumerate(order)}
        valid_clusters = np.array([cluster_map[c] for c in valid_clusters])

        feat_df.loc[valid.index, "variety_cluster"] = valid_clusters

        # Fill NaN clusters with the most common cluster
        most_common = int(pd.Series(valid_clusters).mode()[0])
        feat_df["variety_cluster"] = feat_df["variety_cluster"].fillna(most_common)

    feat_df["variety_cluster"] = feat_df["variety_cluster"].astype(np.int8)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"CLUSTERING SUMMARY (k={VARIETY_CLUSTER_K})")
    print(f"{'=' * 50}")
    for cluster_id in range(VARIETY_CLUSTER_K):
        cluster_data = feat_df[feat_df["variety_cluster"] == cluster_id]
        if len(cluster_data) > 0:
            print(f"\n  Cluster {cluster_id}: {len(cluster_data)} point-years")
            for col in feat_cols:
                vals = cluster_data[col].dropna()
                if len(vals) > 0:
                    print(f"    {col}: mean={vals.mean():.3f}, std={vals.std():.3f}")

    # Save
    out_df = feat_df[["point_id", "year", "variety_cluster"]].copy()
    out_path = PROCESSED_DIR / "variety_clusters.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path.name}")

    return out_df


if __name__ == "__main__":
    run()
