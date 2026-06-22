# Agri-Waste Biomass Valuation Engine: Logistics System Architecture

This document serves as the foundational research and technical design report for the truck logistics subsystem. It completely re-evaluates the initial Capacitated Vehicle Routing Problem (CVRP) assumption from first principles, integrating advanced operations research and real-world agricultural supply chain dynamics.

## 1. Problem Definition
The core problem is **not** simply finding the shortest path between farms. The problem is orchestrating a highly volatile, geographically dispersed, and time-sensitive reverse logistics supply chain. 

We must transport low-density biomass (stubble) from thousands of fragmented smallholder farms to centralized processing facilities (biofuel/paper mills) within a critically narrow 14-21 day post-harvest window. 
*   **Supply is dynamic and stochastic:** Dictated by weather, actual harvest dates, and farmer manual requests.
*   **Constraints are rigid:** Farms have zero storage capacity (stubble is left on the field). Factories have daily processing and unloading limits. Trucks have volume/weight constraints.
*   **The alternative is catastrophic:** If pickup is delayed, the farmer will burn the residue to clear the land for the next crop.

## 2. Functional Requirements
*   **Demand Ingestion:** Receive and process pickup requests from the mobile app.
*   **Predictive Supply Mapping:** Utilize the PatchTST harvest prediction model to map expected biomass supply curves up to 30 days in advance.
*   **Dynamic Dispatching:** Generate and dispatch multi-stop truck routes daily, adapting to real-time cancellations or urgent requests.
*   **Factory Queue Management:** Schedule factory arrival times to prevent multi-hour truck queues at the weighbridge.
*   **Fleet Management:** Manage heterogeneous fleet profiles (e.g., small 5-ton tractors vs. large 15-ton baler trucks).
*   **Priority Handling:** Prioritize farms approaching their critical "burn threshold" (days since harvest).

## 3. Non-Functional Requirements
*   **Scalability:** Must support 100,000+ daily pickup nodes across a state (e.g., Punjab/Haryana).
*   **Fault Tolerance:** Route execution must survive network dead zones in rural areas.
*   **Compute Latency:** Daily batch routing for 10,000 nodes must solve within 2-4 hours. Real-time rerouting must execute in under 3 minutes.
*   **Extensibility:** Easy integration of new variables (e.g., traffic APIs, varying vehicle types).

## 4. Logistics System Objectives
In order of operational importance:
1.  **Maximize Total Biomass Recovered:** (Primary environmental goal - prevent burning).
2.  **Minimize Farmer Wait Time:** (Primary adoption goal - if they wait, they burn).
3.  **Minimize Empty Miles / Transport Cost:** (Primary economic goal for buyers).
4.  **Maximize Factory Throughput:** Ensure factories run at 100% utilization without long truck queues.

## 5. Literature Review
Academic literature on biomass logistics highlights the following:
*   **Low Energy Density:** Transporting raw straw is highly inefficient (hauling air). Research heavily favors *in-field densification* (baling) prior to transport. 
*   **Inventory Routing Problem (IRP):** Most biomass papers frame this not as a routing problem, but an inventory problem. The "inventory" is sitting in the field and must be drawn down before a deadline.
*   **Multi-objective Optimization:** Recent papers (2020+) utilize hybrid metaheuristics (e.g., Genetic Algorithms + Tabu Search) to balance CO2 emissions against financial costs.

## 6. Industry Survey
*   **Sugarcane Logistics (Brazil/India):** Sugarcane loses sugar content rapidly after harvest. They use **Just-In-Time (JIT) VRPTW**, tightly coupling harvester schedules with truck arrivals to guarantee a continuous feed to the crushers.
*   **Dairy Collection (Amul/Nestle):** Daily milk runs from thousands of small farmers to chilling centers. They utilize **fixed master routes** (tactical planning) with daily volume adjustments (operational routing).
*   **Amazon / UPS Logistics:** High density, deterministic routing. They rely heavily on **Zone-based routing** combined with Graph Neural Networks (GNN) to predict traffic delays and optimize last-mile drop-offs.
*   **Waste Collection (Municipal):** Highly analogous. Uses **Periodic VRP (PVRP)**. Trucks are routed based on expected bin fill-levels, prioritizing overflowing bins.

## 7. Comparison of Optimization Formulations

| Formulation | Description | Pros | Cons | Fit for Us? |
| :--- | :--- | :--- | :--- | :--- |
| **CVRP** | Standard capacity constraints | Simple to implement, fast solvers. | Ignores time, urgency, and factory bottlenecks. | **No.** Too naive. |
| **VRPTW** | Adds time windows for pickup/drop-off | Models factory operating hours and farmer availability. | Harder to solve at scale. | **Partial.** Good for daily planning. |
| **Split Delivery (SDVRP)** | Multiple trucks can visit one farm | Crucial if a farm has 20 tons but trucks only hold 15 tons. | Expands search space exponentially. | **Yes.** Essential for large farms. |
| **Inventory Routing (IRP)** | Decides *when* to visit, not just how. | Optimizes across multiple days. Prevents farms from reaching critical "burn dates". | Computationally heavy. | **Yes.** The true paradigm for biomass. |
| **Dynamic VRP** | Routes update on the fly | Handles real-time cancellations. | High infrastructure complexity. | **Future.** Phase 3 requirement. |
| **RL / GNNs** | Learning dispatch policies via Neural Nets | Insanely fast inference (< 1 sec) once trained. | "Black box" routing, hard to enforce strict hard constraints. | **Future.** |

## 8. Recommended Architecture
The system should implement a **Multi-Day Inventory Routing Problem with Time Windows and Split Deliveries (IRP-TW-SD)**. 

Because solving this globally is NP-Hard and impossible for 100,000 farms, we will use a **Two-Echelon Heuristic Architecture**:

1.  **Tactical Layer (Macro-Clustering):** Use the PatchTST harvest predictions to divide the state into dynamic daily "Geofenced Zones" (e.g., K-Means or HDBScan clustering based on expected harvest density).
2.  **Operational Layer (Micro-Routing):** Within each zone, solve a localized VRPTW + Split Delivery problem using a Metaheuristic (e.g., Large Neighborhood Search or ALNS) or Google OR-Tools.

## 9. System Workflow
1.  **T-30 Days:** PatchTST predicts harvest dates. System calculates regional supply curves.
2.  **T-7 Days:** Factory allocates truck fleet based on predicted supply surge.
3.  **T-0 Days (Harvest):** Farmer cuts crop, uploads photo. Satellite validates area and density.
4.  **T+1 Days:** Farm enters the "Inventory Pool" with an increasing Urgency Score.
5.  **Nightly Batch (2:00 AM):** The IRP engine selects which farms must be cleared today to prevent burning, generates routes, schedules factory arrival times, and dispatches to driver apps.
6.  **T+2 Days (Execution):** Trucks execute routes, weigh at factory. Payment is released.

## 10. Data Flow
`[Farmer App] -> (Manual Request + Photo) -> [Valuation Engine]`
`[PatchTST] -> (Harvest Predictions) -> [Valuation Engine]`
`[Valuation Engine] -> (Validated Farm Node: Lat, Lon, Tons, Urgency) -> [Kafka/Message Queue]`
`[Kafka] -> [PostGIS Database (Inventory Pool)]`
`[Batch Optimizer] <- (Pulls Nodes + Truck Fleet + Factory Limits)`
`[Batch Optimizer] -> (Routes + Manifests) -> [Driver App]`

## 11. Required Datasets
*   **Road Network Graph:** OpenStreetMap (OSM) data optimized for heavy trucks (avoiding narrow village mud roads).
*   **Fleet Telemetry:** GPS traces of trucks to learn actual travel times vs. theoretical speeds.
*   **Factory Capacities:** Maximum weighbridge throughput (trucks/hour).

## 12. Required APIs
*   **OSRM / Valhalla:** Open-source routing engines for calculating true driving distance/time matrices (crucial: Euclidean distance is useless in rural road networks).
*   **FCM (Firebase Cloud Messaging):** To push daily manifests to truck driver apps.

## 13. Database Schema Suggestions (PostgreSQL + PostGIS)
*   `farms`: `id`, `geom (Point)`, `farmer_id`, `total_hectares`
*   `pickup_requests`: `id`, `farm_id`, `estimated_tonnage`, `created_at`, `urgency_score`, `status`
*   `fleet`: `id`, `truck_type`, `capacity_tons`, `cost_per_km`
*   `routes`: `id`, `date`, `truck_id`, `total_distance`, `factory_arrival_window`
*   `route_stops`: `id`, `route_id`, `pickup_request_id`, `sequence_index`, `planned_arrival`

## 14. Scalability Analysis
Calculating a distance matrix for 10,000 farms requires 100 million API calls. 
*   **Solution:** We must use localized clustering. By breaking the state into 100 zones of 100 farms, the distance matrices drop to 100 * (100^2) = 1,000,000 calculations (a 99% reduction in compute). Optimization runs in parallel per zone.

## 15. Cost Analysis
*   **Compute:** Heavy. Running daily VRPs requires compute-optimized instances (e.g., AWS C6i or GCP C2). 
*   **Mapping APIs:** Google Maps API will bankrupt the project at scale. We must self-host Valhalla or OSRM on a dedicated server.

## 16. Risks and Failure Cases
*   **"Ghost" Roads:** OSM might route a 15-ton truck down a dirt path it can't traverse. 
    *   *Mitigation:* Restrict routing edges based on truck dimensions.
*   **Overloaded Factory:** All trucks finish routes at 4 PM, causing a 6-hour queue at the factory.
    *   *Mitigation:* VRPTW enforces staggered factory arrival time windows.
*   **Farmer Burns Anyway:** A farmer gets tired of waiting 3 days and burns the field while the truck is en route.
    *   *Mitigation:* Urgency scoring. Farms > 3 days post-harvest get exponentially higher weighting in the objective function.

## 17. Trade-off Analysis
*   **Global Optimality vs. Computation Time:** We sacrifice mathematical global optimality (which would take weeks to compute) for fast, localized heuristic solutions that execute in 1 hour.
*   **Static vs. Dynamic Routing:** We trade the responsiveness of dynamic routing (Uber style) for the high packing efficiency of static batch routing (UPS style).

## 18. Short-term vs Long-term Implementation Strategy
*   **Short-term (Hackathon):** Implement a simple VRPTW using Google OR-Tools. Use Euclidean distance or a cached distance matrix for a small 50-farm mock dataset. Show the *concept* of factory queues and truck capacities.
*   **Long-term (Production):** Self-hosted OSRM. Multi-day Inventory Routing. Hybrid ALNS solvers written in C++ / Rust.

## 19. Why this is superior to the naive CVRP
A naive CVRP only minimizes driving distance on a given day. It will consistently route trucks to the most tightly clustered farms, abandoning isolated farms. Those isolated farms will burn their stubble. CVRP also ignores factory unloading bottlenecks, leading to massive inefficiencies. Our IRP-TW approach balances *urgency* (preventing fires) with *efficiency* (minimizing fuel).

## 20. Phased Implementation Roadmap
**Phase 1: Hackathon MVP (Weeks 1-2)**
*   Generate mock dataset of 100 farm requests.
*   Build a Python VRPTW solver using Google OR-Tools.
*   Visualize routes on a Folium map.

**Phase 2: Tactical Integration (Months 1-3)**
*   Connect PatchTST predictions to pre-allocate "zones" before requests come in.
*   Implement Urgency Scoring based on days-since-harvest.
*   Setup PostGIS database.

**Phase 3: Production Scale (Months 4-6)**
*   Deploy self-hosted Valhalla routing engine.
*   Move to multi-day Inventory Routing formulation.
*   Develop Driver and Factory operator mobile interfaces.
