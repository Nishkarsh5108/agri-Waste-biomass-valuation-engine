from pydantic import BaseModel
from typing import Dict, Any, Optional

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
    photo_s3_url: Optional[str] = None
    photo_url: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True
