"""
Master Pipeline Runner — Orchestrates all steps in sequence.

Usage:
    python run_pipeline.py              # Run all steps
    python run_pipeline.py 1 2 3        # Run specific steps only
    python run_pipeline.py --from 3     # Run from step 3 onwards
    python run_pipeline.py --skip-weather  # Skip weather fetch (step 5)

Steps:
    1. Load & Clean raw satellite data
    2. Compute vegetation indices
    3. Temporal interpolation to 5-day grid
    4. Derive pseudo-labels (harvest date detection)
    5. Fetch weather data (Open-Meteo) — SLOW, ~1-2 hours
    6. Feature engineering
    7. Variety duration clustering
    8. Assemble final training DataFrame
    9. Tier 0: Naive baseline
   10. Tier 1a: CatBoost regression
   11. Tier 1b: XGBoost-AFT survival
"""
import sys
import time
import traceback
from pathlib import Path

# Add this directory to path
sys.path.insert(0, str(Path(__file__).parent))


STEPS = {
    1:  ("Load & Clean",              "step_01_load_and_clean"),
    2:  ("Vegetation Indices",        "step_02_vegetation_indices"),
    3:  ("Temporal Interpolation",    "step_03_temporal_interpolation"),
    4:  ("Pseudo-Labels",            "step_04_pseudo_labels"),
    5:  ("Weather Fetch",            "step_05_weather_fetch"),
    6:  ("Feature Engineering",       "step_06_feature_engineering"),
    7:  ("Variety Clustering",        "step_07_variety_clustering"),
    8:  ("Assemble Training Data",    "step_08_assemble_training"),
    9:  ("Naive Baseline",           "step_09_naive_baseline"),
    10: ("CatBoost Model",           "step_10_catboost_model"),
    11: ("XGBoost-AFT Model",        "step_11_xgboost_aft"),
}


def run_step(step_num: int) -> bool:
    """Run a single pipeline step. Returns True if successful."""
    name, module_name = STEPS[step_num]

    print(f"\n{'#' * 70}")
    print(f"#  STEP {step_num}: {name}")
    print(f"{'#' * 70}")

    start = time.time()
    try:
        module = __import__(module_name)
        module.run()
        elapsed = time.time() - start
        print(f"\n[OK] Step {step_num} completed in {elapsed:.1f}s")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n[FAIL] Step {step_num} FAILED after {elapsed:.1f}s")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def main():
    args = sys.argv[1:]

    # Parse arguments
    skip_weather = "--skip-weather" in args
    args = [a for a in args if not a.startswith("--")]

    if "--from" in sys.argv:
        from_idx = sys.argv.index("--from")
        if from_idx + 1 < len(sys.argv):
            start_step = int(sys.argv[from_idx + 1])
            steps_to_run = [s for s in STEPS if s >= start_step]
        else:
            steps_to_run = list(STEPS.keys())
    elif args:
        steps_to_run = [int(a) for a in args if a.isdigit()]
    else:
        steps_to_run = list(STEPS.keys())

    if skip_weather:
        steps_to_run = [s for s in steps_to_run if s != 5]

    print("=" * 70)
    print("  HARVEST DATE PREDICTION — ML PIPELINE")
    print("=" * 70)
    print(f"\nSteps to run: {steps_to_run}")
    if skip_weather:
        print("  (Skipping weather fetch)")
    print()

    total_start = time.time()
    results = {}

    for step in steps_to_run:
        if step not in STEPS:
            print(f"Unknown step: {step}")
            continue

        success = run_step(step)
        results[step] = success

        if not success:
            print(f"\n[WARN]  Pipeline stopped at step {step}. Fix the error and re-run.")
            print(f"    To resume: python run_pipeline.py --from {step}")
            break

    total_elapsed = time.time() - total_start

    print(f"\n{'=' * 70}")
    print(f"  PIPELINE SUMMARY")
    print(f"{'=' * 70}")
    for step, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        name = STEPS[step][0]
        print(f"  {status} Step {step:2d}: {name}")
    print(f"\n  Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
