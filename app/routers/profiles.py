from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import crud
from app.schemas import ProfileCreate, ProfileUpdate, ProfilePublic
import uuid
import traceback

router = APIRouter(prefix="/api/v1", tags=["profiles"])


@router.post("/profiles/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_past_slots(db: AsyncSession = Depends(get_db)):
    """Remove past exact date time slots from all profiles."""
    count = await crud.cleanup_past_time_slots(db)
    return {"cleaned": count}


@router.post("/profiles", response_model=ProfilePublic, status_code=status.HTTP_201_CREATED)
async def create_profile(profile: ProfileCreate, db: AsyncSession = Depends(get_db)):
    """Create a new player profile."""
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
    """Update a profile."""
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")

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
