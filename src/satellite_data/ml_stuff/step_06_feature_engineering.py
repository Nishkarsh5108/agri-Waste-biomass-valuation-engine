"""
Step 6: Feature Engineering — All strictly causal.

Input:  data/processed/interpolated_5day.csv
        data/processed/pseudo_labels.csv
        data/processed/weather_daily.csv
Output: data/processed/features_all.csv

Per implementation plan §4:
  - Rolling windows (30-day trailing)
  - Cumulative features (SOS -> t)
  - Derivatives (backward difference)
  - Piecewise GDD with T_upper = 35°C
  - VPD from T and RH
  - Calendar features (DOY, week)
  - Growth phase classification
  - Lagged features (t-5, t-10, t-15, t-20 days)
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR,
    TEMPORAL_RESOLUTION_DAYS, ROLLING_WINDOW_DAYS, LAG_STEPS,
    GDD_T_BASE, GDD_T_UPPER,
    VPD_A, VPD_B, VPD_C,
    SOS_NDVI_THRESHOLD,
)


# Rolling window in 5-day steps
ROLLING_STEPS = ROLLING_WINDOW_DAYS // TEMPORAL_RESOLUTION_DAYS  # 6 steps


def compute_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """DOY and week — always known, no causality issue."""
    df["doy"] = df["date"].dt.dayofyear.astype(np.int16)
    df["week"] = df["date"].dt.isocalendar().week.astype(np.int8)
    df["month"] = df["date"].dt.month.astype(np.int8)
    return df


def compute_sos_features(group: pd.DataFrame) -> pd.DataFrame:
    """
    Detect Start of Season (SOS) and compute days_since_sos.
    SOS = first date where NDVI crosses above SOS_NDVI_THRESHOLD.
    """
    ndvi = group["ndvi"].values
    dates = group["date"].values

    # Find SOS
    sos_idx = -1
    for i in range(len(ndvi)):
        if not np.isnan(ndvi[i]) and ndvi[i] > SOS_NDVI_THRESHOLD:
            sos_idx = i
            break

    if sos_idx >= 0:
        sos_date = dates[sos_idx]
        group["days_since_sos"] = (
            (group["date"].values - sos_date).astype("timedelta64[D]").astype(np.float32)
        )
        group["days_since_sos"] = group["days_since_sos"].clip(lower=0)
    else:
        group["days_since_sos"] = np.nan

    return group


def compute_rolling_features(group: pd.DataFrame) -> pd.DataFrame:
    """
    Compute rolling window features (all strictly trailing/causal).
    Window = 30 days = 6 time steps.
    """
    # Rolling max NDVI (30d)
    group["rolling_max_ndvi_30d"] = (
        group["ndvi"].rolling(ROLLING_STEPS, min_periods=1).max().astype(np.float32)
    )
    # Rolling min NDVI (30d) — for amplitude
    rolling_min = group["ndvi"].rolling(ROLLING_STEPS, min_periods=1).min()

    # Rolling amplitude (max - min over 30d)
    group["rolling_amplitude_30d"] = (
        (group["rolling_max_ndvi_30d"] - rolling_min).astype(np.float32)
    )

    # Days since rolling max (within 30d window)
    max_vals = group["rolling_max_ndvi_30d"].values
    ndvi_vals = group["ndvi"].values
    days_since_max = np.zeros(len(group), dtype=np.float32)
    for i in range(len(group)):
        if np.isnan(max_vals[i]) or np.isnan(ndvi_vals[i]):
            days_since_max[i] = np.nan
            continue
        # Look backward up to ROLLING_STEPS to find where max occurred
        start = max(0, i - ROLLING_STEPS + 1)
        window = ndvi_vals[start:i+1]
        if len(window) > 0 and not np.all(np.isnan(window)):
            max_pos = np.nanargmax(window)
            days_since_max[i] = (len(window) - 1 - max_pos) * TEMPORAL_RESOLUTION_DAYS
    group["days_since_rolling_max_30d"] = days_since_max

    return group


def compute_cumulative_features(group: pd.DataFrame) -> pd.DataFrame:
    """
    Cumulative features from SOS to current time t.
    All strictly causal — running sums/integrals.
    """
    # Cumulative NDVI (trapezoidal integral from SOS to t)
    ndvi = group["ndvi"].values
    days_since_sos = group["days_since_sos"].values

    cumul = np.zeros(len(group), dtype=np.float32)
    for i in range(1, len(group)):
        if np.isnan(ndvi[i]) or np.isnan(days_since_sos[i]) or days_since_sos[i] <= 0:
            cumul[i] = cumul[i-1] if i > 0 else 0
        else:
            # Trapezoidal integration: (f(t-1) + f(t)) / 2 * dt
            prev_val = ndvi[i-1] if not np.isnan(ndvi[i-1]) else 0
            cumul[i] = cumul[i-1] + (prev_val + ndvi[i]) / 2.0 * TEMPORAL_RESOLUTION_DAYS
    group["cumul_ndvi_to_t"] = cumul

    return group


def compute_derivative_features(group: pd.DataFrame) -> pd.DataFrame:
    """
    Backward-difference derivatives. Strictly causal.
    Rate = Δvalue / Δt (per 5-day step)
    Acceleration = Δrate / Δt (2nd derivative)
    """
    dt = TEMPORAL_RESOLUTION_DAYS

    # NDVI rate and acceleration
    group["ndvi_rate"] = group["ndvi"].diff() / dt
    group["ndvi_accel"] = group["ndvi_rate"].diff() / dt

    # VH rate and acceleration
    if "VH" in group.columns:
        group["vh_rate"] = group["VH"].diff() / dt
        group["vh_accel"] = group["vh_rate"].diff() / dt
    else:
        group["vh_rate"] = np.nan
        group["vh_accel"] = np.nan

    # Cast to float32
    for col in ["ndvi_rate", "ndvi_accel", "vh_rate", "vh_accel"]:
        group[col] = group[col].astype(np.float32)

    return group


def compute_lag_features(group: pd.DataFrame) -> pd.DataFrame:
    """
    Lagged features: VI and SAR values from t-5, t-10, t-15, t-20 days.
    Strictly causal — only past values.
    """
    for lag in LAG_STEPS:
        for col in ["ndvi", "ndwi", "VH", "VV"]:
            if col in group.columns:
                group[f"{col}_lag{lag}"] = group[col].shift(lag).astype(np.float32)

    return group


def compute_growth_phase(group: pd.DataFrame) -> pd.DataFrame:
    """
    Categorical growth phase based on NDVI + SAR thresholds.
    Uses only past trajectory — strictly causal.

    Phases:
      0 = pre-season (bare soil / fallow)
      1 = flooding / transplanting (LSWI spike)
      2 = vegetative growth (NDVI rising)
      3 = peak / reproductive (NDVI plateau)
      4 = senescence (NDVI declining)
      5 = post-harvest (NDVI < 0.2)
    """
    ndvi = group["ndvi"].values
    ndvi_rate = group["ndvi_rate"].values if "ndvi_rate" in group.columns else np.zeros(len(group))
    lswi = group["lswi"].values if "lswi" in group.columns else np.zeros(len(group))

    phase = np.full(len(group), 0, dtype=np.int8)

    for i in range(len(group)):
        if np.isnan(ndvi[i]):
            phase[i] = 0
        elif ndvi[i] < 0.2:
            phase[i] = 0 if i < len(group) // 2 else 5  # Pre or post season
        elif not np.isnan(lswi[i]) and lswi[i] > 0.2 and ndvi[i] < 0.4:
            phase[i] = 1  # Flooding / transplanting
        elif not np.isnan(ndvi_rate[i]) and ndvi_rate[i] > 0.005:
            phase[i] = 2  # Vegetative growth
        elif ndvi[i] > 0.5 and (np.isnan(ndvi_rate[i]) or abs(ndvi_rate[i]) < 0.005):
            phase[i] = 3  # Peak / reproductive
        elif not np.isnan(ndvi_rate[i]) and ndvi_rate[i] < -0.005:
            phase[i] = 4  # Senescence
        else:
            phase[i] = 0

    group["growth_phase"] = phase
    return group


def merge_weather_features(satellite_df: pd.DataFrame,
                           weather_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge daily weather data with 5-day satellite grid.
    For each 5-day satellite step, take the mean weather over that 5-day window.
    Vectorized for performance.
    """
    print("  Vectorizing weather aggregation...")
    weather_df = weather_df.copy()
    weather_df["date"] = pd.to_datetime(weather_df["date"])
    satellite_df["date"] = pd.to_datetime(satellite_df["date"])

    mean_cols = ["t_max", "t_min", "et0_mm", "solar_rad", "wind_speed"]
    sum_cols = ["precip_mm"]
    
    # Check if cols exist
    mean_cols = [c for c in mean_cols if c in weather_df.columns]
    sum_cols = [c for c in sum_cols if c in weather_df.columns]

    # Sort and set index for rolling by time
    weather_df = weather_df.sort_values(["point_id", "date"]).set_index("date")
    
    # Rolling 5-day mean and sum (requires pandas datetime index)
    # The output will have MultiIndex (point_id, date)
    rolled_means = weather_df.groupby("point_id")[mean_cols].rolling("5D").mean().reset_index()
    
    if sum_cols:
        rolled_sums = weather_df.groupby("point_id")[sum_cols].rolling("5D").sum().reset_index()
        # Merge means and sums
        agg_wx = rolled_means.merge(rolled_sums, on=["point_id", "date"])
    else:
        agg_wx = rolled_means

    # Merge aggregated weather into satellite dataframe
    merged = satellite_df.merge(agg_wx, on=["point_id", "date"], how="left")

    return merged


def compute_gdd_vpd(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute GDD (piecewise, capped at 35°C) and VPD.
    """
    # Piecewise GDD: max(0, min(T_mean, T_upper) - T_base)
    t_mean = (df["t_max"] + df["t_min"]) / 2.0
    df["gdd_daily"] = np.maximum(
        0, np.minimum(t_mean, GDD_T_UPPER) - GDD_T_BASE
    ).astype(np.float32)

    # VPD = e_s - e_a (Tetens formula)
    # Estimate e_a by assuming T_dew ≈ T_min (standard FAO-56 agrometeorological practice)
    e_s_tmax = VPD_A * np.exp(VPD_B * df["t_max"] / (df["t_max"] + VPD_C))
    e_s_tmin = VPD_A * np.exp(VPD_B * df["t_min"] / (df["t_min"] + VPD_C))
    e_s = (e_s_tmax + e_s_tmin) / 2.0
    
    # e_a ≈ e_s(T_min)
    e_a = e_s_tmin
    
    df["vpd"] = (e_s - e_a).clip(lower=0).astype(np.float32)

    return df


def compute_cumulative_weather(group: pd.DataFrame) -> pd.DataFrame:
    """
    Cumulative weather features from SOS to t. Strictly causal running sums.
    """
    # Only accumulate after SOS
    sos_mask = group["days_since_sos"].notna() & (group["days_since_sos"] >= 0)

    # Cumulative GDD
    gdd = group["gdd_daily"].values.copy()
    gdd[~sos_mask.values] = 0
    group["gdd_cumul"] = np.nancumsum(gdd).astype(np.float32)

    # Cumulative precipitation
    precip = group["precip_mm"].values.copy()
    precip[~sos_mask.values] = 0
    group["precip_cumul"] = np.nancumsum(np.nan_to_num(precip)).astype(np.float32)

    # Cumulative ET0
    et0 = group["et0_mm"].values.copy()
    et0[~sos_mask.values] = 0
    group["et0_cumul"] = np.nancumsum(np.nan_to_num(et0)).astype(np.float32)

    # 7-day trailing precipitation sum (rolling)
    precip_series = group["precip_mm"].fillna(0)
    # 7 days = ~1.4 steps at 5-day resolution; use 2 steps
    group["precip_7d"] = precip_series.rolling(2, min_periods=1).sum().astype(np.float32)

    # Consecutive dry days (precip < 1mm)
    dry = (group["precip_mm"].fillna(0) < 1.0).astype(int)
    # Compute consecutive count
    consec = np.zeros(len(group), dtype=np.int16)
    for i in range(len(group)):
        if dry.iloc[i]:
            consec[i] = (consec[i-1] + 1) if i > 0 else 1
        else:
            consec[i] = 0
    group["dry_days_consec"] = consec

    return group


def compute_photoperiod(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute photoperiod (day length in hours).
    Crucial for Paddy (rice), which is a short-day plant where flowering is triggered by decreasing day lengths.
    """
    print("  Computing photoperiod (day length)...")
    df = df.copy()
    
    # We need lat and DOY
    if "lat" not in df.columns:
        print("  WARNING: 'lat' not found in data. Using default 30.0 for Punjab/Haryana region.")
        lat = 30.0
    else:
        lat = df["lat"].values
        
    phi = np.radians(lat)
    J = df["date"].dt.dayofyear.values
    delta = 0.409 * np.sin((2 * np.pi * J / 365) - 1.39)
    
    tan_product = -np.tan(phi) * np.tan(delta)
    tan_product = np.clip(tan_product, -1.0, 1.0)
    
    omega_s = np.arccos(tan_product)
    day_length = (24 / np.pi) * omega_s
    df["photoperiod"] = day_length.astype(np.float32)
    return df


def compute_spatial_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 5km neighborhood average NDVI at each time step."""
    print("  Computing spatial features (5km radius averages)...")
    from scipy.spatial import cKDTree
    
    if "lat" not in df.columns or "lon" not in df.columns:
        print("  WARNING: 'lat' or 'lon' not found. Skipping spatial features.")
        return df
        
    results = []
    grouped = df.groupby("date")
    total_dates = len(grouped)
    
    for idx, (dt, group) in enumerate(grouped):
        coords = group[["lat", "lon"]].values
        # Radius ~ 0.045 degrees (approx 5km)
        tree = cKDTree(coords)
        indices = tree.query_ball_tree(tree, r=0.045)
        
        ndvi_vals = group["ndvi"].values
        
        spatial_ndvi = []
        for neighbors in indices:
            if len(neighbors) > 0:
                # ignore all-nan slices warning
                with np.errstate(invalid='ignore'):
                    spatial_ndvi.append(np.nanmean(ndvi_vals[neighbors]))
            else:
                spatial_ndvi.append(np.nan)
                
        group = group.copy()
        group["spatial_ndvi_5km"] = np.array(spatial_ndvi, dtype=np.float32)
        results.append(group)
            
    return pd.concat(results, ignore_index=True)


def engineer_features_for_group(group: pd.DataFrame) -> pd.DataFrame:
    """Apply all feature engineering to a single (point_id, year) group."""
    group = group.sort_values("date").reset_index(drop=True)

    # Calendar
    group = compute_calendar_features(group)

    # SOS detection
    group = compute_sos_features(group)

    # Derivatives (must be before rolling, which uses ndvi_rate)
    group = compute_derivative_features(group)

    # Rolling features
    group = compute_rolling_features(group)

    # Cumulative
    group = compute_cumulative_features(group)

    # Growth phase
    group = compute_growth_phase(group)

    # Lag features
    group = compute_lag_features(group)

    # Weather cumulative
    if "gdd_daily" in group.columns:
        group = compute_cumulative_weather(group)

    return group


def run():
    """Main execution: feature engineering pipeline."""
    print("=" * 70)
    print("STEP 6: Feature Engineering (Strictly Causal)")
    print("=" * 70)

    out_path = PROCESSED_DIR / "features_all.csv"
    if out_path.exists():
        existing = pd.read_csv(out_path)
        print(f"Found existing features data: {len(existing)} rows")
        user_input = input("  Re-run feature engineering? (y/N): ").strip().lower()
        if user_input != "y":
            print("  Skipping feature engineering (using existing data)")
            return existing

    # Load interpolated satellite data
    sat_path = PROCESSED_DIR / "interpolated_5day.csv"
    df = pd.read_csv(sat_path)
    df["date"] = pd.to_datetime(df["date"])
    print(f"Loaded satellite: {len(df)} rows from {sat_path.name}")

    # Load weather data
    wx_path = PROCESSED_DIR / "weather_daily.csv"
    if wx_path.exists():
        wx_df = pd.read_csv(wx_path)
        wx_df["date"] = pd.to_datetime(wx_df["date"])
        print(f"Loaded weather: {len(wx_df)} rows from {wx_path.name}")

        # Merge weather into satellite grid
        print("Merging weather data with satellite grid...")
        df = merge_weather_features(df, wx_df)
        print(f"  After merge: {len(df)} rows")

        # Compute GDD and VPD
        df = compute_gdd_vpd(df)
    else:
        print(f"WARNING: Weather file not found at {wx_path}")
        print("  Proceeding without weather features. Run step_05 first.")
        # Add placeholder columns
        for col in ["t_max", "t_min", "precip_mm", "et0_mm",
                     "solar_rad", "wind_speed",
                     "gdd_daily", "vpd"]:
            df[col] = np.nan

    # Compute global spatial and temporal features
    df = compute_photoperiod(df)
    df = compute_spatial_features(df)

    # Apply feature engineering per (point_id, year)
    import concurrent.futures
    import multiprocessing

    total_groups = df.groupby(["point_id", "year"]).ngroups
    print(f"\nEngineering features for {total_groups} groups...")

    groups = [group for _, group in df.groupby(["point_id", "year"])]
    all_results = []
    
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    print(f"  Using {max_workers} parallel workers")

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        for idx, result in enumerate(executor.map(engineer_features_for_group, groups)):
            all_results.append(result)
            if (idx + 1) % 500 == 0 or (idx + 1) == total_groups:
                print(f"  Processed {idx + 1} / {total_groups} groups")

    combined = pd.concat(all_results, ignore_index=True)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"FEATURE ENGINEERING SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total rows: {len(combined)}")
    print(f"Total columns: {len(combined.columns)}")
    print(f"Columns: {list(combined.columns)}")
    print(f"\nKey feature statistics:")
    key_features = ["ndvi_rate", "ndvi_accel", "rolling_max_ndvi_30d",
                    "cumul_ndvi_to_t", "days_since_sos", "gdd_cumul", "vpd"]
    for feat in key_features:
        if feat in combined.columns:
            valid = combined[feat].dropna()
            if len(valid) > 0:
                print(f"  {feat:>25s}: mean={valid.mean():.3f}, "
                      f"std={valid.std():.3f}, NaN={combined[feat].isna().mean()*100:.1f}%")

    out_path = PROCESSED_DIR / "features_all.csv"
    combined.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path.name}")

    return combined


if __name__ == "__main__":
    run()
