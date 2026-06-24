from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.modules.listings.models import ListingStatus

class ListingOut(BaseModel):
    id: int
    farm_id: int
    status: ListingStatus
    photo_s3_url: Optional[str]
    cv_density_ratio: Optional[float]
    estimated_tonnage: Optional[float]
    predicted_harvest_date: Optional[datetime]
    quality_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
