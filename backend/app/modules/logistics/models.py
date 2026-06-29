from sqlalchemy import Column, Integer, JSON, DateTime
from datetime import datetime
from app.core.database import Base

class LogisticsRoute(Base):
    __tablename__ = "logistics_routes"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    route_manifest = Column(JSON, nullable=False)
