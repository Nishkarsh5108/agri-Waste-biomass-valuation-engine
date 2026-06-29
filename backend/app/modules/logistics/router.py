from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import json

from app.core.database import get_db
from app.modules.auth.models import User, UserRole
from app.core.dependencies import get_current_user
from app.modules.logistics.schemas import TriggerResponse
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

