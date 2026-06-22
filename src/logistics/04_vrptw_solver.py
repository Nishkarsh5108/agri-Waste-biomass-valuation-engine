import json
import pandas as pd
from pathlib import Path

try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
except ImportError:
    print("Error: ortools not installed. Please run: pip install ortools")
    exit(1)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

def create_data_model():
    """Stores the data for the problem."""
    data = {}
    
    # Load matrices
    with open(DATA_DIR / 'time_matrix.json', 'r') as f:
        data['time_matrix'] = json.load(f)
        
    # Load nodes
    nodes_df = pd.read_csv(DATA_DIR / 'processed_routing_nodes.csv')
    
    # Demands (convert tons to kg for integer math)
    data['demands'] = [int(tons * 1000) for tons in nodes_df['biomass_tonnage']]
    
    # Time Windows (in minutes from start of day 00:00)
    time_windows = []
    for _, row in nodes_df.iterrows():
        start_min = int(row['time_window_start_hr'] * 60)
        end_min = int(row['time_window_end_hr'] * 60)
        time_windows.append((start_min, end_min))
    
    data['time_windows'] = time_windows
    data['num_vehicles'] = 15 # Assume we have 15 trucks available
    data['vehicle_capacities'] = [15000] * data['num_vehicles'] # 15 tons = 15000 kg
    data['depot'] = 0
    data['nodes'] = nodes_df.to_dict('records')
    
    return data

def run():
    print("="*50)
    print("STEP 4: OR-Tools VRPTW Solver")
    print("="*50)
    
    data = create_data_model()
    
    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(
        len(data['time_matrix']), data['num_vehicles'], data['depot']
    )
    
    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)
    
    # Create and register a transit callback (time).
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['time_matrix'][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    
    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Add Capacity constraint.
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
        
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        data['vehicle_capacities'],  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity'
    )
    
    # Add Time Window constraint.
    time = 'Time'
    routing.AddDimension(
        transit_callback_index,
        60,  # allow waiting time (e.g. arrive early and wait up to 60 mins)
        1440,  # maximum time per vehicle (24 hours)
        False,  # Don't force start cumul to zero
        time
    )
    time_dimension = routing.GetDimensionOrDie(time)
    
    # Add soft time window constraints.
    for node_idx, time_window in enumerate(data['time_windows']):
        if node_idx == data['depot']:
            continue
        index = manager.NodeToIndex(node_idx)
        # Soft Time Window: If we arrive after the farm's requested end time, we pay a penalty, 
        # but the node is NOT completely dropped from the route.
        time_dimension.SetCumulVarSoftUpperBound(index, time_window[1], 100) # Penalty of 100 per minute late
        # We still set a hard upper bound to midnight (1440 mins)
        time_dimension.CumulVar(index).SetRange(time_window[0], 1440)
        
    # Allow dropping nodes (for a massive penalty) if we don't have enough trucks.
    penalty = 1000000
    for node in range(1, len(data['time_matrix'])):
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(10) # 10 second solve limit for MVP

    print("Solving the VRP with Soft Time Windows...")
    solution = routing.SolveWithParameters(search_parameters)
    
    if solution:
        print("Solution found!")
        
        routes = []
        total_time = 0
        total_load = 0
        
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            route_load = 0
            route_time = 0
            stops = []
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                time_var = time_dimension.CumulVar(index)
                
                stop_info = {
                    "node_index": node_index,
                    "node_id": data['nodes'][node_index]['node_id'],
                    "load_kg": data['demands'][node_index],
                    "arrival_min": solution.Min(time_var)
                }
                stops.append(stop_info)
                
                route_load += data['demands'][node_index]
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_time += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
                
            # Add Depot End Stop
            node_index = manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            stops.append({
                "node_index": node_index,
                "node_id": data['nodes'][node_index]['node_id'],
                "load_kg": 0,
                "arrival_min": solution.Min(time_var)
            })
            
            if len(stops) > 2: # More than just Start -> End (Empty truck)
                print(f"Truck {vehicle_id}: Picked up {route_load/1000} tons across {len(stops)-2} farms. Return time: {solution.Min(time_var)} mins.")
                total_time += route_time
                total_load += route_load
                routes.append({
                    "truck_id": vehicle_id,
                    "total_load_kg": route_load,
                    "total_time_min": route_time,
                    "stops": stops
                })
                
        print(f"\nTotal routing time across all trucks: {total_time} mins")
        print(f"Total load picked up: {total_load/1000} tons")
        
        out_path = DATA_DIR / "optimized_routes.json"
        with open(out_path, 'w') as f:
            json.dump(routes, f, indent=2)
        print(f"Saved optimized route manifests to: {out_path.name}")
    else:
        print("No solution found!")

if __name__ == '__main__':
    run()
