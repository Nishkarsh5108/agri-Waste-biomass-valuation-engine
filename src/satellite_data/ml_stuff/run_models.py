"""
Master Models Runner — Orchestrates only the modeling steps.

Usage:
    python run_models.py              # Run all modeling steps
    python run_models.py 10 11        # Run specific models only
    python run_models.py --from 10    # Run from step 10 onwards

Steps:
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

    print("=" * 70)
    print("  HARVEST DATE PREDICTION — MODEL RUNNER")
    print("=" * 70)
    print(f"\nSteps to run: {steps_to_run}")
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
            print(f"    To resume: python run_models.py --from {step}")
            break

    total_elapsed = time.time() - total_start

    print(f"\n{'=' * 70}")
    print(f"  MODEL RUN SUMMARY")
    print(f"{'=' * 70}")
    for step, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        name = STEPS[step][0]
        print(f"  {status} Step {step:2d}: {name}")
    print(f"\n  Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
