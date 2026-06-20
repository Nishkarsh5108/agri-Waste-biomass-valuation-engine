"""
Step 13: PatchTST (Patch Time Series Transformer)

This script trains a state-of-the-art PatchTST model for our Sequence-to-Sequence regression task.
It builds on the data loading and training infrastructure from step_12_sequence_models.py.
"""
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import PROCESSED_DIR, MODELS_DIR, CATEGORICAL_FEATURES, EVAL_WINDOWS
from step_12_sequence_models import AgriSequenceDataset, BaseEncoder, train_model, EXCLUDE_COLS, RAW_BAND_COLS, BATCH_SIZE, EPOCHS, LEARNING_RATE, EARLY_STOPPING_PATIENCE

class PatchTSTRegressor(nn.Module):
    """
    PatchTST architecture adapted for sequence-to-sequence prediction.
    Instead of passing 36 individual timesteps to the transformer, we group them into
    non-overlapping patches (e.g., 6 patches of 6 days). The transformer applies attention
    over these patches to learn macroscopic phenological shapes (the NDVI "drop").
    """
    def __init__(self, num_dim, cat_dims, seq_len=36, patch_len=6, stride=6, hidden_dim=64, d_model=128, n_heads=4, n_layers=3, dropout=0.2):
        super().__init__()
        self.seq_len = seq_len
        self.patch_len = patch_len
        self.stride = stride
        
        # Must perfectly divide for this simple adaptation
        assert seq_len % patch_len == 0 and stride == patch_len, "seq_len must be divisible by patch_len"
        self.num_patches = seq_len // patch_len
        
        self.encoder = BaseEncoder(num_dim, cat_dims, hidden_dim=hidden_dim)
        
        # Patch projection (flatten patch and project to d_model)
        self.patch_proj = nn.Linear(patch_len * hidden_dim, d_model)
        
        # Learnable Positional Encoding for patches
        self.pos_embed = nn.Parameter(torch.randn(1, self.num_patches, d_model))
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=n_heads, 
            dim_feedforward=d_model * 2, 
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        
        # Output head (map each d_model patch back to 'patch_len' scalar predictions)
        self.head = nn.Linear(d_model, patch_len)
        
    def forward(self, x_num, x_cat, lengths=None):
        # 1. Base Encoding
        x = self.encoder(x_num, x_cat) # [B, 36, 64]
        B, L, H = x.shape
        
        # 2. Patching
        # Reshape into patches: [B, 6 patches, 6 timesteps, 64 hidden]
        x_patched = x.view(B, self.num_patches, self.patch_len, H)
        # Flatten patches: [B, 6 patches, 384]
        x_patched = x_patched.view(B, self.num_patches, -1) 
        
        # 3. Projection & Positional Encoding
        x_proj = self.patch_proj(x_patched) # [B, 6, 128]
        x_proj = x_proj + self.pos_embed
        
        # 4. Self-Attention over Patches
        out = self.transformer(x_proj) # [B, 6, 128]
        
        # 5. Prediction
        # Predict the 'days_to_harvest' for all timesteps within each patch
        preds = self.head(out) # [B, 6, 6]
        preds = preds.view(B, L) # Flatten back to [B, 36] to match LSTM output format
        
        return preds

def run():
    print("=" * 70)
    print("STEP 13: Patch Time Series Transformer (PatchTST)")
    print("=" * 70)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    df = pd.read_csv(PROCESSED_DIR / "training_data.csv")
    df = df[df["days_to_harvest"].notna() & (df["days_to_harvest"] > 0)].copy()
    
    drop_cols = [c for c in EXCLUDE_COLS + RAW_BAND_COLS if c in df.columns]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in feature_cols]
    num_cols = [c for c in feature_cols if c not in cat_cols]
    
    cat_dims = [df[c].nunique() + 1 for c in cat_cols]
        
    train_df = df[df["split"] == "train"].copy()
    val_df   = df[df["split"] == "val"].copy()
    
    train_dataset = AgriSequenceDataset(train_df, cat_cols, num_cols)
    val_dataset = AgriSequenceDataset(val_df, cat_cols, num_cols)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
    
    num_dim = len(num_cols)
    print(f"Numerical features: {num_dim}, Categorical features: {len(cat_cols)}")
    
    print("\n--- Training PatchTST ---")
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
    
    # We use a lower learning rate than LSTM as Transformers can be unstable initially
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    
    # We can reuse the train_model function from step 12
    model = train_model(model, train_loader, val_loader, None, optimizer, device, is_wtte=False, epochs=EPOCHS, patience=EARLY_STOPPING_PATIENCE)
    
    torch.save(model.state_dict(), MODELS_DIR / "patchtst_harvest.pth")
    print("Saved PatchTST model to models/patchtst_harvest.pth.")

if __name__ == "__main__":
    run()
