"""
Authentication router - OAuth login, callback, logout, and status endpoints.
"""
import os
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.responses import Response

from app.database import get_db
from app.auth import (
    oauth, handle_oauth_callback, get_current_user, SECRET_KEY,
    GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    """Redirect to OAuth provider login page."""
    if provider == "google":
        if "google" not in oauth._clients:
            return {"error": "Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."}
        return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)
    return {"error": f"Unknown provider: {provider}"}


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback."""
    try:
        result = await handle_oauth_callback("google", request, db)
        
        # Set JWT in HttpOnly cookie
        response = RedirectResponse(url="/app", status_code=302)
        response.set_cookie(
            key="ttmm_token",
            value=result["access_token"],
            httponly=True,
            secure=False,  # Set True in production with HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
            path="/",
        )
        print(f"OAuth success, setting cookie for user {result.get('user_id')}")
        return response
    except Exception as e:
        return RedirectResponse(url=f"/app?error={str(e)}", status_code=302)


@router.post("/logout")
async def logout():
    """Clear the auth cookie."""
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie(key="ttmm_token")
    return response


@router.get("/me")
async def get_me(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current user info from JWT."""
    # Debug: log cookie presence
    token = request.cookies.get("ttmm_token")
    print(f"/auth/me - cookie present: {bool(token)}")
    
    user = await get_current_user(request, db)
    if not user:
        return {"authenticated": False}
    
    from app import crud
    profile = await crud.get_profile(db, user["user_id"])
    if not profile:
        return {"authenticated": False}
    
    return {
        "authenticated": True,
        "user_id": str(profile.id),
        "name": profile.name,
        "level": profile.level,
    }


@router.get("/config")
async def auth_config():
    """Return OAuth configuration for frontend."""
    return {
        "google_enabled": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_ID),
        "google_client_id": GOOGLE_CLIENT_ID,
        "google_redirect_uri": GOOGLE_REDIRECT_URI,
    }
