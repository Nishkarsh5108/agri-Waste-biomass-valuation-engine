import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import numpy as np
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.modules.auth.models import User, UserRole
from app.modules.farmers.models import Farm
from app.modules.listings.models import BiomassListing, ListingStatus

# ---------------------------------------------------------
# PatchTST Model Architecture (Copied from src)
# ---------------------------------------------------------

class BaseEncoder(nn.Module):
    def __init__(self, num_dim, cat_dims, embed_dim=8, hidden_dim=64):
        super().__init__()
        self.embeddings = nn.ModuleList([
            nn.Embedding(num_classes, embed_dim) for num_classes in cat_dims
        ])
        in_dim = num_dim + len(cat_dims) * embed_dim
        self.proj = nn.Linear(in_dim, hidden_dim)
        
    def forward(self, x_num, x_cat):
        embeds = []
        for i, emb in enumerate(self.embeddings):
            embeds.append(emb(x_cat[:, :, i]))
        if embeds:
            x_cat_emb = torch.cat(embeds, dim=-1)
            x_in = torch.cat([x_num, x_cat_emb], dim=-1)
        else:
            x_in = x_num
        return F.relu(self.proj(x_in))

class PatchTSTRegressor(nn.Module):
    def __init__(self, num_dim, cat_dims, seq_len=36, patch_len=6, stride=6, hidden_dim=64, d_model=128, n_heads=4, n_layers=3, dropout=0.2):
        super().__init__()
        self.seq_len = seq_len
        self.patch_len = patch_len
        self.stride = stride
        self.num_patches = seq_len // patch_len
        
        self.encoder = BaseEncoder(num_dim, cat_dims, hidden_dim=hidden_dim)
        self.patch_proj = nn.Linear(patch_len * hidden_dim, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, self.num_patches, d_model))
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_model * 2, dropout=dropout, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.head = nn.Linear(d_model, patch_len)
        
    def forward(self, x_num, x_cat, lengths=None):
        x = self.encoder(x_num, x_cat) 
        B, L, H = x.shape
        x_patched = x.view(B, self.num_patches, self.patch_len, H)
        x_patched = x_patched.view(B, self.num_patches, -1) 
        x_proj = self.patch_proj(x_patched)
        x_proj = x_proj + self.pos_embed
        out = self.transformer(x_proj)
        preds = self.head(out)
        preds = preds.view(B, L)
        return preds

# ---------------------------------------------------------
# Seeder Logic
# ---------------------------------------------------------

CATEGORICAL_FEATURES = ["district_code", "agro_zone", "variety_cluster", "growth_phase"]
EXCLUDE_COLS = [
    "point_id", "year", "date", "lat", "lon",
    "harvest_doy", "harvest_date", "days_to_harvest",
    "label_confidence", "ndvi_harvest_doy", "sar_harvest_doy",
    "split", ".geo", "system:index", "weight", "photoperiod"
]
RAW_BAND_COLS = ["B2", "B4", "B5", "B6", "B7", "B8", "B11", "B12"]
MAX_SEQ_LEN = 36

def get_polygon_wkt(lat: float, lon: float, area_hectares: float = 1.0) -> str:
    # 1 hectare = 10,000 sq meters = 100m x 100m square
    # 1 degree lat/lon is roughly 111,000 meters.
    # 100 meters / 111,000 = ~0.0009 degrees full width. 
    # Half width = 0.00045
    half_width = 0.00045 * (area_hectares ** 0.5)
    min_lat = lat - half_width
    max_lat = lat + half_width
    min_lon = lon - half_width
    max_lon = lon + half_width

    # WKT POLYGON((lon lat, lon lat, ...))
    # Must close the loop (start point == end point)
    polygon_str = f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, {max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    return f"SRID=4326;{polygon_str}"

async def seed_2025_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    data_path = os.path.join(base_dir, 'data', 'processed', 'training_data.csv')
    model_path = os.path.join(base_dir, 'models', 'patchtst_harvest.pth')

    if not os.path.exists(data_path):
        return {"error": "2025 dataset not found."}

    print("Loading 2025 test dataset...")
    df = pd.read_csv(data_path)
    # Filter for 2025 (test split)
    df = df[df["split"] == "test"].copy()
    
    if df.empty:
        return {"error": "No 2025 test data found in training_data.csv."}

    drop_cols = [c for c in EXCLUDE_COLS + RAW_BAND_COLS if c in df.columns]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in feature_cols]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in cat_cols:
        df[col] = df[col].astype("category").cat.codes.astype(np.int64)
        df[col] = np.maximum(df[col], 0)

    # Note: We need cat_dims for the model. 
    # Hardcoding based on earlier scripts: we can just find max value + 1, but best to load original or approximate
    # To be safe, we just use large enough embedding dims or dynamically get it from df
    cat_dims = [df[c].max() + 2 for c in cat_cols] 

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PatchTSTRegressor(
        num_dim=len(num_cols), cat_dims=cat_dims, seq_len=36, patch_len=6, stride=6,
        hidden_dim=64, d_model=128, n_heads=4, n_layers=3, dropout=0.2
    ).to(device)

    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location=device), strict=False)
    model.eval()

    db = AsyncSessionLocal()
    
    added_farms = 0
    print("Running PatchTST inference and generating users...")

    # Group by point_id
    for point_id, group in df.groupby("point_id"):
        group = group.sort_values("date")
        lat = group['lat'].iloc[0]
        lon = group['lon'].iloc[0]
        
        x_num = group[num_cols].values.astype(np.float32)
        x_cat = group[cat_cols].values.astype(np.int64)
        
        seq_len = len(x_num)
        if seq_len == 0: continue
        if seq_len > MAX_SEQ_LEN:
            x_num = x_num[-MAX_SEQ_LEN:]
            x_cat = x_cat[-MAX_SEQ_LEN:]
            seq_len = MAX_SEQ_LEN
            
        pad_len = MAX_SEQ_LEN - seq_len
        if pad_len > 0:
            x_num = np.pad(x_num, ((0, pad_len), (0, 0)), mode="constant", constant_values=0)
            x_cat = np.pad(x_cat, ((0, pad_len), (0, 0)), mode="constant", constant_values=0)
        
        x_num_t = torch.tensor(x_num).unsqueeze(0).to(device)
        x_cat_t = torch.tensor(x_cat).unsqueeze(0).to(device)

        with torch.no_grad():
            preds = model(x_num_t, x_cat_t)
            # The prediction is for each timestep. The last valid timestep is at seq_len - 1
            pred_days = preds[0, seq_len - 1].item()
            if pred_days < 0: pred_days = 5 # fallback

        # 1. Create User
        phone = f"+9120250{int(point_id):04d}"
        res = await db.execute(select(User).filter(User.phone_number == phone))
        user = res.scalars().first()
        if not user:
            user = User(
                phone_number=phone,
                hashed_password="mock_password",
                role=UserRole.FARMER
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # 2. Create Farm with Polygon
        res = await db.execute(select(Farm).filter(Farm.user_id == user.id))
        farm = res.scalars().first()
        if not farm:
            geom_wkt = get_polygon_wkt(lat, lon, area_hectares=1.0)
            farm = Farm(
                user_id=user.id,
                name=f"2025 Test Farm #{point_id}",
                area_hectares=1.0,
                geom=geom_wkt
            )
            db.add(farm)
            await db.commit()
            await db.refresh(farm)

        # 3. Create BiomassListing
        harvest_date = datetime.datetime.utcnow() + datetime.timedelta(days=pred_days)
        res = await db.execute(select(BiomassListing).filter(BiomassListing.farm_id == farm.id))
        listing = res.scalars().first()
        if not listing:
            estimated_tonnage = 5.0
            listing = BiomassListing(
                farm_id=farm.id,
                status=ListingStatus.READY,
                estimated_tonnage=estimated_tonnage,
                predicted_harvest_date=harvest_date,
                quality_score=9.0
            )
            db.add(listing)
            await db.commit()
            
        added_farms += 1

    await db.close()
    print(f"Successfully processed and seeded {added_farms} farms.")
    return {"status": "success", "seeded_farms": added_farms}
