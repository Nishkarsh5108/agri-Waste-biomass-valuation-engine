from pydantic import BaseModel
from app.modules.auth.models import UserRole

class UserCreate(BaseModel):
    phone_number: str
    password: str
    role: UserRole

class UserLogin(BaseModel):
    phone_number: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserOut(BaseModel):
    id: int
    phone_number: str
    role: UserRole

    class Config:
        from_attributes = True
