import enum
import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base

class ListingStatus(enum.Enum):
    PROCESSING = "PROCESSING"
    READY = "READY"
    ROUTED = "ROUTED"
    COLLECTED = "COLLECTED"

class BiomassListing(Base):
    __tablename__ = "biomass_listings"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(Enum(ListingStatus), default=ListingStatus.PROCESSING)
    photo_s3_url = Column(String, nullable=True)
    cv_density_ratio = Column(Float, nullable=True)
    estimated_tonnage = Column(Float, nullable=True)
    predicted_harvest_date = Column(DateTime, nullable=True)
    quality_score = Column(Float, nullable=True)

    farm = relationship("Farm", backref="listings")
