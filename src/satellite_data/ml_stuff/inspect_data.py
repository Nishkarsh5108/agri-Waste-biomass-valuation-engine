"""Quick inspection script to understand data structure."""
import pandas as pd
import os

RAW = r"d:\Coding\Hackathon\samsung\agri-Waste-biomass-valuation-engine\data\sattelite_raw"
DATA = r"d:\Coding\Hackathon\samsung\agri-Waste-biomass-valuation-engine\data"

print("=" * 60)
print("SENTINEL-2 (2022)")
print("=" * 60)
df = pd.read_csv(os.path.join(RAW, "sentinel2_raw_2022.csv"))
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Unique points: {df['point_id'].nunique()}")
print(df.head(3).to_string())
print(f"\nNull counts:\n{df.isnull().sum()}")
print(f"\nDtypes:\n{df.dtypes}")

print("\n" + "=" * 60)
print("SENTINEL-2 (2025)")
print("=" * 60)
df25 = pd.read_csv(os.path.join(RAW, "sentinel2_raw_2025.csv"))
print(f"Shape: {df25.shape}")
print(f"Date range: {df25['date'].min()} to {df25['date'].max()}")
print(f"Columns: {list(df25.columns)}")

print("\n" + "=" * 60)
print("SENTINEL-1 (2022)")
print("=" * 60)
df1 = pd.read_csv(os.path.join(RAW, "sentinel1_raw_2022.csv"))
print(f"Shape: {df1.shape}")
print(f"Columns: {list(df1.columns)}")
print(f"Date range: {df1['date'].min()} to {df1['date'].max()}")
print(f"Unique points: {df1['point_id'].nunique()}")
print(df1.head(3).to_string())
print(f"\nNull counts:\n{df1.isnull().sum()}")

print("\n" + "=" * 60)
print("SENTINEL-1 (2025)")
print("=" * 60)
df1_25 = pd.read_csv(os.path.join(RAW, "sentinel1_raw_2025.csv"))
print(f"Shape: {df1_25.shape}")
print(f"Columns: {list(df1_25.columns)}")
print(f"Date range: {df1_25['date'].min()} to {df1_25['date'].max()}")

print("\n" + "=" * 60)
print("STATIC LAYERS")
print("=" * 60)
dfs = pd.read_csv(os.path.join(RAW, "static_layers.csv"))
print(f"Shape: {dfs.shape}")
print(f"Columns: {list(dfs.columns)}")
print(dfs.head(3).to_string())
print(f"\nNull counts:\n{dfs.isnull().sum()}")

print("\n" + "=" * 60)
print("SAMPLE POINTS")
print("=" * 60)
dfp = pd.read_csv(os.path.join(DATA, "sample_points.csv"))
print(f"Shape: {dfp.shape}")
print(f"Columns: {list(dfp.columns)}")
print(dfp.head(3).to_string())

# Check observations per point for S2
print("\n" + "=" * 60)
print("OBSERVATIONS PER POINT (S2 2022)")
print("=" * 60)
obs = df.groupby("point_id").size()
print(f"Mean obs/point: {obs.mean():.1f}")
print(f"Min: {obs.min()}, Max: {obs.max()}")
print(f"Median: {obs.median():.0f}")

# Check observations per point for S1
print("\n" + "=" * 60)
print("OBSERVATIONS PER POINT (S1 2022)")
print("=" * 60)
obs1 = df1.groupby("point_id").size()
print(f"Mean obs/point: {obs1.mean():.1f}")
print(f"Min: {obs1.min()}, Max: {obs1.max()}")
print(f"Median: {obs1.median():.0f}")
