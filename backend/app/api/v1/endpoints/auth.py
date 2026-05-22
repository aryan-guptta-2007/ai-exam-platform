import uuid
from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.redis import redis_service
from app.models.user import User
from app.schemas.v1.user import UserCreate, UserOut, Token, LoginRequest, TokenPayload
from jose import JWTError
from loguru import logger

router = APIRouter()
security = HTTPBearer()

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to retrieve the currently authenticated user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token.credentials)
        user_id_str: str = payload.get("sub")
        jti: str = payload.get("jti")
        token_type: str = payload.get("type")
        
        if not user_id_str or not jti or token_type != "access":
            raise credentials_exception
            
        # Check Redis JWT Blocklist
        if await redis_service.is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been blacklisted"
            )
            
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user

@router.post("/register", response_model=UserOut, status_code=201)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Creates a new user account with hashed password credentials.
    """
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system."
        )
        
    hashed_password = get_password_hash(user_in.password)
    user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        is_superuser=user_in.is_superuser
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Registered new user account: {user.email}")
    return user

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Authenticates email credentials and issues Access + Refresh tokens.
    """
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
        
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    # Generate unique JTIs to support revocation
    access_jti = str(uuid.uuid4())
    refresh_jti = str(uuid.uuid4())
    
    access_token = create_access_token(subject=user.id, jti=access_jti)
    refresh_token = create_refresh_token(subject=user.id, jti=refresh_jti)
    
    logger.info(f"User {user.email} authenticated successfully.")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Decodes the refresh token and issues a fresh Access + Refresh token pair.
    """
    try:
        payload = decode_token(refresh_token)
        user_id_str: str = payload.get("sub")
        jti: str = payload.get("jti")
        token_type: str = payload.get("type")
        
        if not user_id_str or not jti or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
            
        if await redis_service.is_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Refresh token revoked")
            
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token formatting")
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not active or does not exist")
        
    # Revoke old refresh token by adding to Redis blocklist
    await redis_service.add_to_blacklist(jti, 86400 * 7)
    
    # Generate new tokens
    access_jti = str(uuid.uuid4())
    refresh_jti = str(uuid.uuid4())
    
    new_access_token = create_access_token(subject=user.id, jti=access_jti)
    new_refresh_token = create_refresh_token(subject=user.id, jti=refresh_jti)
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }
