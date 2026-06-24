from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=True)
    area_hectares = Column(Float, nullable=False)
    # SRID 4326 is the standard WGS84 coordinate system used by GPS
    geom = Column(Geometry(geometry_type='POLYGON', srid=4326), nullable=False)

    owner = relationship("User", backref="farms")
