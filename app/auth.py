"""
Authentication module - JWT + OAuth providers.

Designed to be extensible: add new OAuth providers by adding entries to OAUTH_PROVIDERS.
"""
import os
import uuid
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from authlib.integrations.starlette_client import OAuth

from app.database import get_db
from app.models import Profile
from app.schemas import ProfileCreate, PlayerLevel
from app import crud
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# ─── Configuration ─────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

# OAuth providers registry - add new providers here
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# ─── OAuth setup ───────────────────────────────────────────────────
oauth = OAuth()

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# ─── JWT utilities ─────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ─── Auth dependency ───────────────────────────────────────────────
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[dict]:
    """Extract user from JWT cookie or Authorization header. Returns None if not authenticated."""
    token = None
    
    # Try cookie first
    token = request.cookies.get("ttmm_token")
    
    # Try Authorization header
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        return None
    
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return {"user_id": uuid.UUID(user_id), "token": token}
    except (JWTError, ValueError):
        return None


async def require_user(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Require authentication. Raises 401 if not authenticated."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Verify user still exists
    profile = await crud.get_profile(db, user["user_id"])
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    user["profile"] = profile
    return user


# ─── OAuth callback handler logic ──────────────────────────────────
async def handle_oauth_callback(provider: str, request: Request, db: AsyncSession) -> dict:
    """Handle OAuth callback: authenticate user, create profile if needed, return JWT."""
    import traceback
    
    if provider == "google":
        if "google" not in oauth._clients:
            raise HTTPException(status_code=500, detail="Google OAuth not configured")
        
        try:
            # Get the token from the callback
            token = await oauth.google.authorize_access_token(request)
            print(f"[OAuth] Token type: {type(token)}")
            if isinstance(token, dict):
                print(f"[OAuth] Token keys: {list(token.keys())}")
                access_token = token.get("access_token")
            else:
                access_token = str(token)
            
            # Fetch user info directly from Google's userinfo endpoint
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_info = resp.json()
            
            print(f"[OAuth] User info: {user_info}")
            
            if not user_info or "sub" not in user_info:
                raise HTTPException(status_code=400, detail=f"Invalid user info from Google: {user_info}")
            
            email = user_info.get("email", "")
            name = user_info.get("name", email.split("@")[0] if "@" in email else "User")
            picture = user_info.get("picture", "")
            google_id = user_info.get("sub", "")
            
            # Find existing profile by google_id or email
            all_profiles = await crud.get_all_profiles(db)
            profile = None
            for p in all_profiles:
                info = p.additional_info
                if isinstance(info, dict):
                    if info.get("google_id") == google_id or info.get("google_email") == email:
                        profile = p
                        break
            
            if not profile:
                # Create new profile linked to Google account
                profile = await crud.create_profile(db, ProfileCreate(
                    name=name,
                    level=PlayerLevel.BEGINNER,
                    available_time=[],
                    desired_place=[],
                    preferences=[],
                    contact_info={"email": email},
                    additional_info={
                        "google_id": google_id,
                        "google_email": email,
                        "google_picture": picture,
                        "auth_provider": "google",
                    },
                ))
                print(f"[OAuth] Created new profile: {profile.id}")
            else:
                print(f"[OAuth] Found existing profile: {profile.id}")
            
            # Create JWT
            access_token_jwt = create_access_token({"sub": str(profile.id), "email": email})
            
            return {
                "user_id": str(profile.id),
                "name": profile.name,
                "access_token": access_token_jwt,
                "token_type": "bearer",
            }
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[OAuth] Error during Google callback:")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")
    
    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
