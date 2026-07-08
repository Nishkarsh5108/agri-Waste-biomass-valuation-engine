from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import json

from app.core.database import get_db
from app.modules.auth.models import User, UserRole
from app.core.dependencies import get_current_user
from app.modules.logistics.schemas import TriggerResponse, RatingRequest
from app.worker.tasks import run_logistics_optimization
from app.modules.farmers.models import Farm
from app.modules.listings.models import BiomassListing, ListingStatus
from app.modules.logistics.models import LogisticsRoute

router = APIRouter(prefix="/logistics", tags=["Logistics"])

@router.post("/trigger", response_model=TriggerResponse)
async def trigger_cvrp(current_user: User = Depends(get_current_user)):
    """
    Trigger the OR-Tools CVRP routing logic for all READY biomass listings.
    Only accessible by Fleet Managers. Runs asynchronously.
    """
    if current_user.role != UserRole.FLEET_MANAGER:
        raise HTTPException(status_code=403, detail="Only fleet managers can trigger routing.")
        
    # Trigger the OR-Tools Celery background task
    task = run_logistics_optimization.delay()
    return {"message": "CVRP Optimization started in background.", "task_id": str(task.id)}

@router.get("/heatmap")
async def get_heatmap(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch raw geospatial data indicating areas of high biomass density.
    This endpoint powers the visual heatmap on the frontend.
    """
    if current_user.role not in [UserRole.FACTORY, UserRole.FLEET_MANAGER]:
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    query = (
        select(func.ST_AsGeoJSON(Farm.geom).label("geojson"), BiomassListing)
        .join(BiomassListing, BiomassListing.farm_id == Farm.id)
        .where(BiomassListing.status == ListingStatus.READY)
    )
    result = await db.execute(query)
    rows = result.all()
    
    features = []
    for geojson_str, listing in rows:
        if not geojson_str: continue
        geometry = json.loads(geojson_str)
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "listing_id": listing.id,
                "farm_id": listing.farm_id,
                "cv_density_ratio": listing.cv_density_ratio,
                "estimated_tonnage": listing.estimated_tonnage
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

@router.get("/routes")
async def get_routes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch the latest generated logistics routes.
    """
    if current_user.role not in [UserRole.FACTORY, UserRole.FLEET_MANAGER]:
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    query = select(LogisticsRoute).order_by(LogisticsRoute.created_at.desc()).limit(1)
    result = await db.execute(query)
    latest_route = result.scalars().first()
    
    if not latest_route:
        return {"data": None}
        
    return {"data": latest_route.route_manifest}

@router.get("/tractor/{listing_id}")
async def get_tractor_for_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch the assigned tractor/driver for a specific listing based on the latest route manifest.
    """
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can access this data.")
        
    # Verify ownership
    query = select(BiomassListing).join(Farm).where(BiomassListing.id == listing_id, Farm.user_id == current_user.id)
    result = await db.execute(query)
    listing = result.scalars().first()
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
        
    if listing.status not in [ListingStatus.READY, ListingStatus.ROUTED, ListingStatus.COLLECTED]:
        return {"tractor": None, "message": "Your listing is not yet processed."}
        
    query_route = select(LogisticsRoute).order_by(LogisticsRoute.created_at.desc()).limit(1)
    res_route = await db.execute(query_route)
    latest_route = res_route.scalars().first()
    
    if latest_route:
        manifest = latest_route.route_manifest
        for route in manifest.get("routes", []):
            for stop in route.get("stops", []):
                if stop.get("listing_id") == listing_id:
                    vid = route.get("vehicle_id")
                    depot = manifest.get("depot", {"lat": 0.0, "lon": 0.0})
                    farm_lat = stop.get("lat", depot["lat"])
                    farm_lon = stop.get("lon", depot["lon"])
                    
                    # Mock current location (interpolated halfway)
                    current_lat = depot["lat"] + (farm_lat - depot["lat"]) * 0.5
                    current_lon = depot["lon"] + (farm_lon - depot["lon"]) * 0.5
                    
                    return {
                        "tractor": {
                            "name": f"Driver {vid + 1}",
                            "vehicle": f"Mahindra Tractor #{vid + 1} with Baler",
                            "eta": f"{15 + (vid * 10)} mins",
                            "rating": "4.8",
                            "phone": f"+91987654321{vid}"
                        },
                        "route": {
                            "depot": {"latitude": depot["lat"], "longitude": depot["lon"]},
                            "farm": {"latitude": farm_lat, "longitude": farm_lon},
                            "current": {"latitude": current_lat, "longitude": current_lon}
                        },
                        "message": "Tractor dispatched!"
                    }
                    
    # If it's READY but not in latest route (or no route exists), provide a mock tractor for demo
    if listing.status == ListingStatus.READY:
        return {
            "tractor": {
                "name": "Local Driver",
                "vehicle": "Swaraj Tractor with Baler",
                "eta": "12 mins",
                "rating": "4.9",
                "phone": "+919876543210"
            },
            "route": {
                "depot": {"latitude": 28.6139, "longitude": 77.2090}, # Mock depot
                "farm": {"latitude": 28.6200, "longitude": 77.2150}, # Mock farm
                "current": {"latitude": 28.6169, "longitude": 77.2120} # Mock current
            },
            "message": "Tractor dispatched from nearby network!"
        }
                
    return {"tractor": None, "message": "No tractor assigned to this request yet."}

@router.post("/tractor/{listing_id}/rate")
async def rate_driver(
    listing_id: int,
    rating_data: RatingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a rating for a driver upon pickup completion.
    Marks the listing as COLLECTED.
    """
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can submit ratings.")
        
    query = select(BiomassListing).join(Farm).where(BiomassListing.id == listing_id, Farm.user_id == current_user.id)
    result = await db.execute(query)
    listing = result.scalars().first()
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
        
    # Mark as collected
    listing.status = ListingStatus.COLLECTED
    await db.commit()
    
    # In a real app, you would save the rating_data to a DriverRating table here.
    return {"message": "Rating submitted successfully and pickup completed!"}

