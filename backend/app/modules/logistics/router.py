from fastapi import APIRouter, Depends, HTTPException
from app.modules.auth.models import User, UserRole
from app.core.dependencies import get_current_user
from app.modules.logistics.schemas import TriggerResponse
from app.worker.tasks import run_logistics_optimization

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
    return {"message": "CVRP Optimization started in background.", "task_id": task.id}

@router.get("/heatmap")
async def get_heatmap(current_user: User = Depends(get_current_user)):
    """
    Fetch raw geospatial data indicating areas of high biomass density.
    This endpoint powers the visual heatmap on the frontend.
    """
    if current_user.role not in [UserRole.FACTORY, UserRole.FLEET_MANAGER]:
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    # Typically executes a PostGIS query: 
    # SELECT ST_AsGeoJSON(geom), cv_density_ratio FROM farms JOIN biomass_listings ...
    return {"data": "Heatmap GeoJSON will be served here (MVP stub)"}
