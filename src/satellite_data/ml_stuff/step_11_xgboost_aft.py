"""
Step 11: Tier 1b — XGBoost-AFT Survival Model.

Input:  data/processed/training_data.csv
Output: models/xgboost_aft_harvest.json  (saved model)
        Printed evaluation metrics

Per implementation plan §5 and §6 (Criticism 6 adjudication):
  XGBoost Accelerated Failure Time (AFT) treats harvest prediction as a
  survival/time-to-event problem. This naturally handles right-censoring
  and outputs a hazard function.
"""
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, MODELS_DIR,
    XGBOOST_AFT_PARAMS, CATEGORICAL_FEATURES,
    EVAL_WINDOWS,
)

# Features to exclude
EXCLUDE_COLS = [
    "point_id", "year", "date", "lat", "lon",
    "harvest_doy", "harvest_date", "days_to_harvest",
    "label_confidence", "ndvi_harvest_doy", "sar_harvest_doy",
    "split", ".geo", "system:index", "photoperiod"
]

RAW_BAND_COLS = ["B2", "B4", "B5", "B6", "B7", "B8", "B11", "B12"]


def prepare_features_xgb(df: pd.DataFrame) -> tuple:
    """Prepare features for XGBoost (no native categoricals — must encode)."""
    weights = np.ones(len(df), dtype=np.float32)
    if "label_confidence" in df.columns:
        conf = df["label_confidence"].values
        weights = np.where(conf == "high", 1.0,
                  np.where(conf == "medium", 0.5,
                  np.where(conf == "low", 0.1, 1.0)))

    drop_cols = [c for c in EXCLUDE_COLS + RAW_BAND_COLS if c in df.columns]
    feature_cols = [c for c in df.columns if c not in drop_cols]

    X = df[feature_cols].copy()

    # Encode categoricals as integers
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in feature_cols]
    for col in cat_cols:
        X[col] = X[col].astype("category").cat.codes.astype(np.float32)

    # Ensure all numeric
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    y = df["days_to_harvest"].values

    return X, y, weights, list(X.columns)


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray,
                         label: str = "XGBoost-AFT") -> dict:
    """Compute evaluation metrics."""
    errors = y_true - y_pred
    abs_errors = np.abs(errors)

    metrics = {
        "model": label,
        "mae": float(np.mean(abs_errors)),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "median_ae": float(np.median(abs_errors)),
        "bias": float(np.mean(errors)),
    }

    for w in EVAL_WINDOWS:
        metrics[f"within_{w}d_pct"] = float(np.mean(abs_errors <= w) * 100)

    return metrics


def run():
    """Main execution: train and evaluate XGBoost-AFT model."""
    print("=" * 70)
    print("STEP 11: Tier 1b — XGBoost-AFT Survival Model")
    print("=" * 70)

    try:
        import xgboost as xgb
    except ImportError:
        print("ERROR: xgboost not installed. Install with: pip install xgboost")
        return None

    # Load data
    df = pd.read_csv(PROCESSED_DIR / "training_data.csv")
    df = df[df["days_to_harvest"].notna() & (df["days_to_harvest"] > 0)].copy()
    print(f"Loaded: {len(df)} valid rows")

    train_df = df[df["split"] == "train"].copy()
    val_df   = df[df["split"] == "val"].copy()
    test_df  = df[df["split"] == "test"].copy()

    print(f"  Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    X_train, y_train, w_train, feature_names = prepare_features_xgb(train_df)
    X_val, y_val, w_val, _ = prepare_features_xgb(val_df)
    X_test, y_test, w_test, _ = prepare_features_xgb(test_df)

    # For AFT, we need to specify censoring bounds
    # Since we have fully observed harvests (historical data), most are uncensored.
    # Format: lower_bound, upper_bound (for interval censoring)
    # Uncensored: lower = upper = actual value
    # For training with pseudo-labels that have uncertainty:
    label_noise = 5  # days of pseudo-label uncertainty

    # Create DMatrix with AFT labels
    dtrain = xgb.DMatrix(X_train, label=y_train, weight=w_train)
    dtrain.set_float_info("label_lower_bound", np.maximum(y_train - label_noise, 1))
    dtrain.set_float_info("label_upper_bound", y_train + label_noise)

    dval = xgb.DMatrix(X_val, label=y_val, weight=w_val)
    dval.set_float_info("label_lower_bound", np.maximum(y_val - label_noise, 1))
    dval.set_float_info("label_upper_bound", y_val + label_noise)

    dtest = xgb.DMatrix(X_test, label=y_test, weight=w_test)

    # Train
    params = {
        "objective": XGBOOST_AFT_PARAMS["objective"],
        "eval_metric": XGBOOST_AFT_PARAMS["eval_metric"],
        "aft_loss_distribution": XGBOOST_AFT_PARAMS["aft_loss_distribution"],
        "aft_loss_distribution_scale": XGBOOST_AFT_PARAMS["aft_loss_distribution_scale"],
        "learning_rate": XGBOOST_AFT_PARAMS["learning_rate"],
        "max_depth": XGBOOST_AFT_PARAMS["max_depth"],
        "tree_method": XGBOOST_AFT_PARAMS["tree_method"],
        "verbosity": 1,
    }

    # Try GPU, fall back to CPU
    try:
        params["device"] = "cuda"
        print("\nTraining XGBoost-AFT (GPU)...")
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=XGBOOST_AFT_PARAMS["n_estimators"],
            evals=[(dtrain, "train"), (dval, "val")],
            early_stopping_rounds=XGBOOST_AFT_PARAMS["early_stopping_rounds"],
            verbose_eval=200,
        )
    except Exception as e:
        print(f"GPU failed ({e}), falling back to CPU...")
        params.pop("device", None)
        params["tree_method"] = "hist"
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=XGBOOST_AFT_PARAMS["n_estimators"],
            evals=[(dtrain, "train"), (dval, "val")],
            early_stopping_rounds=XGBOOST_AFT_PARAMS["early_stopping_rounds"],
            verbose_eval=200,
        )

    # Save model
    model_path = MODELS_DIR / "xgboost_aft_harvest.json"
    model.save_model(str(model_path))
    print(f"\nModel saved -> {model_path.name}")

    # -- Evaluate --
    print(f"\n{'=' * 50}")
    print(f"EVALUATION RESULTS")
    print(f"{'=' * 50}")

    # AFT predicts the expected time-to-event
    y_pred_val = model.predict(dval)
    val_metrics = evaluate_predictions(y_val, y_pred_val, "XGBoost-AFT (Val)")
    print(f"\n  Validation:")
    print(f"    MAE:  {val_metrics['mae']:.1f} days")
    print(f"    RMSE: {val_metrics['rmse']:.1f} days")
    for w in EVAL_WINDOWS:
        print(f"    ±{w:2d}d:  {val_metrics[f'within_{w}d_pct']:.1f}%")

    if len(test_df) > 0:
        y_pred_test = model.predict(dtest)
        test_metrics = evaluate_predictions(y_test, y_pred_test, "XGBoost-AFT (Test)")
        print(f"\n  Test:")
        print(f"    MAE:  {test_metrics['mae']:.1f} days")
        print(f"    RMSE: {test_metrics['rmse']:.1f} days")
        for w in EVAL_WINDOWS:
            print(f"    ±{w:2d}d:  {test_metrics[f'within_{w}d_pct']:.1f}%")

    # Feature importance
    print(f"\n{'=' * 50}")
    print(f"TOP 20 FEATURES (gain)")
    print(f"{'=' * 50}")
    imp = model.get_score(importance_type="gain")
    imp_sorted = sorted(imp.items(), key=lambda x: x[1], reverse=True)
    for feat, score in imp_sorted[:20]:
        # Map feature index back to name
        if feat.startswith("f"):
            idx = int(feat[1:])
            name = feature_names[idx] if idx < len(feature_names) else feat
        else:
            name = feat
        print(f"  {score:10.1f}  {name}")

    # Save metrics
    all_metrics = {"validation": val_metrics}
    if len(test_df) > 0:
        all_metrics["test"] = test_metrics
    with open(MODELS_DIR / "xgboost_aft_metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2)

    return model


if __name__ == "__main__":
    run()
