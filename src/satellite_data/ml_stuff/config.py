"""
Centralized configuration for the Harvest Date Prediction Pipeline.
All paths, band lists, constants, and hyperparameters in one place.
"""
import os
from pathlib import Path

# --- Project Root ------------------------------------------------------------
PROJECT_ROOT = Path(r"d:\Coding\Hackathon\samsung\agri-Waste-biomass-valuation-engine")
DATA_DIR     = PROJECT_ROOT / "data"
RAW_DIR      = DATA_DIR / "sattelite_raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR   = PROJECT_ROOT / "models"

# Create output directories
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# --- Years -------------------------------------------------------------------
YEARS = [2022, 2023, 2024, 2025]
TRAIN_YEARS = [2022, 2023]
VAL_YEARS   = [2024]
TEST_YEARS  = [2025]

# --- Satellite Band Definitions ----------------------------------------------
S2_BANDS = ["B2", "B4", "B5", "B6", "B7", "B8", "B11", "B12"]
S1_BANDS = ["VH", "VV"]

# --- Vegetation Index Definitions --------------------------------------------
# Computed from raw S2 bands in Python (not GEE)
VI_NAMES = ["ndvi", "ndwi", "lswi", "rep", "bsi"]

# --- Temporal Grid -----------------------------------------------------------
TEMPORAL_RESOLUTION_DAYS = 5       # Regularize to 5-day grid
SEASON_START_MMDD = "05-01"        # May 1 — pre-monsoon
SEASON_END_MMDD   = "12-15"        # Dec 15 — post-harvest

# --- Causal Interpolation Parameters ----------------------------------------
EMA_ALPHA   = 0.3                  # Exponential moving average smoothing factor
MAX_GAP_INTERP_DAYS = 15           # Max gap for causal linear interpolation
CARRY_FORWARD_MAX_DAYS = 45        # Max days to carry forward stale observation

# --- Pseudo-Label Parameters -------------------------------------------------
# NDVI drop thresholds for harvest detection
NDVI_PEAK_THRESHOLD  = 0.5         # Minimum NDVI to consider as "peak vegetative"
NDVI_DROP_THRESHOLD  = 0.25        # NDVI must drop below this post-peak
NDVI_DROP_RATE       = -0.03       # Minimum rate of NDVI decline (per 5-day step)

# SAR VH thresholds for harvest confirmation
VH_DROP_THRESHOLD_DB = 3.0         # VH must drop by at least 3 dB from peak
VH_CONFIRMATION_WINDOW_DAYS = 15   # SAR must agree with NDVI within ±15 days

# Label confidence
LABEL_AGREE_HIGH_DAYS   = 3        # S1-S2 agree within ±3 days -> high confidence
LABEL_AGREE_MED_DAYS    = 7        # ±7 days -> medium confidence
# > 7 days -> low confidence (discard or downweight)

# --- Weather (Open-Meteo) ----------------------------------------------------
WEATHER_VARIABLES = [
    "temperature_2m_max", "temperature_2m_min",
    "precipitation_sum", "et0_fao_evapotranspiration",
    "shortwave_radiation_sum",
    "wind_speed_10m_max",
]

# GDD piecewise parameters (paddy-specific)
GDD_T_BASE  = 10.0   # °C — below this, no growth
GDD_T_UPPER = 35.0   # °C — above this, heat stress, capped

# VPD constants (Tetens formula)
VPD_A = 0.6108
VPD_B = 17.27
VPD_C = 237.3

# --- Feature Engineering -----------------------------------------------------
ROLLING_WINDOW_DAYS = 30
LAG_STEPS = [1, 2, 3, 4]          # 5, 10, 15, 20 days back (in 5-day units)

# SOS (Start of Season) detection
SOS_NDVI_THRESHOLD = 0.3           # NDVI crossing above this = start of season

# --- Variety Clustering ------------------------------------------------------
VARIETY_CLUSTER_K = 3              # k-means clusters (short, medium, long duration)
CLUSTER_START_MMDD = "07-01"       # July 1 — vegetative phase for clustering
CLUSTER_END_MMDD   = "08-31"       # Aug 31

# --- Modeling ----------------------------------------------------------------
CATBOOST_PARAMS = {
    "iterations": 10000,
    "learning_rate": 0.05,
    "depth": 8,
    "l2_leaf_reg": 5,
    "loss_function": "MAE",
    "eval_metric": "MAE",
    "early_stopping_rounds": 500,
    "random_seed": 42,
    "verbose": 200,
    "task_type": "GPU",
}

XGBOOST_AFT_PARAMS = {
    "objective": "survival:aft",
    "eval_metric": "aft-nloglik",
    "aft_loss_distribution": "normal",
    "aft_loss_distribution_scale": 1.0,
    "learning_rate": 0.05,
    "max_depth": 8,
    "n_estimators": 2000,
    "early_stopping_rounds": 100,
    "random_state": 42,
    "tree_method": "hist",
    "device": "cuda",
}

# --- Evaluation --------------------------------------------------------------
EVAL_WINDOWS = [3, 5, 7, 10, 14]   # "Within ±N days" metrics
LABEL_NOISE_FLOOR_DAYS = 5          # Estimated pseudo-label uncertainty

# --- Optical Dropout Augmentation --------------------------------------------
OPTICAL_DROPOUT_MONTHS = [6, 7, 8, 9]   # June–September (monsoon)
OPTICAL_DROPOUT_RATE   = 0.5             # Drop 50% of S2 obs during monsoon

# --- Weather Noise Injection -------------------------------------------------
WEATHER_NOISE_SIGMA_TEMP   = 1.5   # °C
WEATHER_NOISE_SIGMA_PRECIP = 3.0   # mm

# --- Static Features ---------------------------------------------------------
CATEGORICAL_FEATURES = ["district_code", "agro_zone", "variety_cluster", "growth_phase"]

print(f"Config loaded. Project root: {PROJECT_ROOT}")
print(f"  Raw data: {RAW_DIR}  ({len(list(RAW_DIR.glob('*.csv')))} CSV files)")
print(f"  Processed: {PROCESSED_DIR}")
print(f"  Years: {YEARS}")
