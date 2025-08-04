"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any

from ..core.auth import (
    verify_password, 
    create_access_token, 
    create_refresh_token,
    get_password_hash,
    get_current_user
)
from ..core.config import settings


router = APIRouter(prefix="/api/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# In-memory user store (in production, use a database)
users_db = {
    settings.ADMIN_USERNAME: {
        "username": settings.ADMIN_USERNAME,
        "hashed_password": get_password_hash(settings.ADMIN_PASSWORD),
        "is_admin": True
    }
}


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    # Get user from database
    user = users_db.get(credentials.username)
    
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(
        data={"sub": user["username"], "is_admin": user.get("is_admin", False)}
    )
    refresh_token = create_refresh_token(
        data={"sub": user["username"]}
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.get("/me")
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current user information."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return current_user