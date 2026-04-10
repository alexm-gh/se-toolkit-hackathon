from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import crud
from app.schemas import ProfileCreate, ProfileUpdate, ProfilePublic
import os
import uuid
import traceback

router = APIRouter(prefix="/api/v1", tags=["profiles"])

LLM_AGENT_URL = os.getenv("LLM_AGENT_URL", "http://llm-agent:8001")


async def moderate_content(text: str) -> tuple[bool, str]:
    """Check if content is appropriate by calling the LLM agent service."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LLM_AGENT_URL}/api/v1/moderate",
                json={"text": text},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("is_safe", True), data.get("reason", "")
    except Exception as e:
        print(f"Content moderation error: {e}")
    return True, ""  # Fail open


@router.post("/profiles/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_past_slots(db: AsyncSession = Depends(get_db)):
    """Remove past exact date time slots from all profiles."""
    count = await crud.cleanup_past_time_slots(db)
    return {"cleaned": count}


@router.post("/profiles", response_model=ProfilePublic, status_code=status.HTTP_201_CREATED)
async def create_profile(profile: ProfileCreate, db: AsyncSession = Depends(get_db)):
    """Create a new player profile (with LLM content moderation)."""
    # Combine fields for moderation check
    text_to_check = f"{profile.name} {profile.additional_info or ''}".strip()
    if text_to_check:
        is_safe, reason = await moderate_content(text_to_check)
        if not is_safe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Profile content not acceptable: {reason}"
            )
    return await crud.create_profile(db, profile)


@router.get("/profiles", response_model=list[ProfilePublic])
async def list_profiles(db: AsyncSession = Depends(get_db)):
    """List all player profiles (contacts hidden). Also cleans past exact time slots."""
    # Auto-cleanup past exact date slots
    await crud.cleanup_past_time_slots(db)
    return await crud.get_all_profiles(db)


@router.get("/profiles/{profile_id}", response_model=ProfilePublic)
async def get_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific profile (contacts hidden)"""
    profile = await crud.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profiles/{profile_id}", response_model=ProfilePublic)
async def update_profile(
    profile_id: uuid.UUID,
    updates: ProfileUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a profile (with LLM content moderation on name and additional_info)."""
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Moderate text fields that are being updated
    text_fields = []
    if "name" in update_data and update_data["name"]:
        text_fields.append(str(update_data["name"]))
    if "additional_info" in update_data and update_data["additional_info"]:
        # Only moderate if it's a string (dict = OAuth metadata, skip)
        ai = update_data["additional_info"]
        if isinstance(ai, str):
            text_fields.append(ai)
        elif isinstance(ai, dict) and ai.get("about_text"):
            text_fields.append(ai["about_text"])

    if text_fields:
        text_to_check = " ".join(text_fields)
        is_safe, reason = await moderate_content(text_to_check)
        if not is_safe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Profile content not acceptable: {reason}"
            )

    try:
        profile = await crud.update_profile(db, profile_id, update_data)
    except Exception as e:
        print(f"UPDATE ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a profile"""
    success = await crud.delete_profile(db, profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
