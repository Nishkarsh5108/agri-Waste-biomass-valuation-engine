"""
Step 4: Derive Pseudo-Labels — Harvest Date Detection.

Input:  data/processed/interpolated_5day.csv
Output: data/processed/pseudo_labels.csv

Per implementation plan §3.4:
  Harvest date = consensus of NDVI drop + SAR VH drop
  - NDVI must rise above 0.5 (peak vegetative), then drop below 0.25
  - SAR VH must drop by ≥ 3 dB from its rolling peak
  - The two signals must agree within ±15 days
  - Label confidence: high (±3d), medium (±7d), low (>7d -> discard/downweight)
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR,
    NDVI_PEAK_THRESHOLD, NDVI_DROP_THRESHOLD, NDVI_DROP_RATE,
    VH_DROP_THRESHOLD_DB, VH_CONFIRMATION_WINDOW_DAYS,
    LABEL_AGREE_HIGH_DAYS, LABEL_AGREE_MED_DAYS,
)


def detect_ndvi_harvest(dates: np.ndarray, ndvi: np.ndarray) -> int:
    """
    Detect harvest date from NDVI time series.

    Algorithm:
      1. Find the first time NDVI exceeds PEAK_THRESHOLD (confirms crop growth)
      2. After that peak, find where NDVI drops below DROP_THRESHOLD
      3. The harvest date is the midpoint of the steepest NDVI decline segment

    Returns: index of estimated harvest date, or -1 if not detected.
    """
    if len(ndvi) < 10 or np.all(np.isnan(ndvi)):
        return -1

    # Step 1: Find peak vegetative phase (NDVI > 0.5)
    above_peak = np.where(ndvi > NDVI_PEAK_THRESHOLD)[0]
    if len(above_peak) == 0:
        return -1

    peak_idx = above_peak[np.nanargmax(ndvi[above_peak])]

    # Step 2: After the peak, find where NDVI drops below threshold
    post_peak = ndvi[peak_idx:]
    below_thresh = np.where(post_peak < NDVI_DROP_THRESHOLD)[0]
    if len(below_thresh) == 0:
        return -1

    drop_idx_relative = below_thresh[0]
    drop_idx = peak_idx + drop_idx_relative

    # Step 3: Find the steepest decline segment between peak and drop
    segment = ndvi[peak_idx:drop_idx + 1]
    if len(segment) < 2:
        return drop_idx

    # Compute rate of change (backward difference)
    rates = np.diff(segment)
    steepest = np.argmin(rates)  # Most negative = steepest decline
    harvest_idx = peak_idx + steepest + 1  # +1 because diff shifts index by 1

    return harvest_idx


def detect_sar_harvest(dates: np.ndarray, vh: np.ndarray) -> int:
    """
    Detect harvest date from SAR VH backscatter time series.

    Algorithm:
      1. Compute 30-day rolling max of VH
      2. Find where VH drops by ≥ VH_DROP_THRESHOLD_DB from its rolling max
      3. The first such drop after DOY 240 (late August) is the harvest signal

    Returns: index of estimated harvest date, or -1 if not detected.
    """
    if len(vh) < 5 or np.all(np.isnan(vh)):
        return -1

    # Rolling max (6 steps = 30 days at 5-day resolution)
    window = 6
    rolling_max = pd.Series(vh).rolling(window, min_periods=1).max().values

    # Drop from rolling max
    drop = rolling_max - vh

    # Find first significant drop (≥ 3 dB) after late August
    # Late August ≈ step index 24 (DOY ~240, from May 1 start = ~24 5-day steps)
    late_season_start = 24
    post_august = drop[late_season_start:]
    significant_drop = np.where(post_august >= VH_DROP_THRESHOLD_DB)[0]

    if len(significant_drop) == 0:
        return -1

    return late_season_start + significant_drop[0]


def compute_pseudo_labels(group: pd.DataFrame) -> dict:
    """
    Compute harvest date pseudo-label for a single (point_id, year) group.

    Returns dict with:
      - harvest_doy: day of year of estimated harvest
      - harvest_date: actual date
      - label_confidence: 'high', 'medium', 'low', or 'none'
      - ndvi_harvest_doy: NDVI-based estimate
      - sar_harvest_doy: SAR-based estimate
    """
    point_id = group["point_id"].iloc[0]
    year = group["year"].iloc[0]

    dates = group["date"].values
    ndvi = group["ndvi"].values.astype(np.float64)
    vh = group["VH"].values.astype(np.float64) if "VH" in group.columns else np.full(len(dates), np.nan)

    result = {
        "point_id": point_id,
        "year": year,
        "harvest_doy": np.nan,
        "harvest_date": pd.NaT,
        "label_confidence": "none",
        "ndvi_harvest_doy": np.nan,
        "sar_harvest_doy": np.nan,
    }

    # Detect from NDVI
    ndvi_idx = detect_ndvi_harvest(dates, ndvi)
    if ndvi_idx >= 0 and ndvi_idx < len(dates):
        ndvi_date = pd.Timestamp(dates[ndvi_idx])
        result["ndvi_harvest_doy"] = ndvi_date.day_of_year

    # Detect from SAR
    sar_idx = detect_sar_harvest(dates, vh)
    if sar_idx >= 0 and sar_idx < len(dates):
        sar_date = pd.Timestamp(dates[sar_idx])
        result["sar_harvest_doy"] = sar_date.day_of_year

    # Consensus logic
    ndvi_doy = result["ndvi_harvest_doy"]
    sar_doy = result["sar_harvest_doy"]

    if not np.isnan(ndvi_doy) and not np.isnan(sar_doy):
        diff = abs(ndvi_doy - sar_doy)
        if diff <= LABEL_AGREE_HIGH_DAYS:
            result["label_confidence"] = "high"
            result["harvest_doy"] = (ndvi_doy + sar_doy) / 2.0
        elif diff <= LABEL_AGREE_MED_DAYS:
            result["label_confidence"] = "medium"
            result["harvest_doy"] = (ndvi_doy + sar_doy) / 2.0
        elif diff <= VH_CONFIRMATION_WINDOW_DAYS:
            result["label_confidence"] = "low"
            # Weight NDVI more (optical phenology is primary signal)
            result["harvest_doy"] = 0.6 * ndvi_doy + 0.4 * sar_doy
        else:
            # Too much disagreement — use NDVI only with low confidence
            result["label_confidence"] = "low"
            result["harvest_doy"] = ndvi_doy
    elif not np.isnan(ndvi_doy):
        # NDVI only (SAR might be missing during monsoon for some regions)
        result["label_confidence"] = "low"
        result["harvest_doy"] = ndvi_doy
    elif not np.isnan(sar_doy):
        result["label_confidence"] = "low"
        result["harvest_doy"] = sar_doy
    # else: both failed -> no label

    # Convert DOY back to date
    if not np.isnan(result["harvest_doy"]):
        doy = int(round(result["harvest_doy"]))
        try:
            result["harvest_date"] = pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=doy - 1)
        except Exception:
            result["harvest_date"] = pd.NaT

    return result


def run():
    """Main execution: compute pseudo-labels for all point-years."""
    print("=" * 70)
    print("STEP 4: Derive Harvest Date Pseudo-Labels")
    print("=" * 70)

    in_path = PROCESSED_DIR / "interpolated_5day.csv"
    df = pd.read_csv(in_path)
    df["date"] = pd.to_datetime(df["date"])
    print(f"Loaded: {len(df)} rows from {in_path.name}")

    labels = []
    total_groups = df.groupby(["point_id", "year"]).ngroups
    print(f"Processing {total_groups} (point_id, year) groups...")

    for idx, ((pid, yr), group) in enumerate(df.groupby(["point_id", "year"])):
        label = compute_pseudo_labels(group.sort_values("date"))
        labels.append(label)

        if (idx + 1) % 500 == 0 or (idx + 1) == total_groups:
            print(f"  Processed {idx + 1} / {total_groups} groups")

    labels_df = pd.DataFrame(labels)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"PSEUDO-LABEL SUMMARY")
    print(f"{'=' * 50}")
    n_total = len(labels_df)
    n_detected = labels_df["harvest_doy"].notna().sum()
    print(f"Total point-years: {n_total}")
    print(f"Harvest detected:  {n_detected} ({100*n_detected/n_total:.1f}%)")
    print(f"\nConfidence distribution:")
    print(labels_df["label_confidence"].value_counts().to_string())
    print(f"\nHarvest DOY statistics (detected only):")
    detected = labels_df[labels_df["harvest_doy"].notna()]["harvest_doy"]
    if len(detected) > 0:
        print(f"  Mean DOY: {detected.mean():.0f} (~ {pd.Timestamp(2022, 1, 1) + pd.Timedelta(days=int(detected.mean()) - 1):%b %d})")
        print(f"  Std:  {detected.std():.1f} days")
        print(f"  Min:  {detected.min():.0f}, Max: {detected.max():.0f}")

    # NDVI vs SAR agreement
    both = labels_df[(labels_df["ndvi_harvest_doy"].notna()) & (labels_df["sar_harvest_doy"].notna())]
    if len(both) > 0:
        diff = (both["ndvi_harvest_doy"] - both["sar_harvest_doy"]).abs()
        print(f"\nNDVI-SAR agreement ({len(both)} point-years with both signals):")
        print(f"  Mean difference: {diff.mean():.1f} days")
        print(f"  Median:          {diff.median():.0f} days")
        print(f"  Within ±3 days:  {(diff <= 3).mean()*100:.1f}%")
        print(f"  Within ±7 days:  {(diff <= 7).mean()*100:.1f}%")

    out_path = PROCESSED_DIR / "pseudo_labels.csv"
    labels_df.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path.name}")

    return labels_df


if __name__ == "__main__":
    run()
