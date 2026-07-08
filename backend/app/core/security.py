from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt
from app.core.config import settings

def get_password_hash(password: str) -> str:
    # 1. Encode to bytes, then slice to strictly 72 bytes
    pwd_bytes = password.encode('utf-8')[:72]
    # 2. Hash using bcrypt directly
    # gensalt() creates a secure, random salt
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # 1. Encode to bytes, slice to 72 bytes
    pwd_bytes = plain_password.encode('utf-8')[:72]
    # 2. Verify against the stored hash
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt