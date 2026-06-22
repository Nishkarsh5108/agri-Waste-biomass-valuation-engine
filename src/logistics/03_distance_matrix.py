import pandas as pd
import numpy as np
import json
from pathlib import Path
from math import radians, cos, sin, asin, sqrt

# Configuration
AVG_TRUCK_SPEED_KMH = 25.0
DATA_DIR = Path(__file__).parent.parent.parent / "data"

def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance in kilometers between two points on the earth."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers
    return c * r

def run():
    print("="*50)
    print("STEP 3: Distance & Time Matrix Calculation")
    print("="*50)

    in_path = DATA_DIR / "processed_routing_nodes.csv"
    if not in_path.exists():
        print(f"Error: {in_path} not found. Run step 02 first.")
        return
        
    df = pd.read_csv(in_path)
    nodes = df.to_dict('records')
    n = len(nodes)
    
    print(f"Loaded {n} nodes. Calculating {n}x{n} matrices...")
    
    # OR-Tools prefers integer matrices for exact solvers, so we will use integers
    distance_matrix = np.zeros((n, n), dtype=int)
    time_matrix = np.zeros((n, n), dtype=int)
    
    for i in range(n):
        for j in range(n):
            if i == j:
                distance_matrix[i][j] = 0
                time_matrix[i][j] = 0
            else:
                dist = haversine(nodes[i]['lon'], nodes[i]['lat'], nodes[j]['lon'], nodes[j]['lat'])
                
                # Scale distance to meters to keep it integer
                distance_matrix[i][j] = int(round(dist * 1000))
                
                # Convert to minutes: (dist / speed) * 60
                time_mins = (dist / AVG_TRUCK_SPEED_KMH) * 60
                
                # Add 20 minutes of fixed loading/unloading time if arriving at a farm
                if nodes[j]['node_id'] != 'DEPOT':
                    time_mins += 20
                
                time_matrix[i][j] = int(round(time_mins))
                
    # Save matrices
    dist_out = DATA_DIR / "distance_matrix.json"
    time_out = DATA_DIR / "time_matrix.json"
    
    with open(dist_out, 'w') as f:
        json.dump(distance_matrix.tolist(), f)
        
    with open(time_out, 'w') as f:
        json.dump(time_matrix.tolist(), f)
        
    print(f"Generated distance and time matrices successfully.")
    print(f"Saved to: {DATA_DIR.resolve()}")

if __name__ == "__main__":
    run()
