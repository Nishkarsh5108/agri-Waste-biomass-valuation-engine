"""
Step 12: Sequence Models (LSTM, WTTE-RNN, Transformer)

Input:  data/processed/training_data.csv
Output: models/lstm_harvest.pth, models/wtte_harvest.pth
        Printed evaluation metrics

This script implements deep sequential learning models for harvest prediction.
It reconstructs time-series sequences from the training data and trains causal models.
"""
import pandas as pd
import numpy as np
import json
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, MODELS_DIR,
    CATEGORICAL_FEATURES, EVAL_WINDOWS
)

# Configuration for Sequences
MAX_SEQ_LEN = 36  # ~180 days at 5-day resolution
BATCH_SIZE = 128
EPOCHS = 300
LEARNING_RATE = 1e-3
EARLY_STOPPING_PATIENCE = 25

# Exclude from inputs
EXCLUDE_COLS = [
    "point_id", "year", "date", "lat", "lon",
    "harvest_doy", "harvest_date", "days_to_harvest",
    "label_confidence", "ndvi_harvest_doy", "sar_harvest_doy",
    "split", ".geo", "system:index", "weight", "photoperiod"
]

RAW_BAND_COLS = ["B2", "B4", "B5", "B6", "B7", "B8", "B11", "B12"]


class AgriSequenceDataset(Dataset):
    """
    Groups flattened time-step data back into sequences.
    """
    def __init__(self, df: pd.DataFrame, cat_cols: list, num_cols: list):
        self.cat_cols = cat_cols
        self.num_cols = num_cols
        
        # We need weights
        weights = np.ones(len(df), dtype=np.float32)
        if "label_confidence" in df.columns:
            conf = df["label_confidence"].values
            weights = np.where(conf == "high", 1.0,
                      np.where(conf == "medium", 0.5,
                      np.where(conf == "low", 0.1, 1.0)))
        df["weight"] = weights

        # Fill NaNs
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        for col in cat_cols:
            df[col] = df[col].astype("category").cat.codes.astype(np.int64)
            # handle -1 from NaNs
            df[col] = np.maximum(df[col], 0)

        # Group by trajectory
        print("Grouping sequences...")
        self.sequences = []
        for _, group in df.groupby(["point_id", "year"]):
            group = group.sort_values("date")
            
            x_num = group[num_cols].values.astype(np.float32)
            x_cat = group[cat_cols].values.astype(np.int64)
            y = group["days_to_harvest"].values.astype(np.float32)
            w = group["weight"].values.astype(np.float32)
            
            seq_len = len(x_num)
            if seq_len == 0: continue
                
            # Truncate if too long (take the most recent steps before harvest)
            if seq_len > MAX_SEQ_LEN:
                x_num = x_num[-MAX_SEQ_LEN:]
                x_cat = x_cat[-MAX_SEQ_LEN:]
                y = y[-MAX_SEQ_LEN:]
                w = w[-MAX_SEQ_LEN:]
                seq_len = MAX_SEQ_LEN
                
            # Pad sequences
            pad_len = MAX_SEQ_LEN - seq_len
            if pad_len > 0:
                x_num = np.pad(x_num, ((0, pad_len), (0, 0)), mode="constant", constant_values=0)
                x_cat = np.pad(x_cat, ((0, pad_len), (0, 0)), mode="constant", constant_values=0)
                y = np.pad(y, (0, pad_len), mode="constant", constant_values=-1.0) # -1 is masked
                w = np.pad(w, (0, pad_len), mode="constant", constant_values=0.0)
            
            self.sequences.append((
                torch.tensor(x_num),
                torch.tensor(x_cat),
                torch.tensor(y),
                torch.tensor(w),
                torch.tensor(seq_len, dtype=torch.long)
            ))
            
    def __len__(self):
        return len(self.sequences)
        
    def __getitem__(self, idx):
        return self.sequences[idx]


class BaseEncoder(nn.Module):
    """Encodes numeric and categorical features into a common representation."""
    def __init__(self, num_dim, cat_dims, embed_dim=8, hidden_dim=64):
        super().__init__()
        self.embeddings = nn.ModuleList([
            nn.Embedding(num_classes, embed_dim) for num_classes in cat_dims
        ])
        
        in_dim = num_dim + len(cat_dims) * embed_dim
        self.proj = nn.Linear(in_dim, hidden_dim)
        
    def forward(self, x_num, x_cat):
        # x_cat shape: (B, T, num_cats)
        embeds = []
        for i, emb in enumerate(self.embeddings):
            embeds.append(emb(x_cat[:, :, i]))
            
        if embeds:
            x_cat_emb = torch.cat(embeds, dim=-1)
            x_in = torch.cat([x_num, x_cat_emb], dim=-1)
        else:
            x_in = x_num
            
        return F.relu(self.proj(x_in))


class LSTMRegressor(nn.Module):
    """Standard sequence-to-sequence LSTM predicting days_to_harvest at each step."""
    def __init__(self, num_dim, cat_dims, hidden_dim=64):
        super().__init__()
        self.encoder = BaseEncoder(num_dim, cat_dims, hidden_dim=hidden_dim)
        # MUST be batch_first=True, bidirectional=False (strict causality)
        self.lstm = nn.LSTM(hidden_dim, hidden_dim, num_layers=2, batch_first=True)
        self.out = nn.Linear(hidden_dim, 1)
        
    def forward(self, x_num, x_cat, lengths=None):
        x = self.encoder(x_num, x_cat)
        out, _ = self.lstm(x)
        preds = self.out(out).squeeze(-1)
        return preds


class WTTERNN(nn.Module):
    """
    Weibull Time-To-Event RNN.
    Outputs Alpha and Beta for a Weibull survival distribution.
    """
    def __init__(self, num_dim, cat_dims, hidden_dim=64):
        super().__init__()
        self.encoder = BaseEncoder(num_dim, cat_dims, hidden_dim=hidden_dim)
        self.lstm = nn.LSTM(hidden_dim, hidden_dim, num_layers=2, batch_first=True)
        self.out_alpha = nn.Linear(hidden_dim, 1)
        self.out_beta = nn.Linear(hidden_dim, 1)
        
    def forward(self, x_num, x_cat, lengths=None):
        x = self.encoder(x_num, x_cat)
        out, _ = self.lstm(x)
        
        # Alpha > 0 (Scale parameter)
        alpha = F.softplus(self.out_alpha(out)).squeeze(-1) + 1e-5
        
        # Beta > 0 (Shape parameter)
        beta = F.softplus(self.out_beta(out)).squeeze(-1) + 1e-5
        
        return alpha, beta


def wtte_loss(y_true, alpha, beta, mask, weight):
    """
    Negative Log-Likelihood of the Weibull distribution.
    Assumes fully observed (uncensored) events since we have historical harvest dates.
    f(t) = (beta/alpha) * (t/alpha)^(beta-1) * exp(-(t/alpha)^beta)
    Log f(t) = log(beta) - log(alpha) + (beta-1)*(log(y) - log(alpha)) - (y/alpha)^beta
    """
    y_true = torch.clamp(y_true, min=1e-5) # Prevent log(0)
    
    term1 = torch.log(beta) - torch.log(alpha)
    term2 = (beta - 1) * (torch.log(y_true) - torch.log(alpha))
    term3 = -torch.pow(y_true / alpha, beta)
    
    log_lik = term1 + term2 + term3
    
    # Apply padding mask and confidence weights
    loss = -log_lik * mask * weight
    return loss.sum() / (mask.sum() + 1e-5)


def train_model(model, train_loader, val_loader, criterion, optimizer, device, is_wtte=False, epochs=EPOCHS, patience=EARLY_STOPPING_PATIENCE):
    best_val_loss = float('inf')
    best_model_state = None
    epochs_no_improve = 0
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        n_batches = 0
        
        for x_num, x_cat, y, w, lengths in train_loader:
            x_num, x_cat, y, w = x_num.to(device), x_cat.to(device), y.to(device), w.to(device)
            mask = (y != -1.0).float()
            
            optimizer.zero_grad()
            
            if is_wtte:
                alpha, beta = model(x_num, x_cat)
                loss = wtte_loss(y, alpha, beta, mask, w)
            else:
                preds = model(x_num, x_cat)
                # MSE loss on active sequence elements
                loss = (F.mse_loss(preds, y, reduction='none') * mask * w).sum() / (mask.sum() + 1e-5)
                
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            n_batches += 1
            
        # Validation
        model.eval()
        val_loss = 0.0
        val_mae = 0.0
        val_mask_sum = 0
        
        with torch.no_grad():
            for x_num, x_cat, y, w, lengths in val_loader:
                x_num, x_cat, y, w = x_num.to(device), x_cat.to(device), y.to(device), w.to(device)
                mask = (y != -1.0).float()
                
                if is_wtte:
                    alpha, beta = model(x_num, x_cat)
                    v_loss = wtte_loss(y, alpha, beta, mask, w)
                    # Expected value of Weibull is alpha * Gamma(1 + 1/beta). 
                    # Approximation: Mode = alpha * ((beta - 1) / beta) ** (1/beta) if beta > 1 else 0
                    # For simplicity, we use alpha as a rough median proxy during training metrics
                    preds = alpha
                else:
                    preds = model(x_num, x_cat)
                    v_loss = (F.mse_loss(preds, y, reduction='none') * mask * w).sum() / (mask.sum() + 1e-5)
                
                val_loss += v_loss.item()
                val_mae += (torch.abs(preds - y) * mask).sum().item()
                val_mask_sum += mask.sum().item()
                
        train_loss /= n_batches
        val_loss /= len(val_loader)
        val_mae /= (val_mask_sum + 1e-5)
        
        print(f"Epoch {epoch+1:03d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val MAE: {val_mae:.2f}")
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = {k: v.cpu() for k, v in model.state_dict().items()}
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            
        if epochs_no_improve >= patience:
            print(f"Early stopping triggered! No improvement for {patience} epochs.")
            break
            
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    return model


def run():
    print("=" * 70)
    print("STEP 12: Sequence Models (LSTM, WTTE-RNN)")
    print("=" * 70)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    df = pd.read_csv(PROCESSED_DIR / "training_data.csv")
    df = df[df["days_to_harvest"].notna() & (df["days_to_harvest"] > 0)].copy()
    
    # Feature setup
    drop_cols = [c for c in EXCLUDE_COLS + RAW_BAND_COLS if c in df.columns]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in feature_cols]
    num_cols = [c for c in feature_cols if c not in cat_cols]
    
    # Categorical dims
    cat_dims = []
    for c in cat_cols:
        cat_dims.append(df[c].nunique() + 1) # +1 for unknown
        
    train_df = df[df["split"] == "train"].copy()
    val_df   = df[df["split"] == "val"].copy()
    
    train_dataset = AgriSequenceDataset(train_df, cat_cols, num_cols)
    val_dataset = AgriSequenceDataset(val_df, cat_cols, num_cols)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
    
    num_dim = len(num_cols)
    print(f"Numerical features: {num_dim}, Categorical features: {len(cat_cols)}")
    
    # -------------------------
    # Train Standard LSTM
    # -------------------------
    print("\n--- Training LSTM Regressor ---")
    lstm_model = LSTMRegressor(num_dim, cat_dims).to(device)
    optimizer = torch.optim.Adam(lstm_model.parameters(), lr=LEARNING_RATE)
    lstm_model = train_model(lstm_model, train_loader, val_loader, None, optimizer, device, is_wtte=False)
    
    torch.save(lstm_model.state_dict(), MODELS_DIR / "lstm_harvest.pth")
    print("Saved LSTM model.")
    
    # -------------------------
    # Train WTTE-RNN
    # -------------------------
    print("\n--- Training WTTE-RNN ---")
    wtte_model = WTTERNN(num_dim, cat_dims).to(device)
    wtte_optimizer = torch.optim.Adam(wtte_model.parameters(), lr=LEARNING_RATE)
    wtte_model = train_model(wtte_model, train_loader, val_loader, None, wtte_optimizer, device, is_wtte=True)
    
    torch.save(wtte_model.state_dict(), MODELS_DIR / "wtte_harvest.pth")
    print("Saved WTTE-RNN model.")

if __name__ == "__main__":
    run()
