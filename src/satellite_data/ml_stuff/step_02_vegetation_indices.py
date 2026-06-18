"""
Step 2: Compute Vegetation Indices from raw Sentinel-2 bands.

Input:  data/processed/merged_raw_all_years.csv
Output: data/processed/with_indices_all_years.csv

Computes 5 strictly non-collinear indices (per implementation plan §3.3):
  NDVI  — primary greenness / phenology
  NDWI  — canopy moisture (early senescence indicator)
  LSWI  — surface water / flood detection (transplanting)
  REP   — Red Edge Position (chlorophyll / maturity)
  BSI   — Bare Soil Index (post-harvest confirmation)
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import PROCESSED_DIR, S2_BANDS, VI_NAMES


def compute_ndvi(df: pd.DataFrame) -> pd.Series:
    """NDVI = (NIR - Red) / (NIR + Red) = (B8 - B4) / (B8 + B4)"""
    nir, red = df["B8"], df["B4"]
    denom = nir + red
    return np.where(denom != 0, (nir - red) / denom, np.nan).astype(np.float32)


def compute_ndwi(df: pd.DataFrame) -> pd.Series:
    """NDWI = (NIR - SWIR1) / (NIR + SWIR1) = (B8 - B11) / (B8 + B11)
    Tracks canopy water content — declines during senescence BEFORE greenness drops."""
    nir, swir1 = df["B8"], df["B11"]
    denom = nir + swir1
    return np.where(denom != 0, (nir - swir1) / denom, np.nan).astype(np.float32)


def compute_lswi(df: pd.DataFrame) -> pd.Series:
    """LSWI = (NIR - SWIR2) / (NIR + SWIR2) = (B8 - B12) / (B8 + B12)
    Land Surface Water Index — spikes during flooding (paddy transplanting)."""
    nir, swir2 = df["B8"], df["B12"]
    denom = nir + swir2
    return np.where(denom != 0, (nir - swir2) / denom, np.nan).astype(np.float32)


def compute_rep(df: pd.DataFrame) -> pd.Series:
    """Red Edge Position = 705 + 35 * ((B4+B7)/2 - B5) / (B6 - B5)
    Sensitive to chlorophyll concentration; superior to NDVI during canopy saturation.
    Returns wavelength in nm (~700-740 range for vegetation)."""
    b4, b5, b6, b7 = df["B4"], df["B5"], df["B6"], df["B7"]
    denom = b6 - b5
    # Avoid division by zero
    result = np.where(
        np.abs(denom) > 1e-6,
        705.0 + 35.0 * ((b4 + b7) / 2.0 - b5) / denom,
        np.nan
    )
    # REP should be in ~680-760 nm range; clip outliers
    result = np.clip(result, 680, 760)
    return result.astype(np.float32)


def compute_bsi(df: pd.DataFrame) -> pd.Series:
    """BSI = ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
         = ((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))
    Bare Soil Index — increases sharply after harvest when vegetation is removed."""
    b11, b4, b8, b2 = df["B11"], df["B4"], df["B8"], df["B2"]
    num = (b11 + b4) - (b8 + b2)
    denom = (b11 + b4) + (b8 + b2)
    return np.where(denom != 0, num / denom, np.nan).astype(np.float32)


def compute_vh_vv_ratio(df: pd.DataFrame) -> pd.Series:
    """VH/VV ratio in dB = VH - VV (in dB domain, subtraction = division in linear)."""
    return (df["VH"] - df["VV"]).astype(np.float32)


def run():
    """Main execution: compute all vegetation indices."""
    print("=" * 70)
    print("STEP 2: Compute Vegetation Indices")
    print("=" * 70)

    in_path = PROCESSED_DIR / "merged_raw_all_years.csv"
    df = pd.read_csv(in_path)
    print(f"Loaded: {len(df)} rows from {in_path.name}")

    # Only compute VIs where S2 bands are present (not NaN)
    s2_valid = df[S2_BANDS].notna().all(axis=1)
    print(f"  S2 valid rows: {s2_valid.sum()} / {len(df)} ({100*s2_valid.mean():.1f}%)")

    # Compute indices
    print("  Computing NDVI...")
    df["ndvi"] = compute_ndvi(df)

    print("  Computing NDWI...")
    df["ndwi"] = compute_ndwi(df)

    print("  Computing LSWI...")
    df["lswi"] = compute_lswi(df)

    print("  Computing REP...")
    df["rep"] = compute_rep(df)

    print("  Computing BSI...")
    df["bsi"] = compute_bsi(df)

    print("  Computing VH/VV ratio...")
    df["vh_vv_ratio"] = compute_vh_vv_ratio(df)

    # Summary
    print(f"\nIndex statistics (non-null rows only):")
    for idx in VI_NAMES + ["vh_vv_ratio"]:
        valid = df[idx].dropna()
        if len(valid) > 0:
            print(f"  {idx:>12s}: mean={valid.mean():.4f}, "
                  f"std={valid.std():.4f}, "
                  f"min={valid.min():.4f}, max={valid.max():.4f}, "
                  f"NaN={df[idx].isna().sum()} ({100*df[idx].isna().mean():.1f}%)")

    # Save
    out_path = PROCESSED_DIR / "with_indices_all_years.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path.name} ({len(df)} rows)")

    return df


if __name__ == "__main__":
    run()
