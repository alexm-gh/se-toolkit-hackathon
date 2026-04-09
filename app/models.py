from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    level = Column(String(50), nullable=False)
    available_time = Column(JSONB, nullable=False, default=list)
    desired_place = Column(JSONB, nullable=False, default=list)
    preferences = Column(JSONB, nullable=False, default=list)
    contact_info = Column(JSONB, nullable=False, default=dict)
    additional_info = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MatchRequest(Base):
    __tablename__ = "match_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    sender_approved = Column(Boolean, nullable=False, default=False)
    receiver_approved = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("sender_id != receiver_id", name="different_users"),
        UniqueConstraint("sender_id", "receiver_id", name="unique_request"),
    )
