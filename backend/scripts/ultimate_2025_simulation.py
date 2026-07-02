import os
import sys
import asyncio
import glob
import datetime
import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from supabase import create_client, Client
from app.core.database import AsyncSessionLocal
from app.modules.auth.models import User, UserRole
from app.modules.farmers.models import Farm
from app.modules.listings.models import BiomassListing, ListingStatus
from app.worker.tasks import process_cv_density
from sqlalchemy.future import select

# ---------------------------------------------------------
# PatchTST Model Architecture (Copied from step 13)
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
    half_width = 0.00045 * (area_hectares ** 0.5)
    min_lat, max_lat = lat - half_width, lat + half_width
    min_lon, max_lon = lon - half_width, lon + half_width
    polygon_str = f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, {max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    return f"SRID=4326;{polygon_str}"

async def run_ultimate_simulation():
    print("="*60)
    print("STARTING ULTIMATE 2025 KHARIF SEASON SIMULATION")
    print("="*60)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(base_dir)
    data_path = os.path.join(project_root, 'data', 'processed', 'training_data.csv')
    model_path = os.path.join(project_root, 'models', 'patchtst_harvest.pth')
    image_dir = os.path.join(project_root, 'data', 'Stubble')
    
    # 1. Setup Supabase
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 2. Get Stubble Images
    images = glob.glob(os.path.join(image_dir, "*.jpg")) + glob.glob(os.path.join(image_dir, "*.jpeg")) + glob.glob(os.path.join(image_dir, "*.png"))
    if not images:
        print(f"No images found in {image_dir}")
        return
    num_to_simulate = min(50, len(images))
    print(f"Found {len(images)} images. We will simulate {num_to_simulate} farms.")

    # 3. Load 2025 Data
    print("Loading preprocessed 2025 satellite data (training_data.csv)...")
    df_full = pd.read_csv(data_path)
    
    drop_cols = [c for c in EXCLUDE_COLS + RAW_BAND_COLS if c in df_full.columns]
    feature_cols = [c for c in df_full.columns if c not in drop_cols]
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in feature_cols]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    for col in num_cols: df_full[col] = pd.to_numeric(df_full[col], errors="coerce").fillna(0.0)
    for col in cat_cols:
        df_full[col] = df_full[col].astype("category").cat.codes.astype(np.int64)
        df_full[col] = np.maximum(df_full[col], 0)

    # Calculate cat_dims on the FULL dataset so it perfectly matches training
    cat_dims = []
    for c in cat_cols:
        cat_dims.append(df_full[c].nunique() + 1)
        
    df = df_full[df_full["split"] == "test"].copy()

    # 4. Load LSTM Model
    model_path = os.path.join(project_root, 'models', 'lstm_harvest.pth')
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMRegressor(
        num_dim=len(num_cols), cat_dims=cat_dims, hidden_dim=64
    ).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device), strict=False)
    model.eval()

    # 5. Process Farms
    added_farms = 0
    unique_points = df["point_id"].unique()
    
    # Pick a random center point
    import random
    center_point = np.random.choice(unique_points)
    center_data = df[df["point_id"] == center_point].iloc[0]
    center_lat, center_lon = center_data["lat"], center_data["lon"]
    
    # Calculate squared distance to center for all unique points
    point_dists = []
    for pid in unique_points:
        pdata = df[df["point_id"] == pid].iloc[0]
        dist = (pdata["lat"] - center_lat)**2 + (pdata["lon"] - center_lon)**2
        point_dists.append((dist, pid))
    
    # Sort and pick the num_to_simulate closest points (forming a tight cluster)
    point_dists.sort()
    sampled_points = [pid for _, pid in point_dists[:num_to_simulate]]

    for idx, point_id in enumerate(sampled_points):
        group = df[df["point_id"] == point_id].sort_values("date")
        # Override actual lat/lon with a synthetic tight cluster around the center point (within ~2km)
        lat = center_lat + random.uniform(-0.02, 0.02)
        lon = center_lon + random.uniform(-0.02, 0.02)
        
        # --- AI 1: SATELLITE HARVEST PREDICTION ---
        x_num = group[num_cols].values.astype(np.float32)
        x_cat = group[cat_cols].values.astype(np.int64)
        
        # Simulate being 2 to 6 timesteps (10 to 30 days) BEFORE harvest
        # by dropping the end of the sequence!
        drop_steps = np.random.randint(2, 7)
        if len(x_num) > drop_steps:
            x_num = x_num[:-drop_steps]
            x_cat = x_cat[:-drop_steps]
            
        seq_len = len(x_num)
        
        if seq_len > MAX_SEQ_LEN:
            x_num, x_cat = x_num[-MAX_SEQ_LEN:], x_cat[-MAX_SEQ_LEN:]
            seq_len = MAX_SEQ_LEN
        pad_len = MAX_SEQ_LEN - seq_len
        if pad_len > 0:
            x_num = np.pad(x_num, ((0, pad_len), (0, 0)), mode="constant", constant_values=0)
            x_cat = np.pad(x_cat, ((0, pad_len), (0, 0)), mode="constant", constant_values=0)
        
        with torch.no_grad():
            preds = model(torch.tensor(x_num).unsqueeze(0).to(device), torch.tensor(x_cat).unsqueeze(0).to(device))
            pred_days = max(0, preds[0, seq_len - 1].item())
        harvest_date = datetime.datetime.utcnow() + datetime.timedelta(days=pred_days)

        # --- SUPABASE UPLOAD ---
        image_path = images[idx]
        file_name = os.path.basename(image_path)
        print(f"[{idx+1}/{num_to_simulate}] Simulating Farm #{point_id} | Harvest in {int(pred_days)} days | Uploading {file_name}...")
        
        with open(image_path, "rb") as f: file_bytes = f.read()
        storage_path = f"kharif_2025/{point_id}_{file_name}"
        try:
            supabase.storage.from_("biomass-photos").upload(file=file_bytes, path=storage_path, file_options={"content-type": "image/jpeg", "upsert": "true"})
        except Exception as e:
            # Suppress error if file already exists
            pass
        public_url = supabase.storage.from_("biomass-photos").get_public_url(storage_path)

        # --- DATABASE INSERTS (Short-lived session) ---
        async with AsyncSessionLocal() as db:
            phone = f"+9120250{int(point_id):04d}"
            user = (await db.execute(select(User).filter(User.phone_number == phone))).scalars().first()
            if not user:
                user = User(phone_number=phone, hashed_password="mock_password", role=UserRole.FARMER)
                db.add(user)
                await db.commit()
                await db.refresh(user)

            farm = (await db.execute(select(Farm).filter(Farm.user_id == user.id))).scalars().first()
            farm_area = round(random.uniform(0.5, 5.0), 2)
            if not farm:
                farm = Farm(user_id=user.id, name=f"2025 Test Farm #{point_id}", area_hectares=farm_area, geom=get_polygon_wkt(lat, lon, farm_area))
                db.add(farm)
            else:
                farm.area_hectares = farm_area
                farm.geom = get_polygon_wkt(lat, lon, farm_area)
            await db.commit()
            await db.refresh(farm)

            # --- CREATE LISTING & TRIGGER YOLO ---
            listing = (await db.execute(select(BiomassListing).filter(BiomassListing.farm_id == farm.id))).scalars().first()
            if not listing:
                listing = BiomassListing(
                    farm_id=farm.id,
                    status=ListingStatus.PROCESSING,
                    photo_s3_url=public_url,
                    predicted_harvest_date=harvest_date
                )
                db.add(listing)
            else:
                listing.status = ListingStatus.PROCESSING
                listing.photo_s3_url = public_url
                listing.predicted_harvest_date = harvest_date
                listing.cv_density_ratio = None
                listing.estimated_tonnage = None
            
            await db.commit()
            await db.refresh(listing)
            
            # --- AI 2: TRIGGER CV YOLO ---
            process_cv_density.delay(listing.id)

        added_farms += 1

    print("="*60)
    print(f"Simulation setup complete! {added_farms} farms queued for YOLO inference.")
    print("Keep your Celery worker running to process the images.")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_ultimate_simulation())
