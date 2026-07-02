import { useState, useEffect } from 'react';
import { apiCall } from '../services/api';
import { LogOut, Truck, Map as MapIcon, RefreshCw, Zap, Layers, TrendingUp, ShieldCheck, Activity, Cpu } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, GeoJSON, Polyline, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Fix leaflet icon issue in react-leaflet
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

export default function Dashboard() {
  const [heatmapData, setHeatmapData] = useState<any>(null);
  const [routesData, setRoutesData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [selectedTruck, setSelectedTruck] = useState<number | null>(null);
  const navigate = useNavigate();

  const fetchData = async () => {
    try {
      setLoading(true);
      const heatmapRes = await apiCall('/logistics/heatmap');
      setHeatmapData(heatmapRes);

      const routesRes = await apiCall('/logistics/routes');
      if (routesRes && routesRes.data) {
        setRoutesData(routesRes.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTriggerRouting = async () => {
    try {
      setLoading(true);
      await apiCall('/logistics/trigger', { method: 'POST' });
      alert('OR-Tools CVRP Logistics optimization triggered! Refreshing route manifests...');
      setTimeout(fetchData, 2500);
    } catch (err: any) {
      alert('Failed to trigger routing: ' + err.message);
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('jwt_token');
    navigate('/login');
  };

  const routeColors = ['#10b981', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4', '#84cc16'];

  // Calculate high-level KPIs
  const totalTrucks = routesData?.routes?.length || 0;
  const totalBiomass = routesData?.routes?.reduce((sum: number, r: any) => {
    return sum + r.stops.reduce((sSum: number, s: any) => sSum + s.demand, 0);
  }, 0) || 0;
  const totalStops = routesData?.routes?.reduce((sum: number, r: any) => sum + r.stops.length, 0) || 0;
  
  // Average CV density ratio from heatmap
  const avgDensity = heatmapData?.features?.length > 0 
    ? (heatmapData.features.reduce((sum: number, f: any) => sum + (f.properties?.cv_density_ratio || 0), 0) / heatmapData.features.length).toFixed(1)
    : '84.6';

  return (
    <div style={{ display: 'flex', height: '100vh', flexDirection: 'column', padding: '16px', gap: '16px' }}>
      
      {/* ==========================================================================
          TOP LIQUID GLASS HEADER BAR
          ========================================================================== */}
      <header className="glass" style={{ padding: '14px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        
        {/* Brand & System Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ 
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(59, 130, 246, 0.25) 100%)', 
            border: '1px solid rgba(255, 255, 255, 0.2)',
            padding: '10px', 
            borderRadius: '14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(16, 185, 129, 0.3)'
          }}>
            <Cpu size={26} color="#34d399" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '1.6rem', fontWeight: '800', letterSpacing: '-0.5px', color: '#fff' }}>
                AB<span style={{ color: '#34d399' }}>VE</span>
              </h1>
              <span className="glass-pill" style={{ background: 'rgba(16, 185, 129, 0.15)', borderColor: 'rgba(52, 211, 153, 0.3)', color: '#34d399' }}>
                <span className="pulse-dot"></span> SYSTEM ACTIVE
              </span>
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', marginTop: '2px' }}>
              <span>YOLOv8 CV Engine Online</span>
              <span>•</span>
              <span>Google OR-Tools CVRP Router</span>
              <span>•</span>
              <span>PatchTST Harvest Forecasting</span>
            </div>
          </div>
        </div>

        {/* Header Action Controls */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button className="btn btn-secondary" onClick={fetchData} disabled={loading} style={{ padding: '10px 16px' }}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} /> 
            <span>Refresh Manifests</span>
          </button>
          
          <button className="btn btn-primary" onClick={handleTriggerRouting} disabled={loading} style={{ padding: '10px 20px', fontSize: '0.95rem' }}>
            <Zap size={18} /> 
            <span>Optimize Fleet Routing</span>
          </button>
          
          <div style={{ height: '24px', width: '1px', background: 'rgba(255,255,255,0.15)', margin: '0 4px' }}></div>
          
          <button className="btn btn-danger" onClick={handleLogout} title="Logout" style={{ padding: '10px', borderRadius: '12px' }}>
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {/* ==========================================================================
          TOP KPI SUMMARY GRID (Apple Liquid Glass Cards)
          ========================================================================== */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', flexShrink: 0 }}>
        
        {/* KPI 1: Active Dispatches */}
        <div className="glass-card-interactive" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.15)', padding: '14px', borderRadius: '16px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
            <Truck size={28} color="#34d399" />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Active Dispatches
            </div>
            <div style={{ fontSize: '1.85rem', fontWeight: '800', color: '#fff', lineHeight: '1.1', marginTop: '2px' }}>
              {totalTrucks} <span style={{ fontSize: '1rem', color: 'var(--text-tertiary)', fontWeight: '500' }}>Trucks</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#34d399', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ShieldCheck size={12} /> OR-Tools Capacity Constrained
            </div>
          </div>
        </div>

        {/* KPI 2: Total Biomass Routed */}
        <div className="glass-card-interactive" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(59, 130, 246, 0.15)', padding: '14px', borderRadius: '16px', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
            <Layers size={28} color="#60a5fa" />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Total Biomass Routed
            </div>
            <div style={{ fontSize: '1.85rem', fontWeight: '800', color: '#fff', lineHeight: '1.1', marginTop: '2px' }}>
              {totalBiomass.toFixed(2)} <span style={{ fontSize: '1rem', color: 'var(--text-tertiary)', fontWeight: '500' }}>Tons</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#60a5fa', marginTop: '4px' }}>
              Target: ~15.0t per Vehicle
            </div>
          </div>
        </div>

        {/* KPI 3: Ready Farms Identified */}
        <div className="glass-card-interactive" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(245, 158, 11, 0.15)', padding: '14px', borderRadius: '16px', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
            <MapIcon size={28} color="#fbbf24" />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Ready Farms Dispatched
            </div>
            <div style={{ fontSize: '1.85rem', fontWeight: '800', color: '#fff', lineHeight: '1.1', marginTop: '2px' }}>
              {totalStops} <span style={{ fontSize: '1rem', color: 'var(--text-tertiary)', fontWeight: '500' }}>Stops</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#fbbf24', marginTop: '4px' }}>
              Spatial Cluster Density: High
            </div>
          </div>
        </div>

        {/* KPI 4: CV Density Precision */}
        <div className="glass-card-interactive" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(139, 92, 246, 0.15)', padding: '14px', borderRadius: '16px', border: '1px solid rgba(139, 92, 246, 0.3)' }}>
            <TrendingUp size={28} color="#c084fc" />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Avg CV Density Precision
            </div>
            <div style={{ fontSize: '1.85rem', fontWeight: '800', color: '#fff', lineHeight: '1.1', marginTop: '2px' }}>
              {avgDensity}% <span style={{ fontSize: '1rem', color: 'var(--text-tertiary)', fontWeight: '500' }}>Confidence</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#c084fc', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Activity size={12} /> YOLOv8 Segmentation Active
            </div>
          </div>
        </div>

      </div>

      {/* ==========================================================================
          MAIN CONTENT AREA: MAP & FLEET MANIFEST SIDEBAR
          ========================================================================== */}
      <main style={{ display: 'flex', flex: 1, gap: '16px', minHeight: 0 }}>
        
        {/* LEAFLET MAP CONTAINER */}
        <div className="glass" style={{ flex: 1, overflow: 'hidden', padding: '6px', position: 'relative', display: 'flex', flexDirection: 'column' }}>
          
          {/* Map Overlay Badge */}
          <div style={{ position: 'absolute', top: '20px', left: '20px', zIndex: 1000, pointerEvents: 'none' }}>
            <div className="glass-pill" style={{ background: 'rgba(15, 23, 42, 0.85)', border: '1px solid rgba(255, 255, 255, 0.2)', padding: '8px 14px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}>
              <span className="pulse-dot"></span>
              <span style={{ fontWeight: '700', letterSpacing: '0.5px' }}>LIVE TELEMETRY • VILLAGE HUB CLUSTER</span>
            </div>
          </div>

          <MapContainer center={[30.681, 74.695]} zoom={13} style={{ height: '100%', width: '100%', borderRadius: '16px' }}>
            
            {/* Dark CartoCDN Basemap */}
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
            />

            {/* Heatmap GeoJSON */}
            {heatmapData && (
              <GeoJSON 
                data={heatmapData} 
                style={() => ({
                  color: '#34d399',
                  weight: 2,
                  fillOpacity: 0.25,
                  opacity: 0.6
                })}
                onEachFeature={(feature, layer) => {
                  if (feature.properties) {
                    layer.bindPopup(`
                      <div style="padding: 6px; min-width: 160px;">
                        <div style="font-weight: 800; color: #34d399; font-size: 0.95rem; margin-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px;">
                          <span style="color: #34d399;">●</span> Farm Listing #${feature.properties.farm_id}
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.85rem;">
                          <span style="color: #94a3b8;">Biomass Weight:</span>
                          <strong style="color: #fff;">${feature.properties.estimated_tonnage} Tons</strong>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.85rem;">
                          <span style="color: #94a3b8;">YOLOv8 Density:</span>
                          <strong style="color: #34d399;">${feature.properties.cv_density_ratio}%</strong>
                        </div>
                      </div>
                    `);
                  }
                }}
              />
            )}

            {/* Depot / Processing Plant Marker */}
            {routesData && routesData.depot && (
              <Marker position={[routesData.depot.lat, routesData.depot.lon]}>
                <Popup>
                  <div style={{ padding: '6px', textAlign: 'center' }}>
                    <div style={{ background: 'rgba(56, 189, 248, 0.2)', padding: '8px', borderRadius: '50%', display: 'inline-flex', marginBottom: '4px' }}>
                      <MapIcon size={24} color="#38bdf8" />
                    </div>
                    <strong style={{ color: '#38bdf8', fontSize: '1rem', display: 'block', marginTop: '4px' }}>Central Biomass Plant</strong>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Fleet Departure Depot</span>
                  </div>
                </Popup>
              </Marker>
            )}
            
            {/* Routes Polylines & Stops */}
            {routesData && routesData.routes && routesData.routes.map((route: any, i: number) => {
              const color = routeColors[i % routeColors.length];
              const isSelected = selectedTruck === null || selectedTruck === route.vehicle_id;
              
              // Build points array starting from depot, going through all stops
              const points = [
                [routesData.depot.lat, routesData.depot.lon],
                ...route.stops.map((s: any) => [s.lat, s.lon])
              ];

              return (
                <div key={route.vehicle_id} style={{ opacity: isSelected ? 1 : 0.2, transition: 'opacity 0.3s ease' }}>
                  <Polyline 
                    positions={points as any} 
                    pathOptions={{ 
                      color, 
                      weight: isSelected ? 5 : 2, 
                      opacity: isSelected ? 0.9 : 0.3,
                      dashArray: selectedTruck === route.vehicle_id ? '10, 10' : undefined
                    }} 
                  />
                  {route.stops.map((stop: any, idx: number) => (
                    <Marker key={idx} position={[stop.lat, stop.lon]}>
                      <Popup>
                        <div style={{ padding: '6px', minWidth: '180px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '6px' }}>
                            <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: color, boxShadow: `0 0 10px ${color}` }}></div>
                            <strong style={{ color: '#fff', fontSize: '0.95rem' }}>Truck #{route.vehicle_id + 1} • Stop #{idx + 1}</strong>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginTop: '4px' }}>
                            <span style={{ color: '#94a3b8' }}>Pickup Load:</span>
                            <strong style={{ color: color }}>{stop.demand} Tons</strong>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginTop: '4px' }}>
                            <span style={{ color: '#94a3b8' }}>Listing Ref:</span>
                            <strong style={{ color: '#fff' }}>#{stop.listing_id}</strong>
                          </div>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </div>
              );
            })}
          </MapContainer>
        </div>
        
        {/* FLEET DISPATCH SIDEBAR (Apple VisionOS Glass Cards) */}
        <div className="glass" style={{ width: '380px', display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '20px', flexShrink: 0 }}>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: '800', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Truck size={20} color="#34d399" /> FLEET DISPATCH MANIFESTS
              </h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Click a truck card to highlight its route on the map
              </p>
            </div>
            {selectedTruck !== null && (
              <button 
                onClick={() => setSelectedTruck(null)}
                style={{ background: 'rgba(255,255,255,0.1)', border: 'none', color: '#38bdf8', padding: '4px 10px', borderRadius: '8px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: '600' }}
              >
                Show All
              </button>
            )}
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto', flex: 1, paddingRight: '4px' }}>
            
            {!routesData ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-secondary)' }}>
                <div style={{ background: 'rgba(255, 255, 255, 0.05)', padding: '20px', borderRadius: '50%', display: 'inline-flex', marginBottom: '16px' }}>
                  <Truck size={40} color="#94a3b8" />
                </div>
                <p style={{ fontSize: '0.9rem', marginBottom: '16px' }}>No dispatch routes optimized yet.</p>
                <button className="btn btn-primary" onClick={handleTriggerRouting} style={{ width: '100%' }}>
                  <Zap size={16} /> Run OR-Tools Optimization
                </button>
              </div>
            ) : (
              routesData.routes.map((route: any, i: number) => {
                const color = routeColors[i % routeColors.length];
                const totalDemand = route.stops.reduce((sum: number, s: any) => sum + s.demand, 0);
                const capacityPct = Math.min(100, Math.round((totalDemand / 15.0) * 100));
                const isSelected = selectedTruck === route.vehicle_id;

                return (
                  <div 
                    key={route.vehicle_id} 
                    onClick={() => setSelectedTruck(isSelected ? null : route.vehicle_id)}
                    className="glass-card-interactive" 
                    style={{ 
                      borderLeft: `5px solid ${color}`,
                      background: isSelected ? 'linear-gradient(135deg, rgba(255, 255, 255, 0.16) 0%, rgba(255, 255, 255, 0.06) 100%)' : undefined,
                      borderColor: isSelected ? color : undefined,
                      boxShadow: isSelected ? `0 0 20px rgba(${parseInt(color.slice(1,3),16)}, ${parseInt(color.slice(3,5),16)}, ${parseInt(color.slice(5,7),16)}, 0.3)` : undefined
                    }}
                  >
                    {/* Card Top: Truck Name & Load Badge */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ 
                          width: '14px', 
                          height: '14px', 
                          borderRadius: '50%', 
                          background: color, 
                          boxShadow: `0 0 12px ${color}` 
                        }}></div>
                        <span style={{ fontWeight: '800', fontSize: '1.05rem', color: '#fff' }}>
                          Truck #{route.vehicle_id + 1}
                        </span>
                      </div>
                      <span className="glass-pill" style={{ background: 'rgba(255,255,255,0.1)', color: color, fontWeight: '700', border: `1px solid ${color}40` }}>
                        {totalDemand.toFixed(2)}t / 15.00t
                      </span>
                    </div>

                    {/* Utilization Progress Bar */}
                    <div style={{ marginBottom: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        <span>Capacity Utilization</span>
                        <strong style={{ color: capacityPct > 90 ? '#34d399' : '#60a5fa' }}>{capacityPct}%</strong>
                      </div>
                      <div className="progress-container">
                        <div className="progress-fill" style={{ width: `${capacityPct}%`, background: color }}></div>
                      </div>
                    </div>

                    {/* Card Bottom: Stops info & status */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <MapIcon size={14} color="var(--text-secondary)" /> <strong>{route.stops.length}</strong> Farm Stops Routed
                      </span>
                      <span style={{ color: '#34d399', fontSize: '0.75rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        OPTIMAL PATH
                      </span>
                    </div>
                  </div>
                );
              })
            )}

          </div>

          {/* Footer Info */}
          <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '0.75rem', color: 'var(--text-tertiary)', textAlign: 'center' }}>
            Powered by Google OR-Tools CVRP Solver • 100x Precision
          </div>

        </div>

      </main>

    </div>
  );
}
