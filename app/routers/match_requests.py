from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import (
    MatchRequestCreate, MatchRequestResponse, MatchRequestPublic, MatchRequestWithContacts
)
from app import crud
from app.models import Profile
from sqlalchemy import select
import uuid

router = APIRouter(prefix="/api/v1", tags=["match-requests"])


@router.post("/match-requests", response_model=MatchRequestPublic, status_code=status.HTTP_201_CREATED)
async def create_match_request(
    request_data: MatchRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """Send a match request to another player"""
    # Verify sender exists
    sender = await crud.get_profile(db, request_data.sender_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender profile not found")
    
    if request_data.receiver_id == request_data.sender_id:
        raise HTTPException(status_code=400, detail="Cannot send request to yourself")
    
    match_request = await crud.create_match_request(db, request_data.sender_id, request_data.receiver_id)
    if not match_request:
        raise HTTPException(status_code=404, detail="Receiver profile not found")
    
    return await _enrich_request_with_names(db, match_request)


@router.get("/match-requests/received/{user_id}", response_model=list[MatchRequestPublic])
async def get_received_requests(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all match requests received by a user"""
    requests = await crud.get_user_received_requests(db, user_id)
    return [await _enrich_request_with_names(db, r) for r in requests]


@router.get("/match-requests/sent/{user_id}", response_model=list[MatchRequestPublic])
async def get_sent_requests(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all match requests sent by a user"""
    requests = await crud.get_user_sent_requests(db, user_id)
    return [await _enrich_request_with_names(db, r) for r in requests]


@router.post("/match-requests/{request_id}/respond", response_model=MatchRequestPublic)
async def respond_to_request(
    request_id: uuid.UUID,
    response: MatchRequestResponse,
    db: AsyncSession = Depends(get_db)
):
    """Respond to a match request (approve/decline)"""
    updated_request = await crud.respond_to_match_request(db, request_id, response.user_id, response.approved)
    if not updated_request:
        raise HTTPException(status_code=404, detail="Request not found or already responded")
    return await _enrich_request_with_names(db, updated_request)


@router.get("/match-requests/{request_id}/contacts", response_model=MatchRequestWithContacts)
async def get_contacts_if_approved(
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get contact info only if both parties have approved"""
    request = await crud.get_match_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # User must be part of the request
    if request.sender_id != user_id and request.receiver_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if not crud.is_mutually_approved(request):
        raise HTTPException(status_code=403, detail="Contacts not available - mutual approval required")
    
    # Fetch both profiles
    sender_result = await db.execute(select(Profile).where(Profile.id == request.sender_id))
    sender = sender_result.scalar_one()
    receiver_result = await db.execute(select(Profile).where(Profile.id == request.receiver_id))
    receiver = receiver_result.scalar_one()
    
    return MatchRequestWithContacts(
        id=request.id,
        sender_id=request.sender_id,
        sender_name=sender.name,
        sender_contact=sender.contact_info,
        receiver_id=request.receiver_id,
        receiver_name=receiver.name,
        receiver_contact=receiver.contact_info,
        status=request.status,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


async def _enrich_request_with_names(db: AsyncSession, request) -> MatchRequestPublic:
    """Helper to add sender/receiver names to request"""
    sender_result = await db.execute(select(Profile).where(Profile.id == request.sender_id))
    sender = sender_result.scalar_one()
    receiver_result = await db.execute(select(Profile).where(Profile.id == request.receiver_id))
    receiver = receiver_result.scalar_one()
    
    return MatchRequestPublic(
        id=request.id,
        sender_id=request.sender_id,
        sender_name=sender.name,
        receiver_id=request.receiver_id,
        receiver_name=receiver.name,
        sender_approved=request.sender_approved,
        receiver_approved=request.receiver_approved,
        status=request.status,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )
