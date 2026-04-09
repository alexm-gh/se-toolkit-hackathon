from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid


class PlayerLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    PROFESSIONAL = "professional"


class WeeklyTimeSlot(BaseModel):
    """Recurring weekly time slot"""
    type: str = "weekly"
    day: str
    start_time: str
    end_time: str


class ExactTimeSlot(BaseModel):
    """One-time exact date/time slot"""
    type: str = "exact"
    date: str  # YYYY-MM-DD
    start_time: str
    end_time: str


# Accept either type in available_time list
TimeSlot = Union[WeeklyTimeSlot, ExactTimeSlot]


class ProfileCreate(BaseModel):
    """Schema for creating a profile"""
    name: str = Field(..., min_length=1, max_length=100)
    level: PlayerLevel
    available_time: List[TimeSlot] = Field(default_factory=list)
    desired_place: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    # additional_info can be a string (About text) or dict (OAuth metadata)
    # Stored as JSONB in DB, so both work
    additional_info: Optional[Any] = None
    contact_info: Dict[str, Any] = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    """Schema for updating a profile (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    level: Optional[PlayerLevel] = None
    available_time: Optional[List[TimeSlot]] = None
    desired_place: Optional[List[str]] = None
    preferences: Optional[List[str]] = None
    additional_info: Optional[Any] = None
    contact_info: Optional[Dict[str, Any]] = None


class ProfilePublic(BaseModel):
    """Public profile - contact_info is always hidden"""
    id: uuid.UUID
    name: str
    level: PlayerLevel
    available_time: List[TimeSlot]
    desired_place: List[str]
    preferences: List[str]
    additional_info: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileWithContacts(BaseModel):
    """Profile with contacts visible (only after mutual approval)"""
    id: uuid.UUID
    name: str
    level: PlayerLevel
    available_time: List[TimeSlot]
    desired_place: List[str]
    preferences: List[str]
    additional_info: Optional[Any] = None
    contact_info: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MatchRequestCreate(BaseModel):
    """Schema for creating a match request"""
    sender_id: uuid.UUID
    receiver_id: uuid.UUID


class MatchRequestResponse(BaseModel):
    """Schema for responding to a match request"""
    approved: bool
    user_id: uuid.UUID


class MatchRequestPublic(BaseModel):
    """Public match request info (contacts hidden)"""
    id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    receiver_id: uuid.UUID
    receiver_name: str
    sender_approved: bool
    receiver_approved: bool
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MatchRequestWithContacts(BaseModel):
    """Match request with contacts visible (after mutual approval)"""
    id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    sender_contact: Dict[str, Any]
    receiver_id: uuid.UUID
    receiver_name: str
    receiver_contact: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
