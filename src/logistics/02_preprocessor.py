import pandas as pd
import numpy as np
from pathlib import Path

# Configuration
MAX_TRUCK_CAPACITY = 15.0  # Tons
URGENCY_THRESHOLD_DAYS = 3 # Don't route farms younger than 3 days

DATA_DIR = Path(__file__).parent.parent.parent / "data"

def run():
    print("="*50)
    print("STEP 2: Data Preprocessing & Split Delivery Hack")
    print("="*50)

    in_path = DATA_DIR / "mock_farm_requests.csv"
    if not in_path.exists():
        print(f"Error: {in_path} not found. Run step 01 first.")
        return
        
    df = pd.read_csv(in_path)
    print(f"Loaded {len(df)} nodes (including Depot).")
    
    # Process Depot separately
    depot_df = df[df['node_id'] == 'DEPOT'].copy()
    farms_df = df[df['node_id'] != 'DEPOT'].copy()
    
    # 1. Urgency Filter (Only route farms that have been waiting >= 3 days)
    # This artificially reduces the search space and focuses on priority
    urgent_farms = farms_df[farms_df['days_since_harvest'] >= URGENCY_THRESHOLD_DAYS].copy()
    print(f"Filtered out {len(farms_df) - len(urgent_farms)} farms (too recent).")
    print(f"Remaining urgent farms to route: {len(urgent_farms)}")
    
    # 2. Split Delivery Preprocessing
    processed_nodes = []
    
    # Add depot back in
    processed_nodes.append(depot_df.iloc[0].to_dict())
    
    split_count = 0
    for _, row in urgent_farms.iterrows():
        tonnage = row['biomass_tonnage']
        farm_id = row['node_id']
        
        if tonnage <= MAX_TRUCK_CAPACITY:
            # Fits in one truck, just add it
            processed_nodes.append(row.to_dict())
        else:
            # Exceeds truck capacity, we must split it into multiple virtual nodes
            split_count += 1
            remaining = tonnage
            part_idx = 1
            
            while remaining > 0:
                chunk = min(remaining, MAX_TRUCK_CAPACITY)
                
                new_row = row.to_dict()
                new_row['node_id'] = f"{farm_id}_PART{part_idx}"
                new_row['biomass_tonnage'] = round(chunk, 1)
                
                processed_nodes.append(new_row)
                
                remaining -= chunk
                part_idx += 1
                
    processed_df = pd.DataFrame(processed_nodes)
    
    out_path = DATA_DIR / "processed_routing_nodes.csv"
    processed_df.to_csv(out_path, index=False)
    
    print(f"\nSplit {split_count} farms that exceeded truck capacity ({MAX_TRUCK_CAPACITY} tons).")
    print(f"Final routable nodes generated: {len(processed_df)} (including Depot).")
    print(f"Total routable biomass: {processed_df['biomass_tonnage'].sum():.1f} tons")
    print(f"Saved to: {out_path.resolve()}")

if __name__ == "__main__":
    run()
