import enum
from sqlalchemy import Column, Integer, String, Enum
from app.core.database import Base

class UserRole(enum.Enum):
    FARMER = "FARMER"
    FACTORY = "FACTORY"
    FLEET_MANAGER = "FLEET_MANAGER"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
