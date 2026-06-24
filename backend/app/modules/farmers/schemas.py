from pydantic import BaseModel
from typing import Dict, Any

class FarmCreate(BaseModel):
    name: str
    area_hectares: float
    geojson_polygon: Dict[str, Any]  # GeoJSON object

class FarmOut(BaseModel):
    id: int
    user_id: int
    name: str
    area_hectares: float
    geojson_polygon: Dict[str, Any]

    class Config:
        from_attributes = True
