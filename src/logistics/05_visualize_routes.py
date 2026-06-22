import json
import pandas as pd
from pathlib import Path
import random

try:
    import folium
except ImportError:
    print("Error: folium not installed. Please run: pip install folium")
    exit(1)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

def run():
    print("="*50)
    print("STEP 5: Route Visualization")
    print("="*50)
    
    routes_path = DATA_DIR / "optimized_routes.json"
    nodes_path = DATA_DIR / "processed_routing_nodes.csv"
    
    if not routes_path.exists():
        print(f"Error: {routes_path} not found. Run step 04 first.")
        return
        
    with open(routes_path, 'r') as f:
        routes = json.load(f)
        
    nodes_df = pd.read_csv(nodes_path)
    nodes_dict = {row['node_id']: row for _, row in nodes_df.iterrows()}
    
    depot_node = nodes_dict['DEPOT']
    
    # Create base map centered at Depot
    m = folium.Map(location=[depot_node['lat'], depot_node['lon']], zoom_start=11)
    
    # Plot Depot
    folium.Marker(
        [depot_node['lat'], depot_node['lon']],
        popup="DEPOT",
        icon=folium.Icon(color="black", icon="home")
    ).add_to(m)
    
    # Calculate priority for each route (Max days waiting among all farms on the route)
    for r in routes:
        max_days = 0
        for stop in r['stops']:
            node_id = stop['node_id']
            if node_id != 'DEPOT':
                node_data = nodes_dict.get(node_id)
                if node_data is not None and 'days_since_harvest' in node_data:
                    days = node_data['days_since_harvest']
                    if pd.notna(days):
                        max_days = max(max_days, float(days))
        r['max_days_waiting'] = max_days
        
    # Sort routes descending by max_days_waiting (highest priority first)
    routes.sort(key=lambda x: x['max_days_waiting'], reverse=True)
    
    # Define a priority color scale (Red -> Orange -> Green -> Blue)
    priority_colors = [
        'darkred', 'red', 'orange', 'green', 'blue', 'purple', 
        'darkblue', 'cadetblue', 'darkpurple', 'lightgray'
    ]
    
    for idx, r in enumerate(routes):
        truck_id = r['truck_id']
        stops = r['stops']
        max_days = r['max_days_waiting']
        dispatch_order = idx + 1
        
        # Assign color based on sorted rank (top priority gets darkred, etc.)
        color_idx = int((idx / max(1, len(routes) - 1)) * (len(priority_colors) - 1))
        color = priority_colors[color_idx]
        
        coordinates = []
        for stop in stops:
            node_id = stop['node_id']
            node_data = nodes_dict.get(node_id)
            if node_data is None:
                continue
                
            lat, lon = node_data['lat'], node_data['lon']
            coordinates.append([lat, lon])
            
            # Don't plot the depot marker again
            if node_id != 'DEPOT':
                days_waiting = node_data.get('days_since_harvest', 'N/A')
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    popup=f"<b>Farm:</b> {node_id}<br><b>Pickup:</b> {stop['load_kg']} kg<br><b>Arrival:</b> {stop['arrival_min']} min<br><b>Waiting:</b> {days_waiting} days",
                    color=color,
                    fill=True,
                    fillColor=color
                ).add_to(m)
                
        # Draw the route line
        folium.PolyLine(
            coordinates,
            weight=4,
            color=color,
            opacity=0.8,
            popup=f"<b>Dispatch Order:</b> #{dispatch_order}<br><b>Truck:</b> {truck_id}<br><b>Priority:</b> {max_days} Days Max Wait"
        ).add_to(m)
        
    out_map = DATA_DIR / "logistics_routes_map.html"
    m.save(str(out_map))
    
    print(f"Plotted {len(routes)} trucks.")
    print(f"Interactive map saved to: {out_map.resolve()}")
    print("Open this HTML file in your web browser to view the routes!")

if __name__ == "__main__":
    run()
