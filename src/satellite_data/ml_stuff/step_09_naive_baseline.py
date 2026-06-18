"""
Step 9: Tier 0 — Naive Baseline (Historical Median Harvest DOY per district).

Input:  data/processed/training_data.csv
Output: Printed metrics + saved predictions

Per implementation plan §5:
  Tier 0 is mandatory. If ML models don't beat this by ≥ 3 days MAE,
  the entire satellite pipeline is not justified.

  Prediction = historical median harvest DOY for each district,
  computed from training years only.
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import PROCESSED_DIR, EVAL_WINDOWS


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray,
                         label: str = "Naive Baseline") -> dict:
    """Compute all evaluation metrics."""
    errors = y_true - y_pred
    abs_errors = np.abs(errors)

    metrics = {
        "model": label,
        "mae": np.mean(abs_errors),
        "rmse": np.sqrt(np.mean(errors ** 2)),
        "median_ae": np.median(abs_errors),
        "std_error": np.std(errors),
        "bias": np.mean(errors),  # Positive = model predicts too early
    }

    for w in EVAL_WINDOWS:
        metrics[f"within_{w}d_pct"] = np.mean(abs_errors <= w) * 100

    return metrics


def run():
    """Main execution: compute and evaluate naive baseline."""
    print("=" * 70)
    print("STEP 9: Tier 0 — Naive Baseline")
    print("=" * 70)

    df = pd.read_csv(PROCESSED_DIR / "training_data.csv")
    print(f"Loaded: {len(df)} rows")

    # We need unique (point_id, year) -> harvest_doy for evaluation
    # The training data has one row per time step — collapse to one row per point-year
    point_years = df.groupby(["point_id", "year"]).agg(
        harvest_doy=("harvest_doy", "first"),
        district_code=("district_code", "first"),
        split=("split", "first"),
        lat=("lat", "first"),
        lon=("lon", "first"),
    ).reset_index()

    train = point_years[point_years["split"] == "train"]
    val = point_years[point_years["split"] == "val"]
    test = point_years[point_years["split"] == "test"]

    print(f"  Train point-years: {len(train)}")
    print(f"  Val point-years:   {len(val)}")
    print(f"  Test point-years:  {len(test)}")

    # -- Compute baselines --

    # 1. Global median
    global_median = train["harvest_doy"].median()
    print(f"\nGlobal median harvest DOY (train): {global_median:.0f}")

    # 2. Per-district median
    district_medians = train.groupby("district_code")["harvest_doy"].median()
    print(f"Per-district medians:")
    for dist, med in district_medians.items():
        n = len(train[train["district_code"] == dist])
        print(f"  {dist}: DOY {med:.0f} (n={n})")

    # -- Evaluate on validation set --
    print(f"\n{'=' * 50}")
    print(f"VALIDATION SET RESULTS")
    print(f"{'=' * 50}")

    if len(val) > 0:
        y_true_val = val["harvest_doy"].values

        # Global baseline
        y_pred_global = np.full(len(val), global_median)
        global_metrics = evaluate_predictions(y_true_val, y_pred_global, "Global Median")
        print(f"\n  Global Median Baseline:")
        print(f"    MAE:     {global_metrics['mae']:.1f} days")
        print(f"    RMSE:    {global_metrics['rmse']:.1f} days")
        print(f"    Bias:    {global_metrics['bias']:.1f} days")
        for w in EVAL_WINDOWS:
            print(f"    ±{w:2d} days: {global_metrics[f'within_{w}d_pct']:.1f}%")

        # Per-district baseline
        y_pred_district = val["district_code"].map(district_medians).fillna(global_median).values
        district_metrics = evaluate_predictions(y_true_val, y_pred_district, "District Median")
        print(f"\n  Per-District Median Baseline:")
        print(f"    MAE:     {district_metrics['mae']:.1f} days")
        print(f"    RMSE:    {district_metrics['rmse']:.1f} days")
        print(f"    Bias:    {district_metrics['bias']:.1f} days")
        for w in EVAL_WINDOWS:
            print(f"    ±{w:2d} days: {district_metrics[f'within_{w}d_pct']:.1f}%")

    # -- Evaluate on test set --
    print(f"\n{'=' * 50}")
    print(f"TEST SET RESULTS")
    print(f"{'=' * 50}")

    if len(test) > 0:
        y_true_test = test["harvest_doy"].values

        y_pred_global_test = np.full(len(test), global_median)
        global_test = evaluate_predictions(y_true_test, y_pred_global_test, "Global Median")

        y_pred_district_test = test["district_code"].map(district_medians).fillna(global_median).values
        district_test = evaluate_predictions(y_true_test, y_pred_district_test, "District Median")

        print(f"\n  Global Median: MAE={global_test['mae']:.1f}, RMSE={global_test['rmse']:.1f}")
        print(f"  District Median: MAE={district_test['mae']:.1f}, RMSE={district_test['rmse']:.1f}")

    # Save baseline predictions and metrics
    results = {
        "global_median_doy": global_median,
        "district_medians": district_medians.to_dict(),
    }

    # Save
    import json
    out_path = PROCESSED_DIR / "naive_baseline_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved -> {out_path.name}")

    return results


if __name__ == "__main__":
    run()
