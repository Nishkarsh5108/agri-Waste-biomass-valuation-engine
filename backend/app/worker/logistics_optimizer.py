import math
from sqlalchemy.future import select
from sqlalchemy import func
from app.core.database import AsyncSessionLocal
import app.modules.auth.models
from app.modules.listings.models import BiomassListing, ListingStatus
from app.modules.farmers.models import Farm
from app.modules.logistics.models import LogisticsRoute
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2.0)**2 + \
        math.cos(phi1)*math.cos(phi2) * math.sin(delta_lambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return int(R * c)

async def run_logistics_optimization_async():
    async with AsyncSessionLocal() as db:
        # Fetch all valid listings with their coordinates
        query = (
            select(
                BiomassListing,
                func.ST_X(func.ST_Centroid(Farm.geom)).label("lon"),
                func.ST_Y(func.ST_Centroid(Farm.geom)).label("lat")
            )
            .join(Farm, BiomassListing.farm_id == Farm.id)
            .where(
                BiomassListing.status.in_([ListingStatus.READY, ListingStatus.ROUTED]),
                BiomassListing.cv_density_ratio.is_not(None)
            )
        )
        result = await db.execute(query)
        rows = result.all()
        
        if not rows:
            return
            
        # Spatial density clustering: find the seed farm that has the smallest distance to its 49th closest neighbor
        if len(rows) > 50:
            best_cluster = rows[:50]
            min_radius = float('inf')
            for i, center_row in enumerate(rows):
                dists = []
                for j, target_row in enumerate(rows):
                    d = haversine(center_row.lat, center_row.lon, target_row.lat, target_row.lon)
                    dists.append((d, target_row))
                dists.sort(key=lambda x: x[0])
                candidate_cluster = [r for _, r in dists[:50]]
                radius = dists[49][0] if len(dists) >= 50 else dists[-1][0]
                if radius < min_radius:
                    min_radius = radius
                    best_cluster = candidate_cluster
            rows = best_cluster
            
        # Node 0: Depot (Let's place it at the first farm's location + offset)
        depot_lat = rows[0].lat + 0.01
        depot_lon = rows[0].lon + 0.01
        
        locations = [(depot_lat, depot_lon)]
        demands = [0]
        listing_map = {0: None}
        
        for i, row in enumerate(rows):
            listing = row.BiomassListing
            node_idx = i + 1
            locations.append((row.lat, row.lon))
            # Scale by 100 for OR-Tools integer solver precision (e.g., 0.76t -> 76)
            demands.append(int(round(float(listing.estimated_tonnage) * 100)))
            listing_map[node_idx] = listing
            
        # Distance Matrix
        num_locations = len(locations)
        distance_matrix = []
        for i in range(num_locations):
            row = []
            for j in range(num_locations):
                dist = haversine(locations[i][0], locations[i][1], locations[j][0], locations[j][1])
                row.append(dist)
            distance_matrix.append(row)
            
        # Vehicle setup (1500 = 15.00 tons scaled by 100)
        total_demand = sum(demands)
        vehicle_capacity = 1500
        num_vehicles = max(1, (total_demand // vehicle_capacity) + 2)
        vehicle_capacities = [vehicle_capacity] * num_vehicles
        
        manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, 0)
        routing = pywrapcp.RoutingModel(manager)
        
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]
            
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return demands[from_node]
            
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # null capacity slack
            vehicle_capacities,  # vehicle maximum capacities
            True,  # start cumul to zero
            'Capacity'
        )
        
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
            
        solution = routing.SolveWithParameters(search_parameters)
        
        if not solution:
            return
            
        routes = []
        routed_listing_ids = []
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            route = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index != 0:
                    listing = listing_map[node_index]
                    route.append({
                        "node": node_index,
                        "listing_id": listing.id,
                        "lat": locations[node_index][0],
                        "lon": locations[node_index][1],
                        "demand": round(float(listing.estimated_tonnage), 2)
                    })
                    routed_listing_ids.append(listing.id)
                index = solution.Value(routing.NextVar(index))
            if route:
                routes.append({
                    "vehicle_id": vehicle_id,
                    "stops": route
                })
                
        # Update statuses
        for node_idx, listing in listing_map.items():
            if listing and listing.id in routed_listing_ids:
                listing.status = ListingStatus.ROUTED
                
        # Save manifest
        manifest = {
            "depot": {"lat": depot_lat, "lon": depot_lon},
            "routes": routes
        }
        
        new_route = LogisticsRoute(route_manifest=manifest)
        db.add(new_route)
        await db.commit()
