"""
Step 13a: Evaluate PatchTST on Unseen Test Set

This script loads the trained PatchTST model and evaluates it STRICTLY on the held-out
Test Set (2025 data). This provides the final, unbiased production metric for the pipeline.
"""
import pandas as pd
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import PROCESSED_DIR, MODELS_DIR, CATEGORICAL_FEATURES
from step_12_sequence_models import AgriSequenceDataset, EXCLUDE_COLS, RAW_BAND_COLS, BATCH_SIZE
from step_13_patchtst_model import PatchTSTRegressor

def run():
    print("=" * 70)
    print("STEP 13a: Final Test Set Evaluation (PatchTST)")
    print("=" * 70)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # 1. Load Data
    df = pd.read_csv(PROCESSED_DIR / "training_data.csv")
    df = df[df["days_to_harvest"].notna() & (df["days_to_harvest"] > 0)].copy()
    
    # 2. Extract Features
    drop_cols = [c for c in EXCLUDE_COLS + RAW_BAND_COLS if c in df.columns]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in feature_cols]
    num_cols = [c for c in feature_cols if c not in cat_cols]
    num_dim = len(num_cols)
    cat_dims = [df[c].nunique() + 1 for c in cat_cols]
    
    # 3. Filter for TEST split only (2025)
    test_df = df[df["split"] == "test"].copy()
    print(f"Test Set Rows: {len(test_df)}")
    if len(test_df) == 0:
        print("ERROR: Test set is empty! Make sure 2025 data is correctly labeled with 'test' split.")
        return
        
    test_dataset = AgriSequenceDataset(test_df, cat_cols, num_cols)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # 4. Load Model
    model_path = MODELS_DIR / "patchtst_harvest.pth"
    if not model_path.exists():
        print(f"ERROR: Model file {model_path} not found. Train step_13 first.")
        return
        
    model = PatchTSTRegressor(
        num_dim=num_dim, 
        cat_dims=cat_dims, 
        seq_len=36, 
        patch_len=6, 
        stride=6, 
        hidden_dim=64, 
        d_model=128, 
        n_heads=4, 
        n_layers=3, 
        dropout=0.2
    ).to(device)
    
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    print("Model loaded successfully.\n")
    
    # 5. Evaluate
    test_loss = 0.0
    test_mae = 0.0
    test_mask_sum = 0
    
    print("Evaluating on Test Set...")
    with torch.no_grad():
        for x_num, x_cat, y, w, lengths in test_loader:
            x_num, x_cat, y, w = x_num.to(device), x_cat.to(device), y.to(device), w.to(device)
            mask = (y != -1.0).float()
            
            preds = model(x_num, x_cat)
            
            # Unweighted MAE for pure physical days difference
            mae_sum = (torch.abs(preds - y) * mask).sum().item()
            
            test_mae += mae_sum
            test_mask_sum += mask.sum().item()
            
    final_mae = test_mae / (test_mask_sum + 1e-5)
    
    print(f"\n{'*' * 40}")
    print(f"FINAL TEST MAE: {final_mae:.2f} days")
    print(f"{'*' * 40}\n")
    
    print("This metric represents the true, unbiased accuracy of the model on the 2025 harvest season.")

if __name__ == "__main__":
    run()
