from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import json

from app.core.database import get_db
from app.modules.auth.models import User, UserRole
from app.core.dependencies import get_current_user
from app.modules.farmers.models import Farm
from app.modules.farmers.schemas import FarmCreate, FarmOut

router = APIRouter(prefix="/farms", tags=["Farms"])

@router.post("/", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
async def register_farm(
    farm_in: FarmCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can register farms.")

    # Convert dictionary to JSON string for PostGIS
    geojson_str = json.dumps(farm_in.geojson_polygon)

    # Use PostGIS ST_GeomFromGeoJSON to insert
    geom_data = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geojson_str), 4326)

    new_farm = Farm(
        user_id=current_user.id,
        name=farm_in.name,
        area_hectares=farm_in.area_hectares,
        geom=geom_data
    )
    
    db.add(new_farm)
    await db.commit()
    
    # Fetch back the record with geom converted to GeoJSON for the response
    result = await db.execute(
        select(Farm.id, Farm.user_id, Farm.name, Farm.area_hectares, func.ST_AsGeoJSON(Farm.geom).label('geojson_polygon'))
        .where(Farm.id == new_farm.id)
    )
    row = result.first()
    
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "area_hectares": row.area_hectares,
        "geojson_polygon": json.loads(row.geojson_polygon)
    }

@router.get("/", response_model=list[FarmOut])
async def get_my_farms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers have farms.")

    # Fetch rows with the geometry output as GeoJSON
    result = await db.execute(
        select(Farm.id, Farm.user_id, Farm.name, Farm.area_hectares, func.ST_AsGeoJSON(Farm.geom).label('geojson_polygon'))
        .where(Farm.user_id == current_user.id)
    )
    rows = result.all()
    
    farms = []
    for row in rows:
        farms.append({
            "id": row.id,
            "user_id": row.user_id,
            "name": row.name,
            "area_hectares": row.area_hectares,
            "geojson_polygon": json.loads(row.geojson_polygon)
        })
        
    return farms
