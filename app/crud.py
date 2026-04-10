from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Profile, MatchRequest
from app.schemas import ProfileCreate
from datetime import datetime, timezone
import uuid


async def get_profile(db: AsyncSession, profile_id: uuid.UUID) -> Profile | None:
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    return result.scalar_one_or_none()


async def get_all_profiles(db: AsyncSession) -> list[Profile]:
    result = await db.execute(select(Profile))
    return result.scalars().all()


async def create_profile(db: AsyncSession, profile: ProfileCreate) -> Profile:
    # Normalize time slots: ensure each has a "type" field
    normalized_times = []
    for t in profile.available_time:
        slot = t if isinstance(t, dict) else t.model_dump()
        if "type" not in slot:
            slot["type"] = "weekly"
        normalized_times.append(slot)

    db_profile = Profile(
        name=profile.name,
        level=profile.level.value,
        available_time=normalized_times,
        desired_place=profile.desired_place,
        preferences=profile.preferences,
        contact_info=profile.contact_info,
        additional_info=profile.additional_info,
    )
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return db_profile


async def update_profile(db: AsyncSession, profile_id: uuid.UUID, updates: dict) -> Profile | None:
    profile = await get_profile(db, profile_id)
    if not profile:
        return None

    for key, value in updates.items():
        if value is not None:
            if key == "level":
                setattr(profile, key, value.value if hasattr(value, "value") else value)
            elif key == "available_time":
                # Handle both Pydantic models and plain dicts
                if hasattr(value[0], "model_dump") if value else False:
                    setattr(profile, key, [t.model_dump() for t in value])
                else:
                    setattr(profile, key, value)
            else:
                setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)
    return profile


async def cleanup_past_time_slots(db: AsyncSession) -> int:
    """Remove exact date time slots that are in the past. Returns count of updated profiles."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    profiles = await get_all_profiles(db)
    updated_count = 0

    for profile in profiles:
        slots = profile.available_time or []
        new_slots = [
            s for s in slots
            if s.get("type") != "exact" or s.get("date", "") >= today
        ]
        if len(new_slots) != len(slots):
            profile.available_time = new_slots
            updated_count += 1

    if updated_count > 0:
        await db.commit()
    return updated_count


async def delete_profile(db: AsyncSession, profile_id: uuid.UUID) -> bool:
    profile = await get_profile(db, profile_id)
    if not profile:
        return False
    await db.delete(profile)
    await db.commit()
    return True


async def create_match_request(db: AsyncSession, sender_id: uuid.UUID, receiver_id: uuid.UUID) -> MatchRequest | None:
    # Check if receiver exists
    receiver = await get_profile(db, receiver_id)
    if not receiver:
        return None
    
    # Check if request already exists
    existing = await get_match_request(db, sender_id, receiver_id)
    if existing:
        return existing
    
    request = MatchRequest(sender_id=sender_id, receiver_id=receiver_id)
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


async def get_match_request(db: AsyncSession, sender_id: uuid.UUID, receiver_id: uuid.UUID) -> MatchRequest | None:
    result = await db.execute(
        select(MatchRequest).where(
            MatchRequest.sender_id == sender_id,
            MatchRequest.receiver_id == receiver_id
        )
    )
    return result.scalar_one_or_none()


async def get_match_request_by_id(db: AsyncSession, request_id: uuid.UUID) -> MatchRequest | None:
    result = await db.execute(select(MatchRequest).where(MatchRequest.id == request_id))
    return result.scalar_one_or_none()


async def respond_to_match_request(
    db: AsyncSession, 
    request_id: uuid.UUID, 
    user_id: uuid.UUID, 
    approved: bool
) -> MatchRequest | None:
    request = await get_match_request_by_id(db, request_id)
    if not request:
        return None
    
    # Only the receiver can respond
    if request.receiver_id != user_id:
        return None
    
    if request.status != "pending":
        return None
    
    request.receiver_approved = approved
    request.sender_approved = True  # Sender already approved by creating request
    
    if approved:
        # Check if both approved (mutual approval)
        if request.sender_approved and request.receiver_approved:
            request.status = "approved"
    else:
        request.status = "declined"
    
    await db.commit()
    await db.refresh(request)
    return request


async def get_user_received_requests(db: AsyncSession, user_id: uuid.UUID) -> list[MatchRequest]:
    result = await db.execute(
        select(MatchRequest).where(MatchRequest.receiver_id == user_id)
    )
    return result.scalars().all()


async def get_user_sent_requests(db: AsyncSession, user_id: uuid.UUID) -> list[MatchRequest]:
    result = await db.execute(
        select(MatchRequest).where(MatchRequest.sender_id == user_id)
    )
    return result.scalars().all()


def is_mutually_approved(request: MatchRequest) -> bool:
    return request.sender_approved and request.receiver_approved and request.status == "approved"
