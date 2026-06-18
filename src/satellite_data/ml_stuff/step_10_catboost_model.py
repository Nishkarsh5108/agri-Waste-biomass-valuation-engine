"""
Step 10: Tier 1a — CatBoost Regression.

Input:  data/processed/training_data.csv
Output: models/catboost_harvest.cbm  (saved model)
        Printed evaluation metrics

Per implementation plan §5:
  CatBoost with MAE loss, GPU training, native categorical handling.
  This is the primary production model candidate.
"""
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, MODELS_DIR,
    CATBOOST_PARAMS, CATEGORICAL_FEATURES,
    EVAL_WINDOWS, LABEL_NOISE_FLOOR_DAYS,
    OPTICAL_DROPOUT_MONTHS, OPTICAL_DROPOUT_RATE,
    WEATHER_NOISE_SIGMA_TEMP, WEATHER_NOISE_SIGMA_PRECIP,
    VI_NAMES,
)

# Features to exclude from training (metadata / target / leaky)
EXCLUDE_COLS = [
    "point_id", "year", "date", "lat", "lon",
    "harvest_doy", "harvest_date", "days_to_harvest",
    "label_confidence", "ndvi_harvest_doy", "sar_harvest_doy",
    "split", ".geo", "system:index", "photoperiod"
]

# Raw band columns (already encoded in VIs — don't double-count)
RAW_BAND_COLS = ["B2", "B4", "B5", "B6", "B7", "B8", "B11", "B12"]


def prepare_features(df: pd.DataFrame) -> tuple:
    """
    Prepare feature matrix and target vector.
    Returns (X, y, weights, feature_names, cat_indices)
    """
    weights = np.ones(len(df), dtype=np.float32)
    if "label_confidence" in df.columns:
        conf = df["label_confidence"].values
        weights = np.where(conf == "high", 1.0,
                  np.where(conf == "medium", 0.5,
                  np.where(conf == "low", 0.1, 1.0)))

    # Drop exclude columns and raw bands
    drop_cols = [c for c in EXCLUDE_COLS + RAW_BAND_COLS if c in df.columns]
    feature_cols = [c for c in df.columns if c not in drop_cols]

    # Identify categorical features
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in feature_cols]

    # Convert categoricals to string type for CatBoost
    for col in cat_cols:
        df[col] = df[col].astype(str).fillna("missing")

    # Fill numeric NaN with -999 (CatBoost handles this, but explicit is better)
    numeric_cols = [c for c in feature_cols if c not in cat_cols]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    X = df[feature_cols].copy()
    y = df["days_to_harvest"].values

    cat_indices = [feature_cols.index(c) for c in cat_cols if c in feature_cols]

    return X, y, weights, feature_cols, cat_indices


def apply_optical_dropout(X: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """
    Optical Dropout Augmentation (per plan §6.5):
    During training, randomly mask 50% of S2 observations for June-September.
    """
    X = X.copy()

    # Check if month column exists
    if "month" not in X.columns:
        return X

    monsoon_mask = X["month"].isin(OPTICAL_DROPOUT_MONTHS)
    n_monsoon = monsoon_mask.sum()
    if n_monsoon == 0:
        return X

    # Random dropout
    dropout_mask = monsoon_mask & (rng.random(len(X)) < OPTICAL_DROPOUT_RATE)
    n_dropped = dropout_mask.sum()

    # Set optical features to NaN for dropped rows
    optical_features = [c for c in X.columns if any(vi in c for vi in VI_NAMES)]
    X.loc[dropout_mask, optical_features] = np.nan

    # Update staleness flag
    if "days_since_valid_optical" in X.columns:
        X.loc[dropout_mask, "days_since_valid_optical"] = 15  # Indicate stale

    return X


def apply_weather_noise(X: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """
    Weather Noise Injection (per plan §6.5):
    Add Gaussian noise to temperature and precipitation during training.
    """
    X = X.copy()

    for col in ["t_max", "t_min"]:
        if col in X.columns:
            mask = X[col].notna()
            X.loc[mask, col] += rng.normal(0, WEATHER_NOISE_SIGMA_TEMP, mask.sum())

    if "precip_mm" in X.columns:
        mask = X["precip_mm"].notna()
        noise = rng.normal(0, WEATHER_NOISE_SIGMA_PRECIP, mask.sum())
        X.loc[mask, "precip_mm"] = (X.loc[mask, "precip_mm"] + noise).clip(lower=0)

    return X


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray,
                         label: str = "CatBoost") -> dict:
    """Compute evaluation metrics."""
    errors = y_true - y_pred
    abs_errors = np.abs(errors)

    metrics = {
        "model": label,
        "mae": float(np.mean(abs_errors)),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "median_ae": float(np.median(abs_errors)),
        "std_error": float(np.std(errors)),
        "bias": float(np.mean(errors)),
    }

    for w in EVAL_WINDOWS:
        metrics[f"within_{w}d_pct"] = float(np.mean(abs_errors <= w) * 100)

    return metrics


def run():
    """Main execution: train and evaluate CatBoost model."""
    print("=" * 70)
    print("STEP 10: Tier 1a — CatBoost Regression")
    print("=" * 70)

    try:
        from catboost import CatBoostRegressor, Pool
    except ImportError:
        print("ERROR: catboost not installed. Install with: pip install catboost")
        print("  Use the 'tf' or 'torch_gpu' environment.")
        return None

    # Load data
    df = pd.read_csv(PROCESSED_DIR / "training_data.csv")
    print(f"Loaded: {len(df)} rows")

    # Filter to rows with valid target
    df = df[df["days_to_harvest"].notna() & (df["days_to_harvest"] > 0)].copy()
    print(f"Valid target rows: {len(df)}")

    # Split
    train_df = df[df["split"] == "train"].copy()
    val_df   = df[df["split"] == "val"].copy()
    test_df  = df[df["split"] == "test"].copy()

    print(f"  Train: {len(train_df)}")
    print(f"  Val:   {len(val_df)}")
    print(f"  Test:  {len(test_df)}")

    # Prepare features
    X_train, y_train, w_train, feature_names, cat_indices = prepare_features(train_df)
    X_val, y_val, w_val, _, _ = prepare_features(val_df)
    X_test, y_test, w_test, _, _ = prepare_features(test_df)

    # Apply augmentations to training data
    rng = np.random.default_rng(42)
    X_train = apply_optical_dropout(X_train, rng)
    X_train = apply_weather_noise(X_train, rng)

    print(f"\nFeatures: {len(feature_names)}")
    print(f"Categorical features ({len(cat_indices)}): "
          f"{[feature_names[i] for i in cat_indices]}")

    # Create CatBoost pools
    train_pool = Pool(X_train, y_train, weight=w_train, cat_features=cat_indices)
    val_pool   = Pool(X_val, y_val, weight=w_val, cat_features=cat_indices)
    test_pool  = Pool(X_test, y_test, weight=w_test, cat_features=cat_indices)

    # Train
    print(f"\nTraining CatBoost...")
    model = CatBoostRegressor(**CATBOOST_PARAMS)

    try:
        model.fit(
            train_pool,
            eval_set=val_pool,
            use_best_model=True,
        )
    except Exception as e:
        # Fallback to CPU if GPU fails
        print(f"GPU training failed ({e}), falling back to CPU...")
        cpu_params = {**CATBOOST_PARAMS, "task_type": "CPU"}
        model = CatBoostRegressor(**cpu_params)
        model.fit(
            train_pool,
            eval_set=val_pool,
            use_best_model=True,
        )

    # Save model
    model_path = MODELS_DIR / "catboost_harvest.cbm"
    model.save_model(str(model_path))
    print(f"\nModel saved -> {model_path.name}")

    # -- Evaluate --
    print(f"\n{'=' * 50}")
    print(f"EVALUATION RESULTS")
    print(f"{'=' * 50}")

    # Validation
    y_pred_val = model.predict(val_pool)
    val_metrics = evaluate_predictions(y_val, y_pred_val, "CatBoost (Val)")
    print(f"\n  Validation Set:")
    print(f"    MAE:     {val_metrics['mae']:.1f} days")
    print(f"    RMSE:    {val_metrics['rmse']:.1f} days")
    print(f"    Bias:    {val_metrics['bias']:.1f} days")
    for w in EVAL_WINDOWS:
        print(f"    ±{w:2d} days: {val_metrics[f'within_{w}d_pct']:.1f}%")

    # Test
    if len(test_df) > 0:
        y_pred_test = model.predict(test_pool)
        test_metrics = evaluate_predictions(y_test, y_pred_test, "CatBoost (Test)")
        print(f"\n  Test Set:")
        print(f"    MAE:     {test_metrics['mae']:.1f} days")
        print(f"    RMSE:    {test_metrics['rmse']:.1f} days")
        print(f"    Bias:    {test_metrics['bias']:.1f} days")
        for w in EVAL_WINDOWS:
            print(f"    ±{w:2d} days: {test_metrics[f'within_{w}d_pct']:.1f}%")

    # -- Feature Importance --
    print(f"\n{'=' * 50}")
    print(f"TOP 20 FEATURE IMPORTANCES")
    print(f"{'=' * 50}")
    importances = model.get_feature_importance()
    imp_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances
    }).sort_values("importance", ascending=False)

    for i, row in imp_df.head(20).iterrows():
        print(f"  {row['importance']:6.2f}  {row['feature']}")

    # Save importance
    imp_path = MODELS_DIR / "catboost_feature_importance.csv"
    imp_df.to_csv(imp_path, index=False)
    print(f"\nSaved feature importance -> {imp_path.name}")

    # Save metrics
    all_metrics = {"validation": val_metrics}
    if len(test_df) > 0:
        all_metrics["test"] = test_metrics
    metrics_path = MODELS_DIR / "catboost_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"Saved metrics -> {metrics_path.name}")

    return model


if __name__ == "__main__":
    run()
