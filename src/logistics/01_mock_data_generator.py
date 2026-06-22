import pandas as pd
import numpy as np
import os
from pathlib import Path

# Configuration
NUM_FARMS = 100
# Ludhiana, Punjab coordinates roughly
DEPOT_LAT = 30.900965
DEPOT_LON = 75.857277
RADIUS_DEG = 0.5  # roughly 50km radius

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data"

def run():
    print("="*50)
    print("STEP 1: Generating Mock Farm Requests")
    print("="*50)

    # Ensure output dir exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    np.random.seed(42)  # For reproducibility

    data = []
    
    # Add the depot as the first node (index 0)
    data.append({
        "node_id": "DEPOT",
        "lat": DEPOT_LAT,
        "lon": DEPOT_LON,
        "biomass_tonnage": 0.0,
        "days_since_harvest": 999,  # N/A
        "time_window_start_hr": 0,  # Open 24/7 or early
        "time_window_end_hr": 24
    })
    
    for i in range(1, NUM_FARMS + 1):
        # Generate random lat/lon within radius
        lat = DEPOT_LAT + np.random.uniform(-RADIUS_DEG, RADIUS_DEG)
        lon = DEPOT_LON + np.random.uniform(-RADIUS_DEG, RADIUS_DEG)
        
        # Random tonnage (between 5 and 35 tons)
        tonnage = np.round(np.random.uniform(5.0, 35.0), 1)
        
        # Days since harvest (urgency)
        days = np.random.randint(1, 21)
        
        # Time windows (e.g. farmer is available between start and end hours)
        # Start time between 6 AM and 10 AM
        start_hr = np.random.randint(6, 11)
        # End time between 4 PM (16) and 8 PM (20)
        end_hr = np.random.randint(16, 21)
        
        data.append({
            "node_id": f"FARM_{i:03d}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "biomass_tonnage": tonnage,
            "days_since_harvest": days,
            "time_window_start_hr": start_hr,
            "time_window_end_hr": end_hr
        })
        
    df = pd.DataFrame(data)
    
    out_path = OUTPUT_DIR / "mock_farm_requests.csv"
    df.to_csv(out_path, index=False)
    
    print(f"Generated {NUM_FARMS} farm requests + 1 Depot.")
    print(f"Total theoretical biomass available: {df['biomass_tonnage'].sum():.1f} tons")
    print(f"Saved to: {out_path.resolve()}")

if __name__ == "__main__":
    run()
